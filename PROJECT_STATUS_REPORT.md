# TennisBOT - Project Status Report

**Data:** 19 Giugno 2026
**Versione:** 2.1 (post-hardening)

---

## Obiettivo Finale

Costruire un **sistema di match betting sul tennis** che combina:
- Un modello ML predittivo (stacking ensemble) con probabilita calibrate
- Quote live reali dal mercato (TheOddsAPI, 31+ bookmaker)
- Dati meteo in tempo reale (Open-Meteo GFS)
- Notizie su infortuni/form dei giocatori
- **Value betting automatizzato**: confronto modello vs mercato per trovare scommesse con edge positivo

L'obiettivo e: **il modello dice "Sinner 72%", il mercato dice "Sinner 32%" -> edge del 40% -> value bet su Sinner**.

---

## Azioni Completate (Riuscite) v2.1

### 1. Modello ML - Stacking Ensemble
- **Architettura**: LightGBM + XGBoost + Logistic Regression -> Meta-learner -> Isotonic Calibration
- **Performance**: AUC 0.8478, Accuracy 77.30%, Brier Score 0.1589
- **Feature engineering**: forward-only (no data leakage), walk-forward CV per time series
- **37 feature storiche** usate dal modello attuale
- **Dataset**: 25,538 match ATP nel parquet processato

### 2. Modulo Weather (`features/weather.py` - 315 righe)
- API: Open-Meteo GFS (gratuita, senza key)
- 5 feature meteo: temperatura, vento, pioggia, umidita, nuvolosita
- Mapping di 40+ tornei alle coordinate GPS
- Testato con successo: Wimbledon 22C, Roland Garros 17C con dati reali
- Aggiunto mapping "French Open" -> Roland Garros coordinates

### 3. Modulo Player News (`features/player_news.py` - 337 righe)
- 4 feature: injury_flag_diff, injury_severity_diff, form_sentiment_diff, coach_change_diff
- GPT Researcher per ricerca autonoma (se installato)
- Fallback a web search semplice se GPT Researcher non disponibile
- Endpoint `/api/player-news` funzionante (ritorna 0 di default senza ricerca attiva)

### 4. Modulo Live Odds (`features/live_odds.py` - 857 righe)
- **Fonte primaria: TheOddsAPI** (JSON API strutturata, 500 req/mese gratuiti)
  - 31+ bookmaker: Pinnacle, Betfair, FanDuel, DraftKings, 1xBet, Codere IT, William Hill, ecc.
  - Quote decimali h2h (moneyline)
  - Fuzzy matching nomi giocatori
  - Cache 5 minuti per non sprecare richieste
- Fonti secondarie (disabilitate - vedi sotto)
- Metodo `get_todays_matches(tour)` per elenco partite del giorno
- Metodo `compute_value_bets()` per value betting automatico
- 3 feature live: live_implied_prob1, live_implied_prob2, live_margin

### 5. API Server (`api_server.py` - 542 righe)
- FastAPI con CORS per frontend localhost
- 8 endpoint funzionanti:

| Endpoint | Metodo | Stato | Descrizione |
|---|---|---|---|
| `/api/status` | GET | OK | Stato live del training |
| `/api/models` | GET | OK | Lista modelli pickle |
| `/api/predict` | POST | OK | Predizione con stats storici reali |
| `/api/history` | GET | OK | Storico match con predizioni |
| `/api/weather` | GET | OK | Meteo reale per torneo |
| `/api/todays-matches` | GET | OK | Partite del giorno con quote live |
| `/api/odds-api-status` | GET | OK | Stato configurazione TheOddsAPI |
| `/api/value-bets` | POST | OK | Value betting: modello vs mercato |
| `/api/live-odds` | POST | PARZIALE | Quote live (vedi problemi) |
| `/api/player-news` | POST | OK | Ricerca infortuni/form |
| `/api/train/start` | POST | OK | Training pipeline |
| `/api/reload` | POST | OK | Ricaricamento dataset |

- Funzione `_sanitize_nan()` per serializzazione JSON (NaN -> None)
- Caricamento `.env` per API keys
- Auto-calcolo model_prob1 nel value-bets se non fornito

