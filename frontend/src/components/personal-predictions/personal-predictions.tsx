"use client"

import { useState } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { usePersonalPredictions } from "@/hooks/usePersonalPredictions"
import { PersonalRows } from "./personal-rows"

export function PersonalPredictions() {
  const [tour, setTour] = useState<"atp" | "wta">("atp")
  const { card, error, loading, refresh } = usePersonalPredictions(tour)
  const measured = card?.backtest.test_2024_2025?.ml_calibrated
  const warning = card?.predictions.find(prediction => prediction.warning)?.warning
  const live = card?.live_performance
  const overall = card?.overall_live_performance
  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <CardTitle>Upcoming match predictions</CardTitle>
          <div className="flex items-center gap-3">
            <select aria-label="Prediction tour" value={tour} className="rounded border px-2 py-1 bg-background"
              onChange={event => setTour(event.target.value as "atp" | "wta")}>
              <option value="atp">ATP</option><option value="wta">WTA</option>
            </select>
            <Button onClick={refresh} disabled={loading}>{loading ? "Loading…" : "Refresh predictions"}</Button>
          </div>
        </div>
        <CardDescription>Real historical models. Every available forecast is recorded locally before the match starts.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {error && <p role="alert">{error}</p>}
        {warning && <p className="text-sm text-amber-500">{warning}</p>}
        {measured && <p className="text-sm text-muted-foreground">
          Historical test (2024–2025): {(measured.accuracy * 100).toFixed(2)}% accuracy across {measured.matches.toLocaleString()} matches.
          {" "}Brier {measured.brier.toFixed(4)}. This is held-out historical performance, not live accuracy.
        </p>}
        {live && <p className="text-sm text-muted-foreground">
          Live results for this model: {live.accuracy == null ? "accuracy not yet measured" : `${(live.accuracy * 100).toFixed(2)}% accuracy`}.
          {" "}{live.completed} completed, {live.pending} pending, {live.void} void.
        </p>}
        {overall && <p className="text-sm text-muted-foreground">
          All recorded model versions, first forecast per match: {overall.accuracy == null ? "accuracy not yet measured" : `${(overall.accuracy * 100).toFixed(2)}% accuracy`}
          {" "}across {overall.completed} completed matches. Small live samples are not reliable performance estimates.
        </p>}
        {card?.message && <p>{card.message}</p>}
        {card && <PersonalRows predictions={card.predictions} />}
        {!!card?.unavailable.length && <details className="text-sm text-muted-foreground">
          <summary>{card.unavailable.length} fixtures without a supported prediction</summary>
          <ul>{card.unavailable.map(item => <li key={item.fixture.id}>
            {item.fixture.player1} vs {item.fixture.player2}: {item.reason}
          </li>)}</ul>
        </details>}
      </CardContent>
    </Card>
  )
}
