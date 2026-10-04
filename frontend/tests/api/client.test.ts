import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { applyToJob, listJobs } from '../../src/api/jobs';
import { ApiError, apiRequest, buildQueryString, isApiError } from '../../src/api/client';
import { getHealth } from '../../src/api/health';
import { deleteApplication, listApplications } from '../../src/api/applications';

const BASE_URL = 'http://api.test/api';

const fetchMock = vi.fn<typeof fetch>();

function jsonResponse(body: unknown, status = 200, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json', ...headers },
  });
}

function lastCall(): { url: string; init: RequestInit } {
  const call = fetchMock.mock.calls.at(-1);
  if (!call) {
    throw new Error('fetch was not called');
  }
  const [url, init] = call;
  const href = typeof url === 'string' ? url : url instanceof URL ? url.href : url.url;
  return { url: href, init: init ?? {} };
}

async function captureError(promise: Promise<unknown>): Promise<ApiError> {
  try {
    await promise;
  } catch (error) {
    if (isApiError(error)) {
      return error;
    }
    throw error;
  }
  throw new Error('expected the request to fail');
}

beforeEach(() => {
  vi.stubEnv('VITE_API_BASE_URL', `${BASE_URL}/`);
  vi.stubGlobal('fetch', fetchMock);
});

afterEach(() => {
  fetchMock.mockReset();
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

describe('apiRequest', () => {
  it('returns the parsed JSON body when the response is 2xx', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ id: 1, name: 'Demo' }));

    const result = await apiRequest<{ id: number; name: string }>('/profile');

    expect(result).toEqual({ id: 1, name: 'Demo' });
    const { url, init } = lastCall();
    expect(url).toBe(`${BASE_URL}/profile`);
    expect(init.method).toBe('GET');
    expect(init.body).toBeUndefined();
    expect(new Headers(init.headers).has('X-Demo-User')).toBe(false);
  });

  it('resolves undefined when the response is 204', async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }));

    await expect(deleteApplication(7)).resolves.toBeUndefined();
    const { url, init } = lastCall();
    expect(url).toBe(`${BASE_URL}/applications/7`);
    expect(init.method).toBe('DELETE');
  });

  it.each(['POST', 'PUT', 'PATCH'] as const)(
    'sends a JSON body with a content type when the method is %s',
    async (method) => {
      fetchMock.mockResolvedValue(jsonResponse({ ok: true }));

      await apiRequest('/applications/3', { method, body: { status: 'Applied' } });

      const { init } = lastCall();
      expect(init.method).toBe(method);
      expect(init.body).toBe('{"status":"Applied"}');
      expect(new Headers(init.headers).get('Content-Type')).toBe('application/json');
    },
  );

  it('passes the abort signal to fetch when one is given', async () => {
    fetchMock.mockResolvedValue(jsonResponse([]));
    const controller = new AbortController();

    await apiRequest('/applications', { signal: controller.signal });

    expect(lastCall().init.signal).toBe(controller.signal);
  });

  it('throws an ApiError with the envelope fields when the response is an error envelope', async () => {
    fetchMock.mockResolvedValue(
      jsonResponse(
        {
          error: {
            code: 'INVALID_STATUS_TRANSITION',
            message: 'Cannot move from Offer to Applied',
            details: { from: 'Offer', to: 'Applied', allowed: ['Withdrawn'] },
          },
        },
        409,
        { 'X-Request-ID': 'req-123' },
      ),
    );

    const error = await captureError(apiRequest('/applications/1', { method: 'PATCH', body: {} }));

    expect(error).toBeInstanceOf(ApiError);
    expect(error).toBeInstanceOf(Error);
    expect(error.code).toBe('INVALID_STATUS_TRANSITION');
    expect(error.message).toBe('Cannot move from Offer to Applied');
    expect(error.status).toBe(409);
    expect(error.details).toEqual({ from: 'Offer', to: 'Applied', allowed: ['Withdrawn'] });
    expect(error.requestId).toBe('req-123');
  });

  it('preserves the validation details list when the response is 422', async () => {
    const details = [
      { loc: ['body', 'technical_skills', 2], msg: 'Value error', type: 'value_error' },
      {
        loc: ['query', 'page'],
        msg: 'Input should be greater than or equal to 1',
        type: 'greater_than_equal',
      },
    ];
    fetchMock.mockResolvedValue(
      jsonResponse(
        { error: { code: 'VALIDATION_ERROR', message: 'Invalid request', details } },
        422,
      ),
    );

    const error = await captureError(apiRequest('/profile', { method: 'PUT', body: {} }));

    expect(error.code).toBe('VALIDATION_ERROR');
    expect(error.status).toBe(422);
    expect(error.details).toEqual(details);
    expect(error.requestId).toBeNull();
  });

  it('throws a generic HTTP_ERROR when the error body is not JSON', async () => {
    fetchMock.mockResolvedValue(
      new Response('<html>Bad Gateway</html>', { status: 502, headers: { 'X-Request-ID': 'r-9' } }),
    );

    const error = await captureError(apiRequest('/jobs'));

    expect(error.code).toBe('HTTP_ERROR');
    expect(error.message).toBe('The request failed with status 502.');
    expect(error.status).toBe(502);
    expect(error.details).toBeNull();
    expect(error.requestId).toBe('r-9');
  });

  it('throws a generic HTTP_ERROR when the JSON error body is not an envelope', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ detail: 'Not Found' }, 404));

    const error = await captureError(apiRequest('/jobs/99'));

    expect(error.code).toBe('HTTP_ERROR');
    expect(error.status).toBe(404);
  });

  it('throws NETWORK_ERROR with status 0 when fetch rejects', async () => {
    fetchMock.mockRejectedValue(new TypeError('Failed to fetch'));

    const error = await captureError(apiRequest('/dashboard'));

    expect(error.code).toBe('NETWORK_ERROR');
    expect(error.status).toBe(0);
    expect(error.requestId).toBeNull();
  });

  it('rethrows the abort error when the request is cancelled', async () => {
    const controller = new AbortController();
    controller.abort();
    const abortError = new DOMException('The operation was aborted.', 'AbortError');
    fetchMock.mockRejectedValue(abortError);

    await expect(apiRequest('/jobs', { signal: controller.signal })).rejects.toBe(abortError);
  });
});

