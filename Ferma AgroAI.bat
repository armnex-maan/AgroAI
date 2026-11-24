@echo off
title AgroAI - Arresto
echo Arresto dei server AgroAI...

for %%P in (8000 5173) do (
  for /f "tokens=5" %%I in ('netstat -ano ^| findstr /r /c:":%%P .*LISTENING"') do (
    echo Chiudo il processo %%I sulla porta %%P
    taskkill /PID %%I /T /F >nul 2>&1
  )
)

echo Fatto.
timeout /t 3 >nul
