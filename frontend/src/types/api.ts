/**
 * Tipi condivisi delle risposte API del backend FastAPI.
 * Regola AGENT: tipi globali in src/types/, proibito `any`.
 */

export interface HealthStatus {
  status?: string
}

export interface ModelsResponse {
  models: string[]
}

export interface OddsApiStatus {
  configured?: boolean
  message?: string
  remaining_requests?: string
  tennis_tournaments?: number
}

export interface PredictResponse {
  match: string
  surface: string
  model_used: string
  prob1: number
  prob2: number
  winner: string
  info?: string
  reliability?: string
  reliability_notes?: string[]
  h2h?: { p1_win_pct: number | null; total_matches: number }
  elo?: {
    p1: number | null
    p2: number | null
    p1_surface_blend?: number | null
    p2_surface_blend?: number | null
  }
  data_through?: string
  error?: string
}

export interface PredictRequest {
  player1: string
  player2: string
  surface: string
  model: string
}

export interface ChartInfo {
  name: string
  file: string
  exists: boolean
}

export interface ChartsResponse {
  tour: "atp" | "wta"
  charts: ChartInfo[]
}

export interface MetricsRow {
  metric: string
  test: number
  val: number
}

export interface TrackRecord {
  id: string
  ts: string
  player1: string
  player2: string
  surface: string
  prob1: number
  predicted_winner: string
  reliability: string | null
  settled: boolean
  actual_winner: string | null
  correct: boolean | null
  match_date?: string | null
}

export interface TrackSummary {
  total?: number
  settled?: number
  open?: number
  correct?: number
  accuracy?: number | null
  brier?: number | null
}

export interface TrackResponse {
  summary?: TrackSummary
  records?: TrackRecord[]
  error?: string
}

export interface TrainingStatus {
  is_training: boolean
  current_task: string
  progress: number
  logs: string[]
  error: boolean
  success: boolean
}

export interface TrainStartRequest {
  tour: string
  trials: number
  startYear: number
  endYear: number
}

// --- Live odds / value bets / player news ---

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
  error?: string
}

// --- Automatic daily card ---

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
  predictions: CardPrediction[]
  n_logged?: number
  n_value_bets?: number
  model_used?: string | null
  min_edge?: number
  message?: string
  error?: string
}

// --- History (raw training-set matches with predictions) ---

export interface HistoryMatchRow {
  id: string
  date: string
  tournament: string
  surface: string
  player1: string
  player2: string
  prob1: number
  prob2: number
  winner: string
  p1_fav?: boolean
  correct?: boolean | null
}

export interface HistoryResponse {
  matches: HistoryMatchRow[]
  error?: string
}

// --- System / dashboard panels ---

export interface SystemStatus {
  status: string
  service: string
}

export interface PlayerStats {
  player1: string
  player2: string
  match_count_p1: number
  match_count_p2: number
}