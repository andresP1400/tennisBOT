import { DataTable } from "@/components/data-table"

export default function HistoryPage() {
        return (
                <div className="@container/main flex flex-1 flex-col gap-2">
                        <div className="flex flex-col gap-4 py-4 md:gap-6 md:py-6 px-4 lg:px-6">
                                <h2 className="text-3xl font-bold tracking-tight">Match History</h2>
                                <p className="text-muted-foreground mb-4">Sezione completa: tutti i match passati con torneo, superficie, probabilità del modello, esito reale e verifica Correct/Miss. Dati processati dal backend Python in tempo reale (GET /api/history).</p>

                                <DataTable />
                        </div>
                </div>
        )
}