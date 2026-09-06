"use client"

import { useEffect, useState } from "react"
import { IconTrendingDown, IconTrendingUp } from "@tabler/icons-react"
import type { ReactNode } from "react"

import { Badge } from "@/components/ui/badge"
import {
  Card,
  CardAction,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { getMetricsRows } from "@/services/analytics"

export interface Metrics {
  auc: number
  accuracy: number
  brier: number
  logloss: number
  totalMatches: number
  testMatches: number
}

interface MetricCardConfig {
  description: string
  value: string
  badge: ReactNode
  footer: string
}

function parseMetrics(rows: { metric: string; test: number }[]): Partial<Metrics> {
  const parsed: Partial<Metrics> = {}
  for (const r of rows) {
    if (r.metric === "auc") parsed.auc = r.test
    else if (r.metric === "accuracy") parsed.accuracy = r.test
    else if (r.metric === "brier") parsed.brier = r.test
    else if (r.metric === "logloss") parsed.logloss = r.test
    else if (r.metric === "totalMatches") parsed.totalMatches = r.test
    else if (r.metric === "testMatches") parsed.testMatches = r.test
  }
  return parsed
}

function trendBadge(
  good: boolean,
  label: string,
  positive: boolean,
): ReactNode {
  const cls = good
    ? "text-emerald-400 border-emerald-400/30"
    : "text-amber-400 border-amber-400/30"
  return (
    <Badge variant="outline" className={cls}>
      {positive ? <IconTrendingUp /> : <IconTrendingDown />}
      {label}
    </Badge>
  )
}

export function SectionCards() {
  const [metrics, setMetrics] = useState<Metrics>({
    auc: 0,
    accuracy: 0,
    brier: 0,
    logloss: 0,
    totalMatches: 0,
    testMatches: 0,
  })
  const [loaded, setLoaded] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    void getMetricsRows("atp", controller.signal)
      .then((rows) => {
        const parsed = parseMetrics(rows)
        if (parsed.auc != null || parsed.accuracy != null) {
          setMetrics((prev) => ({ ...prev, ...parsed }))
          setLoaded(true)
        }
      })
      .catch(() => {
        /* keep defaults / zeros */
      })
    return () => controller.abort()
  }, [])

  const { auc, accuracy, brier, totalMatches, testMatches } = metrics
  const cards: MetricCardConfig[] = [
    {
      description: `ROC-AUC ${loaded ? "(test)" : ""}`,
      value: auc > 0 ? auc.toFixed(4) : "—",
      badge: trendBadge(
        auc > 0.68,
        auc > 0.72 ? "Excellent" : auc > 0.68 ? "Good" : "—",
        auc > 0.68,
      ),
      footer: "From reports/atp/metrics_summary.csv",
    },
    {
      description: `Accuracy ${loaded ? "(test)" : ""}`,
      value: accuracy > 0 ? `${(accuracy * 100).toFixed(1)}%` : "—",
      badge: trendBadge(
        accuracy > 0.65,
        accuracy > 0 ? `${(accuracy * 100).toFixed(1)}%` : "—",
        accuracy > 0.65,
      ),
      footer: "Pure-stats stacking model",
    },
    {
      description: `Brier Score ${loaded ? "(test)" : ""}`,
      value: brier > 0 ? brier.toFixed(4) : "—",
      badge: trendBadge(
        brier > 0 && brier < 0.22,
        brier > 0 && brier < 0.2 ? "Calibrated" : "—",
        brier > 0 && brier < 0.22,
      ),
      footer: "Lower is better",
    },
    {
      description: "Dataset size",
      value:
        totalMatches > 0 ? Math.round(totalMatches).toLocaleString() : "—",
      badge: (
        <Badge variant="outline">
          {testMatches > 0
            ? `${Math.round(testMatches).toLocaleString()} test`
            : "rows"}
        </Badge>
      ),
      footer: "Symmetric feature rows (train+val+test)",
    },
  ]

  return (
    <div className="*:data-[slot=card]:from-primary/5 *:data-[slot=card]:to-card dark:*:data-[slot=card]:bg-card grid grid-cols-1 gap-4 px-4 *:data-[slot=card]:bg-gradient-to-t *:data-[slot=card]:shadow-xs lg:px-6 @xl/main:grid-cols-2 @5xl/main:grid-cols-4">
      {cards.map((card) => (
        <Card key={card.description} className="@container/card">
          <CardHeader>
            <CardDescription>{card.description}</CardDescription>
            <CardTitle className="text-2xl font-semibold tabular-nums @[250px]/card:text-3xl">
              {card.value}
            </CardTitle>
            <CardAction>{card.badge}</CardAction>
          </CardHeader>
          <CardFooter className="text-xs text-muted-foreground">
            {card.footer}
          </CardFooter>
        </Card>
      ))}
    </div>
  )
}