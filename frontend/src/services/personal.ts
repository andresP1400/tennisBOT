import { apiFetch } from "@/lib/api"
import type { PersonalCard } from "@/types/personal"

export function getPersonalPredictions(tour: "atp" | "wta", signal?: AbortSignal): Promise<PersonalCard> {
  return apiFetch<PersonalCard>(`/api/personal/predictions?tour=${tour}`, { signal, cache: "no-store" })
}
