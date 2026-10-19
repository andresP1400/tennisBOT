"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { useMarketOpportunities } from "@/hooks/useMarketOpportunities"
import { ValueRows } from "@/components/value-rows"
import { ValueSummary } from "@/components/value-summary"
import type { MarketOpportunitiesProps } from "./market-opportunities.types"

export function MarketOpportunities({ tour }: MarketOpportunitiesProps) {
  const { card, error } = useMarketOpportunities(tour)
  return <div className="space-y-4">
    <Card><CardHeader><CardTitle>80%+ High-Confidence Value</CardTitle></CardHeader><CardContent>
      {!card && !error && <p>Checking current market evidence…</p>}
      {error && <p role="alert">{error}</p>}
      {card && <><p>{card.message_a}</p><ValueRows candidates={card.category_a} />
        <ValueSummary performance={card.performance_a} /></>}
      <p className="text-sm text-muted-foreground">At least 80% estimated probability and initially -250 or better,
        plus fresh data and positive uncertainty-adjusted EV. An 80% verified win rate is a target, not an established result.</p>
    </CardContent></Card>
    <Card><CardHeader><CardTitle>Best Value Opportunities</CardTitle></CardHeader><CardContent>
      {!card && !error && <p>Checking current market evidence…</p>}
      {error && <p role="alert">Market data is unavailable; no opportunities can be qualified.</p>}
      {card && <><p>{card.message_b}</p><ValueRows candidates={card.category_b} />
        <ValueSummary performance={card.performance_b} />
        <p className="text-sm text-muted-foreground">{card.provider_status}</p>
        <details className="text-sm text-muted-foreground"><summary>Qualification safeguards and missing evidence</summary>
          <ul>{Array.from(new Set(card.candidates.flatMap(candidate => candidate.reasons))).map(reason => <li key={reason}>{reason}</li>)}</ul>
          <p>Policy {card.policy_version}. Estimated EV is not proven profitability. Missing closing prices and public splits remain unavailable.</p>
        </details></>}
    </CardContent></Card>
  </div>
}
