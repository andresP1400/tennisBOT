"use client"

import { useEffect, useState } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import {
  getHealth,
  getAvailableModels,
} from "@/services/system"
import { getTrackRecord } from "@/services/track"
import { getOddsApiStatus } from "@/services/odds"
import type {
  HealthStatus,
  ModelsResponse,
  OddsApiStatus,
  TrackResponse,
} from "@/types/api"

interface SystemStatus {
  apiOk: boolean
  models: string[]
  oddsConfigured: boolean | null
  oddsRemaining: string | null
  oddsTournaments: number | null
}

export function OverviewPanels() {
  const [status, setStatus] = useState<SystemStatus | null>(null)
  const [track, setTrack] = useState<TrackResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    const load = async () => {
      try {
        const [health, models, odds, trackData] = await Promise.all([
          getHealth(controller.signal).catch(() => null as HealthStatus | null),
          getAvailableModels(controller.signal).catch(
            () => null as ModelsResponse | null,
          ),
          getOddsApiStatus(controller.signal).catch(
            () => null as OddsApiStatus | null,
          ),
          getTrackRecord("atp", 200, controller.signal).catch(
            () => null as TrackResponse | null,
          ),
        ])
        setStatus({
          apiOk: health?.status === "ok",
          models: models?.models ?? [],
          oddsConfigured: odds?.configured ?? null,
          oddsRemaining: odds?.remaining_requests ?? null,
          oddsTournaments: odds?.tennis_tournaments ?? null,
        })
        setTrack(trackData)
        setError(null)
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") return
        setError(err instanceof Error ? err.message : "Backend non raggiungibile")
      }
    }
    void load()
    return () => controller.abort()
  }, [])

  const settled = (track?.records ?? []).filter((r) => r.settled).slice(0, 8)

  return (
    <div className="grid gap-4 lg:grid-cols-2 px-4 lg:px-6">
      <Card>
        <CardHeader>
          <CardTitle>System Status</CardTitle>
          <CardDescription>Backend, modelli e feed quote in tempo reale.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          {error && <p className="text-red-400">Backend error: {error}</p>}
          {status && (
            <>
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">FastAPI backend</span>
                <Badge variant={status.apiOk ? "default" : "destructive"} className={status.apiOk ? "bg-emerald-500/15 text-emerald-500 border-emerald-500/40" : ""}>
                  {status.apiOk ? "online" : "offline"}
                </Badge>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">Modelli disponibili</span>
                <span className="font-mono text-xs">
                  {status.models.length > 0 ? status.models.join(", ") : "nessuno"}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">Feed quote (TheOddsAPI)</span>
                <Badge
                  variant={status.oddsConfigured ? "default" : "outline"}
                  className={status.oddsConfigured ? "bg-emerald-500/15 text-emerald-500 border-emerald-500/40" : ""}
                >
                  {status.oddsConfigured ? "configurato" : "non configurato"}
                </Badge>
              </div>
              {status.oddsConfigured && (
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Quote mensili rimaste</span>
                  <span className="font-mono text-xs">{status.oddsRemaining ?? "—"}</span>
                </div>
              )}
              {status.oddsTournaments != null && (
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Tornei tennis live</span>
                  <span className="font-mono text-xs">{status.oddsTournaments}</span>
                </div>
              )}
            </>
          )}
          {!status && !error && <p className="text-muted-foreground">Loading…</p>}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Track Record — ultime chiuse</CardTitle>
          <CardDescription>
            Predizioni verificate sui risultati reali (dettaglio in{" "}
            <a className="underline" href="/dashboard/track">Track Record</a>).
          </CardDescription>
        </CardHeader>
        <CardContent>
          {settled.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              Nessuna predizione chiusa: le partite predette si chiudono quando i
              risultati entrano nel dataset features (refresh settimanale o manuale).
            </p>
          ) : (
            <div className="space-y-2">
              {settled.map((r) => (
                <div key={r.id} className="flex items-center justify-between gap-3 text-sm">
                  <span className="min-w-0 truncate">
                    {r.player1} vs {r.player2}{" "}
                    <span className="text-xs text-muted-foreground">({r.surface})</span>
                  </span>
                  <span className="font-mono text-xs">{(r.prob1 * 100).toFixed(0)}%</span>
                  <Badge
                    variant="outline"
                    className={
                      r.correct
                        ? "border-emerald-500/40 text-emerald-500"
                        : "border-red-500/40 text-red-500"
                    }
                  >
                    {r.correct ? "W" : "L"} {r.actual_winner}
                  </Badge>
                </div>
              ))}
              <p className="text-xs text-muted-foreground pt-2">
                {(track?.summary?.total ?? 0)} predizioni totali ·{" "}
                {(track?.summary?.settled ?? 0)} chiuse
                {track?.summary?.accuracy != null
                  ? ` · accuracy ${(track.summary.accuracy * 100).toFixed(1)}%`
                  : ""}
              </p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}