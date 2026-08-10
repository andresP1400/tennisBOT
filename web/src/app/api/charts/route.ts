import { NextResponse } from "next/server"
import fs from "fs"
import path from "path"
import { z } from "zod"

const TourSchema = z.enum(["atp", "wta"])

const ReportsDir = path.resolve(process.cwd(), "..", "reports")

const CHART_FILES: ReadonlyArray<{ name: string; file: string }> = [
  { name: "ROC Curve", file: "1_roc_curve.png" },
  { name: "Calibration Curve", file: "2_calibration_curve.png" },
  { name: "Feature Importance", file: "3_feature_importance.png" },
  { name: "SHAP Summary", file: "4_shap_summary.png" },
  { name: "Brier Monthly", file: "5_brier_monthly.png" },
]

export async function GET(request: Request) {
  const url = new URL(request.url)
  const parsed = TourSchema.safeParse(url.searchParams.get("tour") ?? "atp")
  if (!parsed.success) {
    return NextResponse.json({ charts: [] }, { status: 400 })
  }
  const tour = parsed.data
  try {
    const reportsDir = path.resolve(ReportsDir, tour)
    const charts = CHART_FILES.map((c) => ({
      ...c,
      exists: fs.existsSync(path.join(reportsDir, c.file)),
    }))
    return NextResponse.json({ tour, charts })
  } catch {
    return NextResponse.json({ tour, charts: [] })
  }
}
