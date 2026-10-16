import type { PersonalFixture } from "@/types/personal"

export interface ValueCandidate {
  fixture: PersonalFixture
  prediction_id: string
  model_version: string
  policy_version: string
  player: string
  probability: number
  decimal_odds: number | null
  bookmaker: string | null
  quote_time?: string | null
  quote_observed_at?: string | null
  no_vig_market_probability: number | null
  probability_edge: number | null
  estimated_ev: number | null
  conservative_ev: number | null
  lower_probability: number | null
  reasons: string[]
  supporting_reasons: string[]
  risks: string[]
}

export interface MarketCard {
  checked_at: string
  valid_until: string
  policy_version: string
  category_a: ValueCandidate[]
  category_b: ValueCandidate[]
  candidates: ValueCandidate[]
  message_a: string
  message_b: string
  provider_status: string
  performance_a: ValuePerformance
  performance_b: ValuePerformance
}

export interface ValuePerformance {
  qualifying_unique_matches?: number
  completed?: number
  pending?: number
  accuracy?: number | null
  paper_roi?: number | null
}
