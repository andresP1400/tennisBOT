import type { PersonalPrediction } from "@/types/personal"
import { PersonalEV } from "@/components/personal-ev"

export function PersonalRows({ predictions }: { predictions: PersonalPrediction[] }) {
  if (!predictions.length) return null
  return <div className="overflow-x-auto"><table className="w-full text-left text-sm">
    <thead><tr><th>Starts</th><th>Match</th><th>Predicted winner</th><th>Win probability</th><th>Available odds</th></tr></thead>
    <tbody>{predictions.map(prediction => {
      const fixture = prediction.fixture
      const probability = prediction.winner === fixture.player1 ? prediction.prob1 : prediction.prob2
      return <tr key={prediction.tracking_id} className="border-t align-top">
        <td className="py-3 pr-4 whitespace-nowrap">{new Date(fixture.commence_time).toLocaleString()}</td>
        <td className="py-3 pr-4">{fixture.player1} vs {fixture.player2}
          <div className="text-xs text-muted-foreground">{fixture.tournament} · {fixture.surface}</div>
          {fixture.tournament_level === "WTA 125" && <p className="text-xs text-amber-500">
            WTA 125: accuracy has not been validated at this level.
          </p>}
          <details className="text-xs text-muted-foreground"><summary>Recorded forecast</summary>
            <div>Recorded: {new Date(prediction.predicted_at).toLocaleString()}</div>
            <div>Model: {prediction.model_version}</div>
            <div>Data through: {prediction.data_through}</div>
            <div className="break-all">Record: {prediction.tracking_id}</div>
          </details>
        </td>
        <td className="py-3 pr-4 font-medium">{prediction.winner}</td>
        <td className="py-3 pr-4">{(probability * 100).toFixed(1)}%</td>
        <td className="py-3">{fixture.odds1 != null && fixture.odds2 != null
          ? `${fixture.odds1.toFixed(2)} / ${fixture.odds2.toFixed(2)}` : "Not available"}
          <PersonalEV prediction={prediction} /></td>
      </tr>
    })}</tbody>
  </table></div>
}
