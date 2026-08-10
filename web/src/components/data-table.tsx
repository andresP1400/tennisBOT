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

export function DataTable() {
  const [matches, setMatches] = React.useState<MatchRow[]>([])
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState("")

  React.useEffect(() => {
    const controller = new AbortController()
    const load = async () => {
      try {
        const res = await fetch("/api/history?limit=30", {
          signal: controller.signal,
        })
        const data = (await res.json()) as {
          matches?: MatchRow[]
          error?: string
        }
        if (data.error) {
          setError(data.error)
        } else if (data.matches) {
          setMatches(data.matches)
        }
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") return
        console.error(err)
        setError("Impossibile connettersi a FastAPI. Avvia Python!")
      } finally {
        setLoading(false)
      }
    }
    void load()
    return () => controller.abort()
  }, [])

  return (
    <Card>
      <CardHeader>
        <CardTitle>Recent Test Matches (Engine Live)</CardTitle>
        <CardDescription>
          True inferences executed by the live Python backend dynamically from the processed Parquet dataset.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {error && <div className="text-red-500 font-bold mb-4">{error}</div>}
        {loading && <div className="text-muted-foreground mb-4">Caricamento in corso dal modello Python...</div>}

        {!loading && !error && (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Date</TableHead>
                <TableHead>Tournament</TableHead>
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
                    <TableCell className="font-medium">{match.date}</TableCell>
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
                        <span className="text-[10px] text-muted-foreground uppercase tracking-wider">{(Math.max(match.prob1, match.prob2) * 100).toFixed(1)}% Confidence</span>
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
      </CardContent>
    </Card>
  )
}
