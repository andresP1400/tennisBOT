"use client"

import { useEffect, useState } from "react"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { AutoDailyCard } from "@/components/auto-daily-card"

const TOP_PLAYERS = [
  "Jannik Sinner", "Carlos Alcaraz", "Novak Djokovic", "Daniil Medvedev",
  "Alexander Zverev", "Andrey Rublev", "Holger Rune", "Casper Ruud",
  "Hubert Hurkacz", "Alex de Minaur", "Stefanos Tsitsipas", "Taylor Fritz",
  "Grigor Dimitrov", "Tommy Paul", "Ben Shelton", "Ugo Humbert",
  "Rafael Nadal", "Roger Federer", "Andy Murray",
  "Iga Swiatek", "Aryna Sabalenka", "Coco Gauff", "Elena Rybakina",
  "Jessica Pegula", "Marketa Vondrousova", "Ons Jabeur", "Maria Sakkari",
].sort()

interface PredictResponse {
  match: string
  surface: string
  model_used: string
  prob1: number
  prob2: number
  winner: string
  info?: string
  reliability?: string
  reliability_notes?: string[]
  h2h?: { p1_win_pct: number | null; total_matches: number }
  elo?: { p1: number | null; p2: number | null; p1_surface_blend?: number | null; p2_surface_blend?: number | null }
  data_through?: string
  error?: string
}

interface ModelsResponse {
  models: string[]
}

