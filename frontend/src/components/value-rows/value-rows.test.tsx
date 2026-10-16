import { expect, it } from "vitest"
import { render, screen } from "@testing-library/react"
import { ValueRows } from "."

it("does not insert demonstration picks into an empty result", () => {
  render(<ValueRows candidates={[]} />)
  expect(screen.queryByRole("article")).not.toBeInTheDocument()
})
