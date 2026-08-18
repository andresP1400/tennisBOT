"use client"

import { useMemo, useState } from "react"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import {
  FEATURE_GROUPS,
  TRAINING_FEATURE_COUNT,
  INFERENCE_ONLY_FEATURE_COUNT,
} from "@/lib/features"

type ColorVariant = "emerald" | "amber" | "sky" | "purple" | "rose" | "default"

const GROUP_COLOR: Record<string, ColorVariant> = {
  Context: "sky",
  "Player Diff": "purple",
  "Rolling Stats": "emerald",
  Fatigue: "amber",
  "Head-to-Head": "default",
  "Strength of Schedule": "default",
  Odds: "default",
  Weather: "sky",
  "Player News": "rose",
  "Live Odds": "amber",
}

const COLOR_CLASS: Record<ColorVariant, string> = {
  emerald: "border-emerald-500/40 text-emerald-400 bg-emerald-500/10",
  amber: "border-amber-500/40 text-amber-400 bg-amber-500/10",
  sky: "border-sky-500/40 text-sky-400 bg-sky-500/10",
  purple: "border-purple-500/40 text-purple-400 bg-purple-500/10",
  rose: "border-rose-500/40 text-rose-400 bg-rose-500/10",
  default: "border-zinc-700 text-zinc-300 bg-zinc-800/60",
}

export default function FeaturesPage() {
  const [query, setQuery] = useState("")

  const groups = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return FEATURE_GROUPS
    return FEATURE_GROUPS
      .map((g) => ({
        ...g,
        features: g.features.filter((f) => f.toLowerCase().includes(q)),
      }))
      .filter((g) => g.features.length > 0)
  }, [query])

  return (
    <div className="@container/main flex flex-1 flex-col gap-2">
      <div className="flex flex-col gap-4 py-4 md:gap-6 md:py-6 px-4 lg:px-6">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h2 className="text-3xl font-bold tracking-tight">Feature Engineering</h2>
            <p className="text-muted-foreground">
              Features fed into the Stacking Ensemble. Numbers are mirrored from
              <code className="ml-1 font-mono">utils/constants.py</code>.
            </p>
          </div>
          <div className="flex flex-col items-end gap-1 text-right">
            <span className="text-3xl font-bold text-emerald-400 font-mono">
              {TRAINING_FEATURE_COUNT}
            </span>
            <span className="text-xs uppercase tracking-wider text-muted-foreground">
              training-time features
            </span>
            <span className="text-xs text-muted-foreground">
              + {INFERENCE_ONLY_FEATURE_COUNT} inference-only (live)
            </span>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <Input
            placeholder="Filter features by name..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="max-w-xs"
          />
          <span className="text-xs text-muted-foreground">
            {groups.reduce((n, g) => n + g.features.length, 0)} match
          </span>
        </div>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {groups.map((g) => {
            const color = GROUP_COLOR[g.name] ?? "default"
            return (
              <Card key={g.name}>
                <CardHeader className="flex flex-row items-start justify-between space-y-0 pb-2">
                  <div className="space-y-1">
                    <CardTitle>{g.name}</CardTitle>
                    <CardDescription>{g.description}</CardDescription>
                  </div>
                  <div className="flex flex-col items-end gap-1">
                    <Badge variant="outline" className="font-mono">
                      {g.features.length}
                    </Badge>
                    <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
                      {g.availability}
                    </span>
                  </div>
                </CardHeader>
                <CardContent>
                  {g.features.length === 0 ? (
                    <p className="text-sm text-muted-foreground italic">
                      No features defined in this group (e.g. intentionally
                      empty after model audit).
                    </p>
                  ) : (
                    <div className="flex flex-wrap gap-2">
                      {g.features.map((f) => (
                        <span
                          key={f}
                          className={`inline-flex items-center rounded-md border px-2 py-1 text-xs font-mono ${COLOR_CLASS[color]}`}
                        >
                          {f}
                        </span>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            )
          })}
        </div>
      </div>
    </div>
  )
}