export default function PredictPage() {
  const [player1, setPlayer1] = useState("Jannik Sinner")
  const [player2, setPlayer2] = useState("Carlos Alcaraz")
  const [surface, setSurface] = useState("Hard")
  const [model, setModel] = useState("atp_stacking_model.pkl")
  const [availableModels, setAvailableModels] = useState<string[]>([])

  const [result, setResult] = useState<PredictResponse | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    const load = async () => {
      try {
        const data = await fetch("/api/models", { signal: controller.signal })
        if (!data.ok) return
        const json = (await data.json()) as ModelsResponse
        if (json.models && json.models.length > 0) {
          setAvailableModels(json.models)
          setModel(json.models[0])
        }
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") return
        console.error("Impossibile contattare FastAPI", err)
      }
    }
    void load()
    return () => controller.abort()
  }, [])

  const handlePredict = async () => {
    setLoading(true)
    setResult(null)
    try {
      const res = await fetch("/api/predict", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ player1, player2, surface, model }),
      })
      const data = (await res.json()) as PredictResponse
      setResult(data)
    } catch {
      alert("Nessun modello backend in esecuzione. Verifica FastAPI.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="@container/main flex flex-1 flex-col gap-2">
      <div className="flex flex-col gap-4 py-4 md:gap-6 md:py-6 px-4 lg:px-6">
        <h2 className="text-3xl font-bold tracking-tight">Predict Match</h2>
        <Card className="max-w-3xl">
          <CardHeader>
            <CardTitle>Submit match parameters</CardTitle>
            <CardDescription>Enter the players and surface to get a prediction loading weights from a custom Pickled model.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-2 mb-2">
              <label className="text-sm font-medium">Select Saved Model</label>
              <select value={model} onChange={e => setModel(e.target.value)} disabled={availableModels.length === 0} className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background">
                {availableModels.length === 0 && <option>No models found in /models</option>}
                {availableModels.map(m => <option key={m} value={m}>{m}</option>)}
              </select>
            </div>

            <div className="flex items-center gap-4">
              <div className="grid flex-1 gap-2">
                <label className="text-sm font-medium">Player 1 Name</label>
                <Input
                  value={player1}
                  onChange={(e) => setPlayer1(e.target.value)}
                  placeholder="Type any player name"
                  list="players-list"
                />
              </div>
              <div className="font-bold text-muted-foreground pt-6">VS</div>
              <div className="grid flex-1 gap-2">
                <label className="text-sm font-medium">Player 2 Name</label>
                <Input
                  value={player2}
                  onChange={(e) => setPlayer2(e.target.value)}
                  placeholder="Type any player name"
                  list="players-list"
                />
              </div>
            </div>
            <datalist id="players-list">
              {TOP_PLAYERS.map((p) => (
                <option key={p} value={p} />
              ))}
            </datalist>

            <div className="grid gap-2">
              <label className="text-sm font-medium">Surface</label>
              <select value={surface} onChange={e => setSurface(e.target.value)} className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background">
                <option value="Hard">Hard</option>
                <option value="Clay">Clay</option>
                <option value="Grass">Grass</option>
              </select>
            </div>

            <Button disabled={loading || availableModels.length === 0} onClick={handlePredict} className="w-full mt-4">
              {loading ? "Calculating Probabilities..." : "Predict Outcome"}
            </Button>
          </CardContent>

          {result && !result.error && (
            <CardFooter className="flex flex-col items-start bg-muted/50 p-6 mt-4 border-t">
              <h3 className="text-xl font-bold mb-4">Prediction Results</h3>
              <div className="flex flex-wrap justify-between w-full mb-4 text-xs text-muted-foreground border-b pb-2 gap-2">
                <span>Loaded Model: <span className="font-mono text-emerald-400">{result.model_used}</span></span>
                <span>Surface: {result.surface}</span>
                {result.reliability && (
                  <span>
                    Reliability:{" "}
                    <span className="font-semibold text-foreground capitalize">{result.reliability}</span>
                  </span>
                )}
                {result.data_through && <span>Data through: {result.data_through}</span>}
              </div>
              <div className="w-full grid grid-cols-2 gap-4">
                <div className="p-4 rounded-md border text-center flex flex-col bg-background relative overflow-hidden">
                  {result.prob1 > result.prob2 && <div className="absolute top-0 left-0 w-full h-1 bg-emerald-500" />}
                  <span className="text-muted-foreground text-sm mb-1 line-clamp-1">{player1}</span>
                  <span className={result.prob1 > result.prob2 ? "text-3xl font-bold text-emerald-500" : "text-3xl font-bold"}>{(result.prob1 * 100).toFixed(1)}%</span>
                  {result.elo?.p1 != null && (
                    <span className="text-[11px] text-muted-foreground mt-1">ELO {result.elo.p1}</span>
                  )}
                </div>
                <div className="p-4 rounded-md border text-center flex flex-col bg-background relative overflow-hidden">
                  {result.prob2 > result.prob1 && <div className="absolute top-0 left-0 w-full h-1 bg-emerald-500" />}
                  <span className="text-muted-foreground text-sm mb-1 line-clamp-1">{player2}</span>
                  <span className={result.prob2 > result.prob1 ? "text-3xl font-bold text-emerald-500" : "text-3xl font-bold"}>{(result.prob2 * 100).toFixed(1)}%</span>
                  {result.elo?.p2 != null && (
                    <span className="text-[11px] text-muted-foreground mt-1">ELO {result.elo.p2}</span>
                  )}
                </div>
              </div>
              {(result.h2h || (result.reliability_notes && result.reliability_notes.length > 0) || result.info) && (
                <div className="mt-4 w-full space-y-1 text-xs text-muted-foreground">
                  {result.h2h && (
                    <p>
                      H2H: {result.h2h.total_matches} match
                      {result.h2h.p1_win_pct != null
                        ? ` · P1 win rate ${(result.h2h.p1_win_pct * 100).toFixed(0)}%`
                        : " · no prior meetings"}
                    </p>
                  )}
                  {result.info && <p>{result.info}</p>}
                  {result.reliability_notes?.map((n) => (
                    <p key={n}>• {n}</p>
                  ))}
                  <p className="pt-1">
                    Salvata nel{" "}
                    <a href="/dashboard/track" className="underline text-foreground">
                      Track Record
                    </a>
                    .
                  </p>
                </div>
              )}
            </CardFooter>
          )}

          {result && result.error && (
            <CardFooter className="flex flex-col items-start bg-red-950/20 p-6 mt-4 border-t text-red-400">
              <h3 className="font-bold flex items-center gap-2">Prediction Engine Error</h3>
              <pre className="mt-2 text-xs overflow-x-auto w-full">{result.error}</pre>
            </CardFooter>
          )}
        </Card>

        <div className="pt-2">
          <h3 className="text-xl font-bold tracking-tight mb-3">Automatic mode</h3>
          <p className="text-muted-foreground text-sm mb-4">
            Invece di inserire i nomi a mano, genera la card della giornata: il modello
            predice automaticamente ogni partita in arrivo di qualsiasi torneo ATP/WTA
            (ELO, forma, fatica, H2H, superficie e quote di mercato), le registra nel
            Track Record e segnala le value bet.
          </p>
          <AutoDailyCard />
        </div>
      </div>
    </div>
  )
}
