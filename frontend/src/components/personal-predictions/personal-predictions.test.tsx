import { describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import { PersonalPredictions } from "./personal-predictions"
import { usePersonalPredictions } from "@/hooks/usePersonalPredictions"

vi.mock("@/hooks/usePersonalPredictions", () => ({ usePersonalPredictions: vi.fn() }))

describe("PersonalPredictions", () => {
  it("shows unavailable data without inventing a prediction", () => {
    vi.mocked(usePersonalPredictions).mockReturnValue({ card: {
      tour: "atp", model_version: null, fetched_at: "2026-10-14", predictions: [], unavailable: [],
      message: "No covered upcoming matches", backtest: {},
    }, loading: false, error: null, refresh: vi.fn() })
    render(<PersonalPredictions />)
    expect(screen.getByText("No covered upcoming matches")).toBeInTheDocument()
    expect(screen.queryByText(/50\.0%/)).not.toBeInTheDocument()
  })

  it("renders recorded probabilities, measured accuracy, and stale-data warnings", () => {
    vi.mocked(usePersonalPredictions).mockReturnValue({ card: {
      tour: "atp", model_version: "test-version", fetched_at: "2026-10-14", unavailable: [], message: null,
      backtest: { test_2024_2025: { ml_calibrated: { accuracy: 0.65, matches: 1000, brier: 0.21, log_loss: 0.61 } } },
      live_performance: { completed: 0, pending: 2, void: 0, accuracy: null },
      overall_live_performance: { completed: 3, accuracy: 1 / 3 },
      predictions: [{ fixture: { id: "unit-test", tour: "atp", player1: "One", player2: "Two",
        tournament: "Test", commence_time: "2026-10-15T15:00:00Z", surface: "Hard", odds1: null, odds2: null },
        model_version: "test-version", model_family: "test", prob1: 0.7, prob2: 0.3, winner: "One",
        predicted_at: "2026-10-14T15:00:00Z", data_through: "2025-12-01", tracking_id: "record-123",
        warning: "Historical results are stale" }],
    }, loading: false, error: null, refresh: vi.fn() })
    render(<PersonalPredictions />)
    expect(screen.getByText("70.0%")).toBeInTheDocument()
    expect(screen.getByText("Historical results are stale")).toBeInTheDocument()
    expect(screen.getByText(/65\.00% accuracy/)).toBeInTheDocument()
    expect(screen.getByText("Not available")).toBeInTheDocument()
    expect(screen.getByText(/Record: record-123/)).toBeInTheDocument()
    expect(screen.getByText(/Live results for this model: accuracy not yet measured/)).toBeInTheDocument()
    expect(screen.getByText(/All recorded model versions, first forecast per match: 33.33% accuracy/)).toBeInTheDocument()
  })
})
