import { Link } from 'react-router-dom';
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { CHART_COLORS } from '../../lib/chartColors';
import { hasAnyCount } from '../../lib/dashboard';
import type { ScoreBucketCount } from '../../types/api';
import { buttonClasses } from '../ui/buttonStyles';
import { Card } from '../ui/Card';
import { EmptyState } from '../ui/EmptyState';
import { ChartFigure } from './ChartFigure';

interface ScoreDistributionChartProps {
  /** The five score buckets in ascending order, as sent by the backend (R6.6). */
  buckets: readonly ScoreBucketCount[];
}

const TICK = { fill: CHART_COLORS.axis, fontSize: 12 };

/** Column chart of non-hidden jobs per match-score bucket. */
export function ScoreDistributionChart({ buckets }: ScoreDistributionChartProps) {
  const summary = `Jobs by match score: ${buckets
    .map((item) => `${item.bucket} ${String(item.count)}`)
    .join(', ')}.`;

  return (
    <Card title="Match score distribution" description="Jobs you have not hidden, by score.">
      {hasAnyCount(buckets) ? (
        <ChartFigure
          summary={summary}
          caption="Number of jobs in each match score range."
          columns={['Score range', 'Jobs']}
          rows={buckets.map((item) => ({
            key: item.bucket,
            label: item.bucket,
            value: item.count,
          }))}
        >
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={[...buckets]} margin={{ top: 4, right: 16, bottom: 4, left: 0 }}>
              <CartesianGrid vertical={false} stroke={CHART_COLORS.grid} />
              <XAxis dataKey="bucket" stroke={CHART_COLORS.axis} tick={TICK} />
              <YAxis allowDecimals={false} width={32} stroke={CHART_COLORS.axis} tick={TICK} />
              <Tooltip cursor={{ fill: CHART_COLORS.grid }} />
              <Bar
                dataKey="count"
                name="Jobs"
                fill={CHART_COLORS.primary}
                isAnimationActive={false}
              />
            </BarChart>
          </ResponsiveContainer>
        </ChartFigure>
      ) : (
        <EmptyState
          titleAs="h3"
          title="No jobs to score yet"
          description="Import or browse jobs to see how well they match your profile."
          action={
            <Link to="/jobs" className={buttonClasses({ variant: 'secondary' })}>
              Browse jobs
            </Link>
          }
        />
      )}
    </Card>
  );
}
