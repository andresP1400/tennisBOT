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