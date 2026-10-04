import { useId, useState } from 'react';
import type { ReactNode } from 'react';
import { Button } from '../ui/Button';

export interface ChartDataRow {
  key: string;
  label: string;
  value: number;
}

interface ChartFigureProps {
  /** Text summary of the chart, read by screen readers instead of the SVG. */
  summary: string;
  /** Visible caption under the chart. */
  caption: string;
  /** Header cells of the data table: [label column, value column]. */
  columns: readonly [string, string];
  rows: readonly ChartDataRow[];
  /** The Recharts chart. */
  children: ReactNode;
}

/**
 * A chart with accessible text alternatives: a `role="img"` summary and a "Show data table"
 * toggle that reveals the same numbers as a table, so the chart is never the only source.
 */
export function ChartFigure({ summary, caption, columns, rows, children }: ChartFigureProps) {
  const tableId = useId();
  const [showTable, setShowTable] = useState(false);

  return (
    <figure className="flex flex-col gap-3">
      <div role="img" aria-label={summary}>
        {children}
      </div>
      <figcaption className="text-sm text-ink-600">{caption}</figcaption>
      <div>
        <Button
          variant="secondary"
          size="sm"
          aria-expanded={showTable}
          aria-controls={tableId}
          onClick={() => {
            setShowTable((shown) => !shown);
          }}
        >
          {showTable ? 'Hide data table' : 'Show data table'}
        </Button>
      </div>
      <div id={tableId} hidden={!showTable}>
        <table className="w-full text-left text-sm">
          <caption className="sr-only">{caption}</caption>
          <thead>
            <tr className="border-b border-ink-200 text-ink-700">
              <th scope="col" className="py-1.5 pr-4 font-medium">
                {columns[0]}
              </th>
              <th scope="col" className="py-1.5 text-right font-medium">
                {columns[1]}
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.key} className="border-b border-ink-100 last:border-0">
                <th scope="row" className="py-1.5 pr-4 font-normal text-ink-800">
                  {row.label}
                </th>
                <td className="py-1.5 text-right tabular-nums text-ink-900">{row.value}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </figure>
  );
}
