import { Link } from 'react-router-dom';
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { CHART_COLORS } from '../../lib/chartColors';
import { hasAnyCount } from '../../lib/dashboard';
import type { StatusCount } from '../../types/api';
import { buttonClasses } from '../ui/buttonStyles';
import { Card } from '../ui/Card';
import { EmptyState } from '../ui/EmptyState';
import { ChartFigure } from './ChartFigure';

interface StatusBreakdownChartProps {
  /** All eight statuses in canonical order, as sent by the backend (R6.4). */
  items: readonly StatusCount[];
}

const TICK = { fill: CHART_COLORS.axis, fontSize: 12 };

/** Horizontal bar chart of tracked applications per status, in the backend's order. */
export function StatusBreakdownChart({ items }: StatusBreakdownChartProps) {
  const summary = `Applications by status: ${items
    .map((item) => `${item.status} ${String(item.count)}`)
    .join(', ')}.`;

  return (
    <Card title="Status breakdown" description="Tracked applications in each status.">
      {hasAnyCount(items) ? (
        <ChartFigure
          summary={summary}
          caption="Number of tracked applications per status."
          columns={['Status', 'Applications']}
          rows={items.map((item) => ({ key: item.status, label: item.status, value: item.count }))}
        >
          <ResponsiveContainer width="100%" height={280}>
            <BarChart
              data={[...items]}
              layout="vertical"
              margin={{ top: 4, right: 16, bottom: 4, left: 8 }}
            >
              <CartesianGrid horizontal={false} stroke={CHART_COLORS.grid} />
              <XAxis type="number" allowDecimals={false} stroke={CHART_COLORS.axis} tick={TICK} />
              <YAxis
                type="category"
                dataKey="status"
                width={88}
                stroke={CHART_COLORS.axis}
                tick={TICK}
              />
              <Tooltip cursor={{ fill: CHART_COLORS.grid }} />
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
          title="No tracked applications yet"
          description="Save a job or add an application to see how your pipeline is spread."
          action={
            <Link to="/applications" className={buttonClasses({ variant: 'secondary' })}>
              Go to applications
            </Link>
          }
        />
      )}
    </Card>
  );
}
