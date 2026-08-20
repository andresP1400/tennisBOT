export interface TodaysMatch {
  player1: string
  player2: string
  tournament: string
  surface: string
  commence_time: string
  best_odds: { player1: number; player2: number }
  implied_prob1: number
  implied_prob2: number
  margin: number
  num_bookmakers: number
}

export interface TodaysResponse {
  tour: string
  count: number
  matches: TodaysMatch[]
  error?: string
}

export interface ValueBet {
  side: string
  model_prob: number
  market_prob: number
  edge: number
  best_odds: number
  bookmaker_count: number
}

export interface ValueResponse {
  player1: string
  player2: string
  model_prob1: number
  market_prob1?: number | null
  market_prob2?: number | null
  edge1?: number | null
  edge2?: number | null
  best_odds: { player1: number | null; player2: number | null }
  value_bets: ValueBet[]
  min_edge?: number
  needs_odds_key?: boolean
  message?: string
  error?: string
}

export interface NewsResponse {
  injury_flag_diff: number
  injury_severity_diff: number
  form_sentiment_diff: number
  coach_change_diff: number
  p1_injury_detail: string
  p2_injury_detail: string
  p1_form_detail: string
  p2_form_detail: string
}

export function fmtPct(v: number | null | undefined, digits = 1): string {
  if (v == null || Number.isNaN(v)) return "—"
  return `${(v * 100).toFixed(digits)}%`
}