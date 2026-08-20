import { Badge } from "@/components/ui/badge"
import { MatchNewsButton } from "@/components/match-news-button"
import type { CardPrediction } from "./types"

export function reliabilityClass(level: string): string {
  if (level === "alta") return "text-emerald-500 border-emerald-500/40"
  if (level === "media") return "text-amber-500 border-amber-500/40"
  return "text-muted-foreground"
}

export function PredictionTable({ predictions }: { predictions: CardPrediction[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b text-left text-xs text-muted-foreground uppercase">
            <th className="py-2 pr-3">Time</th>
            <th className="py-2 pr-3">Matchup</th>
            <th className="py-2 pr-3">Context</th>
            <th className="py-2 pr-3">Tournament</th>
            <th className="py-2 pr-3 text-right">Model</th>
            <th className="py-2 pr-3 text-right">Odds</th>
            <th className="py-2 pr-3 text-right">Edge</th>
            <th className="py-2 pr-3">Reliability</th>
            <th className="py-2 pr-3">Weather</th>
            <th className="py-2">Value bet</th>
          </tr>
        </thead>
        <tbody>
          {predictions.map((p, idx) => {
            const fav = p.prob1 >= 0.5
            return (
              <tr key={`${p.match}-${idx}`} className="border-b border-neutral-800/60">
                <td className="py-2 pr-3 whitespace-nowrap font-mono text-xs text-muted-foreground">
                  {p.commence_time ? p.commence_time.slice(11, 16) : "—"}
                </td>
                <td className="py-2 pr-3 whitespace-nowrap">
                  <div>
                    <span className={fav ? "font-semibold" : ""}>{p.player1}</span>
                    <span className="mx-2 text-muted-foreground text-xs">vs</span>
                    <span className={!fav ? "font-semibold" : ""}>{p.player2}</span>
                    {p.error && (
                      <span className="ml-2 text-xs text-red-400">({p.error})</span>
                    )}
                  </div>
                  <div className="mt-1">
                    <MatchNewsButton
                      player1={p.player1}
                      player2={p.player2}
                      surface={p.surface}
                    />
                  </div>
                </td>
                <td className="py-2 pr-3 text-xs">
                  {p.context ? (
                    <div className="flex flex-col gap-0.5">
                      <div className="flex items-center gap-1">
                        <span className="text-muted-foreground">rank</span>
                        <span>
                          {p.context.p1_rank ?? "—"} / {p.context.p2_rank ?? "—"}
                        </span>
                      </div>
                      <div className="flex items-center gap-1">
                        <span className="text-muted-foreground">form</span>
                        <span className="font-mono">
                          {p.context.p1_form ?? "—"} vs {p.context.p2_form ?? "—"}
                        </span>
                      </div>
                      {(p.context.p1_ret || p.context.p2_ret) && (
                        <Badge className="text-red-400 border-red-400/40 bg-red-500/10 w-fit">
                          RET in recent matches
                        </Badge>
                      )}
                    </div>
                  ) : (
                    <span className="text-muted-foreground">—</span>
                  )}
                </td>
                <td className="py-2 pr-3 text-xs text-muted-foreground">
                  {p.tournament}
                  {p.surface ? ` · ${p.surface}` : ""}
                </td>
                <td className="py-2 pr-3 text-right whitespace-nowrap">
                  <div className="text-xs">
                    <span className={fav ? "font-semibold" : ""}>
                      {(p.prob1 * 100).toFixed(1)}%
                    </span>
                    <span className="text-muted-foreground"> / </span>
                    <span>{(p.prob2 * 100).toFixed(1)}%</span>
                  </div>
                  <div className="text-[10px] text-muted-foreground">
                    winner: <span className="font-medium">{p.winner}</span>
                  </div>
                </td>
                <td className="py-2 pr-3 text-right whitespace-nowrap font-mono text-xs">
                  {p.odds1 ? p.odds1.toFixed(2) : "—"}
                  <span className="text-muted-foreground"> / </span>
                  {p.odds2 ? p.odds2.toFixed(2) : "—"}
                </td>
                <td className="py-2 pr-3 text-right whitespace-nowrap font-mono text-xs">
                  <span
                    className={
                      p.edge1 != null && p.edge1 > 0
                        ? "text-emerald-500"
                        : "text-muted-foreground"
                    }
                  >
                    {p.edge1 != null ? `${(p.edge1 * 100).toFixed(1)}%` : "—"}
                  </span>
                  <span className="text-muted-foreground"> / </span>
                  <span
                    className={
                      p.edge2 != null && p.edge2 > 0
                        ? "text-emerald-500"
                        : "text-muted-foreground"
                    }
                  >
                    {p.edge2 != null ? `${(p.edge2 * 100).toFixed(1)}%` : "—"}
                  </span>
                </td>
                <td className="py-2 pr-3">
                  <Badge variant="outline" className={reliabilityClass(p.reliability)}>
                    {p.reliability}
                  </Badge>
                </td>
                <td className="py-2 pr-3 whitespace-nowrap text-xs">
                  {p.weather ? (
                    <>
                      {p.weather.temperature_c != null && (
                        <span>{Math.round(p.weather.temperature_c)}°C</span>
                      )}
                      {p.weather.rain_probability != null &&
                        p.weather.rain_probability > 0.05 && (
                          <span className="text-sky-500">
                            {" "}
                            · rain {Math.round(p.weather.rain_probability * 100)}%
                          </span>
                        )}
                      {p.weather.wind_speed_kmh != null &&
                        p.weather.wind_speed_kmh > 20 && (
                          <span className="text-amber-500">
                            {" "}
                            · wind {Math.round(p.weather.wind_speed_kmh)} km/h
                          </span>
                        )}
                    </>
                  ) : (
                    <span className="text-muted-foreground">—</span>
                  )}
                </td>
                <td className="py-2">
                  {p.value_bet ? (
                    <Badge className="bg-emerald-500/15 text-emerald-500 border border-emerald-500/40">
                      {p.value_bet.player} @ {p.value_bet.odds.toFixed(2)} ·{" "}
                      {(p.value_bet.edge * 100).toFixed(1)}%
                    </Badge>
                  ) : (
                    <span className="text-xs text-muted-foreground">—</span>
                  )}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}