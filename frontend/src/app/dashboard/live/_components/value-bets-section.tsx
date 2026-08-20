"use client"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import type { ValueResponse } from "./live-page.types"
import { fmtPct } from "./live-page.types"

export function ValueBetsSection({
  player1,
  setPlayer1,
  player2,
  setPlayer2,
  surface,
  setSurface,
  minEdge,
  setMinEdge,
  result,
  error,
  loading,
  onRun,
}: {
  player1: string
  setPlayer1: (v: string) => void
  player2: string
  setPlayer2: (v: string) => void
  surface: string
  setSurface: (v: string) => void
  minEdge: number
  setMinEdge: (v: number) => void
  result: ValueResponse | null
  error: string | null
  loading: boolean
  onRun: () => void
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Value Bet Detection</CardTitle>
        <CardDescription>
          Compares model probability to market implied odds.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <Input value={player1} onChange={(e) => setPlayer1(e.target.value)} placeholder="Player 1" />
          <Input value={player2} onChange={(e) => setPlayer2(e.target.value)} placeholder="Player 2" />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <select
            value={surface}
            onChange={(e) => setSurface(e.target.value)}
            className="h-10 rounded-md border border-input bg-background px-3 text-sm"
          >
            <option value="Hard">Hard</option>
            <option value="Clay">Clay</option>
            <option value="Grass">Grass</option>
          </select>
          <Input
            type="number"
            step={0.01}
            min={0}
            max={1}
            value={minEdge}
            onChange={(e) => setMinEdge(parseFloat(e.target.value || "0"))}
          />
        </div>
        <Button onClick={onRun} disabled={loading} className="w-full">
          {loading ? "Computing..." : "Run value bet check"}
        </Button>
        {error && <p className="text-sm text-red-400">{error}</p>}
        {result && (
          <div className="space-y-2">
            <p className="text-xs text-muted-foreground">
              Modello {player1}: {fmtPct(result.model_prob1)} · Mercato:{" "}
              {fmtPct(result.market_prob1)} · Edge: {fmtPct(result.edge1)}
            </p>
            {result.message && (
              <p className="text-sm text-amber-500 dark:text-amber-400">
                {result.message}
                {result.needs_odds_key ? (
                  <>
                    {" "}
                    File: <code className="font-mono text-xs">.env</code> →{" "}
                    <code className="font-mono text-xs">ODDS_API_KEY=...</code>
                  </>
                ) : null}
              </p>
            )}
            {!result.message && result.value_bets.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                Nessuna value bet sopra edge {(result.min_edge ?? minEdge) * 100}%.
              </p>
            ) : null}
            {result.value_bets.length > 0 && (
              <ul className="text-sm space-y-1">
                {result.value_bets.map((vb, i) => (
                  <li
                    key={i}
                    className="flex items-center justify-between rounded-md border border-emerald-500/40 bg-emerald-500/10 px-3 py-2"
                  >
                    <span className="font-medium">{vb.side}</span>
                    <span className="font-mono text-xs">
                      odds {vb.best_odds.toFixed(2)} - edge {(vb.edge * 100).toFixed(1)}%
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}