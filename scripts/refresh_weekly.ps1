# TennisBot weekly refresh for Windows Task Scheduler.
#
# Install (run once as admin or current user):
#   schtasks /Create /TN "TennisBotWeeklyRefresh" /SC WEEKLY /D MON /ST 06:00 `
#     /TR "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"C:\path\to\scripts\refresh_weekly.ps1`"" `
#     /RL LIMITED
#
# Or run manually:
#   .\scripts\refresh_weekly.ps1
#   .\scripts\refresh_weekly.ps1 -SettleOnly
#   .\scripts\refresh_weekly.ps1 -Tour atp -OptunaTrials 10

param(
    [ValidateSet("atp", "wta", "both")]
    [string]$Tour = "both",
    [int]$OptunaTrials = 20,
    [switch]$SettleOnly,
    [switch]$SkipTrain
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$LogDir = Join-Path $Root "reports"
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir | Out-Null }
$LogFile = Join-Path $LogDir ("refresh_{0:yyyyMMdd_HHmmss}.log" -f (Get-Date))

function Write-Log([string]$msg) {
    $line = "[{0:yyyy-MM-dd HH:mm:ss}] {1}" -f (Get-Date), $msg
    Write-Host $line
    Add-Content -Path $LogFile -Value $line
}

Write-Log "=== TennisBot weekly refresh start (tour=$Tour) ==="
Write-Log "Root: $Root"
Write-Log "Log:  $LogFile"

# Load local secrets if present
foreach ($envFile in @(".env", "local.env")) {
    $p = Join-Path $Root $envFile
    if (Test-Path $p) {
        Get-Content $p | ForEach-Object {
            if ($_ -match '^\s*#' -or $_ -match '^\s*$') { return }
            $kv = $_ -split '=', 2
            if ($kv.Count -eq 2) {
                [System.Environment]::SetEnvironmentVariable($kv[0].Trim(), $kv[1].Trim(), "Process")
            }
        }
        Write-Log "Loaded env from $envFile"
    }
}

$argsList = @("main.py", "refresh", "--tour", $Tour, "--optuna-trials", "$OptunaTrials")
if ($SettleOnly) { $argsList += "--settle-only" }
if ($SkipTrain)  { $argsList += "--skip-train" }

Write-Log ("Running: python " + ($argsList -join " "))
& python @argsList 2>&1 | Tee-Object -FilePath $LogFile -Append
$code = $LASTEXITCODE
Write-Log "=== Refresh finished with exit code $code ==="
exit $code
