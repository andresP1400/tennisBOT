import { afterEach, describe, expect, it, vi } from "vitest"
import { act, cleanup, renderHook } from "@testing-library/react"
import { useMarketOpportunities } from "./useMarketOpportunities"
import { getMarketOpportunities } from "@/services/market"
import type { MarketCard } from "@/types/market"

vi.mock("@/services/market", () => ({ getMarketOpportunities: vi.fn() }))

const card: MarketCard = {
  checked_at: "2026-10-16T14:00:00Z", valid_until: "2026-10-16T14:00:10Z", policy_version: "unit-policy",
  category_a: [], category_b: [], candidates: [], message_a: "No qualifying opportunities.",
  message_b: "No qualifying opportunities.", provider_status: "disabled", performance_a: {}, performance_b: {},
}

afterEach(() => { cleanup(); vi.useRealTimers(); vi.resetAllMocks() })

describe("useMarketOpportunities", () => {
  it("expires displayed market evidence even before the next scheduled refresh", async () => {
    vi.useFakeTimers(); vi.setSystemTime(new Date(card.checked_at))
    vi.mocked(getMarketOpportunities).mockResolvedValue(card)
    const { result } = renderHook(() => useMarketOpportunities("atp"))
    await act(async () => { await Promise.resolve() })
    expect(result.current.card).toEqual(card)
    await act(async () => { await vi.advanceTimersByTimeAsync(10_001) })
    expect(result.current.card).toBeNull()
    expect(result.current.error).toMatch(/expired/)
  })
  it("hides the old tour immediately while a different tour is loading", async () => {
    vi.useFakeTimers(); vi.setSystemTime(new Date(card.checked_at))
    vi.mocked(getMarketOpportunities).mockResolvedValueOnce(card).mockReturnValueOnce(new Promise(() => {}))
    const { result, rerender } = renderHook(({ tour }: { tour: "atp" | "wta" }) => useMarketOpportunities(tour),
      { initialProps: { tour: "atp" } })
    await act(async () => { await Promise.resolve() })
    expect(result.current.card).toEqual(card)
    rerender({ tour: "wta" })
    expect(result.current.card).toBeNull()
  })
  it("clears previous opportunities on a failed refresh", async () => {
    vi.useFakeTimers(); vi.setSystemTime(new Date(card.checked_at))
    vi.mocked(getMarketOpportunities).mockResolvedValueOnce({ ...card, valid_until: "2026-10-16T14:02:00Z" })
      .mockRejectedValueOnce(new Error("Provider failed"))
    const { result } = renderHook(() => useMarketOpportunities("atp"))
    await act(async () => { await Promise.resolve() })
    expect(result.current.card).not.toBeNull()
    await act(async () => { await vi.advanceTimersByTimeAsync(60_001) })
    expect(result.current.card).toBeNull()
    expect(result.current.error).toBe("Provider failed")
  })
})
