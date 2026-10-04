import type { InterviewPrep, PrepPriority } from '../../types/api';
import { Badge } from '../ui/Badge';
import type { BadgeTone } from '../ui/Badge';
import { Card } from '../ui/Card';

interface InterviewPrepViewProps {
  prep: InterviewPrep;
}

const PRIORITY_TONES: Readonly<Record<PrepPriority, BadgeTone>> = {
  high: 'danger',
  medium: 'warning',
  low: 'neutral',
};
const PRIORITY_LABELS: Readonly<Record<PrepPriority, string>> = {
  high: 'High priority',
  medium: 'Medium priority',
  low: 'Low priority',
};

/** Interview questions by section and prep topics (R9.1), as the backend generated them. */
export function InterviewPrepView({ prep }: InterviewPrepViewProps) {
  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
      <div className="flex min-w-0 flex-col gap-6">
        {prep.sections.map((section) => (
          <Card key={section.category} title={section.title}>
            {section.questions.length === 0 ? (
              <p className="text-sm text-ink-600">No questions in this section.</p>
            ) : (
              <ol className="flex list-decimal flex-col gap-2 pl-5 text-sm text-ink-800">
                {section.questions.map((question) => (
                  <li key={question.id}>{question.text}</li>
                ))}
              </ol>
            )}
          </Card>
        ))}
      </div>
      <Card title="Prep topics" className="self-start">
        {prep.prep_topics.length === 0 ? (
          <p className="text-sm text-ink-600">No extra topics to prepare.</p>
        ) : (
          <ul className="flex flex-col gap-3 text-sm">
            {prep.prep_topics.map((topic) => (
              <li key={topic.topic}>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium text-ink-900">{topic.topic}</span>
                  <Badge tone={PRIORITY_TONES[topic.priority]}>
                    {PRIORITY_LABELS[topic.priority]}
                  </Badge>
                </div>
                <p className="mt-0.5 text-ink-700">{topic.reason}</p>
              </li>
            ))}
          </ul>
        )}
        <p className="mt-4 text-xs text-ink-600">
          {prep.provider === 'llm'
            ? 'Questions enriched by the AI provider.'
            : 'Template questions.'}
        </p>
      </Card>
    </div>
  );
}
