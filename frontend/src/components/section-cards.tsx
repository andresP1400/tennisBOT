"use client"

import { useEffect, useState } from "react"
import { IconTrendingDown, IconTrendingUp } from "@tabler/icons-react"

import { Badge } from "@/components/ui/badge"
import {
  Card,
  CardAction,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"

interface Metrics {
  auc: number
  accuracy: number
  brier: number
  logloss: number
  totalMatches: number
  testMatches: number
}

function parseMetricsCsv(text: string): Partial<Metrics> {
  const lines = text.trim().split("\n").filter(Boolean)
  if (lines.length < 2) return {}
  const header = lines[0].split(",").map((h) => h.trim())
  const idxMetric = header.indexOf("metric")
  const idxTest = header.indexOf("test")
  if (idxMetric < 0 || idxTest < 0) return {}

  const out: Partial<Metrics> = {}
  for (const line of lines.slice(1)) {
    const cols = line.split(",")
    const key = cols[idxMetric]?.trim()
    const val = parseFloat(cols[idxTest])
    if (!key || !Number.isFinite(val)) continue
    if (key === "auc") out.auc = val
    else if (key === "accuracy") out.accuracy = val
    else if (key === "brier") out.brier = val
    else if (key === "logloss") out.logloss = val
    else if (key === "totalMatches") out.totalMatches = val
    else if (key === "testMatches") out.testMatches = val
  }
  return out
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
    fetch("/api/metrics?tour=atp", { signal: controller.signal, cache: "no-store" })
      .then((r) => r.text())
      .then((text) => {
        const parsed = parseMetricsCsv(text)
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

  return (
    <div className="*:data-[slot=card]:from-primary/5 *:data-[slot=card]:to-card dark:*:data-[slot=card]:bg-card grid grid-cols-1 gap-4 px-4 *:data-[slot=card]:bg-gradient-to-t *:data-[slot=card]:shadow-xs lg:px-6 @xl/main:grid-cols-2 @5xl/main:grid-cols-4">
      <Card className="@container/card">
        <CardHeader>
          <CardDescription>ROC-AUC {loaded ? "(test)" : ""}</CardDescription>
          <CardTitle className="text-2xl font-semibold tabular-nums @[250px]/card:text-3xl">
            {metrics.auc > 0 ? metrics.auc.toFixed(4) : "—"}
          </CardTitle>
          <CardAction>
            <Badge variant="outline" className={metrics.auc > 0.68 ? "text-emerald-400 border-emerald-400/30" : "text-amber-400 border-amber-400/30"}>
              {metrics.auc > 0.68 ? <IconTrendingUp /> : <IconTrendingDown />}
              {metrics.auc > 0.72 ? "Excellent" : metrics.auc > 0.68 ? "Good" : "—"}
            </Badge>
          </CardAction>
        </CardHeader>
        <CardFooter className="text-xs text-muted-foreground">
          From reports/atp/metrics_summary.csv
        </CardFooter>
      </Card>

      <Card className="@container/card">
        <CardHeader>
          <CardDescription>Accuracy {loaded ? "(test)" : ""}</CardDescription>
          <CardTitle className="text-2xl font-semibold tabular-nums @[250px]/card:text-3xl">
            {metrics.accuracy > 0 ? `${(metrics.accuracy * 100).toFixed(1)}%` : "—"}
          </CardTitle>
          <CardAction>
            <Badge variant="outline" className={metrics.accuracy > 0.65 ? "text-emerald-400 border-emerald-400/30" : "text-amber-400 border-amber-400/30"}>
              {metrics.accuracy > 0.65 ? <IconTrendingUp /> : <IconTrendingDown />}
              {metrics.accuracy > 0 ? `${(metrics.accuracy * 100).toFixed(1)}%` : "—"}
            </Badge>
          </CardAction>
        </CardHeader>
        <CardFooter className="text-xs text-muted-foreground">
          Pure-stats stacking model
        </CardFooter>
      </Card>

      <Card className="@container/card">
        <CardHeader>
          <CardDescription>Brier Score {loaded ? "(test)" : ""}</CardDescription>
          <CardTitle className="text-2xl font-semibold tabular-nums @[250px]/card:text-3xl">
            {metrics.brier > 0 ? metrics.brier.toFixed(4) : "—"}
          </CardTitle>
          <CardAction>
            <Badge variant="outline" className={metrics.brier > 0 && metrics.brier < 0.22 ? "text-emerald-400 border-emerald-400/30" : "text-amber-400 border-amber-400/30"}>
              {metrics.brier > 0 && metrics.brier < 0.22 ? <IconTrendingUp /> : <IconTrendingDown />}
              {metrics.brier > 0 && metrics.brier < 0.20 ? "Calibrated" : "—"}
            </Badge>
          </CardAction>
        </CardHeader>
        <CardFooter className="text-xs text-muted-foreground">
          Lower is better
        </CardFooter>
      </Card>

      <Card className="@container/card">
        <CardHeader>
          <CardDescription>Dataset size</CardDescription>
          <CardTitle className="text-2xl font-semibold tabular-nums @[250px]/card:text-3xl">
            {metrics.totalMatches > 0
              ? Math.round(metrics.totalMatches).toLocaleString()
              : "—"}
          </CardTitle>
          <CardAction>
            <Badge variant="outline">
              {metrics.testMatches > 0
                ? `${Math.round(metrics.testMatches).toLocaleString()} test`
                : "rows"}
            </Badge>
          </CardAction>
        </CardHeader>
        <CardFooter className="text-xs text-muted-foreground">
          Symmetric feature rows (train+val+test)
        </CardFooter>
      </Card>
    </div>
  )
}
