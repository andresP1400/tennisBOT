import { act, renderHook, waitFor } from "@testing-library/react"
import { afterEach, expect, it, vi } from "vitest"
import { usePersonalPredictions } from "./usePersonalPredictions"
import { getPersonalPredictions } from "@/services/personal"
import type { PersonalCard } from "@/types/personal"

vi.mock("@/services/personal", () => ({ getPersonalPredictions: vi.fn() }))

const card: PersonalCard = {
  tour: "atp", model_version: "unit-test", fetched_at: "2026-10-16T05:00:00Z",
  predictions: [], unavailable: [], message: null, backtest: {},
}

afterEach(() => { vi.clearAllMocks(); vi.restoreAllMocks(); vi.useRealTimers() })

it("clears an old card when refresh fails and recovers on the next successful refresh", async () => {
  vi.mocked(getPersonalPredictions).mockResolvedValueOnce(card)
  const { result, unmount } = renderHook(() => usePersonalPredictions("atp"))
  await waitFor(() => expect(result.current.card).toEqual(card))
  vi.mocked(getPersonalPredictions).mockRejectedValueOnce(new Error("Provider unavailable"))
  act(() => result.current.refresh())
  await waitFor(() => expect(result.current.error).toBe("Provider unavailable"))
  expect(result.current.card).toBeNull()
  vi.mocked(getPersonalPredictions).mockResolvedValueOnce(card)
  act(() => result.current.refresh())
  await waitFor(() => expect(result.current.card).toEqual(card))
  expect(result.current.error).toBeNull()
  unmount()
})

it("rejects a delayed previous-tour response instead of displaying it under the new tour", async () => {
  let completePrevious: ((value: PersonalCard) => void) | undefined
  vi.mocked(getPersonalPredictions).mockImplementationOnce(() => new Promise(resolve => { completePrevious = resolve }))
  vi.mocked(getPersonalPredictions).mockResolvedValueOnce({ ...card, tour: "wta" })
  const { result, rerender, unmount } = renderHook(({ tour }: { tour: "atp" | "wta" }) => usePersonalPredictions(tour),
    { initialProps: { tour: "atp" as "atp" | "wta" } })
  rerender({ tour: "wta" })
  await waitFor(() => expect(result.current.card?.tour).toBe("wta"))
  await act(async () => { completePrevious?.(card) })
  expect(result.current.card?.tour).toBe("wta")
  unmount()
})

it("ends loading with an error when the bounded request deadline aborts", async () => {
  const deadline = new AbortController()
  const timeout = vi.spyOn(AbortSignal, "timeout").mockReturnValue(deadline.signal)
  vi.mocked(getPersonalPredictions).mockImplementationOnce((_tour, signal) => new Promise((_resolve, reject) => {
    signal?.addEventListener("abort", () => reject(signal.reason), { once: true })
  }))
  const { result, unmount } = renderHook(() => usePersonalPredictions("atp"))
  await waitFor(() => expect(result.current.loading).toBe(true))
  expect(timeout).toHaveBeenCalledWith(25_000)
  act(() => deadline.abort(new DOMException("Request deadline exceeded", "TimeoutError")))
  await waitFor(() => expect(result.current.error).toBe("Request deadline exceeded"))
  expect(result.current.loading).toBe(false)
  expect(result.current.card).toBeNull()
  unmount()
})

it("removes previously displayed forecasts when an automatic interval refresh fails", async () => {
  vi.useFakeTimers()
  vi.mocked(getPersonalPredictions).mockResolvedValueOnce(card).mockRejectedValueOnce(new Error("Automatic refresh failed"))
  const { result, unmount } = renderHook(() => usePersonalPredictions("atp"))
  await act(async () => { await Promise.resolve() })
  expect(result.current.card).toEqual(card)
  await act(async () => { vi.advanceTimersByTime(60_000); await Promise.resolve() })
  expect(result.current.error).toBe("Automatic refresh failed")
  expect(result.current.card).toBeNull()
  expect(result.current.loading).toBe(false)
  unmount()
})
