import { useEffect } from 'react';

/**
 * Sets `document.title` while the caller is mounted (and `title` is not `null`), restoring the
 * previous title on change or unmount so the shell's section title takes over again.
 */
export function useDocumentTitle(title: string | null): void {
  useEffect(() => {
    if (title === null) {
      return undefined;
    }
    const previous = document.title;
    document.title = title;
    return () => {
      document.title = previous;
    };
  }, [title]);
}
