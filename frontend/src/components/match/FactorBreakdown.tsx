import { formatPoints } from '../../lib/match';
import type { Factor } from '../../types/api';

interface FactorBreakdownProps {
  /** The eight factors in engine order, as sent by the backend. */
  factors: readonly Factor[];
}

/** Per-factor table: points earned out of the factor's weight, with the engine's detail. */
export function FactorBreakdown({ factors }: FactorBreakdownProps) {
  return (
    <table className="w-full text-left text-sm">
      <caption className="sr-only">Score breakdown by factor</caption>
      <thead>
        <tr className="border-b border-ink-200 text-ink-700">
          <th scope="col" className="py-1.5 pr-3 font-medium">
            Factor
          </th>
          <th scope="col" className="py-1.5 pr-3 text-right font-medium">
            Points
          </th>
          <th scope="col" className="py-1.5 pr-3 text-right font-medium">
            Weight
          </th>
          <th scope="col" className="py-1.5 font-medium">
            Detail
          </th>
        </tr>
      </thead>
      <tbody>
        {factors.map((factor) => (
          <tr key={factor.key} className="border-b border-ink-100 align-top last:border-0">
            <th scope="row" className="py-1.5 pr-3 font-normal text-ink-900">
              {factor.label}
            </th>
            <td className="py-1.5 pr-3 text-right tabular-nums text-ink-900">
              {formatPoints(factor.points)}
            </td>
            <td className="py-1.5 pr-3 text-right tabular-nums text-ink-700">{factor.weight}</td>
            <td className="py-1.5 text-ink-700">{factor.detail}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
