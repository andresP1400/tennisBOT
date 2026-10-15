import { describe, expect, it } from "vitest"
import { render, screen } from "@testing-library/react"
import { PersonalRows } from "./personal-rows"
import type { PersonalPrediction } from "@/types/personal"

function prediction(id: string, level: string): PersonalPrediction {
  return {
    fixture: { id, tour: "wta", player1: `One ${id}`, player2: `Two ${id}`, tournament: "Unit fixture",
      tournament_level: level, commence_time: "2026-10-17T12:00:00Z", surface: "Clay", odds1: null, odds2: null },
    model_version: "unit", model_family: "test", prob1: 0.6, prob2: 0.4, winner: `One ${id}`,
    predicted_at: "2026-10-15T12:00:00Z", data_through: "2026-04-21", warning: "History is stale",
    tracking_id: id,
  }
}

describe("forecast validation scope", () => {
  it("shows every WTA 125 warning even when a main-tour forecast appears first", () => {
    render(<PersonalRows predictions={[
      prediction("main", "WTA 1000"), prediction("lower1", "WTA 125"), prediction("lower2", "WTA 125"),
    ]} />)
    expect(screen.getAllByText("WTA 125: accuracy has not been validated at this level.")).toHaveLength(2)
  })

  it("does not add an unvalidated-level warning to supported main-tour forecasts", () => {
    render(<PersonalRows predictions={[prediction("main", "WTA 1000")]} />)
    expect(screen.queryByText(/accuracy has not been validated/)).not.toBeInTheDocument()
    expect(screen.getByText("60.0%")).toBeInTheDocument()
  })
})
