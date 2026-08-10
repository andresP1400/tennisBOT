"use client"

import { useState } from "react"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"

interface UserPrefs {
  apiBaseUrl: string
  defaultTour: "atp" | "wta"
  defaultSurface: "Hard" | "Clay" | "Grass"
  defaultMinEdge: number
  historyRows: number
  defaultPlayer1: string
  defaultPlayer2: string
}

const DEFAULTS: UserPrefs = {
  apiBaseUrl: "",
  defaultTour: "atp",
  defaultSurface: "Hard",
  defaultMinEdge: 0.05,
  historyRows: 30,
  defaultPlayer1: "Jannik Sinner",
  defaultPlayer2: "Carlos Alcaraz",
}

const STORAGE_KEY = "tennisbot.user_prefs.v1"

function loadPrefs(): UserPrefs {
  if (typeof window === "undefined") return DEFAULTS
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (!raw) return DEFAULTS
    return { ...DEFAULTS, ...(JSON.parse(raw) as Partial<UserPrefs>) }
  } catch {
    return DEFAULTS
  }
}

export default function SettingsPage() {
  const [prefs, setPrefs] = useState<UserPrefs>(() => loadPrefs())
  const [savedAt, setSavedAt] = useState<Date | null>(null)

  const update = <K extends keyof UserPrefs>(key: K, value: UserPrefs[K]) => {
    setPrefs((prev) => ({ ...prev, [key]: value }))
  }

  const save = () => {
    if (typeof window !== "undefined") {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(prefs))
      setSavedAt(new Date())
    }
  }

  const reset = () => {
    if (typeof window !== "undefined") {
      window.localStorage.removeItem(STORAGE_KEY)
    }
    setPrefs(DEFAULTS)
    setSavedAt(new Date())
  }

  return (
    <div className="@container/main flex flex-1 flex-col gap-2">
      <div className="flex flex-col gap-4 py-4 md:gap-6 md:py-6 px-4 lg:px-6">
        <h2 className="text-3xl font-bold tracking-tight">Settings</h2>

        <Card className="max-w-2xl">
          <CardHeader>
            <CardTitle>User Preferences</CardTitle>
            <CardDescription>
              Preferences are stored locally in your browser (localStorage).
              They do not affect the backend Python service.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-2">
              <label className="text-sm font-medium">
                Backend API base URL (optional override)
              </label>
              <Input
                placeholder="leave empty to use NEXT_PUBLIC_API_URL"
                value={prefs.apiBaseUrl}
                onChange={(e) => update("apiBaseUrl", e.target.value)}
              />
              <p className="text-xs text-muted-foreground">
                When empty, the dashboard uses the value baked at build time via
                <code className="ml-1 font-mono">NEXT_PUBLIC_API_URL</code>.
              </p>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="grid gap-2">
                <label className="text-sm font-medium">Default tour</label>
                <select
                  value={prefs.defaultTour}
                  onChange={(e) => update("defaultTour", e.target.value as UserPrefs["defaultTour"])}
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                >
                  <option value="atp">ATP (Men)</option>
                  <option value="wta">WTA (Women)</option>
                </select>
              </div>
              <div className="grid gap-2">
                <label className="text-sm font-medium">Default surface</label>
                <select
                  value={prefs.defaultSurface}
                  onChange={(e) => update("defaultSurface", e.target.value as UserPrefs["defaultSurface"])}
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                >
                  <option value="Hard">Hard</option>
                  <option value="Clay">Clay</option>
                  <option value="Grass">Grass</option>
                </select>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="grid gap-2">
                <label className="text-sm font-medium">Default min edge (value bets)</label>
                <Input
                  type="number"
                  min={0}
                  max={1}
                  step={0.01}
                  value={prefs.defaultMinEdge}
                  onChange={(e) => update("defaultMinEdge", parseFloat(e.target.value || "0"))}
                />
              </div>
              <div className="grid gap-2">
                <label className="text-sm font-medium">Default history rows</label>
                <Input
                  type="number"
                  min={5}
                  max={200}
                  step={5}
                  value={prefs.historyRows}
                  onChange={(e) => update("historyRows", parseInt(e.target.value || "30", 10))}
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="grid gap-2">
                <label className="text-sm font-medium">Default player 1</label>
                <Input
                  value={prefs.defaultPlayer1}
                  onChange={(e) => update("defaultPlayer1", e.target.value)}
                />
              </div>
              <div className="grid gap-2">
                <label className="text-sm font-medium">Default player 2</label>
                <Input
                  value={prefs.defaultPlayer2}
                  onChange={(e) => update("defaultPlayer2", e.target.value)}
                />
              </div>
            </div>

            <div className="flex items-center gap-3 pt-2">
              <Button onClick={save}>Save Preferences</Button>
              <Button variant="outline" onClick={reset}>Reset to defaults</Button>
              {savedAt && (
                <Badge variant="outline" className="text-xs">
                  Saved {savedAt.toLocaleTimeString()}
                </Badge>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
