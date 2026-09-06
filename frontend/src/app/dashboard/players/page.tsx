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
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { useHistory } from "@/hooks/useHistory"
import type { HistoryMatchRow } from "@/types/api"

interface PlayerStats {
  name: string
  matches: number
  wins: number
  losses: number
  winPct: number
  surfaces: Record<string, { matches: number; wins: number }>
  lastMatch: string | null
  avgProbWhenFavored: number | null
}

function buildStats(matches: HistoryMatchRow[]): Map<string, PlayerStats> {
  const stats = new Map<string, PlayerStats>()
  const ensure = (name: string): PlayerStats => {
    let s = stats.get(name)
    if (!s) {
      s = {
        name,
        matches: 0,
        wins: 0,
        losses: 0,
        winPct: 0,
        surfaces: {},
        lastMatch: null,
        avgProbWhenFavored: null,
      }
      stats.set(name, s)
    }
    return s
  }
  const favoredProbs: Map<string, number[]> = new Map()
  for (const m of matches) {
    for (const p of [m.player1, m.player2]) {
      const s = ensure(p)
      s.matches += 1
      if (m.winner === p) s.wins += 1
      else s.losses += 1
      const surf = m.surface || "Unknown"
      if (!s.surfaces[surf]) s.surfaces[surf] = { matches: 0, wins: 0 }
      s.surfaces[surf].matches += 1
      if (m.winner === p) s.surfaces[surf].wins += 1
      if (s.lastMatch === null || m.date > s.lastMatch) s.lastMatch = m.date
    }
    if (m.prob1 >= 0.5) {
      const arr = favoredProbs.get(m.player1) ?? []
      arr.push(m.prob1)
      favoredProbs.set(m.player1, arr)
    } else {
      const arr = favoredProbs.get(m.player2) ?? []
      arr.push(m.prob2)
      favoredProbs.set(m.player2, arr)
    }
  }
  for (const [name, arr] of favoredProbs) {
    const s = stats.get(name)
    if (s) {
      s.avgProbWhenFavored = arr.reduce((a, b) => a + b, 0) / arr.length
    }
  }
  for (const s of stats.values()) {
    s.winPct = s.matches > 0 ? s.wins / s.matches : 0
  }
  return stats
}

export default function PlayersPage() {
  const [query, setQuery] = useState("")
  const { matches, loading, error } = useHistory(100)

  const stats = useMemo(() => buildStats(matches), [matches])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    const list = Array.from(stats.values())
    const matched = q ? list.filter((s) => s.name.toLowerCase().includes(q)) : list
    return matched.sort((a, b) => b.matches - a.matches).slice(0, 50)
  }, [stats, query])

  return (
    <div className="@container/main flex flex-1 flex-col gap-2">
      <div className="flex flex-col gap-4 py-4 md:gap-6 md:py-6 px-4 lg:px-6">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h2 className="text-3xl font-bold tracking-tight">Player Database</h2>
            <p className="text-muted-foreground">
              Win rates and surface splits computed from match history predictions.
            </p>
          </div>
          <Input
            placeholder="Filter by player name..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="max-w-xs"
          />
        </div>

        {error && (
          <Card>
            <CardContent className="pt-6 text-sm text-red-400">
              Backend error: {error}
            </CardContent>
          </Card>
        )}

        <Card>
          <CardHeader>
            <CardTitle>Players ({stats.size} found)</CardTitle>
            <CardDescription>
              Aggregated from <span className="font-mono">{matches.length}</span> recent
              matches. Source: <span className="font-mono">/api/history</span>.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {loading ? (
              <p className="text-sm text-muted-foreground">Loading...</p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Player</TableHead>
                    <TableHead className="text-right">Matches</TableHead>
                    <TableHead className="text-right">Wins</TableHead>
                    <TableHead className="text-right">Losses</TableHead>
                    <TableHead className="text-right">Win %</TableHead>
                    <TableHead className="text-right">Avg prob when favored</TableHead>
                    <TableHead>Best surface</TableHead>
                    <TableHead>Last match</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filtered.map((s) => {
                    const bestSurface = Object.entries(s.surfaces)
                      .map(([surf, v]) => ({ surf, pct: v.matches > 0 ? v.wins / v.matches : 0, matches: v.matches }))
                      .filter((x) => x.matches >= 3)
                      .sort((a, b) => b.pct - a.pct)[0]
                    return (
                      <TableRow key={s.name}>
                        <TableCell className="font-medium">{s.name}</TableCell>
                        <TableCell className="text-right font-mono">{s.matches}</TableCell>
                        <TableCell className="text-right font-mono text-emerald-500">{s.wins}</TableCell>
                        <TableCell className="text-right font-mono text-red-400">{s.losses}</TableCell>
                        <TableCell className="text-right font-mono">
                          {(s.winPct * 100).toFixed(1)}%
                        </TableCell>
                        <TableCell className="text-right font-mono text-xs">
                          {s.avgProbWhenFavored !== null
                            ? `${(s.avgProbWhenFavored * 100).toFixed(1)}%`
                            : "-"}
                        </TableCell>
                        <TableCell>
                          {bestSurface ? (
                            <Badge variant="outline" className="uppercase text-xs">
                              {bestSurface.surf} {(bestSurface.pct * 100).toFixed(0)}%
                            </Badge>
                          ) : (
                            <span className="text-xs text-muted-foreground">-</span>
                          )}
                        </TableCell>
                        <TableCell className="text-xs font-mono text-muted-foreground">
                          {s.lastMatch ?? "-"}
                        </TableCell>
                      </TableRow>
                    )
                  })}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
