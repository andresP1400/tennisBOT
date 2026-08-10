# REPORT COMPLETO — tennisBOT v2.0

## 1. RIEPILOGO GENERALE

| Metrica | Valore |
|---------|--------|
| File Python backend | 27 |
| File TypeScript/React | 52 |
| Pagine frontend | 10 (2 placeholder) |
| Endpoint API | 12 (1 rotto, 7 orfani senza UI) |
| Feature nel modello | 37 su 49 definite |
| Bug confermati | 15 |
| Problemi di sicurezza | 6 |
| Codice morto / import inutilizzati | 18 |
| Violazioni AGENTS.md | 14/15 regole |
| `print()` invece di `logging` | 186 occorrenze |
| Test automatizzati | 0 |
| Deployability score | 0/10 |

---

## 2. BUG CRITICI (Da fixare immediatamente)

| # | Bug | File:Riga | Impatto |
|---|-----|-----------|---------|
| 1 | `calibrator.predict()` restituisce **classe (0/1)** invece di probabilità → output binari | `api_server.py:246,322` | Le probabilità sono 0% o 100%, mai valori intermedi |
| 2 | `p2_stats[p1_col_name]` → **KeyError**: indicizza con nome colonna sbagliato | `api_server.py:227` | Differenze feature sempre NaN nel 50% dei casi |
| 3 | Regex corrotto (mojibake) → non matcha mai | `live_odds.py:614-618` | Fallback scraping completamente morto |
| 4 | API Meteo usa GFS forecast (non historical) → dati NaN per match pre-2021 | `weather.py:136` | 5 feature meteo sempre NaN nel training |
| 5 | `useTheme()` senza `<ThemeProvider>` → **crash runtime** | `sonner.tsx:14`, `layout.tsx` | App crascha se si usa Sonner Toaster |
| 6 | Font misconfigured: `geist-sans` vs `inter` | `globals.css:8`, `layout.tsx:7` | Font fallback non funziona |
| 7 | `testMatches` duplicato per riga 'val' nel CSV | `evaluation.py:353` | Metriche di validazione errate |
| 8 | SHAP re-fitta imputer su **test set** (data leakage) | `evaluation.py:338-342` | SHAP values inaffidabili |
| 9 | `_fetch_pinnacle_api` è **no-op**: fa `pass` dopo API call riuscita | `live_odds.py:391-407` | Fallback scraping ancora più morto |
| 10 | `calibration.py` usa `y_min`/`y_max` deprecati → **crash su sklearn ≥1.4** | `calibration.py:23` | Training blocca con `TypeError` |
| 11 | `.str.endswith("_A")` senza `na=False` → crash se NaN in match_id | `api_server.py:169,303-304` | API history e load_dataset crashano |
| 12 | `load_odds_data` hardcoded tour="atp" per WTA | `builder.py:311` | Odds WTA sempre errate |
| 13 | `pd.NA`/`pd.NaT` causa `TypeError` in `np.isnan()` | `fatigue.py:53,59,83` | Fatigue features crashano con date mancanti |
| 14 | `surface=Unknown` → ELO ritorna 1500 invece di globale | `elo.py:121-124` | Nuove superfici danno rating sbagliati |
| 15 | `ZeroDivisionError` se walk-forward folds vuoti | `training.py:258-263` | Crollo training se dati insufficienti |

---

## 3. PROBLEMI DI SICUREZZA

| # | Problema | File | Gravità |
|---|----------|------|---------|
| 1 | **API key TheOddsAPI in chiaro nel file `.env`** | `.env:4` | 🔴 CRITICAL — `9b49...f83` (rotated in v2.1, see docs/SECURITY.md) |
| 2 | **Path traversal in `/api/predict` e `/api/value-bets`** | `api_server.py:188,405` | 🔴 ALTO — `req.model` non sanitizzato |
| 3 | **Path traversal in web `/api/charts/[name]`** | `web/route.ts:12` | 🔴 ALTO — `name` passato direttamente a `path.join()` |
| 4 | CORS misconfigured (`["*"]` + `credentials=True`) | `api_server.py:46-47` | 🟡 MEDIO |
| 5 | API key in query string (loggata da proxy) | `api_server.py:518` | 🟡 MEDIO |
| 6 | Nessuna autenticazione su nessun endpoint | Tutti | 🟡 MEDIO |

