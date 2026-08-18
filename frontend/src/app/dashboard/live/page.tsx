"use client"

import { useEffect, useState } from "react"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { ApiError, apiFetch } from "@/lib/api"
import { AutoDailyCard } from "@/components/auto-daily-card"

interface TodaysMatch {
  player1: string
  player2: string
  tournament: string
  surface: string
  commence_time: string
  best_odds: { player1: number; player2: number }
  implied_prob1: number
  implied_prob2: number
  margin: number
  num_bookmakers: number
}

interface TodaysResponse {
  tour: string
  count: number
  matches: TodaysMatch[]
  error?: string
}

interface ValueBet {
  side: string
  model_prob: number
  market_prob: number
  edge: number
  best_odds: number
  bookmaker_count: number
}

interface ValueResponse {
  player1: string
  player2: string
  model_prob1: number
  market_prob1?: number | null
  market_prob2?: number | null
  edge1?: number | null
  edge2?: number | null
  best_odds: { player1: number | null; player2: number | null }
  value_bets: ValueBet[]
  min_edge?: number
  needs_odds_key?: boolean
  message?: string
  error?: string
}

function fmtPct(v: number | null | undefined, digits = 1): string {
  if (v == null || Number.isNaN(v)) return "—"
  return `${(v * 100).toFixed(digits)}%`
}

interface NewsResponse {
  injury_flag_diff: number
  injury_severity_diff: number
  form_sentiment_diff: number
  coach_change_diff: number
  p1_injury_detail: string
  p2_injury_detail: string
  p1_form_detail: string
  p2_form_detail: string
}

