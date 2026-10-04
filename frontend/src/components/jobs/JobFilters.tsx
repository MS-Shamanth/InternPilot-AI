import { useEffect, useRef, useState } from 'react';
import type { KeyboardEvent } from 'react';
import { useDebouncedValue } from '../../hooks/useDebouncedValue';
import {
  EMPLOYMENT_TYPE_OPTIONS,
  EXPERIENCE_LEVEL_OPTIONS,
  JOB_SOURCE_OPTIONS,
  WORK_MODE_OPTIONS,
  isOptionValue,
} from '../../lib/enumOptions';
import type { Option } from '../../lib/enumOptions';
import {
  LOCATION_MAX_LENGTH,
  MIN_SCORE_OPTIONS,
  QUERY_MAX_LENGTH,
  SORT_OPTIONS,
  applyFilterChange,
  clearFilters,
  effectiveSort,
  effectiveSortOrder,
  formatSkillsText,
  hasActiveFilters,
  parseSkillsText,
} from '../../lib/jobFilters';
import type { JobListParams } from '../../types/api';
import { Button } from '../ui/Button';
import { Checkbox } from '../ui/Checkbox';
import { Select } from '../ui/Select';
import { TextField } from '../ui/TextField';

export const FILTER_DEBOUNCE_MS = 300;

interface JobFiltersProps {
  /** The current (normalized) list params, read from the URL by the page. */
  value: JobListParams;
  /**
   * Called with an update of the latest params (which may include commits not rendered yet);
   * filter and sort changes reset the page to 1.
   */
  onChange: (update: (current: JobListParams) => JobListParams) => void;
}

interface DraftTextFieldProps {
  label: string;
  hint?: string;
  /** The committed value, already in normalized text form. */
  value: string;
  /** Text → the form `value` would take once committed (used to compare drafts). */
  normalize: (text: string) => string;
  onCommit: (text: string) => void;
  type?: 'text' | 'search';
  maxLength?: number;
}

/**
 * Text input that commits its draft after a 300 ms pause or immediately on Enter. The draft
 * follows `value` only when `value` changes to something the draft does not already mean, so
 * typing is never overwritten by its own (normalized) commit.
 */
function DraftTextField({
  label,
  hint,
  value,
  normalize,
  onCommit,
  type = 'text',
  maxLength,
}: DraftTextFieldProps) {
  const [draft, setDraft] = useState(value);
  const [syncedValue, setSyncedValue] = useState(value);
  const debouncedDraft = useDebouncedValue(draft, FILTER_DEBOUNCE_MS);
  const latest = useRef({ value, normalize, onCommit });

  if (value !== syncedValue) {
    setSyncedValue(value);
    if (normalize(draft) !== value) {
      setDraft(value);
    }
  }

  useEffect(() => {
    latest.current = { value, normalize, onCommit };
  });

  useEffect(() => {
    const current = latest.current;
    if (current.normalize(debouncedDraft) !== current.value) {
      current.onCommit(debouncedDraft);
    }
  }, [debouncedDraft]);

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key !== 'Enter') {
      return;
    }
    event.preventDefault();
    if (normalize(draft) !== value) {
      onCommit(draft);
    }
  }

  return (
    <TextField
      type={type}
      label={label}
      hint={hint}
      value={draft}
      maxLength={maxLength}
      onChange={(event) => {
        setDraft(event.target.value);
      }}
      onKeyDown={handleKeyDown}
    />
  );
}

interface CheckboxGroupProps<T extends string> {
  legend: string;
  options: readonly Option<T>[];
  selected: readonly T[] | undefined;
  onChange: (next: T[]) => void;
}

function CheckboxGroup<T extends string>({
  legend,
  options,
  selected = [],
  onChange,
}: CheckboxGroupProps<T>) {
  return (
    <fieldset>
      <legend className="mb-2 text-sm font-semibold text-ink-800">{legend}</legend>
      <div className="flex flex-col gap-2">
        {options.map((option) => (
          <Checkbox
            key={option.value}
            label={option.label}
            checked={selected.includes(option.value)}
            onChange={(event) => {
              onChange(
                event.target.checked
                  ? [...selected, option.value]
                  : selected.filter((value) => value !== option.value),
              );
            }}
          />
        ))}
      </div>
    </fieldset>
  );
}

function trimText(maxLength: number): (text: string) => string {
  return (text) => text.trim().slice(0, maxLength).trim();
}

const normalizeQuery = trimText(QUERY_MAX_LENGTH);
const normalizeLocation = trimText(LOCATION_MAX_LENGTH);
const normalizeSkills = (text: string) => formatSkillsText(parseSkillsText(text));

