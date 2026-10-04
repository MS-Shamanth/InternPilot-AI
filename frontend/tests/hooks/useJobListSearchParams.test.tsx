import { act, renderHook } from '@testing-library/react';
import type { ReactNode } from 'react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import { useJobListSearchParams } from '../../src/hooks/useJobListSearchParams';
import { ROUTER_FUTURE_FLAGS } from '../../src/lib/router';

function renderParams(initialSearch = '') {
  function wrapper({ children }: { children: ReactNode }) {
    return (
      <MemoryRouter initialEntries={[`/jobs${initialSearch}`]} future={ROUTER_FUTURE_FLAGS}>
        {children}
      </MemoryRouter>
    );
  }
  return renderHook(
    () => {
      const [params, setParams] = useJobListSearchParams();
      return { params, setParams, search: useLocation().search };
    },
    { wrapper },
  );
}

describe('useJobListSearchParams', () => {
  it('parses the URL into list params when rendered', () => {
    const { result } = renderParams('?q=react&page=2&unknown=1');
    expect(result.current.params).toEqual({ q: 'react', page: 2 });
  });

  it('keeps both changes when two updates happen before the next render', () => {
    const { result } = renderParams('?q=react');
    const { setParams } = result.current;

    act(() => {
      setParams((current) => ({ ...current, skills: ['React', 'SQL'] }));
      setParams((current) => ({ ...current, location: 'Berlin' }));
    });

    expect(result.current.search).toBe('?q=react&location=Berlin&skills=React%2CSQL');
  });

  it('replaces the params when given an object', () => {
    const { result } = renderParams('?q=react&work_mode=remote');

    act(() => {
      result.current.setParams({ sort: 'title' });
    });

    expect(result.current.search).toBe('?sort=title');
    expect(result.current.params).toEqual({ sort: 'title' });
  });
});
