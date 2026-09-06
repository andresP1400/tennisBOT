/**
 * Servizi di dominio: predizione singola e daily card.
 * Regola AGENT: nessun fetch diretto nei componenti/hooks.
 */
import { apiFetch } from "@/lib/api"
import type { CardResponse, PredictRequest, PredictResponse } from "@/types/api"

interface PredictRequestBody {
  player1: string
  player2: string
  surface: string
  model: string
}

export async function predictMatch(
  request: PredictRequestBody,
  signal?: AbortSignal,
): Promise<PredictResponse> {
  return apiFetch<PredictResponse>("/api/predict", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: request,
    signal,
  })
}

export async function getPredictCard(
  tour: "atp" | "wta",
  minEdge = 0.05,
  log = true,
): Promise<CardResponse> {
  return apiFetch<CardResponse>(`/api/predict-card?tour=${tour}&min_edge=${minEdge}&log=${log}`)
}

export type { PredictRequest, PredictResponse }