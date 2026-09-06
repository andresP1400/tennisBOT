/**
 * Servizi di dominio: Track Record (predizioni certificate).
 * Regola AGENT: nessun fetch diretto nei componenti/hooks.
 */
import { apiFetch } from "@/lib/api"
import type { TrackResponse } from "@/types/api"

export async function getTrackRecord(
  tour: "atp" | "wta" = "atp",
  limit = 200,
): Promise<TrackResponse> {
  return apiFetch<TrackResponse>(`/api/track?tour=${tour}&limit=${limit}`, {
    cache: "no-store",
  }) as Promise<TrackResponse>
}

export async function settleTrack(tour: "atp" | "wta" = "atp"): Promise<{ ok: boolean; error?: string }> {
  const r = await fetch(`/api/track/settle?tour=${tour}`, { method: "POST" })
  const data = (await r.json().catch(() => ({}))) as { error?: string }
  if (!r.ok || data.error) {
    throw new Error(data.error || `Settle failed HTTP ${r.status}`)
  }
  return { ok: true }
}