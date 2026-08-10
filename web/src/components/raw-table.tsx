"use client"

import { useEffect, useState } from "react"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"
import { API_BASE_URL, ApiError, apiFetch } from "@/lib/api"

interface MatchRow {
  id: string
  date: string
  tournament: string
  surface: string
  player1: string
  player2: string
  prob1: number
  prob2: number
  winner: string
}

interface HistoryResponse {
  matches: MatchRow[]
  error?: string
}

export function RawDataTable() {
  const [matches, setMatches] = useState<MatchRow[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [limit, setLimit] = useState(30)

  useEffect(() => {
    const controller = new AbortController()
    const load = async () => {
      setLoading(true)
      setError(null)
      try {
        const data = await apiFetch<HistoryResponse>(
          `/api/history?limit=${limit}`,
          { signal: controller.signal },
        )
        if (data.error) {
          setError(data.error)
          setMatches([])
        } else {
          setMatches(data.matches ?? [])
        }
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") return
        setError(err instanceof ApiError ? err.message : "Failed to load history")
        setMatches([])
      } finally {
        setLoading(false)
      }
    }
    void load()
    return () => controller.abort()
  }, [limit])

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <div className="space-y-1">
          <CardTitle>Match History (Predicted)</CardTitle>
          <CardDescription>
            Real matches from the parquet with model probabilities.
            Backed by <span className="font-mono text-xs">GET /api/history</span>.
          </CardDescription>
        </div>
        <div className="flex items-center gap-2">
          <label className="text-xs text-muted-foreground">Rows</label>
          <select
            value={limit}
            onChange={(e) => setLimit(parseInt(e.target.value, 10))}
            className="h-8 rounded-md border border-input bg-background px-2 text-xs"
          >
            <option value="10">10</option>
            <option value="30">30</option>
            <option value="50">50</option>
            <option value="100">100</option>
          </select>
        </div>
      </CardHeader>
      <CardContent>
        {error && (
          <p className="text-sm text-red-400 mb-4">Backend error: {error}</p>
        )}
        {loading ? (
          <p className="text-sm text-muted-foreground">Loading...</p>
        ) : matches.length === 0 && !error ? (
          <p className="text-sm text-muted-foreground">
            No history available. Train a model with{" "}
            <span className="font-mono">python main.py train</span> first.
          </p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Date</TableHead>
                <TableHead>Tournament</TableHead>
                <TableHead>Surface</TableHead>
                <TableHead>P1 (model prob)</TableHead>
                <TableHead>P2 (model prob)</TableHead>
                <TableHead>Winner</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {matches.map((m) => (
                <TableRow key={m.id}>
                  <TableCell className="font-mono text-xs">{m.date}</TableCell>
                  <TableCell className="text-xs">{m.tournament}</TableCell>
                  <TableCell>
                    <Badge variant="outline" className="uppercase opacity-70">
                      {m.surface}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <div className="flex flex-col">
                      <span className="text-emerald-500 font-semibold text-sm">{m.player1}</span>
                      <span className="text-xs text-muted-foreground font-mono">
                        {(m.prob1 * 100).toFixed(1)}%
                      </span>
                    </div>
                  </TableCell>
                  <TableCell>
                    <div className="flex flex-col">
                      <span className="text-red-400 font-semibold text-sm opacity-80">{m.player2}</span>
                      <span className="text-xs text-muted-foreground font-mono">
                        {(m.prob2 * 100).toFixed(1)}%
                      </span>
                    </div>
                  </TableCell>
                  <TableCell className="text-xs">{m.winner}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
        <p className="text-xs text-muted-foreground mt-3">
          Backend: <span className="font-mono">{API_BASE_URL}</span>
        </p>
      </CardContent>
    </Card>
  )
}
