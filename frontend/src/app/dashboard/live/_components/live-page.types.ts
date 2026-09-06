export type {
  NewsResponse,
  TodaysMatch,
  TodaysResponse,
  ValueBet,
  ValueResponse,
} from "@/types/api"

export function fmtPct(n: number | null | undefined, digits = 1): string {
  if (n == null || !Number.isFinite(n)) return "—"
  return `${(n * 100).toFixed(digits)}%`
}