/** The preset thresholds, plus the URL's value when it is not one of them (e.g. `?min_score=55`). */
function minScoreOptions(current: number | undefined): readonly Option<string>[] {
  if (current === undefined || isOptionValue(MIN_SCORE_OPTIONS, String(current))) {
    return MIN_SCORE_OPTIONS;
  }
  const custom = { value: String(current), label: `${String(current)} or more` };
  return [...MIN_SCORE_OPTIONS, custom].sort((a, b) => Number(a.value) - Number(b.value));
}

/** Search, filters and sort for the job list (R2.3–R2.5); the URL holds the state. */
export function JobFilters({ value, onChange }: JobFiltersProps) {
  const order = effectiveSortOrder(value);
  const filtersActive = hasActiveFilters(value);

  function update(patch: Partial<JobListParams>) {
    onChange((current) => applyFilterChange(current, patch));
  }

  return (
    <form
      role="search"
      aria-label="Jobs"
      className="flex flex-col gap-5"
      onSubmit={(event) => {
        event.preventDefault();
      }}
    >
      <DraftTextField
        type="search"
        label="Search jobs"
        hint="Title, company or description. Press Enter to search now."
        value={value.q ?? ''}
        normalize={normalizeQuery}
        maxLength={QUERY_MAX_LENGTH}
        onCommit={(text) => {
          update({ q: text });
        }}
      />
      <div className="flex flex-col gap-3">
        <Select
          label="Sort by"
          value={effectiveSort(value)}
          onChange={(event) => {
            const sort = SORT_OPTIONS.find((option) => option.value === event.target.value);
            update({ sort: sort?.value, order: undefined });
          }}
        >
          {SORT_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </Select>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => {
            update({ order: order === 'asc' ? 'desc' : 'asc' });
          }}
        >
          {order === 'asc' ? 'Order: ascending' : 'Order: descending'}
        </Button>
      </div>
      <Select
        label="Minimum match score"
        value={value.min_score === undefined ? '' : String(value.min_score)}
        onChange={(event) => {
          update({ min_score: event.target.value === '' ? undefined : Number(event.target.value) });
        }}
      >
        <option value="">Any score</option>
        {minScoreOptions(value.min_score).map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </Select>
      <CheckboxGroup
        legend="Employment type"
        options={EMPLOYMENT_TYPE_OPTIONS}
        selected={value.employment_type}
        onChange={(next) => {
          update({ employment_type: next });
        }}
      />
      <CheckboxGroup
        legend="Work mode"
        options={WORK_MODE_OPTIONS}
        selected={value.work_mode}
        onChange={(next) => {
          update({ work_mode: next });
        }}
      />
      <CheckboxGroup
        legend="Experience level"
        options={EXPERIENCE_LEVEL_OPTIONS}
        selected={value.experience_level}
        onChange={(next) => {
          update({ experience_level: next });
        }}
      />
      <DraftTextField
        label="Location"
        hint="Matches part of the location, e.g. Berlin."
        value={value.location ?? ''}
        normalize={normalizeLocation}
        maxLength={LOCATION_MAX_LENGTH}
        onCommit={(text) => {
          update({ location: text });
        }}
      />
      <DraftTextField
        label="Skills"
        hint="Comma-separated, up to 10. Jobs listing any of them match."
        value={formatSkillsText(value.skills)}
        normalize={normalizeSkills}
        onCommit={(text) => {
          update({ skills: parseSkillsText(text) });
        }}
      />
      <Select
        label="Source"
        value={value.source ?? ''}
        onChange={(event) => {
          const source = JOB_SOURCE_OPTIONS.find((option) => option.value === event.target.value);
          update({ source: source?.value });
        }}
      >
        <option value="">Any source</option>
        {JOB_SOURCE_OPTIONS.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </Select>
      <fieldset>
        <legend className="mb-2 text-sm font-semibold text-ink-800">Show</legend>
        <div className="flex flex-col gap-2">
          <Checkbox
            label="Bookmarked only"
            checked={value.bookmarked === true}
            onChange={(event) => {
              update({ bookmarked: event.target.checked });
            }}
          />
          <Checkbox
            label="Include hidden jobs"
            checked={value.include_hidden === true}
            onChange={(event) => {
              update({ include_hidden: event.target.checked });
            }}
          />
        </div>
      </fieldset>
      <Button
        variant="ghost"
        disabled={!filtersActive}
        onClick={() => {
          onChange(clearFilters);
        }}
      >
        Clear filters
      </Button>
    </form>
  );
}
