import { describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import { SectionCards } from "./section-cards"

vi.mock("@/services/analytics", () => ({
  getMetricsRows: vi.fn(),
}))

import { getMetricsRows } from "@/services/analytics"

describe("SectionCards", () => {
  it("renders four metric cards with placeholder when no data", () => {
    vi.mocked(getMetricsRows).mockResolvedValue([])
    render(<SectionCards />)
    expect(screen.getByText("ROC-AUC")).toBeInTheDocument()
    expect(screen.getByText("Accuracy")).toBeInTheDocument()
    expect(screen.getByText("Brier Score")).toBeInTheDocument()
    expect(screen.getByText("Dataset size")).toBeInTheDocument()
  })

  it("renders parsed metric values from the service", async () => {
    vi.mocked(getMetricsRows).mockResolvedValue([
      { metric: "auc", test: 0.75, val: 0.7 },
      { metric: "accuracy", test: 0.7, val: 0.68 },
      { metric: "brier", test: 0.21, val: 0.22 },
      { metric: "logloss", test: 0.55, val: 0.57 },
      { metric: "totalMatches", test: 1000, val: 1000 },
      { metric: "testMatches", test: 200, val: 200 },
    ])
    render(<SectionCards />)
    expect(await screen.findByText("0.7500")).toBeInTheDocument()
  })
})