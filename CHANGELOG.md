# Changelog

Tutte le modifiche rilevanti al progetto tennisBOT sono documentate in questo file.

Il formato segue [Keep a Changelog](https://keepachangelog.com/it/1.1.0/),
e questo progetto aderisce al [Semantic Versioning](https://semver.org/lang/it/).

## [Unreleased]

### Added
- `features/oddsportal_scraper.py`: scraper OddsPortal end-to-end senza login.
  Decifra i payload `backend.oddsportal.com` (PBKDF2+AES-CBC+gunzip),
  estrae gli eventi tennis dalla home (payload RSC), per ogni match scarica
  il market winner con odds attuali + opening per bookmaker, e salva
  JSONL/CSV in `data/raw/{tour}/odds_portal/`.
- `features/oddsportal_scraper.py`: mappatura COMPLETA dei 13 bookmaker
  OddsPortal scoperta via endpoint `ajax-providers-bonus-data` (888sport,
  bet365.it, BetflagIT, BetssonIT, bwin.it, Eurobet.it, GoldBet,
  Lottomatica, Netwin, Planetwin365, Sisal, SNAI, WilliamHill.it) —
  risolti tutti gli ID precedentemente sconosciuti; `providers.json`
  salvato ad ogni scrape. Chiarito che BetssonIT/BetflagIT/Lottomatica/
  Planetwin365/Netwin condividono lo stesso feed quote (gruppo SKS).
- `features/betfair_volume.py`: polling del volume exchange Betfair via
  `graphs.betfair.com/loadRunnerChart` (niente login): `parse_runner_chart`
  (formato `{"points": [[ts, price, amount], ...], "factor": n}` verificato
  live), `get_runner_snapshot`, `poll_volume`, `summarize_polls` (volume
  velocity + steam flag). `find_tennis_events()` risolve gli eventi tennis
  correnti da betfair.it (selectionId PPB globali, condivisi con
  l'exchange UK) + CLI `--find`.
- `features/betfair_historical.py`: client CLV storico basato
  sull'exchange Betfair via TheOddsAPI (`betfair_ex_eu`, stessa liquidità
  dell'exchange UK per il tennis) + Matchbook (2° exchange) + Pinnacle.
  Snapshot JSONL giornalieri (`data/raw/betfair_exchange/`), `closing_odds`
  (ultimo back pre-inizio), `compute_clv`, CLI `--snapshot/--loop/--report`.
  Copre il gap lasciato dal servizio BASIC di Betfair (estinto).
- `pipeline/track.py`: `summary()` ora include `avg_odds_edge`
  (p_pred * odds presa - 1) su tutte le predizioni loggate.
- `api_server.py`: `_autofill_odds()` riempie odds mancanti nella request
  di `/api/predict` con il mercato live (best_odds da `LiveOddsScraper`),
  e le odds (autofill o fornite) sono esposte nel risultato e nel track log.

### Fixed
- `features/odds.py`: rigenerate le mappature colonne legacy dei file
  tennis-data 2001-2014 (CB/CBL, GBW/GBL, IWW/IWL, SBW/SBL, EXW/EXL,
  LBW/LBL, UBW/UBL, SJW/SJL) — prima il 95% dei match 2001-2013 veniva
  scartato dal merge odds. `_add_synthetic_avg` ora calcola la media
  per-riga (25.660 righe legacy riempite, non più valore costante).
  Aggiunto supporto BFEW/BFEL (Betfair Exchange, 2025+) e mappa
  `ps_w/ps_l` con alias retrocompatibile `pinnacle_w/pinnacle_l`.
  Priorità opening: Pinnacle → Betfair Exchange → Bet365 → Avg;
  priorità closing: Avg → Max → Pinnacle. Fix E741 (`l` → `loss`).
- `pipeline/track.py`: `_HASH_FIELDS` esteso con `odds1`/`odds2`
  (il log non perde più l'edge di prezzo quando le odds cambiano).
- CRITICO: TheOddsAPI rifiuta TUTTI gli header di autenticazione
  (`X-Api-Key`, `apiKey`, `x-api-key`, `APISECRET` → 401 MISSING_KEY,
  verificato live 2026-08-14) e accetta solo `?apiKey=` nel query string.
  Tutte le 6 call site (3 in `live_odds.py`, 2 in `odds_aggregator.py`,
  1 in `api_server.py`) usavano l'header — il modulo live odds risultava
  rotto in produzione. Portate a query param; test di regressione
  `test_theoddsapi_uses_x_api_key_header` riscritto per blindare il fix.
  `docs/SECURITY.md` e `PROJECT_STATUS_REPORT.md` aggiornati di pari passo.

### Changed
- Riaddestrato ATP e WTA con le odds come features (dataset rigenerati
  con le mappature legacy fixate; coverage opening 55%, closing 69%):
  - ATP (`atp_model_odds.pkl`): AUC 0.744, Accuracy 67.85%, Brier 0.205,
    ECE 0.0317. CLV medio +1.52% (94.6% beat rate). Edge-band >10%:
    ROI +15.48% fuori campione.
  - WTA (`wta_model_odds.pkl`): il modello BATTE il mercato di chiusura
    (logloss 0.5825 vs 0.5834). CLV medio +1.36% (92.2% beat rate).
    Edge-band >10%: ROI +26.12%, hit rate 67.4%.
- `features/odds.py` ora accetta anche i nuovi file odds annuali
  (2001-2026) senza eccezioni su colonne mancanti.

### Notes
- Test suite: 44/44 PASS (prima 24/24), ruff 0 errori, tsc 0 errori.

## [2.1.0] - 2026-06-19

### Real-data training results (ATP, 2000-2024)

End-to-end training on real Jeff Sackmann data was executed after the v2.1
hardening:

```
TEST SET (2024, 2973 single matches):
  Brier Score:  0.16009
  Log-loss:     0.49270
  ROC-AUC:      0.84839
  Accuracy:     77.36%

VALIDATION SET (2022-2023, 5716 single matches):
  Brier Score:  0.16846
  Log-loss:     0.51124
  ROC-AUC:      0.83060
  Accuracy:     75.66%
```

Top features (no leakage indicators): `ranking_points_diff`,
`ranking_diff`, `elo_diff`, `sos_last_10_diff`,
`second_serve_return_pts_won_pct_diff`. All within the expected
physiological domain.

### Code quality after real-data run

- `ruff check .` -> 0 errors
- `eslint web/src` -> 0 errors, 0 warnings
- `tsc --noEmit` -> 0 errors
- `next build` -> 17 routes compiled, 0 errors
- `pytest tests/` -> 24/24 passing

### Added
- `tennisBOT-main/backend/exceptions.py` con eccezioni custom di dominio.
- `tennisBOT-main/backend/logging_config.py` con configurazione JSON strutturata.
- `tennisBOT-main/.env.example` come template delle variabili ambiente richieste.
- `docs/SECURITY.md` documenta l'incidente di leak della ODDS_API_KEY
  e la procedura di rotazione.
- `scripts/security/check_no_secrets.py` per prevenire leak futuri
  di chiavi in CI / pre-commit.
- `smoke_test.py` (import check di tutti i moduli) e `smoke_train.py`
  (training end-to-end con dati sintetici).
- 24 unit test in `tests/test_tennisbot.py` inclusi regression test
  per il bug Platt calibration e per il path traversal.
- `.github/workflows/ci.yml` con ruff + mypy + pytest + Next.js build.
- `requirements-dev.txt` per lint / type / test.
- Pagine frontend funzionanti (non più placeholder):
  - `/dashboard/data`  legge `/api/history`
  - `/dashboard/players` aggrega statistiche per giocatore
  - `/dashboard/settings` con preferenze in localStorage
  - `/dashboard/features` lista 37 + 12 feature (single source of truth
    in `web/src/lib/features.ts`)
  - `/dashboard/reports` mostra i PNG e `metrics_summary.csv`
  - `/dashboard/live` aggrega `/api/todays-matches`,
    `/api/value-bets` e `/api/player-news`
- Endpoint backend `/api/metrics` che espone `metrics_summary.csv`.
- Endpoint backend `/api/charts?tour=` che elenca i PNG per tour.
- Supporto `?tour=atp|wta` nella route `/api/charts/[name]`.
- `next.config.ts` con rewrite proxy `/api/* -> backend` e
  `output: "standalone"`.

### Changed
- `pipeline/calibration.py`: `IsotonicRegression.predict` sostituito con
  `LogisticRegression` Platt come default. Risolto bug critico per cui
  `calibrator.predict` ritornava la classe (0/1) invece della probabilità
  calibrata, producendo output sempre binari per l'API `/api/predict`.
- `pipeline/calibration.py`: rimossi parametri `y_min`/`y_max` deprecati in
  sklearn >= 1.4.
- `pipeline/training.py`: file interamente re-indentato. Il corpo di tutte le
  funzioni era a colonna 0 (file sintatticamente valido ma non eseguibile
  nei workflow reali a causa dello stile distrutto).
- `pipeline/evaluation.py`: il valore di `testMatches` per il set VAL usa
  ora `len(y_val)` invece di `len(y_test)` (era un copia-incolla).
- `pipeline/evaluation.py`: SHAP usa l'imputer fittato sul train set invece
  di rifittarlo sul test set (data leakage su metriche SHAP).
- `features/elo.py`: con superficie sconosciuta il rating cade sul globale
  invece di restituire il valore di default (1500).
- `features/fatigue.py`: `np.isnan(mins)` protetto per gestire `pd.NA`
  e `pd.NaT`.
- `features/builder.py`: `load_odds_data` riceve il parametro `tour` per
  evitare odds ATP su run WTA.
- `features/weather.py`: supporto all'endpoint archive per dati storici
  (`v1/archive`) affiancato al forecast (`v1/gfs`).
- `features/live_odds.py`: fallback scraping Pinnacle/OddsPortal/TennisExplorer
  disabilitato di default (codice morto in produzione, geo-bloccato IT).
- `features/live_odds.py`: rimosso no-op `_fetch_pinnacle_api`.
- `features/live_odds.py`: regex mojibake del match_pattern corretto.
- `features/live_odds.py`: `datetime.utcnow()` sostituito con
  `datetime.now(timezone.utc)`.
- `features/player_news.py`: `asyncio.get_event_loop()` sostituito con
  `asyncio.run()` per evitare DeprecationWarning su Python 3.12+.
- `api_server.py`: input `model` validato con whitelist prima di essere
  usato come path (previene path traversal).
- `api_server.py`: `.str.endswith("_A")` con `na=False` per evitare crash
  su match_id nulli.
- `api_server.py`: CORS configurato con origini espliciti invece di `["*"]`.
- `api_server.py`: import morti rimossi (`threading`, `json`, `REPORTS_DIR`).
- `start_all.py`: emoji rimosse per rispettare AGENTS.md.

### Fixed
- **Sicurezza** Path traversal in `web/src/app/api/charts/[name]/route.ts`
  sanificato con validazione del nome file (whitelist) prima del join.
- **Sicurezza** `.env` rimosso e aggiunto `.env.example` + `.gitignore` per
  evitare leak della `ODDS_API_KEY`. La chiave committata deve essere
  ruotata.
- **Sicurezza** `@dnd-kit` versioni allineate (`core@^10`, `sortable@^10`,
  `modifiers@^9`, `utilities@^3`) per evitare runtime crash e peer dep
  warning.
- **Sicurezza** API key TheOddsAPI passata via header invece che in
  query string.
- **Frontend** `<ThemeProvider>` aggiunto a `layout.tsx` per supportare
  `useTheme()` in `sonner.tsx`.
- **Frontend** URL backend sostituiti con variabile ambiente
  `NEXT_PUBLIC_API_URL` (5 punti hardcoded `localhost:8000`).

### Removed
- `fix_calib.py`: duplicato di `pipeline/calibration.py`, rimosso.
- `features/builder.py`: funzione `_map_row` mai chiamata (logica
  vettorizzata presente più sotto).
- `features/elo.py`, `h2h.py`, `context.py`, `split.py`, `player.py`:
  `import numpy as np` mai usato rimosso.
- `config.py`: `PROJECT_ROOT`, `DATA_DIR`, `ROLLING_WINDOWS`,
  `TOURNEY_LEVEL_MAP` mai usati, rimossi.
- `features/live_odds.py`: `ATP_TOURNAMENT_KEYS`, `WTA_TOURNAMENT_KEYS`
  mai usate (la lista sport keys viene ora risolta dinamicamente via API).

### Added (Security)
- `web/src/app/error.tsx` e `web/src/app/dashboard/error.tsx`: error
  boundary globale per intercettare crash runtime (es. Toaster con
  `useTheme` senza ThemeProvider).
- `web/src/lib/api.ts`: client API centralizzato con `ApiError` e base
  URL configurabile via `NEXT_PUBLIC_API_URL`.
- `web/next.config.ts`: rewrite proxy `/api/*` -> backend + `output:
  "standalone"` per build produzione.

### Migration Notes
- Il training produceva probabilita binarie (0/1) a causa di
  `IsotonicRegression.predict()`. I modelli `.pkl` esistenti vanno
  riaddestrati con la nuova calibrazione Platt per beneficiare del
  fix. Fino ad allora l'API continuera a mostrare valori anomali.
  v2.1 include uno smoke training (`smoke_train.py`) e un test
  regression (`test_training_pipeline_runs_end_to_end_with_synthetic_data`)
  che verificano la presenza di almeno 5 valori unici continui.
- La ODDS_API_KEY committata in `.env` deve essere ruotata:
  1) rigenerare la chiave su https://the-odds-api.com
  2) aggiornare `local.env` (NON committato)
  3) NON aggiungere `.env` al repository
  Il vecchio file `.env` e stato rimosso in v2.1; vedi `docs/SECURITY.md`.

## [2.0.0] - 2026-06-09

### Added
- Modulo `features/weather.py` con Open-Meteo GFS.
- Modulo `features/player_news.py` con regex su DuckDuckGo.
- Modulo `features/live_odds.py` con TheOddsAPI.
- 12 nuove feature in `ALL_FEATURES` (49 totali).
- Endpoint FastAPI: `/api/weather`, `/api/todays-matches`,
  `/api/value-bets`, `/api/live-odds`, `/api/player-news`,
  `/api/odds-api-status`.
- Test E2E Arnaldi vs Cobolli con edge +40.6% rilevato.

### Changed
- Modello addestrato su 37 feature storiche (AUC 0.8478).
