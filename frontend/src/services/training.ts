/**
 * Servizi di dominio: addestramento modelli.
 * Regola AGENT: nessun fetch diretto nei componenti/hooks.
 */
import { apiFetch } from "@/lib/api"
import type { TrainingStatus } from "@/types/api"

export async function getTrainingStatus(signal?: AbortSignal): Promise<TrainingStatus> {
  return apiFetch<TrainingStatus>("/api/status", { signal })
}

export async function startTraining(input: {
  tour: string
  trials: number
  startYear: number
  endYear: number
}): Promise<{ ok: boolean }> {
  return apiFetch<{ ok: boolean }>("/api/train/start", {
    method: "POST",
    body: input,
  })
}