import { NextResponse } from "next/server"
import fs from "fs"
import path from "path"
import { z } from "zod"

const ReportsDir = path.resolve(process.cwd(), "..", "reports")

const TourSchema = z.enum(["atp", "wta"])

const ChartNameSchema = z
  .string()
  .min(1)
  .max(128)
  .regex(/^[A-Za-z0-9_\-]+\.png$/, "Invalid chart name")

export async function GET(
  request: Request,
  { params }: { params: Promise<{ name: string }> }
) {
  try {
    const { name } = await params
    const parsedName = ChartNameSchema.safeParse(name)
    if (!parsedName.success) {
      return new NextResponse("Invalid chart name", { status: 400 })
    }

    const url = new URL(request.url)
    const parsedTour = TourSchema.safeParse(
      url.searchParams.get("tour") ?? "atp",
    )
    if (!parsedTour.success) {
      return new NextResponse("Invalid tour", { status: 400 })
    }
    const tour = parsedTour.data

    const filePath = path.resolve(ReportsDir, tour, parsedName.data)
    const reportsTour = path.resolve(ReportsDir, tour) + path.sep

    if (!filePath.startsWith(reportsTour)) {
      return new NextResponse("Forbidden", { status: 403 })
    }

    if (!fs.existsSync(filePath)) {
      return new NextResponse("Not found", { status: 404 })
    }

    const buffer = fs.readFileSync(filePath)
    return new NextResponse(buffer, {
      headers: {
        "Content-Type": "image/png",
        "Cache-Control": "public, max-age=60",
      },
    })
  } catch {
    return new NextResponse("Error", { status: 500 })
  }
}
