import { apiFetch } from "@/lib/api"
import type { MarketCard } from "@/types/market"

export function getMarketOpportunities(tour: "atp" | "wta", signal?: AbortSignal): Promise<MarketCard> {
  return apiFetch<MarketCard>(`/api/personal/markets?tour=${tour}`, { signal, cache: "no-store" })
}
