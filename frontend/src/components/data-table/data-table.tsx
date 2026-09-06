"use client"

import * as React from "react"
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
import { API_BASE_URL } from "@/lib/api"
import { useHistory } from "@/hooks/useHistory"

export function DataTable() {
  const [limit, setLimit] = React.useState(30)
  const { matches, loading, error } = useHistory(limit)

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <div>
          <CardTitle>Match History (Engine Live)</CardTitle>
          <CardDescription>
            True inferences executed by the live Python backend dynamically from the processed
            Parquet dataset: date, tournament, surface, model probability and actual result.
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
        {error && <div className="text-red-500 font-bold mb-4">{error}</div>}
        {loading && <div className="text-muted-foreground mb-4">Caricamento in corso dal modello Python...</div>}

        {!loading && !error && matches.length === 0 && (
          <p className="text-sm text-muted-foreground">
            No history available. Train a model with{" "}
            <span className="font-mono">python main.py train</span> first.
          </p>
        )}

        {!loading && !error && matches.length > 0 && (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Date</TableHead>
                <TableHead>Tournament</TableHead>
                <TableHead>Surface</TableHead>
                <TableHead>Matchup</TableHead>
                <TableHead className="text-right">Prediction</TableHead>
                <TableHead className="text-right">Result</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {matches.map((match) => {
                const p1Fav = match.prob1 >= 0.5
                const correct = match.winner === (p1Fav ? match.player1 : match.player2)

                return (
                  <TableRow key={match.id}>
                    <TableCell className="font-medium whitespace-nowrap">{match.date}</TableCell>
                    <TableCell>
                      {match.tournament}
                      <Badge variant="outline" className="ml-2 text-[10px] uppercase opacity-70">
                        {match.surface}
                      </Badge>
                    </TableCell>
                    <TableCell className="whitespace-nowrap">
                      <span className={p1Fav ? "font-bold" : ""}>{match.player1}</span>
                      <span className="mx-2 text-muted-foreground">vs</span>
                      <span className={!p1Fav ? "font-bold" : ""}>{match.player2}</span>
                    </TableCell>
                    <TableCell className="text-right whitespace-nowrap">
                      <div className="flex flex-col items-end gap-1">
                        <span className="font-semibold text-sm">{p1Fav ? match.player1 : match.player2}</span>
                        <span className="text-[10px] text-muted-foreground uppercase tracking-wider">
                          {(Math.max(match.prob1, match.prob2) * 100).toFixed(1)}%
                        </span>
                      </div>
                    </TableCell>
                    <TableCell className="text-right whitespace-nowrap">
                      <div className="flex flex-col items-end gap-1">
                        <span className="font-semibold text-sm">{match.winner}</span>
                        <Badge variant="outline" className={correct ? "px-1.5 py-0 text-[10px] border-emerald-500/50 text-emerald-500 bg-emerald-500/10" : "px-1.5 py-0 text-[10px] border-destructive/50 text-destructive bg-destructive/10"}>
                          {correct ? "Correct" : "Miss"}
                        </Badge>
                      </div>
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        )}
        <p className="text-xs text-muted-foreground mt-3">
          Backend: <span className="font-mono">{API_BASE_URL}</span> · {matches.length} match
          mostrati · click su &quot;Match History&quot; per la sezione completa.
        </p>
      </CardContent>
    </Card>
  )
}