describe('buildQueryString', () => {
  it('repeats array values and omits undefined and null when building the query', () => {
    const query = buildQueryString({
      status: ['Saved', 'Applied'],
      q: 'react dev',
      location: undefined,
      source: null,
      page: 2,
      bookmarked: true,
    });

    expect(query).toBe('?status=Saved&status=Applied&q=react+dev&page=2&bookmarked=true');
  });

  it('returns an empty string when there are no values', () => {
    expect(buildQueryString({ q: undefined, status: [] })).toBe('');
  });
});

describe('jobs', () => {
  it('builds the list URL with repeated filters and comma-joined skills when listing jobs', async () => {
    fetchMock.mockResolvedValue(
      jsonResponse({ items: [], total: 0, page: 1, page_size: 20, total_pages: 0 }),
    );

    await listJobs({
      employment_type: ['internship', 'full_time'],
      skills: ['React', 'SQL'],
      sort: 'deadline',
      page: 1,
    });

    const { url, init } = lastCall();
    expect(init.method).toBe('GET');
    expect(url).toBe(
      `${BASE_URL}/jobs?employment_type=internship&employment_type=full_time&sort=deadline&page=1&skills=React%2CSQL`,
    );
  });

  it('posts to the apply endpoint without a body when applying to a job', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ id: 1 }, 201));

    await applyToJob(5);

    const { url, init } = lastCall();
    expect(url).toBe(`${BASE_URL}/jobs/5/apply`);
    expect(init.method).toBe('POST');
    expect(init.body).toBeUndefined();
  });
});

describe('applications', () => {
  it('sends repeated status parameters when filtering applications', async () => {
    fetchMock.mockResolvedValue(jsonResponse([]));

    await listApplications({ status: ['Saved', 'Interview'] });

    expect(lastCall().url).toBe(`${BASE_URL}/applications?status=Saved&status=Interview`);
  });
});

describe('health', () => {
  it('resolves the degraded body when the backend answers 503', async () => {
    const degraded = { status: 'degraded', database: 'unavailable', version: '0.1.0' };
    fetchMock.mockResolvedValue(jsonResponse(degraded, 503));

    await expect(getHealth()).resolves.toEqual(degraded);
  });
});
