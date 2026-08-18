/**
 * Shared catalogue of feature groups, their descriptions and whether each
 * group is available at training time or only at inference.
 *
 * The numbers here must match `utils/constants.py` on the Python side
 * and the `ALL_FEATURES` list it exposes.
 */
export type FeatureAvailability = "training" | "inference-only" | "both";

export interface FeatureGroup {
  name: string;
  description: string;
  availability: FeatureAvailability;
  features: string[];
}

export const FEATURE_GROUPS: FeatureGroup[] = [
  {
    name: "Context",
    description: "Match-level context (surface, tournament, round, best-of).",
    availability: "training",
    features: [
      "surface_Hard",
      "surface_Clay",
      "surface_Grass",
      "surface_Carpet",
      "tourney_level_encoded",
      "round_encoded",
      "best_of",
      "indoor_outdoor",
      "altitude",
      "month",
    ],
  },
  {
    name: "Player Diff",
    description: "Per-player demographic / ranking differences.",
    availability: "training",
    features: [
      "ranking_diff",
      "ranking_points_diff",
      "elo_diff",
      "elo_surface_diff",
      "hand_matchup",
      "home_country_flag",
      "qualifier_flag_diff",
    ],
  },
  {
    name: "Rolling Stats",
    description: "Exponentially weighted serve / return stats over last 20 matches.",
    availability: "training",
    features: [
      "ace_pct_diff",
      "df_pct_diff",
      "first_serve_in_pct_diff",
      "win_on_1st_serve_pct_diff",
      "win_on_2nd_serve_pct_diff",
      "bp_saved_pct_diff",
      "bp_converted_pct_diff",
      "first_serve_return_pts_won_pct_diff",
      "second_serve_return_pts_won_pct_diff",
      "return_games_won_pct_diff",
      "win_pct_surface_diff",
      "win_pct_last_10_diff",
      "tiebreak_win_pct_diff",
      "first_set_win_rate_diff",
    ],
  },
  {
    name: "Fatigue",
    description: "Rest, recent court time and short-term match load.",
    availability: "training",
    features: [
      "days_rest_diff",
      "minutes_on_court_last_10_days_diff",
      "matches_last_7_days_diff",
    ],
  },
  {
    name: "Head-to-Head",
    description: "Forward-only H2H win percentage (overall + per surface).",
    availability: "training",
    features: ["h2h_win_pct", "h2h_win_pct_surface"],
  },
  {
    name: "Strength of Schedule",
    description: "Average opponent rank in the last 10 matches.",
    availability: "training",
    features: ["sos_last_10_diff"],
  },
  {
    name: "Odds",
    description:
      "Bookmaker opening / closing odds. Intentionally empty after Model Audit Test #001.",
    availability: "training",
    features: [],
  },
  {
    name: "Weather",
    description: "Real-time weather (Open-Meteo). Historical = archive endpoint.",
    availability: "inference-only",
    features: [
      "temperature_c",
      "wind_speed_kmh",
      "rain_probability",
      "humidity_pct",
      "cloud_cover_pct",
    ],
  },
  {
    name: "Player News",
    description: "GPT-Researcher-extracted injury / form / coach signals.",
    availability: "inference-only",
    features: [
      "injury_flag_diff",
      "injury_severity_diff",
      "form_sentiment_diff",
      "coach_change_diff",
    ],
  },
  {
    name: "Live Odds",
    description: "Live market implied probabilities at prediction time.",
    availability: "inference-only",
    features: ["live_implied_prob1", "live_implied_prob2", "live_margin"],
  },
];

export const TRAINING_FEATURE_COUNT = FEATURE_GROUPS.flatMap((g) =>
  g.features,
).length;

export const INFERENCE_ONLY_FEATURE_COUNT = FEATURE_GROUPS.filter(
  (g) => g.availability === "inference-only",
).flatMap((g) => g.features).length;
