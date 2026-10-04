/**
 * Guards for links built from external (untrusted) data, such as a job's application URL.
 */

const SAFE_PROTOCOLS: ReadonlySet<string> = new Set(['http:', 'https:']);

/**
 * The normalized `href` of `value` when it is an absolute `http`/`https` URL, else `null`.
 *
 * Anything else (`javascript:`, `data:`, relative paths, unparseable text) must never become
 * a link target.
 */
export function safeExternalUrl(value: string | null | undefined): string | null {
  if (value === null || value === undefined) {
    return null;
  }
  let url: URL;
  try {
    url = new URL(value.trim());
  } catch (error) {
    if (error instanceof TypeError) {
      return null;
    }
    throw error;
  }
  return SAFE_PROTOCOLS.has(url.protocol) ? url.href : null;
}

const POSITIVE_INTEGER = /^[1-9]\d*$/;

/** A job id from a route or query param, or `null` when it is not a positive safe integer. */
export function parseJobId(value: string | null | undefined): number | null {
  if (value === null || value === undefined || !POSITIVE_INTEGER.test(value)) {
    return null;
  }
  const id = Number(value);
  return Number.isSafeInteger(id) ? id : null;
}

/** Hosts reserved for documentation and testing; they never serve real job pages. */
const PLACEHOLDER_DOMAINS: readonly string[] = ['example.com', 'example.org', 'example.net'];
const PLACEHOLDER_TLDS: readonly string[] = ['.example', '.test', '.invalid', '.localhost'];

/** `true` when `value` is an http(s) URL on a reserved placeholder host (e.g. example.com). */
export function isPlaceholderUrl(value: string | null | undefined): boolean {
  const href = safeExternalUrl(value);
  if (href === null) {
    return false;
  }
  const host = new URL(href).hostname.toLowerCase();
  return (
    host === 'localhost' ||
    PLACEHOLDER_DOMAINS.some((domain) => host === domain || host.endsWith(`.${domain}`)) ||
    PLACEHOLDER_TLDS.some((tld) => host.endsWith(tld))
  );
}

/** A Google Jobs search for roles like the given one (used for demo listings). */
export function similarRolesSearchUrl(title: string, location: string): string {
  const query = `${title} internship ${location}`.trim();
  return `https://www.google.com/search?q=${encodeURIComponent(query)}&ibp=htmlahl;jobs`;
}
