@echo off
title AgroAI - Avvio
cd /d "%~dp0"

echo Avvio di AgroAI...
echo.

if not exist "backend\.venv\Scripts\python.exe" (
  echo [ERRORE] Ambiente Python non trovato in backend\.venv
  pause
  exit /b 1
)

echo [1/2] Server API  -  http://localhost:8000
start "AgroAI API" /D "%~dp0backend" cmd /k ".venv\Scripts\python.exe scripts\dev_server.py"

echo [2/2] App web     -  http://localhost:5173
start "AgroAI Web" /D "%~dp0frontend" cmd /k "npm run dev"

echo.
echo Attendo che i server siano pronti...
timeout /t 8 /nobreak >nul
start "" "http://localhost:5173"

echo.
echo AgroAI e' avviato. Per spegnerlo chiudi le due finestre "AgroAI API" e "AgroAI Web"
echo oppure usa "Ferma AgroAI.bat".
timeout /t 5 >nul