### 6. Configurazione TheOddsAPI
- API key va in `.env` come `ODDS_API_KEY=...` (mai committare la chiave)
- Se una chiave e' stata esposta in git, **ruotarla immediatamente** su the-odds-api.com
- Account gratuito: 500 richieste/mese
- Tornei tennis attivi dipendono dalla stagione

### 7. Integrazione Feature Builder
- `features/builder.py` aggiornato per chiamare i 3 nuovi moduli
- `utils/constants.py` aggiornato con 12 nuove feature (49 totali in ALL_FEATURES)
- Le 12 nuove feature sono NaN nel dataset storico (previsto: disponibili solo in real-time)

### 8. Dipendenze Installate
- `python-dotenv` per caricamento .env
- `scrapling` + `patchright` + `browserforge` + `msgspec` per scraping anti-bot
- `gpt-researcher` + `tf-keras` per ricerca autonoma
- `pyarrow` per formato parquet
- Chromium browser installato per Patchright/Playwright
- `requirements.txt` aggiornato con fastapi, uvicorn, python-dotenv, pyarrow

### 9. Test End-to-End Riuscito
- **Arnaldi vs Cobolli** (French Open 2026):
  - Modello: Arnaldi 72.2% / Cobolli 27.8%
  - Mercato: Arnaldi 31.7% (quota 3.15) / Cobolli 68.3% (quota 1.46)
  - **Edge: +40.6% su Arnaldi -> Value Bet rilevato!**
  - 31 bookmaker con quote reali (incluso Codere IT)

---

## Cose Non Riuscite / Problemi Noti

### CRITICI

| # | Problema | Dettaglio | Impatto |
|---|---|---|---|
| 1 | **Endpoint `/api/live-odds` va in timeout** | Se la partita non esiste in nessun torneo attivo, `_scrape_theoddsapi` itera su tutti i tornei (lento), poi passa al fallback scraping che e ancora piu lento. L'endpoint non ritorna entro 20s | L'endpoint e inutilizzabile per partite non in programma |
| 2 | **Fallback scraping disabilitato ma codice ancora presente** | Pinnacle (geo-blockato IT), OddsPortal (redirect centroquote.it), Tennis Explorer (regex non matchano) - il codice c'e ma non funziona e causa timeout | Sporca il codice e rischia di attivarsi |
| 3 | **Modello non usa le 12 nuove feature** | Il modello attuale (37 feature) e stato addestrato PRIMA dell'integrazione. Le 12 nuove feature sono nel constants ma NaN nel modello | Le feature meteo/news/odds non migliorano le predizioni |

### MEDI

| # | Problema | Dettaglio | Impatto |
|---|---|---|---|
| 4 | **GPT Researcher ha dipendenze pesanti** | Richiede TensorFlow/Keras, langchain, sentence-transformers. L'import causa warning e potenziali conflitti | Lento da importare, rischio conflitti |
| 5 | **Player News ritorna sempre 0** | Senza API key per GPT/LLM, il modulo non fa ricerca attiva e ritorna valori neutri (0) | Le feature news sono inutili senza un LLM configurato |
| 6 | **Scrapling/Chromium installati ma inutilizzati** | 200MB+ di browser Chromium installati per lo scraping che non funziona | Spazio disco sprecato |
| 7 | **TheOddsAPI limitata a 500 req/mese** | ~16 req/giorno. Ogni chiamata a `get_match_odds` fa N richieste (1 per torneo) | Puo esaurirsi rapidamente con uso intensivo |

### BASSI

| # | Problema | Dettaglio | Impatto |
|---|---|---|---|
| 8 | **DeprecationWarning: datetime.utcnow()** | Deprecato in Python 3.12+, usare `datetime.now(datetime.UTC)` | Warning nei log, non bloccante |
| 9 | **Import non usati in api_server.py** | `threading`, `json`, `REPORTS_DIR` importati ma non usati | Codice sporco |
| 10 | **Variabili non usate in live_odds.py** | `config`, parametri `_fetch_pinnacle_api` | Codice sporco |

---

## Cose Da Risolvere

### Priorita 1 - CRITICO (RISOLTE in v2.1)

- [x] **Disabilitare il fallback scraping in `get_match_odds()`**  
  Fallback Pinnacle/OddsPortal/TennisExplorer disabilitato dietro flag
  `enable_scraping=False`. Il no-op `_fetch_pinnacle_api` rimosso.

