"use client"

import { useCallback, useEffect, useState } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { ApiError } from "@/lib/api"
import { getPredictCard } from "@/services/predict"
import type { CardResponse } from "./types"
import { PredictionTable } from "./predictions-table"

export function AutoDailyCard() {
  const [tour, setTour] = useState<"atp" | "wta">("atp")
  const [card, setCard] = useState<CardResponse | null>(null)
  const [cardLoading, setCardLoading] = useState(false)
  const [cardError, setCardError] = useState<string | null>(null)

  const runCard = useCallback(async (t: "atp" | "wta") => {
    setCardLoading(true)
    setCardError(null)
    try {
      const data = await getPredictCard(t)
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
            retirement marks — from local data) and weather (open-meteo). The &quot;News&quot;
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
                variant={(card.n_value_bets ?? 0) > 0 ? "default" : "outline"}
                className={
                  (card.n_value_bets ?? 0) > 0
                    ? "bg-emerald-500/15 text-emerald-500 border-emerald-500/40"
                    : ""
                }
              >
                {card.n_value_bets ?? 0} value bets (edge ≥ {((card.min_edge ?? 0.05) * 100).toFixed(0)}%)
              </Badge>
              <Badge variant="outline">{card.n_logged ?? 0} logged to Track</Badge>
              <Badge variant="outline" className="font-mono">
                {card.model_used}
              </Badge>
            </div>
            <PredictionTable predictions={card.predictions} />
          </div>
        )}
      </CardContent>
    </Card>
  )
}