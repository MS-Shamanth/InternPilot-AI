import { describe, expect, it } from 'vitest';
import { safeExternalUrl } from '../../src/lib/url';
import { isPlaceholderUrl, similarRolesSearchUrl } from '../../src/lib/url';

describe('safeExternalUrl', () => {
  it('returns the normalized href of an http or https URL', () => {
    expect(safeExternalUrl('https://jobs.example.com/apply?id=1')).toBe(
      'https://jobs.example.com/apply?id=1',
    );
    expect(safeExternalUrl('  http://Example.com  ')).toBe('http://example.com/');
  });

  it.each(['javascript:alert(1)', 'JAVASCRIPT:alert(1)', 'data:text/html,hi', 'mailto:a@b.c'])(
    'returns null for the non-http scheme %s',
    (value) => {
      expect(safeExternalUrl(value)).toBeNull();
    },
  );

  it('returns null for relative, unparseable or missing values', () => {
    expect(safeExternalUrl('/apply')).toBeNull();
    expect(safeExternalUrl('not a url')).toBeNull();
    expect(safeExternalUrl('')).toBeNull();
    expect(safeExternalUrl(null)).toBeNull();
    expect(safeExternalUrl(undefined)).toBeNull();
  });
});

describe('isPlaceholderUrl', () => {
  it.each([
    'https://example.com/a',
    'https://careers.example.com/x',
    'http://jobs.example.org',
    'https://shop.test/apply',
    'http://localhost:3000/job',
  ])('returns true when the URL is %s', (url) => {
    expect(isPlaceholderUrl(url)).toBe(true);
  });

  it.each([
    'https://remotive.com/jobs/1',
    'https://www.arbeitnow.com/view/x',
    'https://notexample.com',
    'javascript:alert(1)',
    '',
  ])('returns false when the URL is %s', (url) => {
    expect(isPlaceholderUrl(url)).toBe(false);
  });
});

describe('similarRolesSearchUrl', () => {
  it('builds an encoded Google Jobs search when given a title and location', () => {
    expect(similarRolesSearchUrl('Frontend Intern', 'Berlin, Germany')).toBe(
      'https://www.google.com/search?q=Frontend%20Intern%20internship%20Berlin%2C%20Germany&ibp=htmlahl;jobs',
    );
  });
});
