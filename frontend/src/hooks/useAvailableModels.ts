"use client"

import { useEffect, useState } from "react"
import { getAvailableModels } from "@/services/system"

export interface UseAvailableModelsResult {
  models: string[]
  loading: boolean
  error: string | null
}

export function useAvailableModels(): UseAvailableModelsResult {
  const [models, setModels] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    const load = async () => {
      setLoading(true)
      setError(null)
      try {
        const data = await getAvailableModels(controller.signal)
        setModels(data.models ?? [])
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") return
        setError(err instanceof Error ? err.message : "Failed to load models")
      } finally {
        setLoading(false)
      }
    }
    void load()
    return () => controller.abort()
  }, [])

  return { models, loading, error }
}