/**
 * Servizi di dominio: stato di sistema, modelli, health-check.
 * Regola AGENT: nessun fetch diretto nei componenti/hooks.
 * (Il Track Record vive in services/track.ts.)
 */
import { apiFetch } from "@/lib/api"
import type { HealthStatus, ModelsResponse } from "@/types/api"

export async function getHealth(signal?: AbortSignal): Promise<HealthStatus> {
  return apiFetch<HealthStatus>("/api/health", { signal })
}

export async function getAvailableModels(signal?: AbortSignal): Promise<ModelsResponse> {
  return apiFetch<ModelsResponse>("/api/models", { signal })
}