import { describe, expect, it, vi } from "vitest"
import { researchPlayerNews } from "./news"

vi.mock("@/lib/api", () => ({
  apiFetch: vi.fn(),
}))

import { apiFetch } from "@/lib/api"

describe("researchPlayerNews", () => {
  it("POSTs the research input", async () => {
    vi.mocked(apiFetch).mockResolvedValue({
      injury_flag_diff: 0,
      injury_severity_diff: 0,
      form_sentiment_diff: 0,
      coach_change_diff: 0,
      p1_injury_detail: "",
      p2_injury_detail: "",
      p1_form_detail: "",
      p2_form_detail: "",
    })
    await researchPlayerNews({
      player1: "Sinner",
      player2: "Alcaraz",
      surface: "Hard",
    })
    expect(apiFetch).toHaveBeenCalledWith(
      "/api/player-news",
      expect.objectContaining({
        method: "POST",
        body: { player1: "Sinner", player2: "Alcaraz", surface: "Hard" },
      }),
    )
  })
})