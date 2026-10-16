import { describe, expect, it } from "vitest"
import { render, screen } from "@testing-library/react"
import { ValueSummary } from "."

describe("ValueSummary", () => {
  it("keeps absent returns and accuracy unmeasured", () => {
    render(<ValueSummary performance={{ completed: 0, pending: 0, accuracy: null, paper_roi: null }} />)
    expect(screen.getByText(/Accuracy unmeasured; unit-stake paper ROI unmeasured/)).toBeInTheDocument()
  })
  it("shows losses and category accuracy independently", () => {
    render(<ValueSummary performance={{ completed: 5, pending: 2, accuracy: .8, paper_roi: -.12 }} />)
    expect(screen.getByText(/5 completed, 2 pending. Accuracy 80.0%; unit-stake paper ROI -12.0%/)).toBeInTheDocument()
  })
})
