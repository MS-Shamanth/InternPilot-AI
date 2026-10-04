import { useCallback, useSyncExternalStore } from 'react';

/** `true` while the CSS media query matches; `false` where `matchMedia` is unavailable. */
export function useMediaQuery(query: string): boolean {
  const subscribe = useCallback(
    (onChange: () => void) => {
      if (typeof window.matchMedia !== 'function') {
        return () => undefined;
      }
      const media = window.matchMedia(query);
      media.addEventListener('change', onChange);
      return () => {
        media.removeEventListener('change', onChange);
      };
    },
    [query],
  );
  const getSnapshot = useCallback(
    () => typeof window.matchMedia === 'function' && window.matchMedia(query).matches,
    [query],
  );
  return useSyncExternalStore(subscribe, getSnapshot);
}
