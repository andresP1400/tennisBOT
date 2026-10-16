import { describe, expect, it } from "vitest"
import { render, screen } from "@testing-library/react"
import type { PersonalPrediction } from "@/types/personal"
import { PersonalEV } from "./personal-ev"

const prediction: PersonalPrediction = {
  fixture: { id: "unit", tour: "atp", player1: "One", player2: "Two", tournament: "Test",
    commence_time: "2026-10-17T12:00:00Z", surface: "Hard", odds1: null, odds2: null },
  model_version: "unit", model_family: "test", prob1: 0.6, prob2: 0.4, winner: "One",
  predicted_at: "2026-10-15T12:00:00Z", data_through: "2025-12-01", warning: null, tracking_id: "unit",
}

describe("guarded expected value", () => {
  it("does not invent EV when quotes are missing", () => {
    render(<PersonalEV prediction={prediction} />)
    expect(screen.getByText("EV unavailable")).toBeInTheDocument()
    expect(screen.queryByText(/Estimated EV/)).not.toBeInTheDocument()
  })

  it("shows why a positive EV cannot be acted on with stale inputs", () => {
    const blocked = { eligible: false, expected_value: 0.2, edge: 0.1, stake_fraction: 0,
      reasons: ["Historical model inputs are stale"] }
    render(<PersonalEV prediction={{ ...prediction, betting_analysis: { player1: blocked, player2: blocked } }} />)
    expect(screen.getByText("Blocked by data guards")).toBeInTheDocument()
    expect(screen.getByText("Estimated EV: 20.0%")).toBeInTheDocument()
    expect(screen.getByText("Historical model inputs are stale")).toBeInTheDocument()
    expect(screen.getByText("Bankroll fraction: 0.00%")).toBeInTheDocument()
  })

  it("selects the winning player's analysis and keeps it informational", () => {
    const blocked = { eligible: false, expected_value: null, edge: null, stake_fraction: 0, reasons: [] }
    const eligible = { eligible: true, expected_value: 0.15, edge: 0.08, stake_fraction: 0.01, reasons: [] }
    render(<PersonalEV prediction={{ ...prediction, winner: "Two",
      betting_analysis: { player1: blocked, player2: eligible } }} />)
    expect(screen.getByText("Passes data guards; informational only")).toBeInTheDocument()
    expect(screen.getByText("Estimated EV: 15.0%")).toBeInTheDocument()
    expect(screen.getByText("Bankroll fraction: 1.00%")).toBeInTheDocument()
  })
})
