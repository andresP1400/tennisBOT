import type { ValueSummaryProps } from "./value-summary.types"

export function ValueSummary({ performance }: ValueSummaryProps) {
  const accuracy = performance.accuracy == null ? "unmeasured" : `${(performance.accuracy * 100).toFixed(1)}%`
  const roi = performance.paper_roi == null ? "unmeasured" : `${(performance.paper_roi * 100).toFixed(1)}%`
  return <p className="text-sm text-muted-foreground">
    This category, both tours, first archived pick per match: {performance.completed ?? 0} completed,
    {" "}{performance.pending ?? 0} pending. Accuracy {accuracy}; unit-stake paper ROI {roi}.
    Paper returns do not establish executable profitability.
  </p>
}