---

## 4. CODICE MORTO / IMPORT INUTILIZZATI

| # | File | Simbolo |
|---|------|---------|
| 1 | `api_server.py:5` | `import threading` |
| 2 | `api_server.py:6` | `import json` |
| 3 | `api_server.py:14` | `REPORTS_DIR` dalla config |
| 4 | `player_news.py:28` | `import json` |
| 5 | `player_news.py:31` | `import numpy as np` |
| 6 | `split.py:13` | `import numpy as np` |
| 7 | `context.py:16` | `import numpy as np` |
| 8 | `elo.py:14` | `import numpy as np` |
| 9 | `player.py:17` | `import numpy as np` |
| 10 | `player.py:20` | `import config` |
| 11 | `builder.py:164-192` | Funzione `_map_row` (mai chiamata) |
| 12 | `live_odds.py:52-82` | `ATP_TOURNAMENT_KEYS`, `WTA_TOURNAMENT_KEYS` |
| 13 | `live_odds.py:391-407` | `_fetch_pinnacle_api` (no-op) |
| 14 | `nav-documents.tsx` | Componente orfano (mai importato) |
| 15 | `nav-user.tsx` | Componente orfano (mai importato) |
| 16 | `config.py:10-11,34,92` | `PROJECT_ROOT`, `DATA_DIR`, `ROLLING_WINDOWS`, `TOURNEY_LEVEL_MAP` |
| 17 | `live_odds.py:43` | `import config` (mai referenziato) |
| 18 | `calibration.py:23` | `y_min=0.01, y_max=0.99` deprecati |

---

## 5. PAGINE FRONTEND NON IMPLEMENTATE / PLACEHOLDER

| Pagina | Stato | Problema |
|--------|-------|----------|
| `/dashboard/players` | ❌ Placeholder | Solo "Feature currently being integrated" — nessun link sidebar |
| `/dashboard/settings` | ❌ Placeholder | Input senza handler, bottone Save non funziona |
| `/dashboard/features` | ⚠️ Parziale | Dice "42" → sono 37. `closing_odds_diff` non esiste nel modello |
| `/dashboard/analytics` | ⚠️ Vuoto | Solo `ChartAreaInteractive` — nessuna analisi |
| `/dashboard/reports` | ⚠️ Vuoto | Identico ad `analytics/` — duplicato |
| `/dashboard/data` | ⚠️ Mock | 6 righe hardcoded, non dati reali |

---

## 6. ENDPOINT API ORFANI (7 senza UI)

| Endpoint | Funzione |
|----------|---------|
| `POST /api/reload` | Invalida cache dataset |
| `GET /api/weather` | Meteo per torneo |
| `POST /api/live-odds` | Quote live |
| `POST /api/value-bets` | Value betting |
| `POST /api/player-news` | Ricerca infortuni |
| `GET /api/todays-matches` | Partite del giorno |
| `GET /api/odds-api-status` | Stato API key |

---

## 7. ARCHITETTURA — ANTI-PATTERN

| # | Anti-Pattern | Dove | Impatto |
|---|--------------|------|---------|
| 1 | `sys.path.insert(0, ...)` in 11+ file | Ovunque | Sistema import fragile |
| 2 | Stato globale mutabile (`training_status`, `_global_dataset`) | `api_server.py` | Thread-unsafe |
| 3 | Logica inference duplicata 3x (predict, value-bets, history) | `api_server.py` | Bug va fixato in 3 posti |
| 4 | `print()` invece di logging strutturato | 186 chiamate in 20 file | Impossibile filtrare/aggregare |
| 5 | Ogni modulo fa `import config` diretto | Ovunque | Impossibile testare |
| 6 | `subprocess.Popen` per training | `api_server.py:85` | Output fragile |
| 7 | `__init__.py` vuoti (nessun `__all__`) | 4 file | Namespace pollution |
| 8 | Imputer/scaler fittati globalmente, non per-fold | `training.py:330-334` | Lookahead leakage |
| 9 | Doppio uso holdout (Optuna + early stopping) | `training.py:225-226` | Overfitting su validation |

