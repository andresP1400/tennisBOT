"use client"

import { useCallback, useEffect, useState } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { ApiError, apiFetch } from "@/lib/api"
import { MatchNewsButton } from "@/components/match-news-button"

interface CardPrediction {
  match: string
  player1: string
  player2: string
  tournament: string
  surface: string
  commence_time: string
  prob1: number
  prob2: number
  winner: string
  reliability: string
  odds1: number | null
  odds2: number | null
  edge1: number | null
  edge2: number | null
  value_bet: { player: string; odds: number; edge: number } | null
  weather?: {
    temperature_c?: number | null
    humidity_pct?: number | null
    rain_probability?: number | null
    wind_speed_kmh?: number | null
  }
  context?: {
    p1_rank?: number | null
    p2_rank?: number | null
    p1_form?: string | null
    p2_form?: string | null
    p1_ret?: boolean | null
    p2_ret?: boolean | null
    p1_age?: number | null
    p2_age?: number | null
    p1_last_match_date?: string | null
    p2_last_match_date?: string | null
  }
  error?: string
}

interface CardResponse {
  tour: string
  count: number
  n_value_bets: number
  n_logged: number
  model_used: string | null
  min_edge: number
  predictions: CardPrediction[]
  message?: string
  error?: string
}

function reliabilityClass(level: string): string {
  if (level === "alta") return "text-emerald-500 border-emerald-500/40"
  if (level === "media") return "text-amber-500 border-amber-500/40"
  return "text-muted-foreground"
}

export function AutoDailyCard() {
  const [tour, setTour] = useState<"atp" | "wta">("atp")
  const [card, setCard] = useState<CardResponse | null>(null)
  const [cardLoading, setCardLoading] = useState(false)
  const [cardError, setCardError] = useState<string | null>(null)

  const runCard = useCallback(async (t: "atp" | "wta") => {
    setCardLoading(true)
    setCardError(null)
    try {
      const data = await apiFetch<CardResponse>(
        `/api/predict-card?tour=${t}&min_edge=0.05&log=true`,
      )
      if (data.error) {
        setCardError(data.error)
        setCard(null)
      } else {
        setCard(data)
      }
    } catch (err) {
      setCardError(err instanceof ApiError ? err.message : "Failed to generate card")
      setCard(null)
    } finally {
      setCardLoading(false)
    }
  }, [])

  useEffect(() => {
    runCard(tour)
  }, [tour, runCard])

  const handleTourChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setTour(e.target.value as "atp" | "wta")
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-start justify-between gap-4 space-y-0">
        <div>
          <CardTitle>Automatic Daily Card</CardTitle>
          <CardDescription>
            Generated automatically on page open: model prediction for EVERY{" "}
            {tour.toUpperCase()} match of the day (all tournaments in the live feed) with
            odds, edge vs market, value-bet flags, player context (rank, recent form,
            retirement marks — from local data) and weather (open-meteo). The "News"
            button researches injuries/form/coach for that match on demand. Predictions
            are logged to the Track Record automatically. Source:{" "}
            <span className="font-mono">/api/predict-card?tour={tour}</span>.
          </CardDescription>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={tour}
            onChange={handleTourChange}
            className="h-9 rounded-md border border-input bg-background px-3 text-sm"
          >
            <option value="atp">ATP</option>
            <option value="wta">WTA</option>
          </select>
          <Button onClick={() => runCard(tour)} disabled={cardLoading}>
            {cardLoading ? "Generating..." : "Refresh"}
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {cardError && <p className="text-sm text-red-400 mb-3">{cardError}</p>}
        {!card && !cardError && !cardLoading && (
          <p className="text-sm text-muted-foreground">
            Generating the card for all {tour.toUpperCase()} matches of the day...
          </p>
        )}
        {cardLoading && !card && (
          <p className="text-sm text-muted-foreground">
            Generating {tour.toUpperCase()} card... (model inference + odds + weather, a
            few seconds)
          </p>
        )}
        {card?.message && !card.predictions?.length && (
          <p className="text-sm text-amber-500 dark:text-amber-400">{card.message}</p>
        )}
        {card && card.predictions.length > 0 && (
          <div className="space-y-3">
            <div className="flex flex-wrap gap-2 text-xs">
              <Badge variant="outline">{card.count} matches</Badge>
              <Badge
                variant={card.n_value_bets > 0 ? "default" : "outline"}
                className={
                  card.n_value_bets > 0
                    ? "bg-emerald-500/15 text-emerald-500 border-emerald-500/40"
                    : ""
                }
              >
                {card.n_value_bets} value bets (edge ≥ {(card.min_edge * 100).toFixed(0)}%)
              </Badge>
              <Badge variant="outline">{card.n_logged ?? 0} logged to Track</Badge>
              <Badge variant="outline" className="font-mono">
                {card.model_used}
              </Badge>
            </div>
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
                  {card.predictions.map((p, idx) => {
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
          </div>
        )}
      </CardContent>
    </Card>
  )
}