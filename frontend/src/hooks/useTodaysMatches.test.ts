import { describe, expect, it, vi, beforeEach } from "vitest"
import { renderHook, waitFor } from "@testing-library/react"
import { useTodaysMatches } from "./useTodaysMatches"

vi.mock("@/services/odds", () => ({
  getOddsApiStatus: vi.fn(),
  getTodaysMatches: vi.fn(),
}))

import { getOddsApiStatus, getTodaysMatches } from "@/services/odds"
import type { TodaysMatch } from "@/types/api"

const match: TodaysMatch = {
  player1: "Sinner",
  player2: "Alcaraz",
  tournament: "AO",
  surface: "Hard",
  commence_time: "2026-01-01T00:00:00Z",
  best_odds: { player1: 1.8, player2: 2.1 },
  implied_prob1: 0.53,
  implied_prob2: 0.47,
  margin: 0.02,
  num_bookmakers: 8,
}

beforeEach(() => {
  vi.mocked(getOddsApiStatus).mockReset()
  vi.mocked(getTodaysMatches).mockReset()
})

describe("useTodaysMatches", () => {
  it("flags needsKey when odds API is not configured", async () => {
    vi.mocked(getOddsApiStatus).mockResolvedValue({ configured: false })
    vi.mocked(getTodaysMatches).mockResolvedValue({ tour: "atp", count: 1, matches: [match] })
    const { result } = renderHook(() => useTodaysMatches("atp"))
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.needsKey).toBe(true)
    expect(result.current.matches).toEqual([match])
  })

  it("reflects error from the backend", async () => {
    vi.mocked(getOddsApiStatus).mockResolvedValue({ configured: true })
    vi.mocked(getTodaysMatches).mockResolvedValue({
      tour: "atp",
      count: 0,
      matches: [],
      error: "ODDS_API_KEY not set",
    })
    const { result } = renderHook(() => useTodaysMatches("atp"))
    await waitFor(() => expect(result.current.error).toBe("ODDS_API_KEY not set"))
    expect(result.current.needsKey).toBe(true)
  })
})