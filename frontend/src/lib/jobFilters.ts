/**
 * Job list query ↔ URL search params (R2.3–R2.6, R3, design.md §8, §15.2).
 *
 * The Jobs page keeps its search, filters, sort and page in the URL. `parseJobListParams`
 * reads a URL leniently: unknown keys and invalid values are dropped instead of being sent to
 * the backend (which would answer 422). `serializeJobListParams` writes the normalized params
 * with defaults omitted, in a stable key order. Both go through `normalizeJobListParams`, so
 * `parse(serialize(x))` equals `normalize(x)`.
 *
 * `match_score` is the backend's default sort, so it is never written to the URL.
 */
import type {
  EmploymentType,
  ExperienceLevel,
  JobListParams,
  JobSortKey,
  SortOrder,
  WorkMode,
} from '../types/api';
import {
  EMPLOYMENT_TYPE_OPTIONS,
  EXPERIENCE_LEVEL_OPTIONS,
  JOB_SOURCE_OPTIONS,
  WORK_MODE_OPTIONS,
  isOptionValue,
} from './enumOptions';
import type { Option } from './enumOptions';

/** The backend's sort key when `sort` is omitted. */
export const DEFAULT_SORT: JobSortKey = 'match_score';

export const SORT_OPTIONS: readonly Option<JobSortKey>[] = [
  { value: 'match_score', label: 'Match score' },
  { value: 'discovered_at', label: 'Date discovered' },
  { value: 'deadline', label: 'Deadline' },
  { value: 'title', label: 'Title' },
  { value: 'company', label: 'Company' },
  { value: 'salary', label: 'Salary' },
];

/** The backend's order for a key when `order` is omitted (design.md §8 sort semantics). */
export const DEFAULT_SORT_ORDER: Readonly<Record<JobSortKey, SortOrder>> = {
  match_score: 'desc',
  discovered_at: 'desc',
  deadline: 'asc',
  title: 'asc',
  company: 'asc',
  salary: 'desc',
};

/** Thresholds offered by the minimum-score filter; 60 is the "matching job" line (R6.1). */
export const MIN_SCORE_OPTIONS: readonly Option<string>[] = [
  { value: '40', label: '40 or more' },
  { value: '60', label: '60 or more (matching jobs)' },
  { value: '80', label: '80 or more' },
];

export const DEFAULT_PAGE = 1;
export const DEFAULT_PAGE_SIZE = 20;
export const PAGE_SIZE_OPTIONS: readonly number[] = [10, 20, 50, 100];
export const QUERY_MAX_LENGTH = 100;
export const LOCATION_MAX_LENGTH = 120;
export const SKILLS_MAX_ITEMS = 10;
export const SKILL_MAX_LENGTH = 50;

const PAGE_SIZE_MAX = 100;
const SCORE_MAX = 100;
const SKILLS_SEPARATOR = ',';
const SORT_ORDERS: readonly Option<SortOrder>[] = [
  { value: 'asc', label: 'Ascending' },
  { value: 'desc', label: 'Descending' },
];
const TRUE = 'true';
/** Search and filter keys: everything except sort and paging. */
const FILTER_KEYS: readonly (keyof JobListParams)[] = [
  'q',
  'employment_type',
  'work_mode',
  'experience_level',
  'location',
  'source',
  'skills',
  'min_score',
  'bookmarked',
  'include_hidden',
];

/** Trimmed text capped at `maxLength`, or `undefined` when blank. */
function cleanText(value: string | undefined, maxLength: number): string | undefined {
  const text = value?.trim().slice(0, maxLength).trim();
  return text === undefined || text === '' ? undefined : text;
}

/** Valid values only, de-duplicated, in canonical option order; `undefined` when none. */
function cleanEnumList<T extends string>(
  options: readonly Option<T>[],
  values: readonly string[] | undefined,
): T[] | undefined {
  if (values === undefined) {
    return undefined;
  }
  const picked = options.map((option) => option.value).filter((value) => values.includes(value));
  return picked.length > 0 ? picked : undefined;
}

/**
 * Skills as typed: trimmed, blank entries dropped, de-duplicated case-insensitively (first
 * spelling wins), each capped at 50 characters and at most 10. The backend normalizes them.
 */
export function cleanSkills(values: readonly string[] | undefined): string[] | undefined {
  if (values === undefined) {
    return undefined;
  }
  const seen = new Set<string>();
  const skills: string[] = [];
  for (const value of values) {
    const skill = cleanText(value, SKILL_MAX_LENGTH);
    if (skill === undefined || seen.has(skill.toLowerCase())) {
      continue;
    }
    seen.add(skill.toLowerCase());
    skills.push(skill);
  }
  return skills.length > 0 ? skills.slice(0, SKILLS_MAX_ITEMS) : undefined;
}

/** Comma-separated skills text → cleaned list (used by the URL and the skills input). */
export function parseSkillsText(text: string): string[] | undefined {
  return cleanSkills(text.split(SKILLS_SEPARATOR));
}

export function formatSkillsText(skills: readonly string[] | undefined): string {
  return (skills ?? []).join(', ');
}

function isSortKey(value: string | undefined): value is JobSortKey {
  return value !== undefined && isOptionValue(SORT_OPTIONS, value);
}

function cleanInteger(value: number | undefined, min: number, max: number): number | undefined {
  return value !== undefined && Number.isSafeInteger(value) && value >= min && value <= max
    ? value
    : undefined;
}

/** The sort key actually applied (`match_score` when none is set). */
export function effectiveSort(params: JobListParams): JobSortKey {
  return isSortKey(params.sort) ? params.sort : DEFAULT_SORT;
}

