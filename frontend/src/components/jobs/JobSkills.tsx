import type { JobSummary } from '../../types/api';
import { SkillList } from './SkillList';

interface JobSkillsProps {
  job: Pick<JobSummary, 'required_skills' | 'preferred_skills'>;
}

/** Both skill lists of a job, or a note that it lists none. */
export function JobSkills({ job }: JobSkillsProps) {
  if (job.required_skills.length === 0 && job.preferred_skills.length === 0) {
    return <p className="text-sm text-ink-600">No skills listed.</p>;
  }
  return (
    <div className="flex flex-col gap-2">
      <SkillList kind="Required" skills={job.required_skills} />
      <SkillList kind="Preferred" skills={job.preferred_skills} />
    </div>
  );
}
