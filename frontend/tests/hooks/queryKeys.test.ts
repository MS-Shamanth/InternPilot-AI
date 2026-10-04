import { QueryClient } from '@tanstack/react-query';
import { describe, expect, it, vi } from 'vitest';
import { INVALIDATION_MAP, invalidateFor, queryKeys } from '../../src/lib/queryKeys';

describe('queryKeys', () => {
  it('nests list and detail keys under their family prefix when built', () => {
    expect(queryKeys.jobs.list({ page: 2 })).toEqual(['jobs', 'list', { page: 2 }]);
    expect(queryKeys.jobs.detail(7)).toEqual(['jobs', 'detail', 7]);
    expect(queryKeys.jobs.list({}).slice(0, 2)).toEqual(queryKeys.jobs.lists());
    expect(queryKeys.jobs.lists().slice(0, 1)).toEqual(queryKeys.jobs.all());
    expect(queryKeys.applications.list({ status: ['Applied'] }).slice(0, 2)).toEqual(
      queryKeys.applications.lists(),
    );
    expect(queryKeys.applications.meta()).toEqual(['applications', 'meta']);
    expect(queryKeys.recommendations.list(5)).toEqual(['recommendations', { limit: 5 }]);
    expect(queryKeys.interview.detail(3)).toEqual(['interview', 3]);
  });
});

describe('INVALIDATION_MAP', () => {
  it('refreshes everything match-dependent when the profile changes', () => {
    expect(INVALIDATION_MAP.profileUpdated).toEqual([
      ['profile'],
      ['jobs', 'list'],
      ['jobs', 'detail'],
      ['recommendations'],
      ['dashboard'],
      ['interview'],
    ]);
  });

  it('refreshes tracker, jobs, recommendations and dashboard when an application changes', () => {
    expect(INVALIDATION_MAP.applicationChanged).toEqual([
      ['applications', 'list'],
      ['jobs', 'list'],
      ['jobs', 'detail'],
      ['recommendations'],
      ['dashboard'],
    ]);
  });

  it('refreshes jobs, recommendations and dashboard when a bookmark or hide flag changes', () => {
    expect(INVALIDATION_MAP.jobStateChanged).toEqual([
      ['jobs', 'list'],
      ['jobs', 'detail'],
      ['recommendations'],
      ['dashboard'],
    ]);
  });

  it('refreshes every view of job data when jobs are ingested', () => {
    expect(INVALIDATION_MAP.jobsIngested).toEqual([
      ['jobs', 'list'],
      ['jobs', 'detail'],
      ['recommendations'],
      ['dashboard'],
      ['applications', 'list'],
      ['interview'],
    ]);
  });
});

describe('invalidateFor', () => {
  it('invalidates each mapped prefix when called', async () => {
    const queryClient = new QueryClient();
    const spy = vi.spyOn(queryClient, 'invalidateQueries');

    await invalidateFor(queryClient, 'jobStateChanged');

    expect(spy.mock.calls.map(([filters]) => filters?.queryKey)).toEqual(
      INVALIDATION_MAP.jobStateChanged,
    );
  });

  it('marks matching cached queries stale and leaves unrelated ones fresh when called', async () => {
    const queryClient = new QueryClient();
    const jobsPage = queryKeys.jobs.list({ page: 2, q: 'react' });
    const jobDetail = queryKeys.jobs.detail(4);
    const meta = queryKeys.applications.meta();
    const profile = queryKeys.profile();
    for (const key of [jobsPage, jobDetail, meta, profile]) {
      queryClient.setQueryData(key, {});
    }

    await invalidateFor(queryClient, 'applicationChanged');

    expect(queryClient.getQueryState(jobsPage)?.isInvalidated).toBe(true);
    expect(queryClient.getQueryState(jobDetail)?.isInvalidated).toBe(true);
    expect(queryClient.getQueryState(meta)?.isInvalidated).toBe(false);
    expect(queryClient.getQueryState(profile)?.isInvalidated).toBe(false);
  });
});
