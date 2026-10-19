"use client"

import { useEffect, useState } from "react"
import { getMarketOpportunities } from "@/services/market"
import type { MarketCard } from "@/types/market"

export function useMarketOpportunities(tour: "atp" | "wta") {
  const [snapshot, setSnapshot] = useState<{ tour: "atp" | "wta"; card: MarketCard | null; error: string | null }>(
    { tour, card: null, error: null })
  useEffect(() => {
    if (!snapshot.card || snapshot.tour !== tour) return
    const remaining = Date.parse(snapshot.card.valid_until) - Date.now()
    const timer = setTimeout(() => setSnapshot({ tour, card: null,
      error: "Market evidence expired; waiting for a fresh check." }), Math.max(0, Number.isFinite(remaining) ? remaining : 0))
    return () => clearTimeout(timer)
  }, [snapshot.card, snapshot.tour, tour])
  useEffect(() => {
    const controller = new AbortController()
    async function load() {
      try {
        const signal = AbortSignal.any([controller.signal, AbortSignal.timeout(25_000)])
        const response = await getMarketOpportunities(tour, signal)
        if (!controller.signal.aborted) setSnapshot({ tour, card: response, error: null })
      } catch (failure) {
        if (!controller.signal.aborted) {
          setSnapshot({ tour, card: null, error: failure instanceof Error || failure instanceof DOMException
            ? failure.message : "Market research unavailable" })
        }
      }
    }
    void load()
    const interval = setInterval(() => void load(), 60_000)
    return () => { controller.abort(); clearInterval(interval) }
  }, [tour])
  return snapshot.tour === tour ? { card: snapshot.card, error: snapshot.error } : { card: null, error: null }
}
