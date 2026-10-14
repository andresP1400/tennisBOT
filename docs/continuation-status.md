# Verified continuation baseline

The unavailable earlier task reportedly had 80 backend and 17 frontend tests. Inspection found the local `work` branch and GitHub `main` at `207fbd04101cc2cbedbed93d1377e7497dfd0ba7`, with 53 backend and 13 frontend tests. Remote branches/PR refs, local history, reflog, and unreachable-object checks did not expose that task's commits. No unverified model improvements were claimed or reconstructed from test counts. The user subsequently authorized continuing from this verified baseline.

This preservation checkpoint includes strict typing fixes in the Betfair JSON request and LightGBM probability slicing, system fonts for builds without external font downloads, generated-file exclusions, and the reproducible licensed historical-data downloader. Original research notes remain preserved in the onboarding workspace at `/workspace/tennisbot-research`; source provenance is committed under `docs/data-sources`.

The original 53 backend tests, 13 frontend tests, strict mypy (90 source files), frontend TypeScript/ESLint, import smoke tests, production build, and production dashboard/API proxy checks passed before adding the downloader's integrity tests. Synthetic training tests validate code only and are not measured historical prediction performance.

Read-only access to ESPN's public ATP/WTA scoreboards succeeded without sportsbook keys. Their events contain nested singles groupings and competition status/date/player information. Upcoming prediction integration must exclude completed/live/cancelled matches, doubles, and unresolved players, and retain source timestamps. Public availability does not itself grant redistribution rights; provider terms apply. SofaScore access returned HTTP 403.

Actual historical model training, chronological evaluation, calibration, upcoming predictions, and permanent pre-match tracking remain the next phase. No real-data prediction accuracy is claimed at this checkpoint.