export default function LivePage() {
  const [tour, setTour] = useState<"atp" | "wta">("atp")
  const [matches, setMatches] = useState<TodaysMatch[]>([])
  const [needsKey, setNeedsKey] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // value-bets UI
  const [player1, setPlayer1] = useState("Jannik Sinner")
  const [player2, setPlayer2] = useState("Carlos Alcaraz")
  const [surface, setSurface] = useState("Hard")
  const [minEdge, setMinEdge] = useState(0.05)
  const [valueResult, setValueResult] = useState<ValueResponse | null>(null)
  const [valueError, setValueError] = useState<string | null>(null)
  const [valueLoading, setValueLoading] = useState(false)

  // news UI
  const [news, setNews] = useState<NewsResponse | null>(null)
  const [newsLoading, setNewsLoading] = useState(false)
  const [newsError, setNewsError] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    const load = async () => {
      setError(null)
      try {
        // Check odds API key first for clearer UX
        try {
          const st = await apiFetch<{ configured?: boolean; message?: string }>(
            "/api/odds-api-status",
            { signal: controller.signal },
          )
          setNeedsKey(st.configured === false)
        } catch {
          /* ignore */
        }

        const data = await apiFetch<TodaysResponse>(
          `/api/todays-matches?tour=${tour}`,
          { signal: controller.signal },
        )
        setMatches(data.matches ?? [])
        if (data.error) {
          setError(data.error)
          if (/ODDS_API_KEY|not set|not configured/i.test(data.error)) setNeedsKey(true)
        } else {
          setError(null)
        }
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") return
        setError(err instanceof ApiError ? err.message : "Failed to load matches")
        setMatches([])
      }
    }
    void load()
    return () => controller.abort()
  }, [tour])

  const runValueBet = async () => {
    setValueLoading(true)
    setValueError(null)
    try {
      const data = await apiFetch<ValueResponse & { error?: string }>("/api/value-bets", {
        method: "POST",
        body: {
          player1,
          player2,
          surface,
          min_edge: minEdge,
          model: "atp_stacking_model.pkl",
        },
      })
      if (data.error) {
        setValueError(data.error)
        setValueResult(null)
      } else {
        setValueResult(data)
      }
    } catch (err) {
      setValueError(err instanceof ApiError ? err.message : "Failed to compute value bet")
      setValueResult(null)
    } finally {
      setValueLoading(false)
    }
  }

  const runNews = async () => {
    setNewsLoading(true)
    setNewsError(null)
    try {
      const data = await apiFetch<NewsResponse & { error?: string }>("/api/player-news", {
        method: "POST",
        body: { player1, player2, surface },
      })
      if ((data as { error?: string }).error) {
        setNewsError((data as { error?: string }).error ?? "Research failed")
        setNews(null)
      } else {
        setNews(data)
      }
    } catch (err) {
      setNewsError(err instanceof ApiError ? err.message : "Failed to research players")
      setNews(null)
    } finally {
      setNewsLoading(false)
    }
  }

  return (
    <div className="@container/main flex flex-1 flex-col gap-2">
      <div className="flex flex-col gap-4 py-4 md:gap-6 md:py-6 px-4 lg:px-6">
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div>
            <h2 className="text-3xl font-bold tracking-tight">Live Market &amp; Value Bets</h2>
            <p className="text-muted-foreground">
              Today&apos;s matches from <span className="font-mono">TheOddsAPI</span>,
              plus value bet detection vs model.
            </p>
          </div>
          <select
            value={tour}
            onChange={(e) => setTour(e.target.value as "atp" | "wta")}
            className="h-9 rounded-md border border-input bg-background px-3 text-sm"
          >
            <option value="atp">ATP</option>
            <option value="wta">WTA</option>
          </select>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Today&apos;s matches</CardTitle>
            <CardDescription>
              Source: <span className="font-mono">/api/todays-matches?tour={tour}</span>.
              Requires <span className="font-mono">ODDS_API_KEY</span>.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {error && (
              <p className="text-sm text-red-400 mb-3">
                {needsKey
                  ? "ODDS_API_KEY not configured on the backend. Add it to local.env."
                  : `Backend error: ${error}`}
              </p>
            )}
            {matches.length === 0 && !error ? (
              <p className="text-sm text-muted-foreground">
                No matches returned for today.
              </p>
            ) : (
              <div className="grid gap-3">
                {matches.map((m, idx) => (
                  <div
                    key={`${m.player1}-${m.player2}-${idx}`}
                    className="rounded-md border border-neutral-800 bg-muted/20 p-3 flex flex-wrap items-center gap-3"
                  >
                    <div className="flex-1 min-w-0">
                      <div className="font-medium">
                        {m.player1}{" "}
                        <span className="text-muted-foreground text-xs">vs</span>{" "}
                        {m.player2}
                      </div>
                      <div className="text-xs text-muted-foreground">
                        {m.tournament}
                        {m.surface ? ` - ${m.surface}` : ""}
                        {m.commence_time ? ` - ${m.commence_time.slice(0, 16)}` : ""}
                      </div>
                    </div>
                    <div className="flex flex-col items-end text-xs">
                      <div>
                        {m.player1}: <span className="font-mono">
                          {(m.best_odds.player1 || 0).toFixed(2)}
                        </span>{" "}
                        <span className="text-muted-foreground">
                          ({m.implied_prob1 ? `${(m.implied_prob1 * 100).toFixed(1)}%` : "-"})
                        </span>
                      </div>
                      <div>
                        {m.player2}: <span className="font-mono">
                          {(m.best_odds.player2 || 0).toFixed(2)}
                        </span>{" "}
                        <span className="text-muted-foreground">
                          ({m.implied_prob2 ? `${(m.implied_prob2 * 100).toFixed(1)}%` : "-"})
                        </span>
                      </div>
                      <Badge variant="outline" className="mt-1 text-[10px]">
                        {m.num_bookmakers} books - margin {((m.margin || 0) * 100).toFixed(1)}%
                      </Badge>
                    </div>
                  </div>
                ))}
              </div>
            )}
            <p className="text-xs text-muted-foreground mt-3">
              {needsKey
                ? "Serve ODDS_API_KEY nel .env (the-odds-api.com, free tier 500 req/mese)."
                : "Quote live da TheOddsAPI quando la chiave è configurata."}
            </p>
          </CardContent>
        </Card>

        <AutoDailyCard />

        <div className="grid gap-4 lg:grid-cols-2">
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
              <Button onClick={runValueBet} disabled={valueLoading} className="w-full">
                {valueLoading ? "Computing..." : "Run value bet check"}
              </Button>
              {valueError && <p className="text-sm text-red-400">{valueError}</p>}
              {valueResult && (
                <div className="space-y-2">
                  <p className="text-xs text-muted-foreground">
                    Modello {player1}: {fmtPct(valueResult.model_prob1)} · Mercato:{" "}
                    {fmtPct(valueResult.market_prob1)} · Edge: {fmtPct(valueResult.edge1)}
                  </p>
                  {valueResult.message && (
                    <p className="text-sm text-amber-500 dark:text-amber-400">
                      {valueResult.message}
                      {valueResult.needs_odds_key ? (
                        <>
                          {" "}
                          File: <code className="font-mono text-xs">.env</code> →{" "}
                          <code className="font-mono text-xs">ODDS_API_KEY=...</code>
                        </>
                      ) : null}
                    </p>
                  )}
                  {!valueResult.message && valueResult.value_bets.length === 0 ? (
                    <p className="text-sm text-muted-foreground">
                      Nessuna value bet sopra edge {(valueResult.min_edge ?? minEdge) * 100}%.
                    </p>
                  ) : null}
                  {valueResult.value_bets.length > 0 && (
                    <ul className="text-sm space-y-1">
                      {valueResult.value_bets.map((vb, i) => (
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
              <Button onClick={runNews} disabled={newsLoading} className="w-full">
                {newsLoading ? "Researching..." : "Research matchup"}
              </Button>
              {newsError && <p className="text-sm text-red-400">{newsError}</p>}
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
        </div>
      </div>
    </div>
  )
}
