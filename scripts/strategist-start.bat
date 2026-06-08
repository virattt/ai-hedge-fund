@echo off
REM Strategist — silent background launcher.
REM Launches snapshot-ui detached so the console window closes immediately.
REM Logs go to %USERPROFILE%\.strategist\logs\strategist.log
REM
REM Usage:
REM   scripts\strategist-start.bat            ← starts the server in background
REM   scripts\strategist-start.bat --open     ← also opens the browser
REM   scripts\strategist-start.bat --foreground ← keep the console window open

setlocal

REM === Resolve project root regardless of where you run this from ===
set "PROJECT_ROOT=%~dp0.."
pushd "%PROJECT_ROOT%"

REM === Set up data + log directories under ~/.strategist ===
if not exist "%USERPROFILE%\.strategist\logs" mkdir "%USERPROFILE%\.strategist\logs" >nul 2>&1

REM === Already running? ===
curl -fsS http://127.0.0.1:8765/api/settings -o nul --connect-timeout 1 >nul 2>&1
if not errorlevel 1 (
    echo [strategist] already running at http://127.0.0.1:8765/
    if "%~1"=="--open" start "" "http://127.0.0.1:8765/"
    popd & endlocal & exit /b 0
)

REM === Locate poetry ===
set "POETRY=%APPDATA%\Python\Scripts\poetry.exe"
if not exist "%POETRY%" set "POETRY=poetry"

REM === Foreground mode (visible console) ===
if "%~1"=="--foreground" (
    "%POETRY%" run python -X utf8 -m src.analysis.web --no-open
    popd & endlocal & exit /b 0
)

REM === Background mode (default): detach via start /B, log to file ===
echo [strategist] starting in background on http://127.0.0.1:8765/
echo [strategist] logs: %USERPROFILE%\.strategist\logs\strategist.log
start "Strategist" /MIN cmd /c ""%POETRY%" run python -X utf8 -m src.analysis.web --no-open >> "%USERPROFILE%\.strategist\logs\strategist.log" 2>&1"

REM === Wait briefly, then optionally open the browser ===
if "%~1"=="--open" (
    timeout /T 3 /NOBREAK >nul
    start "" "http://127.0.0.1:8765/"
)

popd & endlocal & exit /b 0
