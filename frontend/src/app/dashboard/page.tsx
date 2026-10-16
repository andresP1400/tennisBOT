import { SectionCards } from "@/components/section-cards"
import { OverviewPanels } from "@/components/overview-panels"
import { PersonalPredictions } from "@/components/personal-predictions"

export default function Page() {
  return (
    <div className="@container/main flex flex-1 flex-col gap-2">
      <div className="flex flex-col gap-4 py-4 md:gap-6 md:py-6">
        <PersonalPredictions />
        <section aria-label="Legacy stacking tools" className="space-y-4">
          <p className="px-4 text-sm text-muted-foreground lg:px-6">
            The panels below use the separate legacy stacking pipeline. Its model list, metrics, and track record
            do not include the personal ATP/WTA forecasts and live results shown above.
          </p>
          <SectionCards />
          <OverviewPanels />
        </section>
      </div>
    </div>
  )
}
