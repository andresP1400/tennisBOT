"use client"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import type { NewsResponse } from "./live-page.types"

export function NewsSection({
  player1,
  setPlayer1,
  player2,
  setPlayer2,
  news,
  loading,
  error,
  onRun,
}: {
  player1: string
  setPlayer1: (v: string) => void
  player2: string
  setPlayer2: (v: string) => void
  news: NewsResponse | null
  loading: boolean
  error: string | null
  onRun: () => void
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Player News Research</CardTitle>
        <CardDescription>
          In-context research on injuries, form, and coach changes.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <Input value={player1} onChange={(e) => setPlayer1(e.target.value)} />
          <Input value={player2} onChange={(e) => setPlayer2(e.target.value)} />
        </div>
        <Button onClick={onRun} disabled={loading} className="w-full">
          {loading ? "Researching..." : "Research matchup"}
        </Button>
        {error && <p className="text-sm text-red-400">{error}</p>}
        {news && (
          <div className="text-xs space-y-1">
            <div>
              <span className="text-muted-foreground">Injury diff:</span>{" "}
              <span className="font-mono">{news.injury_flag_diff}</span>{" "}
              <span className="text-muted-foreground">
                ({news.p1_injury_detail || "no detail"} / {news.p2_injury_detail || "no detail"})
              </span>
            </div>
            <div>
              <span className="text-muted-foreground">Form diff:</span>{" "}
              <span className="font-mono">{news.form_sentiment_diff}</span>{" "}
              <span className="text-muted-foreground">
                ({news.p1_form_detail || "-"} / {news.p2_form_detail || "-"})
              </span>
            </div>
            <div>
              <span className="text-muted-foreground">Coach change diff:</span>{" "}
              <span className="font-mono">{news.coach_change_diff}</span>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}