/**
 * Servizi di dominio: storia partite.
 * Regola AGENT: nessun fetch diretto nei componenti/hooks.
 */
import { apiFetch } from "@/lib/api"
import type { HistoryResponse } from "@/types/api"

export async function getHistory(
  limit = 30,
  signal?: AbortSignal,
): Promise<HistoryResponse> {
  return apiFetch<HistoryResponse>(`/api/history?limit=${limit}`, { signal })
}