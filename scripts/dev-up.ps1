# AGROAI — local dev mode (no Docker).
# Opens three windows: API (0.0.0.0:8000, reachable by ESP32 on the LAN), simulation worker, dashboard.

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$venvPy = Join-Path $root "backend\.venv\Scripts\python.exe"

if (-not (Test-Path $venvPy)) {
    Write-Host "== creating Python venv and installing backend (incl. YAMNet runtime) =="
    py -m venv "$root\backend\.venv"
    & $venvPy -m pip install --upgrade pip
    & $venvPy -m pip install -e "$root\backend[dev,ml]" "setuptools<81"
}

if (-not (Test-Path "$root\frontend\node_modules")) {
    Write-Host "== installing frontend packages =="
    Push-Location "$root\frontend"; npm install; Pop-Location
}

Start-Process powershell -ArgumentList @("-NoExit", "-Command",
    "`$host.UI.RawUI.WindowTitle='AGROAI API'; & '$venvPy' '$root\backend\scripts\dev_server.py'")
Start-Sleep -Seconds 4
Start-Process powershell -ArgumentList @("-NoExit", "-Command",
    "`$host.UI.RawUI.WindowTitle='AGROAI simulator'; & '$venvPy' '$root\backend\scripts\dev_worker.py'")
Start-Process powershell -ArgumentList @("-NoExit", "-Command",
    "`$host.UI.RawUI.WindowTitle='AGROAI dashboard'; Set-Location '$root\frontend'; npm run dev")

$ip = (Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
       Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254*" } |
       Select-Object -First 1).IPAddress
Write-Host ""
Write-Host "Dashboard:      http://localhost:5173"
Write-Host "API docs:       http://localhost:8000/docs"
Write-Host "ESP32 server:   http://$($ip):8000   (allow inbound TCP 8000 in Windows Firewall)"
Write-Host "Dev database:   $root\agroai-dev.db"
