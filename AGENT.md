# RULES

## Changelog
- CHANGELOG.md obbligatorio nella root, aggiornato prima di ogni merge
- Sezioni: Added Changed Fixed Removed sotto [Unreleased] o [x.y.z] - YYYY-MM-DD
- Voci generiche vietate — keepachangelog.com

## Struttura
- backend/src/ — api/ core/ models/ services/ utils/ config/
- backend/tests/ — unit/ integration/ — rispecchia src/
- frontend/src/ — components/ hooks/ pages/ services/ store/ types/ utils/
- docs/architecture.md — .env.example mai .env

## Generali
- non volgio vedere emoji, la UI del sito web deve essere minimal stile apple
- Naming: snake_case variabili/funzioni/file Python, PascalCase classi/componenti/file React, UPPER_SNAKE_CASE costanti, useCamelCase hooks
- Nomi autoesplicativi, zero abbreviazioni, variabili corte solo per indici loop
- Una funzione = una cosa; un file = uno scopo; se la descrizione contiene "e", dividere
- DRY: stesso blocco 2 volte → funzione; piu' layer → utils/
- Limiti: max 40 righe/funzione, 300 righe/file, 120 char/riga
- Commenti: solo il "perche'", mai il "cosa"; TODO con autore e data

## Python
- Tooling: black + ruff prima di ogni commit, mypy --strict senza errori, pytest, uv/poetry
- Type hints obbligatori su ogni funzione pubblica, mai Any
- Sottomoduli: __init__.py espone __all__, _internal.py e' privato e non si importa fuori
- Error handling: vietato bare except, eccezioni custom in exceptions.py, re-raise con from e
- Config: zero secrets nel codice, tutto da env via Pydantic Settings
- Test: Arrange/Act/Assert, deterministici, un test per ogni funzione pubblica
- Moduli grossi (>300 LOC): un orchestratore sottile + moduli helper/mixin sotto `features/<domain>_<role>.py`. Esempio: `live_odds.py` orchestra tre mixin (`live_odds_theoddsapi.TheOddsApiMixin`, `live_odds_matches.TodaysMatchesMixin`, `live_odds_match_odds.MatchOddsMixin`). I test risolvono i metodi via MRO attribute lookup (`inspect.getsource(LiveOddsScraper.<method>)`).
- `sys.path.insert(...)` + `import config` / `from utils import …` dopo `logger = get_logger(__name__)` portano `# noqa: E402` (consolidato in `features/cleaning.py`, `features/context.py`, `data/download.py`, `pipeline/{evaluation,inference,split,track,track_io}.py`).
- Re-export da un modulo pubblico: aggiungere l'import `...  # noqa: F401` + la voce in `__all__`, altrimenti `ruff --fix` rimuove l'import come "unused".

## React / TS
- usa sempre react con "npx create-next-app@latest "nome-progetto" --typescript" con ESLint — si consiglia Yes, Tailwind CSS — a scelta, src/ directory — Yes, App Router — Yes, Turbopack — Yes, import alias — Yes, default @/*
- Ogni componente in cartella propria: Component.tsx + .types.ts + .test.tsx + index.ts
- Importare sempre dall'index.ts, max 100 righe per componente
- Solo function components, props tipizzate in .types.ts, zero logica nel JSX
- Hook: uno per dominio, nome descrive cosa restituisce, nessuna assunzione sul chiamante
- Tipi: vietato any, unknown + narrowing; interface per oggetti, type per union; globali in src/types/
- Services: nessun fetch diretto in componenti/hook, tutto in src/services/ per dominio
- Componenti shadcn/ui >300 LOC (es. `components/ui/sidebar.tsx`, `components/ui/chart.tsx`): spostati in `components/ui/<name>/` con moduli per sottocomponente + `index.ts` barrel re-export; il vecchio `components/ui/<name>.tsx` viene rimosso, gli import `@/components/ui/<name>` continuano a funzionare via risoluzione `index.ts`.
- Page Next.js >300 LOC (`app/<route>/page.tsx`): mantenere `page.tsx` come orchestrator sottile; estrarre le sezioni in `app/<route>/_components/` (cartelle con prefisso `_` sono ignorate dal routing).

## Server
- Input: validare tutto al bordo prima della business logic, errori espliciti mai silenziosi
- Logging: vietato print(), usare logging/structlog JSON — DEBUG/INFO/WARNING/ERROR/CRITICAL
- Sicurezza: query DB parametrizzate, secrets mai in log/response, CORS+rate limiting+auth a livello framework, autenticazione e autorizzazione separati
- Performance: zero query in loop (batch/join), operazioni lente su worker, paginazione obbligatoria, dati sensibili mai in cache non cifrata