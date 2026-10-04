import { render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { MatchExplanationPanel } from '../../src/components/match/MatchExplanationPanel';
import { MatchScoreRing } from '../../src/components/match/MatchScoreRing';
import { makeMatchExplanation } from '../jobs/jobFixtures';

describe('MatchScoreRing', () => {
  it('shows the score as text with an aria-label and a band label when rendered', () => {
    render(<MatchScoreRing score={87} />);
    expect(screen.getByText('MATCH SCORE: 87/100')).toBeInTheDocument();
    expect(screen.getByRole('img', { name: 'Match score 87 out of 100' })).toBeInTheDocument();
    expect(screen.getByText('Strong match')).toBeInTheDocument();
  });

  it('uses a text band that does not rely on color when the score is low', () => {
    render(<MatchScoreRing score={12} name="Compatibility score" />);
    expect(screen.getByText('COMPATIBILITY SCORE: 12/100')).toBeInTheDocument();
    expect(screen.getByText('Low match')).toBeInTheDocument();
  });
});

describe('MatchExplanationPanel', () => {
  it('lists + positive and - negative reasons, skills and the factor table when rendered', () => {
    render(<MatchExplanationPanel explanation={makeMatchExplanation()} />);
    expect(screen.getByRole('heading', { name: 'MATCH SCORE: 72/100' })).toBeInTheDocument();
    expect(screen.getByRole('list', { name: 'Why it fits' })).toHaveTextContent(
      '+ You have 1 of 2 required skills: React',
    );
    expect(screen.getByRole('list', { name: 'What holds it back' })).toHaveTextContent(
      '- Missing required skills: TypeScript',
    );
    expect(screen.getByRole('list', { name: 'Missing required skills' })).toHaveTextContent(
      'TypeScript',
    );
    const row = screen.getByRole('row', { name: /Required skills/ });
    expect(
      within(row)
        .getAllByRole('cell')
        .map((cell) => cell.textContent),
    ).toEqual(['17.5', '35', '1 of 2 required skills']);
  });

  it('shows None when a reason list is empty', () => {
    render(<MatchExplanationPanel explanation={makeMatchExplanation({ negative_reasons: [] })} />);
    expect(screen.queryByRole('list', { name: 'What holds it back' })).not.toBeInTheDocument();
    expect(screen.getAllByText('None.').length).toBeGreaterThan(0);
  });
});
