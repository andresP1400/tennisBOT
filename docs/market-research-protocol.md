# Independent model and market research protocol

Declared on 2026-10-16 before evaluating the new candidate study. This project does not establish market-beating performance or promise an 80% win rate. Category win rate and economic performance are separate objectives.

## Fixed initial selection policy

Category A requires calibrated probability >=0.80, decimal odds >=1.40 (American -250 or better), positive conservative EV and all common admission checks. The price threshold is configurable and versioned. Category B has no 80% probability requirement and uses positive conservative EV plus the same admission checks. A match may meet both categories; each category is scored separately and combined portfolio reports must deduplicate it.

Common admission requires source-timestamped pre-match paired odds, at least two independent bookmakers, exact fixture/player binding, history no older than 30 days, sufficient coverage, documented calibration/uncertainty evidence, a conservative probability edge >=0.02 above no-vig consensus, and no material quality concern. Large model/market disagreements (>0.20 probability) require review and are blocked. These constants are declared policy assumptions, not optimized historical profit thresholds. Positive estimated EV is not demonstrated profitability.

EV(p,d)=p*d-1. Conservative EV uses a validated lower probability bound, not the point probability. Fair decimal odds=1/p. Current evidence does not establish individual-match probability intervals; absent reviewed uncertainty evidence means no category admission, even when raw EV is positive. Manual observations are unverified and cannot supply trusted calibration or provider authority.

## Data and timing

Record provider, bookmaker identity, player orientation, fixture ID/start, provider quote time and local observation/recording time. Relay copies of one bookmaker do not count as independent. All decision inputs must exist before the start and as of the decision. Opening is only an explicitly sourced opening quote; first observed is labeled separately. Closing and CLV are evaluation-only and unavailable unless an actual timestamped closing observation exists. Never reconstruct a closing price from a winner or choose a favorable price after seeing results.

Public ticket/money percentages require explicit provider/manual attribution, publication/observation times, scope and exact fixture linkage. These are optional descriptive observations. They do not identify sharp bettors. No incremental performance claim is possible without sufficient chronological split data.

## Model study and untouched evaluation

Current deployed models remain unchanged. Compare fixed logistic, histogram boosting, XGBoost, LightGBM and optional CatBoost candidates using training through 2023 and selection in 2024; calibration uses 2025 only. Equal-weight ensembles must be declared before examining test results. The existing partial-2026 test has already been inspected; scores on it remain retrospective chronological out-of-sample results, not a new untouched test. No candidate is deployed based on those test scores.

Report the >=0.80 selected-winner subset with sample size, selection coverage, mean estimated probability, accuracy and an interval, including empty/poor subsets. Without contemporaneous odds, this subset is not Category A and cannot establish profitability or an 80% hit rate at the requested prices. Do not sweep probability/price filters to find an impressive result.

Reserve prospectively collected observations and a future uninspected period for confirmation. No currently available historical period is certified untouched. Odds, public percentages and closing prices are excluded from the independent statistical model's feature matrix. Injury, exact fatigue/rest, indoor/outdoor and other unavailable fields are not fabricated. Missing CatBoost or authorized market/public-data feeds must be reported as unavailable, not scored as a successful model or integration.
