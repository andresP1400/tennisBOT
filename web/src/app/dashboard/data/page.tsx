import { RawDataTable } from "@/components/raw-table"

export default function RawDataPage() {
        return (
                <div className="@container/main flex flex-1 flex-col gap-2">
                        <div className="flex flex-col gap-4 py-4 md:gap-6 md:py-6 px-4 lg:px-6">
                                <h2 className="text-3xl font-bold tracking-tight">Raw Dataset</h2>
                                <p className="text-muted-foreground mb-4">View the downloaded raw ATP match data before feature engineering is applied.</p>

                                <RawDataTable />
                        </div>
                </div>
        )
}
