import type { ValueRowsProps } from "./value-rows.types"

export function ValueRows({ candidates }: ValueRowsProps) {
  return <div className="space-y-3">{candidates.map(candidate => <article key={`${candidate.prediction_id}:${candidate.player}`} className="border-t py-3 text-sm">
    <p>{candidate.fixture.player1} vs {candidate.fixture.player2} · {candidate.fixture.tournament} · {candidate.fixture.surface}</p>
    <p>{candidate.player}: {(candidate.probability * 100).toFixed(1)}% estimated win probability.
      Odds {candidate.decimal_odds?.toFixed(2) ?? "unavailable"} at {candidate.bookmaker ?? "unavailable"}.</p>
    <p>No-vig market {candidate.no_vig_market_probability == null ? "unavailable" : `${(candidate.no_vig_market_probability * 100).toFixed(1)}%`}.
      Edge {candidate.probability_edge == null ? "unavailable" : `${(candidate.probability_edge * 100).toFixed(1)} points`}.
      Estimated EV {candidate.estimated_ev == null ? "unavailable" : `${(candidate.estimated_ev * 100).toFixed(1)}%`}.
      Conservative EV {candidate.conservative_ev == null ? "unavailable" : `${(candidate.conservative_ev * 100).toFixed(1)}%`}.</p>
    <p>Validation-bin lower probability {candidate.lower_probability == null ? "unavailable" : `${(candidate.lower_probability * 100).toFixed(1)}%`}.</p>
    <p>Provider quote: {candidate.quote_time ?? "unavailable"}; observed: {candidate.quote_observed_at ?? "unavailable"}.</p>
    <details><summary>Evidence and risks</summary><p>{candidate.supporting_reasons.join("; ")}</p>
      <p>{candidate.risks.join("; ") || "Provider timing and model uncertainty still apply; execution is not guaranteed."}</p>
      <p>Model {candidate.model_version}; policy {candidate.policy_version}; forecast {candidate.prediction_id}.</p></details>
  </article>)}</div>
}
