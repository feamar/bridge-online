# Starts everything for a practice session on this Windows pc:
#   1. BEN (gameapi.exe), the bidding engine for the opponents and the review
#   2. a Cloudflare quick tunnel, so your partner can reach the app from anywhere
#   3. the Bridge Oefenen server itself
# Close this window (or press Ctrl+C) to stop everything again.

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Tools = Join-Path $Root "tools"
$Venv = Join-Path $Root ".venv"
$Port = 8000
$BenUrl = "http://127.0.0.1:8085"
$started = @()

function Say($text, $color = "Gray") { Write-Host $text -ForegroundColor $color }

function Test-Url($url) {
    try { Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 3 | Out-Null; return $true }
    catch { return $false }
}

New-Item -ItemType Directory -Force -Path $Tools | Out-Null

# ---------- 1. Python environment ----------
$Python = Join-Path $Venv "Scripts\python.exe"
if (-not (Test-Path $Python)) {
    Say "Eerste keer: Python-omgeving maken..." Cyan
    $made = $false
    foreach ($v in "-3.13", "-3.12") {
        try {
            & py $v -m venv $Venv
            if ($LASTEXITCODE -eq 0) { $made = $true; break }
        } catch {}
    }
    if (-not $made) {
        Say "Python 3.13 of 3.12 niet gevonden. Installeer Python 3.13 via https://www.python.org/downloads/windows/ en start opnieuw." Red
        Read-Host "Druk op Enter om te sluiten"; exit 1
    }
}
Say "Benodigde pakketten controleren..." Cyan
& $Python -m pip install --quiet --disable-pip-version-check -r (Join-Path $Root "server\requirements.txt")
if ($LASTEXITCODE -ne 0) { Say "Installeren van pakketten mislukt." Red; Read-Host "Druk op Enter om te sluiten"; exit 1 }

try {
    # ---------- 2. BEN ----------
    if (Test-Url "$BenUrl/") {
        Say "BEN draait al." Green
    } else {
        $candidates = @($env:BEN_DIR, (Join-Path $Root "ben"), (Join-Path (Split-Path -Parent $Root) "BENAPI"), "C:\BEN", "C:\BENAPI") |
            Where-Object { $_ -and (Test-Path $_) }
        $gameapi = $candidates | ForEach-Object {
            Get-ChildItem -Path $_ -Filter "gameapi.exe" -Recurse -Depth 2 -ErrorAction SilentlyContinue
        } | Select-Object -First 1

        if ($gameapi) {
            Say "BEN starten vanuit $($gameapi.DirectoryName) (dit kan een minuut duren)..." Cyan
            $ben = Start-Process -FilePath $gameapi.FullName -WorkingDirectory $gameapi.DirectoryName `
                -WindowStyle Minimized -PassThru
            $started += $ben
            $deadline = (Get-Date).AddMinutes(4)
            while (-not (Test-Url "$BenUrl/")) {
                if ($ben.HasExited) { Say "BEN is gestopt tijdens het opstarten." Red; break }
                if ((Get-Date) -gt $deadline) { Say "BEN reageert nog niet; ik ga toch verder." Yellow; break }
                Start-Sleep -Seconds 3
            }
            if (Test-Url "$BenUrl/") { Say "BEN is klaar." Green }
        } else {
            Say "BEN (gameapi.exe) niet gevonden. De tegenstanders passen dan alleen maar." Yellow
            Say "Zie README.md, kopje 'BEN installeren'." Yellow
        }
    }

    # ---------- 3. Tunnel ----------
    $cloudflared = Join-Path $Tools "cloudflared.exe"
    if (-not (Test-Path $cloudflared)) {
        Say "Eerste keer: Cloudflare-tunnelprogramma downloaden..." Cyan
        Invoke-WebRequest -UseBasicParsing -OutFile $cloudflared `
            -Uri "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
    }
    $tunnelLog = Join-Path $Tools "tunnel.log"
    Remove-Item $tunnelLog -ErrorAction SilentlyContinue
    $tunnel = Start-Process -FilePath $cloudflared -WindowStyle Hidden -PassThru `
        -ArgumentList "tunnel", "--no-autoupdate", "--url", "http://localhost:$Port", "--logfile", "`"$tunnelLog`""
    $started += $tunnel

    $publicUrl = $null
    $deadline = (Get-Date).AddSeconds(45)
    while (-not $publicUrl -and (Get-Date) -lt $deadline) {
        Start-Sleep -Seconds 1
        if (Test-Path $tunnelLog) {
            $m = Select-String -Path $tunnelLog -Pattern "https://[a-z0-9-]+\.trycloudflare\.com" | Select-Object -First 1
            if ($m) { $publicUrl = $m.Matches[0].Value }
        }
    }

    Say ""
    if ($publicUrl) {
        Say "==============================================================" Green
        Say "  Open op jullie telefoons:  $publicUrl" Green
        Say "  (dit adres is nieuw bij elke start; deel het met de knop" Green
        Say "   'Tafel ...' in de app of stuur het via WhatsApp)" Green
        Say "==============================================================" Green
        $env:PUBLIC_URL = $publicUrl
        try { Set-Clipboard -Value $publicUrl; Say "  Het adres staat ook op je klembord." Gray } catch {}
    } else {
        Say "De tunnel kwam niet op tijd op. In hetzelfde wifi-netwerk werkt http://<ip-van-deze-pc>:$Port wel." Yellow
    }
    Say ""

    # ---------- 4. The app ----------
    $env:BEN_URL = $BenUrl
    Say "Bridge Oefenen draait. Sluit dit venster om alles te stoppen." Cyan
    & $Python -m uvicorn main:app --app-dir (Join-Path $Root "server") --host 0.0.0.0 --port $Port --log-level warning
}
finally {
    foreach ($p in $started) {
        if ($p -and -not $p.HasExited) { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue }
    }
}
