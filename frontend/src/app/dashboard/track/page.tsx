"use client"

import { useCallback, useEffect, useState } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { getTrackRecord, settleTrack } from "@/services/track"
import type { TrackRecord, TrackSummary } from "@/types/api"

function reliabilityVariant(level: string | null): "default" | "secondary" | "destructive" | "outline" {
  if (level === "alta") return "default"
  if (level === "media") return "secondary"
  if (level === "bassa") return "destructive"
  return "outline"
}

export default function TrackPage() {
  const [summary, setSummary] = useState<TrackSummary>({})
  const [records, setRecords] = useState<TrackRecord[]>([])
  const [reachable, setReachable] = useState(true)
  const [settling, setSettling] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await getTrackRecord("atp", 200)
      if (data.error) throw new Error(data.error)
      setSummary(data.summary ?? {})
      setRecords(Array.isArray(data.records) ? data.records : [])
      setReachable(true)
    } catch (e) {
      setReachable(false)
      setError(e instanceof Error ? e.message : "Backend non raggiungibile")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
    const id = setInterval(() => { void load() }, 15000)
    return () => clearInterval(id)
  }, [load])

  const settle = async () => {
    setSettling(true)
    setError(null)
    try {
      await settleTrack("atp")
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Settle fallito")
    } finally {
      setSettling(false)
    }
  }

  const acc =
    summary.accuracy != null ? `${(summary.accuracy * 100).toFixed(1)}%` : "—"
  const brier = summary.brier != null ? summary.brier.toFixed(4) : "—"

  return (
    <div className="@container/main flex flex-1 flex-col gap-2">
      <div className="flex flex-col gap-4 py-4 md:gap-6 md:py-6 px-4 lg:px-6">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 className="text-3xl font-bold tracking-tight">Track Record</h2>
            <p className="text-muted-foreground mt-1 max-w-2xl">
              Ogni predizione viene registrata prima del match e chiusa sul risultato reale —
              storico verificabile, senza hindsight.
            </p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => void load()} disabled={loading}>
              Refresh
            </Button>
            <Button onClick={() => void settle()} disabled={settling || !reachable}>
              {settling ? "Settling…" : "Settle now"}
            </Button>
          </div>
        </div>

        {!reachable && (
          <p className="text-sm text-amber-600 dark:text-amber-400">
            Backend offline o errore: {error}. Avvia{" "}
            <code className="font-mono">python api_server.py</code> (porta 9090) e premi Refresh.
          </p>
        )}
        {reachable && error && (
          <p className="text-sm text-amber-600 dark:text-amber-400">{error}</p>
        )}
        {reachable && !loading && (summary.total ?? records.length) === 0 && (
          <p className="text-sm text-muted-foreground">
            Nessuna predizione in log. Vai su{" "}
            <a className="underline" href="/dashboard/predict">Predict Match</a>{" "}
            e lancia una predizione: viene registrata qui automaticamente.
          </p>
        )}

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard
            label="Predictions logged"
            value={String(summary.total ?? records.length ?? 0)}
          />
          <StatCard
            label="Settled"
            value={String(summary.settled ?? 0)}
            sub={`${summary.open ?? Math.max(0, (summary.total ?? records.length) - (summary.settled ?? 0))} open`}
          />
          <StatCard
            label="Realized accuracy"
            value={acc}
            sub={
              (summary.settled ?? 0) > 0
                ? `${summary.correct ?? 0} correct`
                : "serve almeno 1 settle"
            }
          />
          <StatCard
            label="Realized Brier"
            value={brier}
            sub={(summary.settled ?? 0) > 0 ? "lower is better" : "dopo settle"}
          />
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Logged predictions</CardTitle>
            <CardDescription>
              Le più recenti per prime. Le predizioni aperte si chiudono quando i risultati
              entrano nel dataset features.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {loading ? (
              <p className="text-sm text-muted-foreground">Loading…</p>
            ) : records.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                Nessuna predizione ancora. Usane alcune da Predict Match — ogni risultato viene
                registrato qui automaticamente.
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-left text-muted-foreground text-xs uppercase tracking-wider">
                      <th className="py-2 pr-3 font-medium">Logged</th>
                      <th className="py-2 pr-3 font-medium">Matchup</th>
                      <th className="py-2 pr-3 font-medium">Pick</th>
                      <th className="py-2 pr-3 font-medium">P1%</th>
                      <th className="py-2 pr-3 font-medium">Reliability</th>
                      <th className="py-2 font-medium text-right">Result</th>
                    </tr>
                  </thead>
                  <tbody>
                    {records.map((r) => (
                      <tr key={r.id} className="border-b last:border-0">
                        <td className="py-2.5 pr-3 whitespace-nowrap">
                          {r.ts?.slice(0, 10) ?? "—"}
                        </td>
                        <td className="py-2.5 pr-3">
                          {r.player1} vs {r.player2}
                          <span className="ml-1 text-xs text-muted-foreground">
                            ({r.surface})
                          </span>
                        </td>
                        <td className="py-2.5 pr-3 font-medium">{r.predicted_winner}</td>
                        <td className="py-2.5 pr-3">
                          {(r.prob1 * 100).toFixed(1)}%
                        </td>
                        <td className="py-2.5 pr-3">
                          {r.reliability ? (
                            <Badge variant={reliabilityVariant(r.reliability)}>
                              {r.reliability}
                            </Badge>
                          ) : (
                            "—"
                          )}
                        </td>
                        <td className="py-2.5 text-right">
                          {!r.settled ? (
                            <span className="text-muted-foreground">open</span>
                          ) : r.correct ? (
                            <span className="text-emerald-600 dark:text-emerald-400 font-medium">
                              W {r.actual_winner}
                            </span>
                          ) : (
                            <span className="text-red-600 dark:text-red-400 font-medium">
                              L {r.actual_winner}
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

function StatCard({
  label,
  value,
  sub,
}: {
  label: string
  value: string
  sub?: string
}) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardDescription>{label}</CardDescription>
        <CardTitle className="text-2xl">{value}</CardTitle>
      </CardHeader>
      {sub ? (
        <CardContent className="pt-0">
          <p className="text-xs text-muted-foreground">{sub}</p>
        </CardContent>
      ) : null}
    </Card>
  )
}