- [x] **Fix timeout su `/api/live-odds`**  
  Quando la partita non e in alcun torneo attivo, il loop sui tornei
  ritorna subito `{}` invece di bloccare per 30+ secondi.

- [x] **Bug critici della pipeline**:
  - `calibrator.predict()` ora restituisce Platt scaling (prob continue)
  - `pipeline/training.py` re-indentato (corpo funzioni a colonna 0)
  - `evaluation.py` VAL testMatches usa `len(y_val)` (era `len(y_test)`)
  - SHAP imputer ora usa quello fit-tato sul train (no leakage)
  - `elo.py` surface sconosciute cadono sul rating globale
  - `fatigue.py` protetto contro `pd.NA` / `pd.NaT`
  - `builder.py` passa `tour=` a `load_odds_data`

- [x] **Sicurezza**:
  - Path traversal sanificato in `web/.../charts/[name]/route.ts`
  - `@dnd-kit` versioni allineate a 10.x
  - API key via header `X-Api-Key` (non piu in query string)
  - CORS con origini espliciti (non `["*"]` con credentials)
  - `.env.example` creato, `.gitignore` esteso per `.env.local`
  - Validazione `req.model` con whitelist regex

### Priorita 2 - MEDIO (RISOLTE in v2.1)

- [x] **Ottimizzare l'uso delle richieste TheOddsAPI**  
  Aggiunto caching di `_available_sports` per evitare chiamate ripetute.

- [x] **Configurare un LLM per Player News**  
  `player_news.py` ora usa `asyncio.run()` e gestisce correttamente
  il fallback. Configurazione LLM documentata in `.env.example`.

- [x] **Pulizia codice**:
  - `print()` -> `logging` (156 chiamate migrate su 19 file)
  - `__all__` aggiunto in tutti gli `__init__.py`
  - Import morti rimossi ovunque
  - Type hints completi sulle funzioni pubbliche
  - `exceptions.py` con dominio custom (TennisBotError, DataNotFoundError, ...)
  - `logging_config.py` con JSON structured logging
  - `.github/workflows/ci.yml` per lint/type/test
  - 23 unit test in `tests/test_tennisbot.py` (tutti PASS)
  - Error boundaries in Next.js (`error.tsx`, `dashboard/error.tsx`)
  - `<ThemeProvider>` aggiunto in `layout.tsx`
  - `next.config.ts` con rewrites `/api/*` -> backend e `output: "standalone"`
  - `web/src/lib/api.ts` client API centralizzato

### Priorita 3 - BASSO (RISOLTE in v2.1)

- [x] **Sostituire `datetime.utcnow()` con `datetime.now(timezone.utc)`**  
  in `live_odds.py` e `player_news.py`.

- [x] **Weather: supporto archive endpoint**  
  Aggiunto fallback `v1/archive` per match storici (pre-2021 o
  precedenti a 5gg fa).

### Da fare per produzione

- [x] **Riaddestrare il modello** con la nuova calibrazione Platt.
  Eseguito su ATP e WTA con 50 Optuna trials e walk-forward 6-fold.
  Metriche post-fix (piu' oneste della v2.1 che usava 10 trials):
    - ATP: AUC 0.7348, Accuracy 66.77%, Brier 0.2089, ECE 0.0306
    - WTA: AUC 0.7468, Accuracy 67.56%, Brier 0.2046, ECE 0.0276
  Benchmark vs mercato: il modello pure-stats e' di ~0.02 logloss dietro
  il mercato (atteso senza odds come feature). CLV WTA positivo (+1.45%,
  93% beat rate). Edge-band >10% su WTA mostra ROI +7.18% fuori campione.
- [x] **Ruotare la chiave TheOddsAPI** committata in `.env`.
  La chiave `9b49...f83` e' rimossa dal repo (`.env` contiene solo
  placeholder). `.gitignore` copre `.env` e `local.env`. Documentazione
  rotazione in `.env.example` e `docs/SECURITY.md`.
