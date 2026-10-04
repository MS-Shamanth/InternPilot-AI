import type { JobSummary } from '../../types/api';
import { Badge } from '../ui/Badge';

interface JobFlagsProps {
  job: Pick<JobSummary, 'application_status' | 'is_bookmarked' | 'is_hidden'>;
}

/** Text badges for the user's application status, bookmark and hidden flags. */
export function JobFlags({ job }: JobFlagsProps) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {job.application_status !== null && (
        <Badge tone="signal">Status: {job.application_status}</Badge>
      )}
      {job.is_bookmarked && <Badge tone="pilot">Bookmarked</Badge>}
      {job.is_hidden && <Badge tone="warning">Hidden</Badge>}
    </div>
  );
}