/** The order actually applied (explicit `order`, else the effective key's default). */
export function effectiveSortOrder(params: JobListParams): SortOrder {
  return params.order ?? DEFAULT_SORT_ORDER[effectiveSort(params)];
}

/**
 * Canonical form of list params: invalid values and defaults removed (page 1, page size 20,
 * `false` flags, minimum score 0, sort `match_score`, an `order` equal to the key's default).
 */
export function normalizeJobListParams(params: JobListParams): JobListParams {
  const sortKey = effectiveSort(params);
  const order =
    params.order !== undefined &&
    isOptionValue(SORT_ORDERS, params.order) &&
    params.order !== DEFAULT_SORT_ORDER[sortKey]
      ? params.order
      : undefined;
  const minScore = cleanInteger(params.min_score, 0, SCORE_MAX);
  const page = cleanInteger(params.page, DEFAULT_PAGE, Number.MAX_SAFE_INTEGER);
  const pageSize = cleanInteger(params.page_size, 1, PAGE_SIZE_MAX);
  const normalized: JobListParams = {
    q: cleanText(params.q, QUERY_MAX_LENGTH),
    employment_type: cleanEnumList(EMPLOYMENT_TYPE_OPTIONS, params.employment_type),
    work_mode: cleanEnumList(WORK_MODE_OPTIONS, params.work_mode),
    experience_level: cleanEnumList(EXPERIENCE_LEVEL_OPTIONS, params.experience_level),
    location: cleanText(params.location, LOCATION_MAX_LENGTH),
    source:
      params.source !== undefined && isOptionValue(JOB_SOURCE_OPTIONS, params.source)
        ? params.source
        : undefined,
    skills: cleanSkills(params.skills),
    min_score: minScore === 0 ? undefined : minScore,
    bookmarked: params.bookmarked === true ? true : undefined,
    include_hidden: params.include_hidden === true ? true : undefined,
    sort: sortKey === DEFAULT_SORT ? undefined : sortKey,
    order,
    page: page === DEFAULT_PAGE ? undefined : page,
    page_size: pageSize === DEFAULT_PAGE_SIZE ? undefined : pageSize,
  };
  return withoutUndefined(normalized);
}

function withoutUndefined(params: JobListParams): JobListParams {
  return Object.fromEntries(Object.entries(params).filter(([, value]) => value !== undefined));
}

function integerParam(value: string | null): number | undefined {
  return value !== null && /^\d{1,15}$/.test(value) ? Number(value) : undefined;
}

function listParam(search: URLSearchParams, key: string): string[] | undefined {
  const values = search.getAll(key);
  return values.length > 0 ? values : undefined;
}

/** URL search params → normalized list params; unknown keys and invalid values are dropped. */
export function parseJobListParams(search: URLSearchParams): JobListParams {
  const skills = search.get('skills');
  return normalizeJobListParams({
    q: search.get('q') ?? undefined,
    employment_type: listParam(search, 'employment_type') as EmploymentType[] | undefined,
    work_mode: listParam(search, 'work_mode') as WorkMode[] | undefined,
    experience_level: listParam(search, 'experience_level') as ExperienceLevel[] | undefined,
    location: search.get('location') ?? undefined,
    source: (search.get('source') ?? undefined) as JobListParams['source'],
    skills: skills === null ? undefined : parseSkillsText(skills),
    min_score: integerParam(search.get('min_score')),
    bookmarked: search.get('bookmarked') === TRUE,
    include_hidden: search.get('include_hidden') === TRUE,
    sort: (search.get('sort') ?? undefined) as JobSortKey | undefined,
    order: (search.get('order') ?? undefined) as SortOrder | undefined,
    page: integerParam(search.get('page')),
    page_size: integerParam(search.get('page_size')),
  });
}

/**
 * Normalized params → URL search params: defaults omitted, keys in a fixed order, multi-valued
 * filters as repeated keys, skills comma-separated.
 */
export function serializeJobListParams(params: JobListParams): URLSearchParams {
  const p = normalizeJobListParams(params);
  const search = new URLSearchParams();
  const set = (key: string, value: string | number | boolean | undefined) => {
    if (value !== undefined) {
      search.append(key, String(value));
    }
  };
  set('q', p.q);
  p.employment_type?.forEach((value) => {
    set('employment_type', value);
  });
  p.work_mode?.forEach((value) => {
    set('work_mode', value);
  });
  p.experience_level?.forEach((value) => {
    set('experience_level', value);
  });
  set('location', p.location);
  set('source', p.source);
  set('skills', p.skills?.join(SKILLS_SEPARATOR));
  set('min_score', p.min_score);
  set('bookmarked', p.bookmarked);
  set('include_hidden', p.include_hidden);
  set('sort', p.sort);
  set('order', p.order);
  set('page', p.page);
  set('page_size', p.page_size);
  return search;
}

/** `true` when any search or filter (not sort or paging) is set. */
export function hasActiveFilters(params: JobListParams): boolean {
  const normalized = normalizeJobListParams(params);
  return FILTER_KEYS.some((key) => normalized[key] !== undefined);
}

/** Params with search and filters removed; sort and page size are kept, page resets to 1. */
export function clearFilters(params: JobListParams): JobListParams {
  const { sort, order, page_size } = normalizeJobListParams(params);
  return normalizeJobListParams({ sort, order, page_size });
}

/** Params after a filter or sort change: the patch applied and the page reset to 1. */
export function applyFilterChange(
  params: JobListParams,
  patch: Partial<JobListParams>,
): JobListParams {
  return normalizeJobListParams({ ...params, ...patch, page: undefined });
}
