import { describe, expect, it } from 'vitest';
import {
  applyFilterChange,
  clearFilters,
  effectiveSortOrder,
  hasActiveFilters,
  normalizeJobListParams,
  parseJobListParams,
  parseSkillsText,
  serializeJobListParams,
} from '../../src/lib/jobFilters';
import type { JobListParams } from '../../src/types/api';

function parse(query: string): JobListParams {
  return parseJobListParams(new URLSearchParams(query));
}

function serialize(params: JobListParams): string {
  return serializeJobListParams(params).toString();
}

/** Deterministic PRNG (mulberry32) so the round-trip cases are the same on every run. */
function seededRandom(seed: number): () => number {
  let state = seed;
  return () => {
    state = (state + 0x6d2b79f5) | 0;
    let t = Math.imul(state ^ (state >>> 15), 1 | state);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function pick<T>(random: () => number, values: readonly T[]): T {
  const value = values[Math.floor(random() * values.length)];
  if (value === undefined) {
    throw new Error('empty choice');
  }
  return value;
}

function subset<T>(random: () => number, values: readonly T[]): T[] {
  return values.filter(() => random() < 0.4);
}

/** Arbitrary params, including invalid values a hand-edited URL could carry. */
function randomParams(random: () => number): JobListParams {
  const maybe = <T>(value: T): T | undefined => (random() < 0.5 ? value : undefined);
  return {
    q: maybe(pick(random, ['react', '  data  ', '', 'x'.repeat(120), 'ünïcode & co'])),
    employment_type: maybe(
      subset(random, ['contract', 'internship', 'gig', 'full_time', 'part_time', 'internship']),
    ) as JobListParams['employment_type'],
    work_mode: maybe(
      subset(random, ['onsite', 'remote', 'space', 'hybrid']),
    ) as JobListParams['work_mode'],
    experience_level: maybe(
      subset(random, ['senior', 'guru', 'entry', 'junior']),
    ) as JobListParams['experience_level'],
    location: maybe(pick(random, ['Berlin', ' ', 'New York, NY'])),
    source: maybe(pick(random, ['remotive', 'linkedin', 'seed'])) as JobListParams['source'],
    skills: maybe(subset(random, ['React', 'react', ' SQL ', '', 'C++', 'Node.js'])),
    min_score: maybe(pick(random, [0, 40, 60, 100, 101, -1, 55.5])),
    bookmarked: maybe(random() < 0.5),
    include_hidden: maybe(random() < 0.5),
    sort: maybe(
      pick(random, ['title', 'salary', 'deadline', 'match_score', 'bogus']),
    ) as JobListParams['sort'],
    order: maybe(pick(random, ['asc', 'desc', 'up'])) as JobListParams['order'],
    page: maybe(pick(random, [0, 1, 2, 7, -3, 2.5])),
    page_size: maybe(pick(random, [0, 1, 20, 50, 100, 101])),
  };
}

describe('parseJobListParams', () => {
  it('reads every supported parameter when all values are valid', () => {
    const params = parse(
      'q=react&employment_type=internship&work_mode=remote&work_mode=hybrid' +
        '&experience_level=entry&location=Berlin&source=remotive&skills=React,SQL' +
        '&bookmarked=true&include_hidden=true&sort=title&order=desc&page=3&page_size=50',
    );
    expect(params).toEqual({
      q: 'react',
      employment_type: ['internship'],
      work_mode: ['remote', 'hybrid'],
      experience_level: ['entry'],
      location: 'Berlin',
      source: 'remotive',
      skills: ['React', 'SQL'],
      bookmarked: true,
      include_hidden: true,
      sort: 'title',
      order: 'desc',
      page: 3,
      page_size: 50,
    });
  });

  it('drops unknown keys and invalid enum, flag and number values', () => {
    expect(
      parse(
        'foo=1&work_mode=space&employment_type=gig&source=linkedin&bookmarked=yes' +
          '&sort=bogus&order=up&page=0&page_size=500&min_score=101',
      ),
    ).toEqual({});
    expect(parse('page=-2&page_size=abc&min_score=-5')).toEqual({});
    expect(parse('page=2.5&page_size=0&min_score=7.5')).toEqual({});
  });

  it('reads min_score and drops 0 as the default', () => {
    expect(parse('min_score=60')).toEqual({ min_score: 60 });
    expect(parse('min_score=0')).toEqual({});
  });

  it('drops defaults and an order that equals the sort key default', () => {
    expect(parse('page=1&page_size=20&bookmarked=false&sort=deadline&order=asc')).toEqual({
      sort: 'deadline',
    });
    expect(parse('sort=match_score&order=desc')).toEqual({});
    expect(parse('order=asc')).toEqual({ order: 'asc' });
  });

  it('trims text, ignores blanks and caps lengths', () => {
    expect(parse('q=%20%20&location=%20')).toEqual({});
    expect(parse('q=%20react%20')).toEqual({ q: 'react' });
    expect(parse(`q=${'a'.repeat(150)}`).q).toHaveLength(100);
  });

  it('de-duplicates multi-valued filters into canonical order', () => {
    expect(parse('work_mode=onsite&work_mode=remote&work_mode=onsite').work_mode).toEqual([
      'remote',
      'onsite',
    ]);
  });
});

describe('parseSkillsText', () => {
  it('splits on commas, trims, drops blanks and de-duplicates case-insensitively', () => {
    expect(parseSkillsText(' React, ,react,SQL ,')).toEqual(['React', 'SQL']);
    expect(parseSkillsText(' , ')).toBeUndefined();
  });

  it('keeps at most 10 skills of at most 50 characters', () => {
    const many = Array.from({ length: 12 }, (_, index) => `skill${String(index)}`).join(',');
    expect(parseSkillsText(many)).toHaveLength(10);
    expect(parseSkillsText('x'.repeat(60))?.[0]).toHaveLength(50);
  });
});

describe('serializeJobListParams', () => {
  it('writes keys in a fixed order with repeated multi-values and comma-joined skills', () => {
    expect(
      serialize({
        page: 2,
        skills: ['React', 'SQL'],
        work_mode: ['hybrid', 'remote'],
        q: 'data',
        sort: 'salary',
        order: 'asc',
      }),
    ).toBe(
      'q=data&work_mode=remote&work_mode=hybrid&skills=React%2CSQL&sort=salary&order=asc&page=2',
    );
  });

  it('omits defaults and empty values', () => {
    expect(
      serialize({
        q: ' ',
        work_mode: [],
        bookmarked: false,
        include_hidden: false,
        page: 1,
        page_size: 20,
        sort: 'discovered_at',
        order: 'desc',
      }),
    ).toBe('sort=discovered_at');
    expect(serialize({})).toBe('');
  });
});

describe('job list params round trip', () => {
  it('parse(serialize(x)) equals normalize(x) for 500 seeded cases', () => {
    const random = seededRandom(20250101);
    for (let index = 0; index < 500; index += 1) {
      const params = randomParams(random);
      const normalized = normalizeJobListParams(params);
      expect(parseJobListParams(serializeJobListParams(params))).toEqual(normalized);
      expect(normalizeJobListParams(normalized)).toEqual(normalized);
    }
  });
});

describe('filter helpers', () => {
  it('applyFilterChange applies the patch and resets the page', () => {
    expect(
      applyFilterChange({ page: 4, page_size: 50, q: 'a' }, { work_mode: ['remote'] }),
    ).toEqual({ page_size: 50, q: 'a', work_mode: ['remote'] });
  });

  it('clearFilters keeps only sort and page size', () => {
    expect(
      clearFilters({
        q: 'a',
        bookmarked: true,
        sort: 'title',
        order: 'desc',
        page: 3,
        page_size: 10,
      }),
    ).toEqual({ sort: 'title', order: 'desc', page_size: 10 });
  });

  it('hasActiveFilters ignores sort and paging', () => {
    expect(hasActiveFilters({ sort: 'title', page: 2, page_size: 50 })).toBe(false);
    expect(hasActiveFilters({ include_hidden: true })).toBe(true);
    expect(hasActiveFilters({ q: '  ' })).toBe(false);
  });

  it('effectiveSortOrder uses the key default unless an order is given', () => {
    expect(effectiveSortOrder({ sort: 'deadline' })).toBe('asc');
    expect(effectiveSortOrder({ sort: 'salary' })).toBe('desc');
    expect(effectiveSortOrder({ sort: 'title', order: 'desc' })).toBe('desc');
    expect(effectiveSortOrder({})).toBe('desc');
    expect(effectiveSortOrder({ order: 'asc' })).toBe('asc');
  });
});
