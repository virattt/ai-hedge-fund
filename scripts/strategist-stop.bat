@echo off
REM Strategist — stop the running server (port 8765).
setlocal
echo [strategist] stopping any process bound to TCP/8765 ...
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 8765 -ErrorAction SilentlyContinue | ForEach-Object { try { Stop-Process -Id $_.OwningProcess -Force -ErrorAction Stop; Write-Host '[strategist] stopped PID ' $_.OwningProcess } catch { } }"
endlocal & exit /b 0
