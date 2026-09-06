/**
 * Servizi di dominio: player news research.
 * Regola AGENT: nessun fetch diretto nei componenti/hooks.
 */
import { apiFetch } from "@/lib/api"
import type { NewsResponse } from "@/types/api"

export interface PlayerNewsRequest {
  tour?: string
  player1: string
  player2: string
  surface?: string
}

export async function researchPlayerNews(
  input: PlayerNewsRequest,
  signal?: AbortSignal,
): Promise<NewsResponse> {
  return apiFetch<NewsResponse>("/api/player-news", {
    method: "POST",
    body: input,
    signal,
  })
}