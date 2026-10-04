import { Skeleton } from '../ui/Skeleton';
import { SkeletonBlock } from '../ui/SkeletonBlock';

/** Suspense fallback while a lazily loaded page chunk downloads. */
export function PageLoading() {
  return (
    <Skeleton label="Loading page…">
      <SkeletonBlock className="h-8 w-48" />
      <SkeletonBlock className="h-4 w-80 max-w-full" />
      <SkeletonBlock className="h-40 w-full" />
    </Skeleton>
  );
}
