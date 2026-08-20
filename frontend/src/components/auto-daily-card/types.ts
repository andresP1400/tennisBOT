export interface CardPrediction {
  match: string
  player1: string
  player2: string
  tournament: string
  surface: string
  commence_time: string
  prob1: number
  prob2: number
  winner: string
  reliability: string
  odds1: number | null
  odds2: number | null
  edge1: number | null
  edge2: number | null
  value_bet: { player: string; odds: number; edge: number } | null
  weather?: {
    temperature_c?: number | null
    humidity_pct?: number | null
    rain_probability?: number | null
    wind_speed_kmh?: number | null
  }
  context?: {
    p1_rank?: number | null
    p2_rank?: number | null
    p1_form?: string | null
    p2_form?: string | null
    p1_ret?: boolean | null
    p2_ret?: boolean | null
    p1_age?: number | null
    p2_age?: number | null
    p1_last_match_date?: string | null
    p2_last_match_date?: string | null
  }
  error?: string
}

export interface CardResponse {
  tour: string
  count: number
  n_value_bets: number
  n_logged: number
  model_used: string | null
  min_edge: number
  predictions: CardPrediction[]
  message?: string
  error?: string
}