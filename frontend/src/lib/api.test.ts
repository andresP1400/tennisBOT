import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { apiFetch, ApiError, API_BASE_URL } from "./api"

const originalFetch = globalThis.fetch

beforeEach(() => {
  globalThis.fetch = vi.fn()
})

afterEach(() => {
  globalThis.fetch = originalFetch
})

describe("apiFetch", () => {
  it("concats relative path with empty base URL", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    )
    await apiFetch("/api/health")
    expect(globalThis.fetch).toHaveBeenCalledWith(
      `${API_BASE_URL}/api/health`,
      expect.objectContaining({ headers: expect.any(Headers) }),
    )
  })

  it("stringifies JSON body and sets content-type", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({}), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    )
    await apiFetch("/api/predict", { method: "POST", body: { player1: "x" } })
    const [, options] = vi.mocked(globalThis.fetch).mock.calls[0] as [
      string,
      RequestInit,
    ]
    const headers = new Headers(options.headers)
    expect(headers.get("content-type")).toBe("application/json")
    expect(options.body).toBe(JSON.stringify({ player1: "x" }))
  })

  it("throws ApiError on non-ok response", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response("boom", { status: 500, statusText: "Server Error" }),
    )
    await expect(apiFetch("/api/x")).rejects.toThrow(ApiError)
  })

  it("parses JSON responses", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "ok" }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    )
    const data = await apiFetch<{ status: string }>("/api/health")
    expect(data.status).toBe("ok")
  })
})