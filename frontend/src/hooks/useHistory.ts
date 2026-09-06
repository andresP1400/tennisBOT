"use client"

import { useEffect, useState } from "react"
import { getHistory } from "@/services/history"
import type { HistoryMatchRow } from "@/types/api"

export interface UseHistoryResult {
  matches: HistoryMatchRow[]
  loading: boolean
  error: string | null
  reload: () => void
}

export function useHistory(limit = 30): UseHistoryResult {
  const [matches, setMatches] = useState<HistoryMatchRow[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [tick, setTick] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    const load = async () => {
      setLoading(true)
      setError(null)
      try {
        const data = await getHistory(limit, controller.signal)
        setMatches(data.matches ?? [])
        setError(data.error ?? null)
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") return
        setError(err instanceof Error ? err.message : "Failed to load history")
      } finally {
        setLoading(false)
      }
    }
    void load()
    return () => controller.abort()
  }, [limit, tick])

  const reload = () => setTick((t) => t + 1)

  return { matches, loading, error, reload }
}