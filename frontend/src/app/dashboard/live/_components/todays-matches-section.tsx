import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import type { TodaysMatch } from "./live-page.types"

export function TodaysMatchesSection({
  matches,
  error,
  needsKey,
  tour,
}: {
  matches: TodaysMatch[]
  error: string | null
  needsKey: boolean
  tour: "atp" | "wta"
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Today&apos;s matches</CardTitle>
        <CardDescription>
          Source: <span className="font-mono">/api/todays-matches?tour={tour}</span>.
          Requires <span className="font-mono">ODDS_API_KEY</span>.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {error && (
          <p className="text-sm text-red-400 mb-3">
            {needsKey
              ? "ODDS_API_KEY not configured on the backend. Add it to local.env."
              : `Backend error: ${error}`}
          </p>
        )}
        {matches.length === 0 && !error ? (
          <p className="text-sm text-muted-foreground">
            No matches returned for today.
          </p>
        ) : (
          <div className="grid gap-3">
            {matches.map((m, idx) => (
              <div
                key={`${m.player1}-${m.player2}-${idx}`}
                className="rounded-md border border-neutral-800 bg-muted/20 p-3 flex flex-wrap items-center gap-3"
              >
                <div className="flex-1 min-w-0">
                  <div className="font-medium">
                    {m.player1}{" "}
                    <span className="text-muted-foreground text-xs">vs</span>{" "}
                    {m.player2}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {m.tournament}
                    {m.surface ? ` - ${m.surface}` : ""}
                    {m.commence_time ? ` - ${m.commence_time.slice(0, 16)}` : ""}
                  </div>
                </div>
                <div className="flex flex-col items-end text-xs">
                  <div>
                    {m.player1}: <span className="font-mono">
                      {(m.best_odds.player1 || 0).toFixed(2)}
                    </span>{" "}
                    <span className="text-muted-foreground">
                      ({m.implied_prob1 ? `${(m.implied_prob1 * 100).toFixed(1)}%` : "-"})
                    </span>
                  </div>
                  <div>
                    {m.player2}: <span className="font-mono">
                      {(m.best_odds.player2 || 0).toFixed(2)}
                    </span>{" "}
                    <span className="text-muted-foreground">
                      ({m.implied_prob2 ? `${(m.implied_prob2 * 100).toFixed(1)}%` : "-"})
                    </span>
                  </div>
                  <Badge variant="outline" className="mt-1 text-[10px]">
                    {m.num_bookmakers} books - margin {((m.margin || 0) * 100).toFixed(1)}%
                  </Badge>
                </div>
              </div>
            ))}
          </div>
        )}
        <p className="text-xs text-muted-foreground mt-3">
          {needsKey
            ? "Serve ODDS_API_KEY nel .env (the-odds-api.com, free tier 500 req/mese)."
            : "Quote live da TheOddsAPI quando la chiave è configurata."}
        </p>
      </CardContent>
    </Card>
  )
}