import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import { JobFilters } from '../../src/components/jobs/JobFilters';
import { useJobListSearchParams } from '../../src/hooks/useJobListSearchParams';
import { ROUTER_FUTURE_FLAGS } from '../../src/lib/router';

function CurrentSearch() {
  const location = useLocation();
  return <output aria-label="Current search">{location.search}</output>;
}

/** The page's wiring: URL ↔ params via the same hook JobsPage uses. */
function Harness() {
  const [params, setParams] = useJobListSearchParams();
  return (
    <>
      <JobFilters value={params} onChange={setParams} />
      <CurrentSearch />
    </>
  );
}

function renderFilters(initialSearch = '') {
  render(
    <MemoryRouter initialEntries={[`/jobs${initialSearch}`]} future={ROUTER_FUTURE_FLAGS}>
      <Harness />
    </MemoryRouter>,
  );
  return { user: userEvent.setup() };
}

function currentSearch(): string {
  return screen.getByRole('status', { name: 'Current search' }).textContent ?? '';
}

describe('JobFilters', () => {
  it('updates ?q= after the debounce when typing a search', async () => {
    const { user } = renderFilters();
    await user.type(screen.getByRole('searchbox', { name: /Search jobs/ }), 'react');
    expect(currentSearch()).toBe('');
    await waitFor(() => {
      expect(currentSearch()).toBe('?q=react');
    });
  });

  it('applies the search immediately on Enter', async () => {
    const { user } = renderFilters();
    await user.type(screen.getByRole('searchbox', { name: /Search jobs/ }), 'data{Enter}');
    expect(currentSearch()).toBe('?q=data');
  });

  it('adds repeated params for checked work modes', async () => {
    const { user } = renderFilters();
    await user.click(screen.getByRole('checkbox', { name: 'Remote' }));
    await user.click(screen.getByRole('checkbox', { name: 'Onsite' }));
    expect(currentSearch()).toBe('?work_mode=remote&work_mode=onsite');
  });

  it('resets the page when a filter changes', async () => {
    const { user } = renderFilters('?page=3&page_size=50');
    await user.click(screen.getByRole('checkbox', { name: 'Bookmarked only' }));
    expect(currentSearch()).toBe('?bookmarked=true&page_size=50');
  });

  it('populates the controls from the initial URL', () => {
    renderFilters(
      '?q=react&employment_type=internship&work_mode=hybrid&experience_level=entry' +
        '&location=Berlin&source=remotive&skills=React,SQL&include_hidden=true&sort=deadline&order=desc',
    );
    expect(screen.getByRole('searchbox', { name: /Search jobs/ })).toHaveValue('react');
    expect(screen.getByRole('group', { name: 'Employment type' })).toHaveTextContent('Internship');
    expect(screen.getByRole('checkbox', { name: 'Internship', checked: true })).toBeInTheDocument();
    expect(screen.getByRole('checkbox', { name: 'Hybrid' })).toBeChecked();
    expect(screen.getByRole('checkbox', { name: 'Remote' })).not.toBeChecked();
    expect(screen.getByRole('checkbox', { name: 'Entry level' })).toBeChecked();
    expect(screen.getByRole('textbox', { name: /^Location/ })).toHaveValue('Berlin');
    expect(screen.getByRole('textbox', { name: /^Skills/ })).toHaveValue('React, SQL');
    expect(screen.getByRole('combobox', { name: /^Source/ })).toHaveValue('remotive');
    expect(screen.getByRole('checkbox', { name: 'Include hidden jobs' })).toBeChecked();
    expect(screen.getByRole('checkbox', { name: 'Bookmarked only' })).not.toBeChecked();
    expect(screen.getByRole('combobox', { name: /^Sort by/ })).toHaveValue('deadline');
    expect(screen.getByRole('button', { name: 'Order: descending' })).toBeEnabled();
  });

  it('defaults to match score sort and toggles the order when a key is chosen', async () => {
    const { user } = renderFilters();
    const sort = screen.getByRole('combobox', { name: /^Sort by/ });
    expect(Array.from((sort as HTMLSelectElement).options).map((option) => option.value)).toEqual([
      'match_score',
      'discovered_at',
      'deadline',
      'title',
      'company',
      'salary',
    ]);
    expect(sort).toHaveValue('match_score');
    expect(screen.getByRole('button', { name: 'Order: descending' })).toBeEnabled();
    await user.selectOptions(sort, 'title');
    expect(currentSearch()).toBe('?sort=title');
    await user.click(screen.getByRole('button', { name: 'Order: ascending' }));
    expect(currentSearch()).toBe('?sort=title&order=desc');
  });

  it('writes ?min_score= when a minimum score is chosen and removes it for any score', async () => {
    const { user } = renderFilters('?page=2');
    const minScore = screen.getByRole('combobox', { name: /^Minimum match score/ });
    await user.selectOptions(minScore, '60');
    expect(currentSearch()).toBe('?min_score=60');
    await user.selectOptions(minScore, '');
    expect(currentSearch()).toBe('');
  });

  it('sends skills as a comma list and location after the debounce', async () => {
    const { user } = renderFilters();
    await user.type(screen.getByRole('textbox', { name: /^Skills/ }), 'React, sql,');
    await user.type(screen.getByRole('textbox', { name: /^Location/ }), 'Berlin{Enter}');
    await waitFor(() => {
      expect(currentSearch()).toBe('?location=Berlin&skills=React%2Csql');
    });
    expect(screen.getByRole('textbox', { name: /^Skills/ })).toHaveValue('React, sql,');
  });

  it('empties the URL and the controls with Clear filters', async () => {
    const { user } = renderFilters('?q=react&work_mode=remote&bookmarked=true&page=2');
    await user.click(screen.getByRole('button', { name: 'Clear filters' }));
    expect(currentSearch()).toBe('');
    expect(screen.getByRole('searchbox', { name: /Search jobs/ })).toHaveValue('');
    expect(screen.getByRole('checkbox', { name: 'Remote' })).not.toBeChecked();
    expect(screen.getByRole('button', { name: 'Clear filters' })).toBeDisabled();
  });
});
