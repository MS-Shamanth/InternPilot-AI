import { Badge } from '../ui/Badge';

interface SkillListProps {
  kind: 'Required' | 'Preferred';
  skills: readonly string[];
}

/** Required skills are solid and bold, preferred ones dashed; each list has a text label. */
export function SkillList({ kind, skills }: SkillListProps) {
  if (skills.length === 0) {
    return null;
  }
  const required = kind === 'Required';
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <span className="text-xs font-semibold text-ink-700">{kind}:</span>
      <ul aria-label={`${kind} skills`} className="flex flex-wrap gap-1.5">
        {skills.map((skill) => (
          <li key={skill}>
            <Badge
              tone={required ? 'pilot' : 'neutral'}
              className={required ? 'font-semibold' : 'border-dashed bg-white'}
            >
              <span className="sr-only">{kind}: </span>
              {skill}
            </Badge>
          </li>
        ))}
      </ul>
    </div>
  );
}
