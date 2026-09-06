import { describe, expect, it, vi, beforeEach } from "vitest"
import { renderHook, waitFor } from "@testing-library/react"
import { useHistory } from "./useHistory"

vi.mock("@/services/history", () => ({
  getHistory: vi.fn(),
}))

import { getHistory } from "@/services/history"
import type { HistoryMatchRow } from "@/types/api"

const rows: HistoryMatchRow[] = [
  {
    id: "1_A",
    date: "2026-01-01",
    tournament: "AO",
    surface: "Hard",
    player1: "Sinner",
    player2: "Alcaraz",
    prob1: 0.6,
    prob2: 0.4,
    winner: "Sinner",
  },
]

beforeEach(() => {
  vi.mocked(getHistory).mockReset()
})

describe("useHistory", () => {
  it("loads matches on mount", async () => {
    vi.mocked(getHistory).mockResolvedValue({ matches: rows })
    const { result } = renderHook(() => useHistory(30))
    expect(result.current.loading).toBe(true)
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.matches).toEqual(rows)
    expect(getHistory).toHaveBeenCalledWith(30, expect.any(AbortSignal))
  })

  it("surfaces errors", async () => {
    vi.mocked(getHistory).mockResolvedValue({ matches: [], error: "boom" })
    const { result } = renderHook(() => useHistory(10))
    await waitFor(() => expect(result.current.error).toBe("boom"))
  })
})