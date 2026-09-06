"use client"

import { useState, type ReactNode } from "react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { researchPlayerNews } from "@/services/news"
import type { NewsResponse } from "@/types/api"

function diffBadge(
  label: string,
  diff: number | undefined,
  pos: string,
  neg: string,
): ReactNode | null {
  if (diff == null || diff === 0) return null
  const cls = diff > 0 ? pos : neg
  return (
    <Badge variant="outline" className={cls}>
      {label} {diff > 0 ? "+1" : "-1"}
    </Badge>
  )
}

export function MatchNewsButton({
  player1,
  player2,
  surface,
}: {
  player1: string
  player2: string
  surface?: string
}) {
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [news, setNews] = useState<NewsResponse | null>(null)

  const run = async () => {
    if (open && news) {
      setOpen(false)
      return
    }
    setLoading(true)
    setError(null)
    try {
      const data = await researchPlayerNews({ player1, player2, surface })
      if (data.error) {
        setError(data.error)
        setNews(null)
      } else {
        setNews(data)
      }
      setOpen(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Research failed")
      setNews(null)
      setOpen(true)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col gap-1">
      <Button
        variant="outline"
        size="sm"
        onClick={run}
        disabled={loading}
        className="h-6 px-2 text-[11px]"
        title={`Research news for ${player1} vs ${player2}`}
      >
        {loading ? "..." : open && news ? "Hide" : "News"}
      </Button>
      {open && error && <p className="text-[10px] text-red-400 max-w-[220px]">{error}</p>}
      {open && news && (
        <div className="flex flex-col gap-1 max-w-[240px]">
          <div className="flex flex-wrap gap-1">
            {diffBadge(
              "injury",
              news.injury_flag_diff,
              "text-red-400 border-red-400/40",
              "text-emerald-500 border-emerald-500/40",
            )}
            {diffBadge(
              "form",
              news.form_sentiment_diff,
              "text-emerald-500 border-emerald-500/40",
              "text-red-400 border-red-400/40",
            )}
            {diffBadge(
              "coach",
              news.coach_change_diff,
              "text-amber-500 border-amber-500/40",
              "text-amber-500 border-amber-500/40",
            )}
          </div>
          {(news.p1_injury_detail || news.p2_injury_detail) && (
            <p className="text-[10px] text-muted-foreground leading-tight">
              {news.p1_injury_detail && <span>{player1}: {news.p1_injury_detail}</span>}
              {news.p1_injury_detail && news.p2_injury_detail && <span> · </span>}
              {news.p2_injury_detail && <span>{player2}: {news.p2_injury_detail}</span>}
            </p>
          )}
          {(news.p1_form_detail || news.p2_form_detail) && (
            <p className="text-[10px] text-muted-foreground leading-tight">
              Form: {news.p1_form_detail || "—"} vs {news.p2_form_detail || "—"}
            </p>
          )}
          {!news.injury_flag_diff && !news.form_sentiment_diff && !news.coach_change_diff && (
            <p className="text-[10px] text-muted-foreground">
              No significant news found.
            </p>
          )}
        </div>
      )}
    </div>
  )
}