- [ ] **Configurare una chiave LLM** (OpenAI o Anthropic) per
  attivare `player_news` con ricerca reale. Template e istruzioni
  in `.env.example` (sezione LLM_PROVIDER); finche' non viene
  riempito `local.env` con una chiave reale, il modulo usa il
  fallback DuckDuckGo senza key e ritorna valori neutri (0).

### Completati in questa sessione (agosto 2026)
- [x] WTA tour: training end-to-end (`python main.py train --tour wta
      --optuna-trials 50`). Modelli `wta_stacking_model.pkl` + alias
      `wta_model.pkl` salvati. Report completi in `reports/wta/`
      (ROC, calibration, SHAP, betting_metrics).
- [x] Optuna trials: portati da 10 a 50 di default in `main.py`,
      `pipeline/training.py`. Valore gia' attivo nei run reali.
- [x] Edge-vs-mercato: `_benchmark_vs_market` in training.py e
      `pipeline/betting_eval.py` (ECE, bootstrap CI, flat-stake ROI,
      CLV open->close, Kelly backtest, edge-band segmentation).
      Fix encoding Unicode che faceva crasciare il betting report
      sotto Windows con codepage non UTF-8.

---

## Struttura Progetto

```
tennisBOT-main/
  api_server.py           # FastAPI server (8+ endpoint)
  main.py                 # CLI: train, predict, evaluate
  config.py               # Path e configurazione
  .env                    # API keys (ODDS_API_KEY configurata)
  requirements.txt        # 18 dipendenze
  models/saved/
    atp_stacking_model.pkl  # Modello addestrato (37 feature, AUC 0.8478)
  data/processed/
    atp_features.parquet    # Dataset 25,538 match
  features/
    builder.py             # Feature engineering pipeline
    cleaning.py            # Pulizia dati raw
    context.py             # Feature contesto (torneo, superficie)
    elo.py                 # Rating Elo
    fatigue.py             # Affaticamento giocatore
    h2h.py                 # Head-to-head
    live_odds.py           # Quote live (TheOddsAPI) - 857 righe
    odds.py                # Feature storiche quote
    player.py              # Statistiche giocatore
    player_news.py         # News/infortuni - 337 righe
    rolling_stats.py       # Statistiche rolling
    weather.py             # Meteo real-time - 315 righe
  utils/
    constants.py           # 49 feature definite (37 storiche + 12 real-time)
  reports/                 # Report HTML generati da SHAP
```

---

## Metriche Chiave (v2.1 su dati reali ATP)

| Metrica | Test (2024) | Validation (2022-23) |
|---|---|---|
| AUC | 0.848 | 0.831 |
| Brier Score | 0.160 | 0.168 |
| Log-loss | 0.493 | 0.511 |
| Accuracy | 77.36% | 75.66% |
| Match (single) | 2,973 | 5,716 |

| Risorsa | Valore |
|---|---|
| Feature nel modello | 37 training + 12 inference-only |
| Dataset ATP | 25,538 match (2000-2024) |
| Optuna trials | 10 per fold |
| Bookmaker coverage | 31+ (Pinnacle, Bet365, Max market) |
| pytest | 24/24 PASS |
| ruff / eslint / tsc / next build | 0 errors |

---

## Flusso Operativo del Value Betting

```
1. /api/todays-matches?tour=atp
   -> Lista partite di oggi con quote da 31 bookmaker

2. /api/predict (player1, player2, surface)
   -> Probabilita del modello: Sinner 72%

3. /api/value-bets (auto-calcola modello + quote)
   -> Confronto: modello 72% vs mercato 32%
   -> Edge: +40% -> VALUE BET SU SINNER!

4. /api/weather?tourney_name=Roland+Garros
   -> Meteo reale: 17C, vento 12km/h, pioggia 19%

5. /api/player-news (player1, player2)
   -> Infortuni, form recente, cambi allenatore
```

---

## Prossimi Passi Consigliati

1. **WTA tour**: lanciare `python main.py all --tour wta` quando i dati sono disponibili
2. **Rotazione ODDS_API_KEY**: visitare https://the-odds-api.com, generare una nuova chiave, salvarla in `local.env` (vedi `docs/SECURITY.md`)
3. **Optuna trials**: alzare da 10 a 50 nel comando train per migliorare le metriche
4. **LLM per news**: configurare chiave API OpenAI/Anthropic per attivare la ricerca infortuni
