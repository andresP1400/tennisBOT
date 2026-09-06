# TennisBOT Dashboard

Next.js 16 (App Router) + TypeScript dashboard for the TennisBOT ML engine.
All `/api/*` requests are proxied to the FastAPI backend on `:9090`
(see `next.config.ts`).

## Scripts

```bash
npm run dev         # development server (http://localhost:3000)
npm run build       # production build
npm start           # start production server
npm run lint        # ESLint
npm run typecheck   # tsc --noEmit
npm test            # Vitest (unit tests, jsdom)
```

## Structure

```
src/
├── app/                 # App Router routes: dashboard pages + /api rewrite handlers
├── components/          # UI components (shadcn/ui) each in its own folder + index.ts barrel
├── hooks/               # one hook per domain (useHistory, useTodaysMatches, useAvailableModels)
├── services/            # typed API clients (analytics, history, news, odds, predict, system, track, training)
├── types/               # shared TypeScript types (src/types/api.ts)
└── lib/                 # api client (apiFetch + ApiError), feature catalogue, cn() util
```

## Conventions (AGENT.md)

- Function components only, props typed, zero logic in JSX.
- No `any` in TypeScript — `unknown` + narrowing, `interface` for objects,
  `type` for unions.
- No direct `fetch` in components/hooks — all network I/O goes through
  `src/services/*`.
- Types shared in `src/types/api.ts` (single source of truth).
- Tests next to the unit under test (`*.test.ts(x)`), run via Vitest.

## Testing

```bash
npm test
```

A Vitest + `@testing-library/react` + `jsdom` suite covers the `lib/api`
client, the domain services, the data-fetching hooks and key components.