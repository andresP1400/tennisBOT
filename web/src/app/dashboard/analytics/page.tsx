import { ChartAreaInteractive } from "@/components/chart-area-interactive"

export default function AnalyticsPage() {
        return (
                <div className="@container/main flex flex-1 flex-col gap-2">
                        <div className="flex flex-col gap-4 py-4 md:gap-6 md:py-6 px-4 lg:px-6">
                                <h2 className="text-3xl font-bold tracking-tight">Model Analytics</h2>
                                <p className="text-muted-foreground mb-4">Deep dive into feature importance, calibration, and prediction logic.</p>

                                <ChartAreaInteractive />
                        </div>
                </div>
        )
}
