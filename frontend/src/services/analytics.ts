/**
 * Servizi di dominio: metriche e chart di valutazione.
 * Regola AGENT: nessun fetch diretto nei componenti/hooks.
 */
import { apiFetch } from "@/lib/api"
import type { ChartsResponse, MetricsRow } from "@/types/api"

export async function getCharts(tour: "atp" | "wta", signal?: AbortSignal): Promise<ChartsResponse> {
  return apiFetch<ChartsResponse>(`/api/charts?tour=${tour}`, { signal })
}

/** Scarica il CSV /api/metrics e lo converte in righe tipizzate. */
export async function getMetricsRows(
  tour: "atp" | "wta",
  signal?: AbortSignal,
): Promise<MetricsRow[]> {
  const res = await fetch(`/api/metrics?tour=${tour}`, {
    signal,
    cache: "no-store",
  })
  if (!res.ok) return []
  const text = await res.text()
  const lines = text.trim().split("\n").filter(Boolean)
  const header = lines.shift()?.split(",") ?? []
  const idxMetric = header.indexOf("metric")
  const idxTest = header.indexOf("test")
  const idxVal = header.indexOf("val")
  if (idxMetric < 0 || idxTest < 0 || idxVal < 0) return []
  return lines
    .map((line) => {
      const cols = line.split(",")
      return {
        metric: cols[idxMetric],
        test: parseFloat(cols[idxTest]),
        val: parseFloat(cols[idxVal]),
      }
    })
    .filter((r) => r.metric && Number.isFinite(r.test))
}