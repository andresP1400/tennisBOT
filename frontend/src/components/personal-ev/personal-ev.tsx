import type { PersonalEVProps } from "./personal-ev.types"

export function PersonalEV({ prediction }: PersonalEVProps) {
  const side = prediction.winner === prediction.fixture.player1 ? "player1" : "player2"
  const analysis = prediction.betting_analysis?.[side]
  if (!analysis) return <span>EV unavailable</span>
  const value = analysis.expected_value == null ? "EV unavailable" : `Estimated EV: ${(analysis.expected_value * 100).toFixed(1)}%`
  const status = analysis.eligible ? "Passes data guards; informational only" : "Blocked by data guards"
  return <details className="text-xs text-muted-foreground">
    <summary>{status}</summary>
    <div>{value}</div>
    <div>Bankroll fraction: {(analysis.stake_fraction * 100).toFixed(2)}%</div>
    {analysis.reasons.map(reason => <div key={reason}>{reason}</div>)}
  </details>
}
