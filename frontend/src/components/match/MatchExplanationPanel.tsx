import type { MatchExplanation } from '../../types/api';
import { Badge } from '../ui/Badge';
import type { BadgeTone } from '../ui/Badge';
import { Card } from '../ui/Card';
import { FactorBreakdown } from './FactorBreakdown';
import { MatchScoreRing } from './MatchScoreRing';

interface MatchExplanationPanelProps {
  explanation: MatchExplanation;
  className?: string;
}

interface ReasonListProps {
  title: string;
  prefix: '+' | '-';
  reasons: readonly string[];
}

function ReasonList({ title, prefix, reasons }: ReasonListProps) {
  const positive = prefix === '+';
  return (
    <div>
      <h3 className="mb-1.5 text-sm font-semibold text-ink-800">{title}</h3>
      {reasons.length === 0 ? (
        <p className="text-sm text-ink-600">None.</p>
      ) : (
        <ul aria-label={title} className="flex flex-col gap-1 text-sm">
          {reasons.map((reason) => (
            <li
              key={reason}
              className={positive ? 'text-success-800' : 'text-danger-800'}
            >{`${prefix} ${reason}`}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

interface SkillGroupProps {
  title: string;
  skills: readonly string[];
  tone: BadgeTone;
}

function SkillGroup({ title, skills, tone }: SkillGroupProps) {
  return (
    <div>
      <h3 className="mb-1.5 text-sm font-semibold text-ink-800">{title}</h3>
      {skills.length === 0 ? (
        <p className="text-sm text-ink-600">None.</p>
      ) : (
        <ul aria-label={title} className="flex flex-wrap gap-1.5">
          {skills.map((skill) => (
            <li key={skill}>
              <Badge tone={tone}>{skill}</Badge>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/**
 * Why a job got its score (R4.7): the score, `+`/`-` reasons, matched and missing skills and the
 * factor breakdown, all exactly as the backend computed them.
 */
export function MatchExplanationPanel({ explanation, className }: MatchExplanationPanelProps) {
  return (
    <Card title={`MATCH SCORE: ${String(explanation.score)}/100`} className={className}>
      <div className="flex flex-col gap-5">
        <MatchScoreRing score={explanation.score} showLabel={false} />
        <div className="grid gap-4 sm:grid-cols-2">
          <ReasonList title="Why it fits" prefix="+" reasons={explanation.positive_reasons} />
          <ReasonList
            title="What holds it back"
            prefix="-"
            reasons={explanation.negative_reasons}
          />
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <SkillGroup
            title="Matched required skills"
            skills={explanation.matched_required_skills}
            tone="success"
          />
          <SkillGroup
            title="Missing required skills"
            skills={explanation.missing_required_skills}
            tone="danger"
          />
          <SkillGroup
            title="Matched preferred skills"
            skills={explanation.matched_preferred_skills}
            tone="success"
          />
          <SkillGroup
            title="Missing preferred skills"
            skills={explanation.missing_preferred_skills}
            tone="warning"
          />
        </div>
        <div>
          <h3 className="mb-1.5 text-sm font-semibold text-ink-800">Score breakdown</h3>
          <FactorBreakdown factors={explanation.factors} />
        </div>
      </div>
    </Card>
  );
}
