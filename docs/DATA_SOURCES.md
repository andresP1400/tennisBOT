# Data sources

## Current source (in use)

ATP & WTA match data is pulled from a maintained mirror of the Sackmann layout:

- **Repo:** https://github.com/Artur73737/ATP-WTA_DATA
- **Raw base:** `https://raw.githubusercontent.com/Artur73737/ATP-WTA_DATA/main`
- **Layout:**
  - `raw/atp/atp_matches_<YYYY>.csv`, `raw/atp/atp_players.csv`, `raw/atp/odds/<YYYY>.xlsx`
  - `raw/wta/...` same pattern
- Coverage: **1968–2026** (ATP & WTA)

Configured in `config.py` (`DATA_REPO_BASE`, `ATP_REPO_BASE`, `WTA_REPO_BASE`).

## Original source (deprecated)

Jeff Sackmann's public tennis repositories were removed around June 2026:

- ATP: `https://github.com/JeffSackmann/tennis_atp` → **404**
- WTA: `https://github.com/JeffSackmann/tennis_wta` → **404**

## Odds

Bookmaker odds (`raw/{tour}/odds/<YYYY>.xlsx`) originate from
http://www.tennis-data.co.uk. The downloader tries the mirror first, then
the live tennis-data.co.uk site.
