"use client"

import { useEffect, useState } from "react"
import { getTodaysMatches, getOddsApiStatus } from "@/services/odds"
import type { TodaysMatch } from "@/types/api"

export interface UseTodaysMatchesResult {
  matches: TodaysMatch[]
  needsKey: boolean
  loading: boolean
  error: string | null
}

export function useTodaysMatches(tour: "atp" | "wta"): UseTodaysMatchesResult {
  const [matches, setMatches] = useState<TodaysMatch[]>([])
  const [needsKey, setNeedsKey] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    const load = async () => {
      setLoading(true)
      setError(null)
      try {
        try {
          const st = await getOddsApiStatus(controller.signal)
          setNeedsKey(st.configured === false)
        } catch {
          /* ignore */
        }
        const data = await getTodaysMatches(tour, controller.signal)
        setMatches(data.matches ?? [])
        if (data.error) {
          setError(data.error)
          if (/ODDS_API_KEY|not set|not configured/i.test(data.error)) {
            setNeedsKey(true)
          }
        }
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") return
        setError(err instanceof Error ? err.message : "Failed to load matches")
        setMatches([])
      } finally {
        setLoading(false)
      }
    }
    void load()
    return () => controller.abort()
  }, [tour])

  return { matches, needsKey, loading, error }
}