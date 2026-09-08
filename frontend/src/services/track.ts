/**
 * Servizi di dominio: Track Record (predizioni certificate).
 * Regola AGENT: nessun fetch diretto nei componenti/hooks.
 */
import { apiFetch } from "@/lib/api"
import type { TrackResponse } from "@/types/api"

export async function getTrackRecord(
  tour: "atp" | "wta" = "atp",
  limit = 200,
  signal?: AbortSignal,
): Promise<TrackResponse> {
  return apiFetch<TrackResponse>(`/api/track?tour=${tour}&limit=${limit}`, {
    signal,
    cache: "no-store",
  })
}

export async function settleTrack(
  tour: "atp" | "wta" = "atp",
): Promise<{ ok: boolean }> {
  return apiFetch<{ ok: boolean }>(`/api/track/settle?tour=${tour}`, {
    method: "POST",
  })
}