"use client"

import { useCallback, useEffect, useState } from "react"
import { getPersonalPredictions } from "@/services/personal"
import type { PersonalCard } from "@/types/personal"

export function usePersonalPredictions(tour: "atp" | "wta") {
  const [card, setCard] = useState<PersonalCard | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [refreshKey, setRefreshKey] = useState(0)
  const refresh = useCallback(() => setRefreshKey(key => key + 1), [])

  useEffect(() => {
    const controller = new AbortController()
    setCard(null)
    async function load() {
      setLoading(true)
      try {
        const signal = AbortSignal.any([controller.signal, AbortSignal.timeout(25_000)])
        const response = await getPersonalPredictions(tour, signal)
        if (!controller.signal.aborted) { setCard(response); setError(null) }
      } catch (failure) {
        if (!controller.signal.aborted) {
          setCard(null)
          setError(failure instanceof Error || failure instanceof DOMException ? failure.message : "Predictions unavailable")
        }
      } finally {
        if (!controller.signal.aborted) setLoading(false)
      }
    }
    void load()
    const interval = setInterval(() => void load(), 60_000)
    return () => { controller.abort(); clearInterval(interval) }
  }, [tour, refreshKey])

  return { card, error, loading, refresh }
}
