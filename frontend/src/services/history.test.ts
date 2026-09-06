import { describe, expect, it, vi } from "vitest"
import { getHistory } from "./history"

vi.mock("@/lib/api", () => ({
  apiFetch: vi.fn(),
}))

import { apiFetch } from "@/lib/api"

describe("getHistory", () => {
  it("calls apiFetch with limit query", async () => {
    vi.mocked(apiFetch).mockResolvedValue({ matches: [], error: undefined })
    await getHistory(30)
    expect(apiFetch).toHaveBeenCalledWith("/api/history?limit=30", expect.anything())
  })

  it("passes abort signal", async () => {
    vi.mocked(apiFetch).mockResolvedValue({ matches: [] })
    const signal = new AbortController().signal
    await getHistory(10, signal)
    expect(apiFetch).toHaveBeenCalledWith(
      "/api/history?limit=10",
      expect.objectContaining({ signal }),
    )
  })
})