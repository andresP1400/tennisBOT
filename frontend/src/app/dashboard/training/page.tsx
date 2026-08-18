"use client"

import { useEffect, useRef, useState } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { IconAdjustments, IconPlayerPlay, IconTerminal2, IconCheck, IconX, IconCopy } from "@tabler/icons-react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { API_DISPLAY_URL, ApiError, apiFetch } from "@/lib/api"

interface TrainingStatus {
  is_training: boolean
  current_task: string
  progress: number
  logs: string[]
  error: boolean
  success: boolean
}

export default function TrainingPage() {
  const [trials, setTrials] = useState(50)
  const [tour, setTour] = useState("atp")
  const [startYear, setStartYear] = useState(2000)
  const [endYear, setEndYear] = useState(2026)
  const [backendOnline, setBackendOnline] = useState<boolean | null>(null)
  const [pollError, setPollError] = useState<string | null>(null)
  const logEndRef = useRef<HTMLDivElement | null>(null)
  const [status, setStatus] = useState<TrainingStatus>({
    is_training: false,
    current_task: "Idle",
    progress: 0,
    logs: [],
    error: false,
    success: false,
  })

  useEffect(() => {
    const controller = new AbortController()
    const tick = async () => {
      if (controller.signal.aborted) return
      try {
        const data = await apiFetch<TrainingStatus>("/api/status", { signal: controller.signal })
        setStatus({
          is_training: !!data.is_training,
          current_task: data.current_task ?? "Idle",
          progress: data.progress ?? 0,
          logs: Array.isArray(data.logs) ? data.logs : [],
          error: !!data.error,
          success: !!data.success,
        })
        setBackendOnline(true)
        setPollError(null)
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") return
        setBackendOnline(false)
        setPollError(err instanceof ApiError ? err.message : "Backend non raggiungibile")
      }
    }
    void tick()
    // Poll faster while training so the live log feels real-time
    const interval = setInterval(tick, status.is_training ? 1000 : 2000)
    return () => {
      controller.abort()
      clearInterval(interval)
    }
  }, [status.is_training])

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" })
  }, [status.logs.length])

  const handleStart = async () => {
    if (status.is_training) return
    try {
      await apiFetch("/api/train/start", {
        method: "POST",
        body: { tour, trials, startYear, endYear },
      })
      setPollError(null)
      setBackendOnline(true)
    } catch (err) {
      if (err instanceof ApiError) {
        alert(`Training non avviato: ${err.message}`)
      } else {
        alert("Errore avvio server Python. Hai lanciato 'python api_server.py' (porta 9090)?")
      }
    }
  }

  const copyLogs = () => {
    navigator.clipboard.writeText(status.logs.join("\n"))
    alert("Copiato negli appunti!")
  }

  return (
    <div className="@container/main flex flex-1 flex-col gap-2">
      <div className="flex flex-col gap-4 py-4 md:gap-6 md:py-6 px-4 lg:px-6">
        <h2 className="text-3xl font-bold tracking-tight">Model Training</h2>
        <p className="text-muted-foreground mb-4">Manage the automated training pipeline and hyperparameter tuning from UI.</p>

        <div className="grid gap-4 md:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2"><IconAdjustments className="h-5 w-5" /> Walk-Forward Cross Validation</CardTitle>
              <CardDescription>Current model was trained using Walk-Forward evaluation.</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between border-b pb-2"><span className="text-muted-foreground">Train size</span> <span className="font-mono">127,180 rows</span></div>
                <div className="flex justify-between border-b pb-2"><span className="text-muted-foreground">Validation size</span> <span className="font-mono">11,432 rows</span></div>
                <div className="flex justify-between border-b pb-2"><span className="text-muted-foreground">Test size</span> <span className="font-mono">5,946 rows</span></div>
                <div className="flex justify-between pt-2"><span className="text-muted-foreground">Base estimators</span> <span>LGBM, XGBoost, LogReg</span></div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2"><IconPlayerPlay className="h-5 w-5" /> Start New Pipeline</CardTitle>
              <CardDescription>Trigger a new hyperparameter tuning session using Optuna.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="grid gap-2">
                  <label className="text-sm font-medium">Tour</label>
                  <select value={tour} onChange={e => setTour(e.target.value)} disabled={status.is_training} className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background">
                    <option value="atp">ATP (Men)</option>
                    <option value="wta">WTA (Women)</option>
                  </select>
                </div>
                <div className="grid gap-2">
                  <label className="text-sm font-medium">Optuna Trials</label>
                  <input type="number" value={trials} min={1} max={200} onChange={e => setTrials(Math.max(1, parseInt(e.target.value || "1", 10)))} disabled={status.is_training} className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background" />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4 mt-2">
                <div className="grid gap-2">
                  <label className="text-sm font-medium">Start Year</label>
                  <select value={startYear} onChange={e => setStartYear(parseInt(e.target.value, 10))} disabled={status.is_training} className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background">
                    {Array.from({ length: 27 }, (_, i) => 2000 + i).map(year => (
                      <option key={year} value={year}>{year}</option>
                    ))}
                  </select>
                </div>
                <div className="grid gap-2">
                  <label className="text-sm font-medium">End Year</label>
                  <select value={endYear} onChange={e => setEndYear(parseInt(e.target.value, 10))} disabled={status.is_training} className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background">
                    {Array.from({ length: 27 }, (_, i) => 2000 + i).map(year => (
                      <option key={year} value={year}>{year}</option>
                    ))}
                  </select>
                </div>
              </div>
              <Button variant={status.is_training ? "secondary" : "default"} disabled={status.is_training || backendOnline === false} onClick={handleStart} className="w-full">
                {status.is_training ? `Training Running...` : "Initialize Training"}
              </Button>
              {backendOnline === false && (
                <p className="text-xs text-amber-500">
                  Backend offline. Avvia: <code className="font-mono">python api_server.py</code> (porta 9090)
                </p>
              )}
            </CardContent>
          </Card>
        </div>

        <Card className="mt-4">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <div className="space-y-1">
              <CardTitle className="flex items-center gap-2">
                <IconTerminal2 className="h-5 w-5" />
                Python Live Log
                {backendOnline === true && <Badge variant="outline" className="ml-2 text-emerald-400 border-emerald-400/40">online</Badge>}
                {backendOnline === false && <Badge variant="destructive" className="ml-2">offline</Badge>}
                {status.success && <Badge className="ml-2 bg-emerald-500 hover:bg-emerald-600"><IconCheck className="w-3 h-3 mr-1" /> Success</Badge>}
                {status.error && <Badge variant="destructive" className="ml-2"><IconX className="w-3 h-3 mr-1" /> Failed</Badge>}
              </CardTitle>
              <CardDescription>
                Status: {status.current_task}
                {status.is_training ? " · polling 1s" : ""}
                {pollError ? ` · ${pollError}` : ""}
              </CardDescription>
            </div>
            <Button variant="outline" size="sm" onClick={copyLogs} className="gap-2" disabled={status.logs.length === 0}>
              <IconCopy className="w-4 h-4" /> Copy Logs
            </Button>
          </CardHeader>
          <CardContent>
            <div className="bg-black/95 text-[#00ff88] p-4 rounded-md font-mono text-[10px] sm:text-xs overflow-y-auto min-h-[250px] max-h-[500px] whitespace-pre-wrap flex flex-col gap-1 ring-1 ring-inset ring-white/10">
              {status.logs.length === 0 ? (
                <p className="opacity-50">
                  {backendOnline === false
                    ? "Backend offline — impossibile leggere i log."
                    : status.is_training
                      ? "Training avviato, in attesa delle prime righe di log..."
                      : "Waiting for python logs... Avvia un training per vedere l'output live."}
                </p>
              ) : null}
              {status.logs.map((log, i) => (
                <span key={i} className={log.toLowerCase().includes("error") || log.toLowerCase().includes("exception") ? "text-red-400 font-bold" : ""}>
                  {log}
                </span>
              ))}
              <div ref={logEndRef} />
            </div>
            <p className="text-xs text-muted-foreground mt-2">
              API: {API_DISPLAY_URL} · endpoint <span className="font-mono">/api/status</span> + <span className="font-mono">/api/train/start</span>
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
