export interface PersonalFixture {
  id: string
  tour: string
  player1: string
  player2: string
  tournament: string
  commence_time: string
  surface: string | null
  odds1: number | null
  odds2: number | null
  tournament_level?: string | null
}

export interface PersonalPrediction {
  fixture: PersonalFixture
  model_version: string
  model_family: string
  prob1: number
  prob2: number
  winner: string
  predicted_at: string
  data_through: string
  warning: string | null
  tracking_id: string
  betting_analysis?: { player1: PersonalBettingAnalysis; player2: PersonalBettingAnalysis } | null
}

export interface PersonalBettingAnalysis {
  eligible: boolean
  expected_value: number | null
  edge: number | null
  stake_fraction: number
  reasons: string[]
}

export interface MeasuredMetrics {
  accuracy: number
  matches: number
  brier: number
  log_loss: number
}

export interface PersonalCard {
  tour: string
  fetched_at: string
  model_version: string | null
  predictions: PersonalPrediction[]
  unavailable: { fixture: PersonalFixture; reason: string }[]
  message: string | null
  backtest: {
    test_2024_2025?: { ml_calibrated: MeasuredMetrics }
    evaluation?: { period: string; metrics: MeasuredMetrics }
  }
  live_performance?: {
    completed: number
    pending: number
    void: number
    accuracy: number | null
  }
  overall_live_performance?: {
    completed: number
    accuracy: number | null
  }
}
