import { PageHeader } from '../components/layout/PageHeader';
import { ProfileForm } from '../components/profile/ProfileForm';
import { ErrorState } from '../components/ui/ErrorState';
import { Skeleton } from '../components/ui/Skeleton';
import { SkeletonBlock } from '../components/ui/SkeletonBlock';
import { useProfile } from '../hooks/useProfile';
import { useToast } from '../hooks/useToast';
import { useUpdateProfile } from '../hooks/useUpdateProfile';

function ProfileSkeleton() {
  return (
    <Skeleton label="Loading profile…">
      <SkeletonBlock className="h-40 w-full" />
      <SkeletonBlock className="h-56 w-full" />
      <SkeletonBlock className="h-40 w-full" />
    </Skeleton>
  );
}

export default function ProfilePage() {
  const toast = useToast();
  const profileQuery = useProfile();
  const updateProfile = useUpdateProfile({
    onSuccess: () => {
      toast.success('Profile saved');
    },
    onError: (error) => {
      toast.fromError(error);
    },
  });

  function handleRetry() {
    void profileQuery.refetch();
  }

  return (
    <>
      <PageHeader
        title="Profile"
        description="Your skills, preferences, education and projects drive every match score."
      />
      {profileQuery.isPending ? (
        <ProfileSkeleton />
      ) : profileQuery.isError ? (
        <ErrorState
          title="Could not load your profile"
          error={profileQuery.error}
          onRetry={handleRetry}
          isRetrying={profileQuery.isFetching}
        />
      ) : (
        <ProfileForm
          profile={profileQuery.data}
          onSave={updateProfile.mutateAsync}
          isSaving={updateProfile.isPending}
        />
      )}
    </>
  );
}
