import type { ReactNode } from 'react';
import type { ResumeAnalysis } from '../../types/api';
import { MatchScoreRing } from '../match/MatchScoreRing';
import { Badge } from '../ui/Badge';
import { Card } from '../ui/Card';

interface ResumeResultsProps {
  analysis: ResumeAnalysis;
}

function NoneText({ children }: { children: ReactNode }) {
  return <p className="text-sm text-ink-600">{children}</p>;
}

/**
 * Resume analysis results (R8.2): every value comes from `POST /resume/analyze` and is only
 * displayed; suggestions show the backend's evidence lines.
 */
export function ResumeResults({ analysis }: ResumeResultsProps) {
  const sourceText =
    analysis.resume_source === 'request' ? 'the pasted resume text' : 'your profile resume';

  return (
    <div className="flex flex-col gap-6">
      <Card title="Compatibility">
        <MatchScoreRing score={analysis.compatibility_score} name="Compatibility score" />
        <p className="mt-3 text-sm text-ink-700">
          {`Analyzed ${sourceText} (${String(analysis.word_count)} words).`}
        </p>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Matching skills">
          {analysis.matching_skills.length === 0 ? (
            <NoneText>No job skills found in your resume.</NoneText>
          ) : (
            <ul aria-label="Matching skills" className="flex flex-wrap gap-1.5">
              {analysis.matching_skills.map((item) => (
                <li key={item.skill}>
                  <Badge tone="success">
                    {`${item.skill} · ${item.is_required ? 'required' : 'preferred'}`}
                  </Badge>
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card title="Missing skills">
          {analysis.missing_skills.length === 0 ? (
            <NoneText>Your resume mentions every job skill.</NoneText>
          ) : (
            <ul aria-label="Missing skills" className="flex flex-col gap-1.5 text-sm">
              {analysis.missing_skills.map((item) => (
                <li key={item.skill} className="flex flex-wrap items-center gap-2">
                  <Badge tone={item.is_required ? 'danger' : 'warning'}>{item.skill}</Badge>
                  <span className="text-ink-700">
                    {`${item.is_required ? 'Required' : 'Preferred'} · ${
                      item.in_profile ? 'in your profile' : 'not in your profile'
                    }`}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Relevant projects">
          {analysis.relevant_projects.length === 0 ? (
            <NoneText>No profile projects use this job&apos;s skills.</NoneText>
          ) : (
            <ul className="flex flex-col gap-2 text-sm">
              {analysis.relevant_projects.map((project) => (
                <li key={project.name}>
                  <p className="font-medium text-ink-900">{project.name}</p>
                  <p className="text-ink-700">
                    {`Skills: ${project.matched_skills.join(', ')} · ${
                      project.mentioned_in_resume ? 'mentioned in resume' : 'not in resume'
                    }`}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card title="Missing keywords">
          {analysis.missing_keywords.length === 0 ? (
            <NoneText>No important job keywords are missing.</NoneText>
          ) : (
            <ul aria-label="Missing keywords" className="flex flex-wrap gap-1.5">
              {analysis.missing_keywords.map((keyword) => (
                <li key={keyword}>
                  <Badge tone="neutral">{keyword}</Badge>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <Card title="Suggestions">
        {analysis.suggestions.length === 0 ? (
          <NoneText>No suggestions: your resume already covers this job well.</NoneText>
        ) : (
          <ol className="flex flex-col gap-3 text-sm">
            {analysis.suggestions.map((suggestion) => (
              <li key={`${suggestion.rule}-${suggestion.message}`}>
                <p className="font-medium text-ink-900">{suggestion.message}</p>
                {suggestion.evidence.length > 0 && (
                  <ul aria-label="Evidence" className="mt-1 list-disc pl-5 text-ink-700">
                    {suggestion.evidence.map((line) => (
                      <li key={line}>{line}</li>
                    ))}
                  </ul>
                )}
              </li>
            ))}
          </ol>
        )}
      </Card>
    </div>
  );
}
