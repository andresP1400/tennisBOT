import { describe, expect, it, vi } from "vitest"
import { render, screen, within } from "@testing-library/react"
import { MarketOpportunities } from "."
import { useMarketOpportunities } from "@/hooks/useMarketOpportunities"
import type { MarketCard } from "@/types/market"

vi.mock("@/hooks/useMarketOpportunities", () => ({ useMarketOpportunities: vi.fn() }))

const empty: MarketCard = {
  checked_at: "2026-10-16T14:00:00Z", valid_until: "2026-10-16T14:01:00Z",
  policy_version: "unit-test-policy", category_a: [], category_b: [], candidates: [],
  message_a: "No qualifying opportunities.", message_b: "No qualifying opportunities.",
  provider_status: "Optional sportsbook API disabled or unconfigured", performance_a: {}, performance_b: {},
}

describe("MarketOpportunities", () => {
  it("shows no qualifying opportunities in both categories without inventing prices or success", () => {
    vi.mocked(useMarketOpportunities).mockReturnValue({ card: empty, error: null })
    render(<MarketOpportunities tour="atp" />)
    expect(screen.getAllByText("No qualifying opportunities.")).toHaveLength(2)
    expect(screen.getByText(/80% verified win rate is a target, not an established result/)).toBeInTheDocument()
    expect(screen.queryByText(/80.0% estimated/)).not.toBeInTheDocument()
  })
  it("keeps a lower-confidence Category B opportunity out of Category A", () => {
    const candidate = {
      fixture: { id: "test", tour: "wta", player1: "One", player2: "Two", tournament: "Unit fixture",
        surface: "Clay", commence_time: "2026-10-17T14:00:00Z", odds1: null, odds2: null },
      prediction_id: "unit-test-id", model_version: "test-model", policy_version: "unit-test-policy", player: "One",
      probability: .75, decimal_odds: 1.8, bookmaker: "test-book", no_vig_market_probability: .60,
      probability_edge: .15, estimated_ev: .35, conservative_ev: .17, lower_probability: .65,
      reasons: [], supporting_reasons: ["Unit-test evidence"], risks: ["Unit-test risk"],
    }
    vi.mocked(useMarketOpportunities).mockReturnValue({ card: {
      ...empty, category_b: [candidate], message_b: "Potential market value; not proven profitability",
    }, error: null })
    render(<MarketOpportunities tour="wta" />)
    const categoryA = screen.getByText("80%+ High-Confidence Value").closest('[data-slot="card"]') as HTMLElement
    const categoryB = screen.getByText("Best Value Opportunities").closest('[data-slot="card"]') as HTMLElement
    expect(within(categoryA).queryByText(/75.0% estimated/)).not.toBeInTheDocument()
    expect(within(categoryB).getByText(/75.0% estimated/)).toBeInTheDocument()
    expect(within(categoryB).getByText(/Unit-test risk/)).toBeInTheDocument()
  })
  it("clears eligibility when the market refresh fails", () => {
    vi.mocked(useMarketOpportunities).mockReturnValue({ card: null, error: "Feed unavailable" })
    render(<MarketOpportunities tour="atp" />)
    expect(screen.getByText("Feed unavailable")).toBeInTheDocument()
    expect(screen.getByText(/no opportunities can be qualified/)).toBeInTheDocument()
    expect(screen.queryByText(/Potential market value/)).not.toBeInTheDocument()
  })
})
