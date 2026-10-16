# Surface-context research continuation

Completed October 16, 2026, approximately 2:12 p.m. America/Toronto. The [predeclared protocol](context-research-protocol.md) adds surface-specific serve/return, recent results, surface sample size and an observed-inactivity proxy to the existing research logistic baseline. These are research artifacts, not deployed model replacements.

The existing 44-file history, 21-day result-availability embargo and annual train/selection/calibration/test splits were reused. Training preprocessing is separate from selection/test data. Missing surface rates/dates stay missing until training-only imputation. Neither current match outcomes nor immature results enter context features. The global/surface Elo and deployed source fingerprints remain unchanged.

| Tour / fixed logistic model | 2024 selection log loss | Partial-2026 matches | Test accuracy | Test Brier | Test log loss | Test ECE |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| ATP original research baseline | 0.60946 | 1,406 | 65.79% | 0.21200 | 0.61100 | 0.03043 |
| ATP with surface context | 0.60558 | 1,406 | 65.93% | 0.21073 | 0.60851 | 0.02901 |
| WTA original research baseline | 0.61377 | 957 | 66.56% | 0.21009 | 0.60627 | 0.03242 |
| WTA with surface context | 0.61091 | 957 | 66.67% | 0.20956 | 0.60479 | 0.03442 |

Both tours select surface context using only 2024 raw log loss. The baseline reproduces the earlier fixed logistic study. Test Brier/log-loss point estimates improve slightly, but WTA ECE worsens. Approximate paired tournament-date-block 95% log-loss-difference intervals (context minus baseline) are ATP [-0.00852, +0.00294] and WTA [-0.00394, +0.00093]. Accuracy and Brier difference intervals also include zero. This does not establish a reliable improvement or betting advantage, so no active model pointer or old artifact was changed.

The comparison is against the **fixed 20-feature research logistic**, not necessarily the active deployed model family. No candidate was selected using its 2026 performance. The 2026 period was already inspected before this extension; these are retrospective chronological out-of-sample results and not new untouched confirmation. No new sportsbook prices, ROI, CLV or prospective Category A/B success were measured. Existing category filters and sparse-uncertainty guards remain intact.

The [aggregate report](model-validation/context-study-20261016.json) retains both arms, high-confidence probability-only subsets, paired intervals, source audits, artifact hashes and the research implementation fingerprint. Fitted models/calibrators are saved privately in a new timestamped directory under `reports/personal/context-study-*`, alongside the full report. Reproducing the study creates another directory instead of overwriting artifacts:

```bash
PYTHONPATH=backend/src OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 python -m pipeline.context_study
```

No extra packages are required beyond the existing core environment. This study does not install CatBoost, re-run the previous five-family search, or change serving behavior. Tests exercise maturity boundaries, surface isolation, missing/partial point counts, current-outcome invariance, canonical alignment, reversal, train-only transforms/calibration and model-artifact reload/preservation. The full backend suite now passes 211 tests; strict mypy checks 137 source files including the launcher. Black/Ruff and dependency checks pass. No frontend source changed; its earlier 34 tests and production build are the retained baseline, not newly re-run checks.

Fresh-history investigation also continued: current metadata for the reviewed Kadantte ATP and VictorSquidWei WTA mirrors returns the same last-2026-file revisions already pinned in the manifests (`712be0c5...` / `85ef6efa...`). No newer history was acquired or assumed. October player state, exact match-time fatigue/injury data, complete tournament coverage and priced historical validation remain outstanding.

See [private preservation](private-preservation.md) for the distinction between source pushed to GitHub, published environment versions, private workspace archives and an independently verified off-machine backup. Publishing before this continuation cannot by itself preserve its later research files or future predictions.
