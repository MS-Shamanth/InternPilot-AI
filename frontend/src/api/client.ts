/**
 * The only module that calls `fetch` (design.md §3.4, §15.1).
 *
 * Requests go to `VITE_API_BASE_URL` (e.g. `http://localhost:8000/api`) as JSON. Any non-2xx
 * response becomes an `ApiError` built from the backend error envelope (design.md §8.2).
 * No `X-Demo-User` header is sent: the backend resolves the seeded demo user (design.md §13.2).
 */
import type { ApiErrorDetails, ValidationErrorItem } from '../types/api';

export type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';

type QueryScalar = string | number | boolean;
export type QueryValue = QueryScalar | readonly QueryScalar[] | null | undefined;
export type QueryParams = Readonly<Record<string, QueryValue>>;

export interface RequestOptions {
  method?: HttpMethod;
  query?: QueryParams;
  /** Serialized as JSON when not `undefined`. */
  body?: unknown;
  signal?: AbortSignal;
  /** Non-2xx statuses whose body is a normal response (only `GET /health` 503 uses this). */
  acceptStatuses?: readonly number[];
}

export const NETWORK_ERROR = 'NETWORK_ERROR';
export const HTTP_ERROR = 'HTTP_ERROR';
export const INVALID_RESPONSE = 'INVALID_RESPONSE';

const REQUEST_ID_HEADER = 'X-Request-ID';
const NO_CONTENT = 204;

/** A failed API call: the envelope's `code`/`message`/`details`, the HTTP status and request id. */
export class ApiError extends Error {
  override readonly name = 'ApiError';

  constructor(
    readonly code: string,
    message: string,
    /** HTTP status; 0 when no response was received. */
    readonly status: number,
    readonly details: ApiErrorDetails = null,
    readonly requestId: string | null = null,
  ) {
    super(message);
  }
}

export function isApiError(value: unknown): value is ApiError {
  return value instanceof ApiError;
}

/** `?a=1&b=x&b=y` from params: arrays become repeated keys; `undefined`/`null` are omitted. */
export function buildQueryString(params: QueryParams = {}): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    const values: readonly QueryValue[] = Array.isArray(value) ? value : [value];
    for (const item of values) {
      if (item !== undefined && item !== null) {
        search.append(key, String(item));
      }
    }
  }
  const query = search.toString();
  return query ? `?${query}` : '';
}

function apiBaseUrl(): string {
  const base: unknown = import.meta.env.VITE_API_BASE_URL;
  if (typeof base !== 'string' || base.trim() === '') {
    throw new Error('VITE_API_BASE_URL is not configured (see .env.example).');
  }
  return base.trim().replace(/\/+$/, '');
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isValidationErrorItem(value: unknown): value is ValidationErrorItem {
  return (
    isRecord(value) &&
    Array.isArray(value.loc) &&
    value.loc.every((part) => typeof part === 'string' || typeof part === 'number') &&
    typeof value.msg === 'string' &&
    typeof value.type === 'string'
  );
}

function parseDetails(value: unknown): ApiErrorDetails {
  if (Array.isArray(value)) {
    return value.filter(isValidationErrorItem);
  }
  return isRecord(value) ? value : null;
}

function parseJson(text: string): unknown {
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return undefined;
  }
}

function errorFromResponse(status: number, text: string, requestId: string | null): ApiError {
  const body = parseJson(text);
  const error = isRecord(body) ? body.error : undefined;
  if (isRecord(error) && typeof error.code === 'string' && typeof error.message === 'string') {
    return new ApiError(error.code, error.message, status, parseDetails(error.details), requestId);
  }
  return new ApiError(
    HTTP_ERROR,
    `The request failed with status ${String(status)}.`,
    status,
    null,
    requestId,
  );
}

async function send(url: string, init: RequestInit): Promise<Response> {
  try {
    return await fetch(url, init);
  } catch (error) {
    // Cancellation is not a failure: let the caller (TanStack Query) see the AbortError.
    if (init.signal?.aborted) {
      throw error;
    }
    throw new ApiError(NETWORK_ERROR, 'Could not reach the server. Check your connection.', 0);
  }
}

/** Send one JSON request; resolves with the parsed body (`undefined` for 204). */
export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', query, body, signal, acceptStatuses = [] } = options;
  const headers: Record<string, string> = { Accept: 'application/json' };
  const init: RequestInit = { method, headers };
  if (body !== undefined) {
    headers['Content-Type'] = 'application/json';
    init.body = JSON.stringify(body);
  }
  if (signal) {
    init.signal = signal;
  }

  const response = await send(`${apiBaseUrl()}${path}${buildQueryString(query)}`, init);
  const requestId = response.headers.get(REQUEST_ID_HEADER);
  const text = await response.text();

  if (!response.ok && !acceptStatuses.includes(response.status)) {
    throw errorFromResponse(response.status, text, requestId);
  }
  if (response.status === NO_CONTENT) {
    return undefined as T;
  }
  const data = parseJson(text);
  if (data === undefined) {
    throw new ApiError(
      INVALID_RESPONSE,
      'The server returned an unexpected response.',
      response.status,
      null,
      requestId,
    );
  }
  return data as T;
}

type BodylessOptions = Omit<RequestOptions, 'method' | 'body'>;

export const api = {
  get: <T>(path: string, options?: BodylessOptions): Promise<T> =>
    apiRequest<T>(path, { ...options, method: 'GET' }),
  post: <T>(path: string, body?: unknown, options?: BodylessOptions): Promise<T> =>
    apiRequest<T>(path, { ...options, method: 'POST', body }),
  put: <T>(path: string, body?: unknown, options?: BodylessOptions): Promise<T> =>
    apiRequest<T>(path, { ...options, method: 'PUT', body }),
  patch: <T>(path: string, body?: unknown, options?: BodylessOptions): Promise<T> =>
    apiRequest<T>(path, { ...options, method: 'PATCH', body }),
  delete: <T>(path: string, options?: BodylessOptions): Promise<T> =>
    apiRequest<T>(path, { ...options, method: 'DELETE' }),
};
