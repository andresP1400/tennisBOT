import { NextResponse } from "next/server"
import { z } from "zod"

const TourSchema = z.enum(["atp", "wta"])

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:9090"

export async function GET(request: Request) {
  const url = new URL(request.url)
  const parsed = TourSchema.safeParse(url.searchParams.get("tour") ?? "atp")
  if (!parsed.success) {
    return new NextResponse("Invalid tour", { status: 400 })
  }
  try {
    const upstream = await fetch(`${BACKEND_URL}/api/metrics?tour=${parsed.data}`, {
      cache: "no-store",
    })
    const text = await upstream.text()
    return new NextResponse(text, {
      status: upstream.status,
      headers: { "Content-Type": "text/csv" },
    })
  } catch {
    return new NextResponse("metric,test,val\n", {
      status: 200,
      headers: { "Content-Type": "text/csv" },
    })
  }
}
