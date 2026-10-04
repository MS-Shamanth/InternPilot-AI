import { Link } from 'react-router-dom';
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { CHART_COLORS } from '../../lib/chartColors';
import { applicationCountText, formatWeekStart, hasAnyCount } from '../../lib/dashboard';
import { formatDate } from '../../lib/format';
import type { WeeklyApplicationCount } from '../../types/api';
import { buttonClasses } from '../ui/buttonStyles';
import { Card } from '../ui/Card';
import { EmptyState } from '../ui/EmptyState';
import { ChartFigure } from './ChartFigure';

interface ApplicationsOverTimeChartProps {
  /** The last eight ISO weeks (Monday start), oldest first, as sent by the backend. */
  weeks: readonly WeeklyApplicationCount[];
}

const TICK = { fill: CHART_COLORS.axis, fontSize: 12 };

function weekOf(weekStart: string): string {
  return `Week of ${formatDate(weekStart)}`;
}

/** Weekly bar chart of submitted applications (by applied-on date). */
export function ApplicationsOverTimeChart({ weeks }: ApplicationsOverTimeChartProps) {
  const summary = `Applications submitted per week: ${weeks
    .map((week) => `${weekOf(week.week_start)}, ${applicationCountText(week.count)}`)
    .join('; ')}.`;

  return (
    <Card title="Applications over time" description="Applications submitted in the last 8 weeks.">
      {hasAnyCount(weeks) ? (
        <ChartFigure
          summary={summary}
          caption="Applications submitted per week, by applied-on date."
          columns={['Week', 'Applications']}
          rows={weeks.map((week) => ({
            key: week.week_start,
            label: weekOf(week.week_start),
            value: week.count,
          }))}
        >
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={[...weeks]} margin={{ top: 4, right: 16, bottom: 4, left: 0 }}>
              <CartesianGrid vertical={false} stroke={CHART_COLORS.grid} />
              <XAxis
                dataKey="week_start"
                tickFormatter={formatWeekStart}
                stroke={CHART_COLORS.axis}
                tick={TICK}
              />
              <YAxis allowDecimals={false} width={32} stroke={CHART_COLORS.axis} tick={TICK} />
              <Tooltip
                cursor={{ fill: CHART_COLORS.grid }}
                labelFormatter={(label: string) => weekOf(label)}
              />
              <Bar
                dataKey="count"
                name="Applications"
                fill={CHART_COLORS.primary}
                isAnimationActive={false}
              />
            </BarChart>
          </ResponsiveContainer>
        </ChartFigure>
      ) : (
        <EmptyState
          titleAs="h3"
          title="No applications submitted in the last 8 weeks"
          description="Mark a job as applied to start your weekly trend."
          action={
            <Link to="/jobs" className={buttonClasses({ variant: 'secondary' })}>
              Find jobs to apply to
            </Link>
          }
        />
      )}
    </Card>
  );
}
