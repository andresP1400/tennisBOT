import { SectionCards } from "@/components/section-cards"
import { OverviewPanels } from "@/components/overview-panels"
import { PersonalPredictions } from "@/components/personal-predictions"

export default function Page() {
  return (
    <div className="@container/main flex flex-1 flex-col gap-2">
      <div className="flex flex-col gap-4 py-4 md:gap-6 md:py-6">
        <PersonalPredictions />
        <SectionCards />
        <OverviewPanels />
      </div>
    </div>
  )
}
