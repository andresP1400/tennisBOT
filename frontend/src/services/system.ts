/**
 * Servizi di dominio: stato di sistema, modelli, health-check e track record.
 * Regola AGENT: nessun fetch diretto nei componenti/hooks.
 */
import { apiFetch } from "@/lib/api"
import type {
  HealthStatus,
  ModelsResponse,
  TrackResponse,
} from "@/types/api"

export async function getHealth(signal?: AbortSignal): Promise<HealthStatus> {
  return apiFetch<HealthStatus>("/api/health", { signal })
}

export async function getAvailableModels(signal?: AbortSignal): Promise<ModelsResponse> {
  return apiFetch<ModelsResponse>("/api/models", { signal })
}

export async function getTrack(
  tour = "atp",
  limit = 200,
  signal?: AbortSignal,
): Promise<TrackResponse> {
  return apiFetch<TrackResponse>(`/api/track?tour=${tour}&limit=${limit}`, { signal })
}