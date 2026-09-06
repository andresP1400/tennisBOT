"use client"

import { useState } from "react"
import { AutoDailyCard } from "@/components/auto-daily-card"
import { computeValueBets } from "@/services/odds"
import { researchPlayerNews } from "@/services/news"
import { useTodaysMatches } from "@/hooks/useTodaysMatches"
import { NewsSection } from "./_components/news-section"
import { TodaysMatchesSection } from "./_components/todays-matches-section"
import { ValueBetsSection } from "./_components/value-bets-section"
import type {
  NewsResponse,
  ValueResponse,
} from "@/types/api"

export default function LivePage() {
  const [tour, setTour] = useState<"atp" | "wta">("atp")
  const { matches, needsKey, error } = useTodaysMatches(tour)

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

  const runValueBet = async () => {
    setValueLoading(true)
    setValueError(null)
    try {
      const data = await computeValueBets({
        player1,
        player2,
        surface,
        minEdge,
        model: "atp_stacking_model.pkl",
      })
      if (data.error) {
        setValueError(data.error)
        setValueResult(null)
      } else {
        setValueResult(data)
      }
    } catch (err) {
      setValueError(err instanceof Error ? err.message : "Failed to compute value bet")
      setValueResult(null)
    } finally {
      setValueLoading(false)
    }
  }

  const runNews = async () => {
    setNewsLoading(true)
    setNewsError(null)
    try {
      const data = await researchPlayerNews({ player1, player2, surface })
      if (data.error) {
        setNewsError(data.error)
        setNews(null)
      } else {
        setNews(data)
      }
    } catch (err) {
      setNewsError(err instanceof Error ? err.message : "Failed to research players")
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