# Stop AGROAI dev processes started by dev-up.ps1.
# Kills uvicorn, the simulation worker, and the Vite dev server.

Get-Process python -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -match "uvicorn|app\.simulation\.worker" } |
    Stop-Process -Force -ErrorAction SilentlyContinue

Get-Process node -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -match "vite" } |
    Stop-Process -Force -ErrorAction SilentlyContinue

Write-Host "dev processes stopped (if any were running)."