---

## 8. VIOLAZIONI AGENTS.md (14/15 regole FAIL)

| # | Regola | Status |
|---|--------|--------|
| 1 | CHANGELOG.md obbligatorio | ❌ Manca |
| 2 | Struttura `backend/src/ tests/ docs/` | ❌ Struttura diversa |
| 3 | No emoji nella UI | ❌ `start_all.py` usa emoji |
| 4 | Naming (snake_case, PascalCase) | ❌ Componenti React in kebab-case |
| 5 | Funzioni ≤ 40 righe | ❌ `predict_match` ~80 righe |
| 6 | File ≤ 300 righe | ❌ `api_server.py` 542, `sidebar.tsx` 726 |
| 7 | Riga ≤ 120 caratteri | ❌ 9 violazioni trovate |
| 8 | Type hints obbligatori | ❌ 23 funzioni pubbliche senza |
| 9 | `__all__` in `__init__.py` | ❌ Nessun `__all__` |
| 10 | No bare `except` | ✅ PASS |
| 11 | Nessun segreto nel codice | ❌ API key in `.env` |
| 12 | Componenti React con types/test/index | ❌ Tutti flat, nessun test |
| 13 | No `any` in frontend | ❌ 3 uscite di `useState<any>` |
| 14 | Fetch in `services/`, non in componenti | ❌ `services/` inesistente |
| 15 | No `print()`, usare `logging` | ❌ 186 `print()`, 0 `logging` |

---

## 9. DEPENDENCY PROBLEMS

| # | Problema | Impatto |
|---|----------|---------|
| 1 | `@dnd-kit` versioni mismatch (`core@6` vs `modifiers@9`) | 🔴 Alto — crash runtime |
| 2 | `zod` ^4.3.6 incompatibile con shadcn forms | 🟡 Medio |
| 3 | `scrapling 0.4.8` (richiesto >=1.2.0) | 🟡 Medio |
| 4 | `next` 16.1.6 con 13 vulnerabilità (4 moderate, 9 high) | 🟡 Medio |
| 5 | 5 extraneous packages in `node_modules` | 🟢 Basso |
| 6 | `lucide-react` + `@tabler/icons-react` duplicati | 🟢 Basso |

---

## 10. DATA FLOW E STATO

| Aspetto | Stato |
|---------|-------|
| State management | ❌ Nessuno — solo `useState` + `useEffect` |
| Caching frontend | ❌ Zero caching |
| Caching backend | ⚠️ Cache manuale senza lock (race condition) |
| Polling training | `setInterval` 2s senza AbortController |
| URL backend | 5x `localhost:8000` hardcoded, 3x relativo `/api/` |
| Next.js rewrites | ❌ Nessun proxy configurato |

---

## 11. COMPLIANCE LOGGING

| Metrica | Valore |
|---------|--------|
| `print()` totali | 186 |
| `import logging` | 0 |
| `logging.info/warning/error` | 0 |
| `structlog` | 0 |
| `exceptions.py` | ❌ Manca |
| Custom exceptions | ❌ Zero |

---

## 12. DEPLOYMENT READINESS

| Risorsa | Presente? |
|---------|-----------|
| CI/CD config | ❌ |
| .env.example | ❌ |
| next.config.ts `output: standalone` | ❌ |
| Production uvicorn command | ❌ (usa `reload=True`) |
| Health check endpoints | ❌ |
| Process manager | ❌ (`start_all.py` non adatto) |
| **Score** | **0/10** |

---

## 13. RIEPILOGO QUANTITATIVO

| Categoria | Conteggio |
|-----------|-----------|
| Bug critici | 15 |
| Problemi sicurezza | 6 |
| Codice morto | 18 |
| Pagine placeholder | 2 |
| Componenti orfani | 2 |
| File che violano 300 righe | 3 |
| Violazioni AGENTS.md | 14/15 |
| Endpoint senza UI | 7 |
| Infrastruttura mancante | 12 elementi |
| `print()` da sostituire | 186 |
| Feature page errate | 3 (conteggio, nome, feature inesistente) |
| Hardcoded URL localhost | 5 |
| Hardcoded valori frontend | 70+ |
| **TOTALE** | **~300+ problemi** |
