/**
 * Servizi di dominio: odds live, value bets, partite del giorno.
 * Regola AGENT: nessun fetch diretto nei componenti/hooks.
 */
import { apiFetch } from "@/lib/api"
import type {
  OddsApiStatus,
  TodaysResponse,
  ValueResponse,
} from "@/types/api"

export async function getOddsApiStatus(
  signal?: AbortSignal,
): Promise<OddsApiStatus> {
  return apiFetch<OddsApiStatus>("/api/odds-api-status", { signal })
}

export async function getTodaysMatches(
  tour: "atp" | "wta",
  signal?: AbortSignal,
): Promise<TodaysResponse> {
  return apiFetch<TodaysResponse>(`/api/todays-matches?tour=${tour}`, { signal })
}

export async function computeValueBets(input: {
  player1: string
  player2: string
  surface: string
  minEdge: number
  model: string
}): Promise<ValueResponse & { error?: string }> {
  return apiFetch<ValueResponse & { error?: string }>("/api/value-bets", {
    method: "POST",
    body: {
      player1: input.player1,
      player2: input.player2,
      surface: input.surface,
      min_edge: input.minEdge,
      model: input.model,
    },
  })
}