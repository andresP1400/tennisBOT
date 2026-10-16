# Surface-context ablation protocol

Declared October 16, 2026 before running this extension. Existing deployed models, historical reports, category thresholds and private forecasts remain unchanged.

Compare the existing fixed 20-feature research logistic model with the same logistic model plus five signed differences: surface serve-point win rate, surface return-point win rate, surface recent result rate, log prior surface-match count, and log days since the latest known tournament start. Surface point/result summaries use at most the last 20 matured matches on that surface. Missing rates/dates remain missing and preprocessing learns imputation within training only. Inactivity is an observed-history proxy, not verified rest, fatigue or injury.

Every result becomes available 21 days after tournament start, matching the existing conservative protocol. Read features before queuing the current result. Do not update surface summaries from future, current, or unmatured outcomes. Retain observed point counts and skip partial/contradictory statistics. Verify alignment with the baseline dates, labels, surface and pre-event counts before fitting.

Fixed logistic C=0.1, max_iter=500, seed=42; train through 2023, compare 2024 raw log loss, calibrate independently on 2025 only, score inspected partial-2026 data. Mirror training rows and symmetrize before calibration; preserve the existing symmetric coverage-sum context when reversing. Both models use training-only imputation/scaling, with missing indicators. No threshold/hyperparameter sweeps, test-score selection or automatic deployment. Keep both good and bad results and paired date-block intervals.

The partial-2026 period is already inspected. These are retrospective out-of-sample measurements, not newly untouched confirmation or evidence of betting returns. No prices enter model features. Future uninspected prospective data remains necessary. Save timestamped reports and research artifacts privately without overwriting a previous study or a deployed pointer.
