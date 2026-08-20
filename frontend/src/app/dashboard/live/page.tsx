"use client"

import { useEffect, useState } from "react"
import { AutoDailyCard } from "@/components/auto-daily-card"
import { ApiError, apiFetch } from "@/lib/api"
import { NewsSection } from "./_components/news-section"
import { TodaysMatchesSection } from "./_components/todays-matches-section"
import { ValueBetsSection } from "./_components/value-bets-section"
import type {
  NewsResponse,
  TodaysMatch,
  TodaysResponse,
  ValueResponse,
} from "./_components/live-page.types"

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

        <TodaysMatchesSection
          matches={matches}
          error={error}
          needsKey={needsKey}
          tour={tour}
        />

        <AutoDailyCard />

        <div className="grid gap-4 lg:grid-cols-2">
          <ValueBetsSection
            player1={player1}
            setPlayer1={setPlayer1}
            player2={player2}
            setPlayer2={setPlayer2}
            surface={surface}
            setSurface={setSurface}
            minEdge={minEdge}
            setMinEdge={setMinEdge}
            result={valueResult}
            error={valueError}
            loading={valueLoading}
            onRun={runValueBet}
          />

          <NewsSection
            player1={player1}
            setPlayer1={setPlayer1}
            player2={player2}
            setPlayer2={setPlayer2}
            news={news}
            loading={newsLoading}
            error={newsError}
            onRun={runNews}
          />
        </div>
      </div>
    </div>
  )
}