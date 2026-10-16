# Changelog

Tutte le modifiche rilevanti al progetto tennisBOT sono documentate in questo file.

Il formato segue [Keep a Changelog](https://keepachangelog.com/it/1.1.0/),
e questo progetto aderisce al [Semantic Versioning](https://semver.org/lang/it/).

## [Unreleased]

### Added
- Research-only surface serve/return, recent-result and observed-inactivity ablation with delayed chronology, fold-local missing-value preprocessing, immutable experimental artifacts and paired evaluation; deployed models remain untouched.
- Private preservation guide distinguishing GitHub source, published environment state and independently recoverable model/ledger copies, with checksum and non-overwriting recovery instructions.
- Separate high-confidence/value dashboard categories with versioned filters, conservative net EV, quote expiry and explicit missing-evidence reasons.
- Opt-in, persistently request-budgeted multi-book moneyline adapter with exact fixture binding, source timestamps, paired no-vig consensus and immutable price/split/selection archives.
- Category-specific paper performance, real-price benchmarks, explicit-closing-only CLV, date-block return intervals and planned 100/250/500/1000-pick checks retaining losing picks.
- Reproducible five-family chronological ML/ensemble study with paired deployed-model comparisons and guarded version-specific calibration-bin evidence; no candidate deployment or profitability claim.
- Public ticket/money manual-entry and provider contracts with provenance/timing validation; unsupported public-data effects remain unmeasured.
- Real-data daily-use readiness audit and step-by-step local Mac setup, startup, monitoring and private-backup instructions.
- Inspectable ATP/WTA prediction/settlement poller health with attempt, success, error-class and missed-cycle timestamps.
- Reviewed 2026 WTA surfaces for Osaka, Ningbo, and Rio with official calendar/provider identity evidence and existing WTA 125 validation safeguards.
- Reviewed partial-2026 ATP/WTA data extension with 2,464 additional licensed records, original manifest snapshots, and hash-named local acquisition reviews.
- Annual train/selection/calibration/test protocols, five-year chronological walk-forward reports, paired date-block uncertainty intervals, and historical minimum-player-coverage metrics.
- Explicit 2026 evaluation labels for deployed models and visible per-row WTA 125 validation warnings.
- Reproducible raw/eligible history suitability reports for serving-count completeness, missing demographics, and player identities; existing audit files are never overwritten.
- Reviewed 2026 WTA surface coverage for Mallorca, Rovereto, and Lisbon with explicit cross-provider IDs, name/season checks, and WTA 125 accuracy/EV safeguards.
- Forecast snapshots retain changed surface provenance and tournament level without overwriting earlier records.
- Opponent-adjusted result/serve/return residuals using frozen pre-event baselines, optional recent-form ablation, and auditable feature-schema/runtime metadata in versioned ATP/WTA models.
- Regression tests for fold-local preprocessing, chronological mirrors, consistent live calibration, paired bookmaker consensus, bounded EV admission, and artifact reload/preservation.
- Dashboard details for informational EV, missing quotes, zero-stake guard failures, and their reasons.
- Append-only live outcome settlement, void handling for retirements/defaults, and separate current-model/all-version live performance on the dashboard.
- Personal ATP/WTA prediction engine with global/surface Elo, lightweight model selection on 2022, probability calibration on 2023, and chronological held-out 2024–2025 evaluation.
- Genuine upcoming singles forecasts on the dashboard, unavailable-match explanations, measured accuracy, and stale-history warnings.
- Automatic five-minute private pre-match tracking with immutable SQLite events, model versions, probabilities, and observed odds when available.
- Reproducible ATP/WTA research-data restoration with pinned revisions, SHA-256 verification, original CC BY-NC-SA attribution, and preservation of existing files.
- Integrity tests for malformed data, corrupt downloads, and repeat downloads that preserve local files.

### Security
- CSRF guard sugli endpoint mutanti: nuovo middleware
  `block_cross_site_writes` in `backend/src/api_server.py` che rifiuta con
  `403` ogni `POST/PUT/PATCH/DELETE` il cui header `Origin` non è nella
  allow-list. Il CORS impedisce di *leggere* le risposte cross-origin, ma il
  browser inviava comunque la richiesta (sufficiente a innescare
  `/api/train/start` o `/api/reload`); ora è bloccata. Le chiamate
  server-to-server (proxy Next.js, CLI) non inviano `Origin` cross-site e
  passano. Coperto da due test in `test_tennisbot.py`.
- Hardening di `resolve_model_path` (`backend/src/api/predict_core.py`):
  il controllo di contenimento sotto `MODELS_DIR` usa ora
  `Path.relative_to` invece del fragile confronto di prefisso di stringa
  (che avrebbe accettato un sibling tipo `models_evil`). Comportamento
  invariato per i nomi validi; il regex già impediva il traversal.

### Fixed
- Personal-use launcher checks HTTP readiness, supports private standalone production startup, supervises both services, and cleans up owned children on errors or shutdown.
- Failed dashboard refreshes clear old forecast cards; requests have a 25-second deadline and bypass browser caches.
- Dashboard labels the separate legacy model/metrics/track panels so they cannot be confused with personal forecasts.
- Upcoming schedules query a rolling seven-day range instead of only today's tournaments, retaining the exact time horizon and original quote observation times.
- Production startup instructions use the configured Next.js standalone server with its public/static assets.
- Historical restoration follows only reviewed manifest years instead of stopping unconditionally at 2025; unsupported years still fail without overwriting source files.
- Single-class evaluation now reports undefined AUC and computes valid binary log-loss instead of inventing an AUC score.
- Serving/returning summaries skip partial, nonfinite, negative, or contradictory point counts instead of treating missing points won as zero.
- Legacy raw cleaning no longer fills missing ages/heights with full-dataset means; demographic imputation is deferred to training folds.
- Legacy stacking now tunes and stops inside each outer training fold, refits transforms per fold, and shares symmetrization/calibration order across evaluation, history, and inference.
- Adaptive temporal splits keep full dates and match mirrors together; fully missing training columns are retained.
- Bookmaker consensus now de-vigs paired quotes per book, deduplicates relays, and preserves player orientation; TheOddsAPI no longer creates fictitious cross-book price pairs.
- Guarded betting analysis requires calibration/freshness provenance, recent quotes, independent paired books, edge/positive net EV, and caps quarter Kelly at 1% with zero stake on failure.
- Historical features now wait 21 days after tournament start before using outcomes; unavailable year-end labels are excluded from fitting, selection, and calibration.
- Future forecast timestamps are rejected; repeated odds snapshots cannot inflate live accuracy or erase earlier model performance.
- Production dashboard builds use system fonts and no longer download Inter from Google Fonts.
- Strict Python typing accepts the Betfair JSON request body and normalizes LightGBM probability output before slicing.
- `run_training_pipeline` (`backend/src/api/routes/training.py`): sostituito
  `assert process.stdout is not None` con un controllo esplicito che solleva
  `RuntimeError` (gli `assert` verrebbero rimossi con `python -O`).

### Added
- `ruff.toml` alla radice: `line-length = 120`, lint `E,F,W`, `E402` ignorato
  (pattern `sys.path.insert` + `# noqa` consolidato in AGENT.md). La CI ora
  esegue `ruff check .` senza `--ignore` a mano, quindi `E501` (120 char) e
  la presenza dei `# noqa: E402` sono enforce.
- Frontend: infrastruttura test con `vitest` + `@testing-library/react` +
  `jsdom` (`vitest.config.ts`, `vitest.setup.ts`). Script `npm run test` /
  `npm run test:watch` / `npm run typecheck`; la CI web esegue anche i test.
- Frontend: test unit per `lib/api`, `services/history`, `services/news`,
  `hooks/useHistory`, `hooks/useTodaysMatches`, `components/section-cards`
  (13 test, tutti verdi).
- Frontend: hook di dominio `useAvailableModels`, `useHistory`,
  `useTodaysMatches` in `src/hooks/` (regola "uno per dominio", nome che
  descrive il risultato); consumer refactorati (predict, players, live,
  data-table).
- Backend: `config.Settings` (Pydantic `BaseSettings`) per tutte le
  variabili d'ambiente (API port, TheOddsAPI/Betfair keys, LLM providers,
  batch-weather toggle). I 19 punti `os.environ.get` sparsi sono migrati al
  singleton `config.settings`; `pydantic-settings` aggiunto a requirements.
- Backend: `features/cleaning_loaders.py`, `cleaning_transforms.py`,
  `cleaning_enrichment.py` (split di `features/cleaning.py`, orchestratore
  sottile + re-export); `api/card_core.py` (split di `api/routes/card.py`);
  `features/builder_symmetric.py` (split di `builder_helpers.py`);
  `pipeline/train_oof.py` (split di `train_helpers.py`). Tutti i moduli
  sotto il budget di 300 LOC/riga.
- `AGENT.md` aggiunto nella root del repository (le regole erano referenziate
  da `docs/architecture.md` ma il file mancava); copia fedele delle regole
  ingegneristiche di progetto (changelog, struttura, naming, tooling Python,
  React/TS, server).

### Changed
- Frontend services: aggiunti `services/history.ts` e `services/news.ts`;
  `services/system.ts` ora espone anche `getTrack`; `services/odds.ts` e
  `services/system.ts` non duplicano più `getOddsApiStatus`; rimossa la
  duplicazione `researchPlayerNews` da `services/odds.ts` (vive in
  `services/news.ts`). Componenti e pagine migrati dal fetch diretto
  (`apiFetch`/`fetch`) ai services (`data-table`, `players`, `training`,
  `live`, `overview-panels`, `section-cards`, `chart-area-interactive`,
  `match-news-button`, `predict`).
- Frontend: tipi API deduplicati in `src/types/api.ts` — aggiunti
  `HistoryMatchRow`, `HistoryResponse`, `SystemStatus`, `PlayerStats`;
  `CardResponse` allineato al payload reale del backend (`n_value_bets`,
  `model_used`, `min_edge`, `message`); i tipi duplicati locali
  (`auto-daily-card/types.ts`, `match-news-button/types.ts`,
  `live-page.types.ts`) ora re-exportano dal globale.
- Frontend: componenti root spostati in cartelle proprie con barrel
  `index.ts` (regola "ogni componente in cartella propria, import sempre
  dall'index"): `data-table`, `overview-panels`, `section-cards`,
  `chart-area-interactive`, `nav-main`, `nav-secondary`, `site-header`,
  `app-sidebar`.
- Backend: type hints aggiunti alle firme pubbliche senza annotazioni
  (`betting_metrics`, `eval_charts`, `learners`, `historical_core`,
  `state`, `inference`, `clv`, `elo`, `fatigue`, `h2h`, `rolling_stats`,
  `main`, `live_odds_scraping`, `player_context`, `evaluation`,
  `predict_core`). `Any` eliminato dalle firme pubbliche dove non necessario
  (rimasto solo per artefatti deserializzati joblib e `sanitize_nan`, come
  già documentato).
- Backend: **`mypy --strict` completo e verde su tutto il backend (0 errori)**.
  Impostato `strict = True` in `mypy.ini` e RIMOSSI tutti i 16 blocchi
  `ignore_errors` per i moduli legacy. Risolti ~320 errori: generici annotati
  (`dict[str, Any]`, `list[dict[str, Any]]`, `tuple[Any, ...]`,
  `ndarray[Any, Any]`, `set[str]`, ecc.), `Optional` impliciti
  (`start_year: int | None = None`), return `Any` da `json`/numpy/sklearn
  via `# type: ignore[no-any-return]`, mismatch `dict[int, ...]` vs
  `dict[str, ...]`, unpacking di union (`type: ignore[assignment]` nei
  tracker state), import `Any` aggiunti dove mancanti. `Any` è usato
  esplicitamente solo per artefatti deserializzati/ML/JSON (tensione nota
  con la regola "mai Any", documentata).
- Backend: attivati i flag mypy `disallow_untyped_defs` e `warn_return_any`
  (rafforzamento verso `--strict` senza lo churn dei 198 `type-arg` da
  `disallow_any_generics`, che confligge con la regola "mai Any" sui dati
  eterogenei). Annotati 33 siti: artefatti ML/JSON via `Any` esplicito e
  return di `json.loads`/numpy/`sanitize_nan` via `# type: ignore[no-any-return]`.
- Backend: `pipeline/eval_charts.py` (307 LOC) splittato in
  `eval_charts_curves.py` + `eval_charts_explain.py` + `eval_charts_style.py`
  con facciata sottile di re-export (budget 300 LOC/riga).
- Backend: `black` aggiunto al tooling (`requirements-dev.txt` + step
  `black --check .` in CI); 12 file riallineati al formatter.
- Formattato l'intero backend con `black` (`black backend/src start_all.py`,
  82 file riformattati) per allinearsi alla regola AGENT.md
  "black + ruff prima di ogni commit". Nessun cambio di logica;
  `black --check`, `ruff check`, `mypy --strict` e `pytest` sono tutti verdi.
- `api_server.py`: `print()` di warmup e del messaggio di ascolto sostituiti
  con `log = get_logger(__name__)` (logging_config JSON), nessun cambio di
  comportamento.
- `AutoDailyCard`: il fetch diretto (`apiFetch("/api/predict-card")`) nel
  componente è stato sostituito dalla chiamata al service `getPredictCard`,
  rendendo attiva la funzione di `services/predict.ts`
- `settleTrack` (`services/track.ts`): `fetch` raw sostituito con `apiFetch`
  (coerenza services layer)
- `start_all.py`: `print()` sostituiti con logging standard (`logging.basicConfig`
  + `log.info`), senza impatto sui subprocess (continuano a ereditare stdout).
- `features/live_odds_match_odds.py`: `print()` informativo convertito in
  `logger.warning`; i due `except Exception: pass` delle fonti quote ora
  loggano il motivo (regola "errori espliciti mai silenziosi").
- `api/routes/card.py`: i `except Exception: return None` (weather/context
  enrich) ora loggano a livello debug.
- `api/routes/models.py`: `except Exception` ristretto a `OSError` con
  `logger.warning`.
- `api/predict_core.py`: la firma di `sanitize_nan` tentata come `object`
  è stata riportata a `Any` perché il tipo `object` rompeva la compilazione
  mypy strict nei routes che restituiscono il suo risultato
  (`dict[Any, Any]`); si preserva il comportamento identico senza aggiungere
  nuovi errori di tipo.

### Fixed
- Backend: le eccezioni custom di `exceptions.py` sono ora usate al posto dei
  builtin generici nei punti di dominio: `DataNotFoundError` in
  `cleaning_loaders.py` e `training.py` (era `FileNotFoundError`/`ValueError`),
  `TrainingError` in `train_oof.py` (era `RuntimeError`),
  `ExternalAPIError` in `oddsportal_parse.py` con `raise ... from last`
  (era `RuntimeError` senza catena).
- Backend: rimossi gli swallow silenziosi di eccezioni (regola "errori
  espliciti mai silenziosi"): `predict_core.py` (odds autofill, `log.debug`),
  `historical_core.py` (`hand_matchup`, `log.debug`),
  `live_odds_theoddsapi.py` (3 siti `log.warning`), `player_news.py`
  (fallback web search, `log.warning`), `weather_fetch.py` (`log.warning`).
- Backend: `start_year: int = None` -> `int | None = None` in
  `cleaning.py`/`cleaning_loaders.py` (no_implicit_optional, mypy).
- `app/dashboard/predict/page.tsx`: `getAvailableModels` era importato da
  `@/services/predict` ma è esportato da `@/services/system` (errore TS2305
  che rompeva `tsc --noEmit` e la build).
- `components/auto-daily-card/auto-daily-card.tsx`: virgolette non escapate
  nel JSX (2 errori `react/no-unescaped-entities` di ESLint) sostituite con
  `&quot;`.
- `components/ui/chart/chart-context.ts` e
  `components/ui/sidebar/sidebar-parts.tsx`: risolti i 3 warning ESLint
  `no-unused-vars` (const `THEMES` ridotta a `ChartThemeKey`; import
  ristretto alla sola costante usata).
- `pipeline/betting_eval.py`: i 16 `print()` di `full_betting_report`
  sostituiti con `logger.info` via `get_logger(__name__)` (regola AGENT
  "vietato print()"); rimosso il workaround `sys.stdout.reconfigure`.
- `features/elo_system.py`, `features/player_stats_tracker.py` e
  `pipeline/track.py`: aggiunto `# noqa: E402` sugli import dopo
  `sys.path.insert` (allineamento al pattern consolidato AGENT.md).
- `AGENT.md` duplicato in `tennisBOT-main/` rimosso (unica copia fedele
  nella root).
- `features/elo_system.py`: corretti gli errori mypy strict (no_implicit_optional
  + annotazioni di variabili): i parametri con `= None` ora sono
  `int | None` / `str | None`, e i dict di stato (`ratings_global`,
  `ratings_surface`, `match_counts`, ecc.) sono annotati esplicitamente.
  `last_date` è tipato `dict[int, pd.Timestamp]`, mentre `current_date` e
  `date` sono `pd.Timestamp | None`; `_level_mult`, `_mov_mult` e
  `_sets_margin` accettano `str | None` (risolti i 4 errori residui di
  `pd.isna(object)` e degli argomenti `str | None`). `_level_mult` usa
  `get(level or "", 1.0)` per gestire `str | None` senza errori mypy, e
  `config.ELO_LEVEL_K_MULT` è annotato esplicitamente come `dict[str, float]`.
- `api/routes/training.py`: aggiunto `assert process.stdout is not None`
  dopo `subprocess.Popen` (risolve `Item "None" of "IO[str] | None"`).
- `features/odds_loading.py`: `frames.append(df)` ora è in `if df is not None`
  (df è `DataFrame | None` nella rama Excel/html).
- `features/odds_pinnacle.py` e `features/odds_betfair.py`: aggiunta la
  guardia `isinstance(cached, list)` prima di ritornare dalla cache tipata
  `object`.
- `features/odds_theoddsapi.py`: `_available_sports` viene assegnato solo se
  la cache è `list` (filtrata a `str`); `headers` annotato `dict[str, str]`.
- `features/live_odds_theoddsapi.py`: `_available_sports` annotato
  `list[str] | None` e aggiunto stub `_get_api_key()` (il metodo reale vive in
  `LiveOddsScraper`); `[s["key"] ...]` forzato a `list[str]`.
- `features/live_odds_matches.py`: aggiunto stub
  `_get_todays_matches_api()` e ritorni `cached or []` per evitare `Any | None`.
- `features/live_odds_match_odds.py`: aggiunti stub per `_get_api_key`,
  `_scrape_theoddsapi`, `_scrape_pinnacle`, `_scrape_oddsportal`,
  `_scrape_tennis_explorer` e attributo `enable_scraping: bool`.
- `features/live_odds.py`: `_available_sports` in `__init__` allineato a
  `list[str] | None`.
- `features/odds_sofascore.py`: `_http`/`_impersonate` tipizzati (moduli
  intercambiabili di requests/curl_cffi); `_get()` ritorna `dict | None`
  con narrowing; `_event_detail` usa solo `dict`/`isinstance` (estratto
  `event = cached.get("event")` per il narrowing); `_epoch_to_iso`
  accetta `Any`.
- `pipeline/eval_charts.py`: `set_xlim`/`set_ylim` con tuple invece di list;
  `groupby.apply(...)` con `# type: ignore[call-overload]`.
- `pipeline/train_helpers.py`: `mirror_probs`, `o1`, `o2` convertiti con
  `np.asarray(..., dtype=float)` per evitare il tipo pandas `ExtensionArray`.
- `pipeline/inference.py`: firma di `build_match_features` corretta con
  `odds_a/odds_b: float | None` e `now: pd.Timestamp | None`.
- `api/predict_core.py`: `h2h_total` ridotto a int con `isinstance` prima di
  passarlo a `assess_reliability` e di usarlo nel campo `total_matches`.

### Removed
- `services/system.ts`: rimosso `getTrack` (duplicato di
  `getTrackRecord` in `services/track.ts`, stesso endpoint `/api/track`).
  `overview-panels` ora usa `getTrackRecord` (che accetta `AbortSignal`).
  Cleanup repo: nessun duplicato testuale, nessun file non tracciato da
  rimuovere.

### Added
- `backend/src/features/player_context.py`: contesto giocatore 100% locale
  (zero scraping, zero costi) da CSV Sackmann: ranking e punti (ultima
  data ranking), età da DOB, forma recente (ultimi 5 W/L), flag RET nei
  match recenti e superficie dell'ultimo match. Matching nome
  case/accent-insensitive (fold_name) con preferenza per l'ID duplicato
  più attivo (Sackmann ha ID doppi, es. Jakub Mensik 11 vs 212 match).
  Cache lazy per tour; ritorna {} per giocatori sconosciuti.
- `api_server.py`: `GET /api/predict-card` arricchisce ogni predizione con
  `context` (rank, form, RET, età di entrambi i giocatori) in parallelo
  con il meteo; best-effort e silenzioso.
- `frontend/src/components/match-news-button.tsx`: bottone "News" per riga
  della card — ricerca on-demand (GPT Researcher/LLM) di infortuni, forma
  e cambio coach per il singolo match con badge diff (+1/-1) e dettagli.
- `frontend/src/components/auto-daily-card.tsx`: nuova colonna "Context"
  (rank 1/2, form W/L, badge RET se presente negli ultimi match) accanto
  al matchup; la card resta auto-generata all'apertura (meteo + contesto
  locale + news su richiesta).
- `backend/tests/test_player_context.py`: 5 test per il modulo context
  (rank/form/RET/età, giocatore sconosciuto, accenti, ID duplicati,
  file mancanti).
- `api_server.py`: `GET /api/predict-card` arricchisce ogni predizione con il
  meteo della località del torneo (open-meteo, gratuito, nessuna chiave):
  temperatura, umidità, probabilità pioggia e velocità del vento, calcolati
  in parallelo (ThreadPoolExecutor) e silenziosi in caso di errore. Le news
  giocatore (infortuni/forma/coach) restano volutamente fuori dalla card:
  il pipeline GPT Researcher costa chiamate LLM ed è lento per 20+ match;
  resta disponibile nel pannello Player News Research di Live Market.
- `frontend/src/components/auto-daily-card.tsx`: la card ora si genera
  automaticamente all'apertura della pagina (useEffect on mount) e al cambio
  ATP/WTA; nuovo pulsante "Refresh". Aggiunta la colonna Weather (temperatura,
  badge pioggia se >5%, badge vento se >20 km/h).
- Predict Match: la sezione "Automatic daily card" è ora la prima cosa della
  pagina (nessuna ricerca manuale richiesta); il form manuale custom è
  collassato sotto un <details> "Manual prediction".
- `api_server.py`: `GET /api/predict-card` accetta `log=true` — ogni
  predizione della card viene registrata nel Track Record certificato con
  dedup su (player1, player2, surface, prob1, odds1, odds2): rigenerare la
  stessa card non crea duplicati, mentre variazioni di prezzo/probabilità
  producono nuove entry. Risposta con campo `n_logged`.
- `frontend/src/components/auto-daily-card.tsx`: componente condiviso
  "Automatic Daily Card" (ATP/WTA, tabella completa con value-bet e badge
  "logged to Track"); usato sia in Live Market sia nella nuova sezione
  "Automatic mode" di Predict Match.
- `frontend/src/components/overview-panels.tsx`: Dashboard Overview rivista
  — rimossi i plot duplicati (erano gli stessi di Model Analytics e
  Evaluation Reports) e la tabella Match History duplicata; ora mostra le
  metriche di sintesi, lo stato del sistema (backend, modelli, feed quote
  con richieste rimaste e tornei live) e le ultime predizioni chiuse del
  Track Record.
- Predict Match: nomi giocatori ora in input libero con suggerimenti
  (datalist) invece del menu fisso di ~30 nomi.
- `api_server.py`: nuovo endpoint `GET /api/predict-card?tour=atp|wta&min_edge=0.05`
  — genera automaticamente la predizione del modello per OGNI match del giorno
  (tutti i tornei ATP/WTA dal feed TheOddsAPI cached, zero quota extra):
  probabilità, vincitore, reliability, odds di mercato, edge vs probabilità
  implicita e flag value-bet. Superficie inferita dal nome del torneo
  (`_infer_surface`, keyword Clay/Grass/Hard, default Hard). Usa il modello
  `<tour>_model_odds.pkl` (fallback `<tour>_model.pkl`).
- `web/src/app/dashboard/live/page.tsx`: sezione "Automatic Daily Card" —
  un click genera le predizioni di tutti i match del giorno per ATP/WTA
  con tabella completa (orario, match, torneo, superficie, prob modello,
  odds, edge, reliability, badge value-bet).
- `web/src/app/dashboard/history/page.tsx` + `web/src/components/data-table.tsx`:
  sezione unica "Match History" completa (fusa con la vecchia "Raw Data"):
  date, torneo, superficie, matchup, probabilità modello, esito reale,
  badge Correct/Miss e selettore righe 10-100. Rimossa pagina
  `/dashboard/data` e componente `raw-table.tsx` (duplicavano `/api/history`
  con descrizioni fuorvianti); voce "Raw Data" rimossa dalla sidebar.
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
- Matching nomi giocatori ora insensibile agli accenti (NFD): il frontend
  invia nomi accentati da TheOddsAPI ("Kecmanović", "Machač") mentre il
  modello/dataset usano forme senza accenti — prima `/api/predict` dava
  cold-start 50/50 e `/api/value-bets` non trovava quote. Fix in
  `pipeline/inference.py` (`fold_name` + `resolve_player_id`),
  `features/live_odds.py` (`_normalize_player_name`),
  `features/odds_aggregator.py` (`_normalize_player`),
  `api_server.py` (fallback parquet `_get_player_latest_stats`,
  `_get_h2h_stats`). Test `test_player_name_matching_is_accent_insensitive`.
- `features/odds_aggregator.py`: CRITICO — il filtro tour in `_aggregate`
  cercava "atp"/"wta" nel NOME del torneo ("Cincinnati Open" non lo
  contiene) e scartava TUTTI i match: `/api/todays-matches` e
  `/api/predict-card` restituivano lista vuota con la quota API sana.
  Aggiunto campo `tour` esplicito a `MatchOdds` (impostato da
  `TheOddsApiAdapter` dal sport_key) e filtro su quello con fallback sul
  nome. Test `test_aggregator_tour_filter_uses_explicit_tour_field`.
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
- Ristrutturazione repository secondo AGENT.md (nessuna funzionalità rimossa,
  git mv per preservare la history):
  - `backend/src/` raccoglie tutto il codice Python (api_server.py, main.py,
    config.py, features/, pipeline/, data/, utils/, smoke test); import e
    nomi dei package invariati.
  - `backend/tests/` la suite pytest (prima in `tests/`).
  - `frontend/` (prima `web/`) la dashboard Next.js.
  - `data/`, `models/saved/`, `reports/`, `.env`/`local.env` restano alla
    root: `config.py` ora ancora `_PROJECT_ROOT` tre livelli sopra, e
    `api_server.py` distingue `SRC_DIR` (cwd del subprocess train) da
    `BASE_DIR` (root per .env e dataset).
  - `docs/architecture.md` aggiunto (layout + regole di ancoraggio dei path);
    `data/DATA_SOURCES.md` spostato in `docs/`; `update_csv_count.py` in
    `scripts/`.
  - CI aggiornato: `pytest backend/tests`, mypy con `working-directory:
    backend/src`, smoke `python backend/src/smoke_test.py`, job web-build su
    `frontend/`; Weekly Refresh usa `python backend/src/main.py`.
  - Entry point utente: `python backend/src/main.py <cmd>`,
    `python backend/src/api_server.py`, `python start_all.py` invariato.
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
