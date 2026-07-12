@echo off
REM Dev startup script — kills stale servers, initializes DB, starts with --reload
REM Run from: app\ directory

setlocal

echo [DEV] Stopping any existing backend on port 8000...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000 ^| findstr LISTENING') do (
    taskkill /F /PID %%a >nul 2>&1
)

echo [DEV] Stopping any existing frontend on port 5173...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5173 ^| findstr LISTENING') do (
    taskkill /F /PID %%a >nul 2>&1
)

REM Move to repo root for proper imports
cd /d "%~dp0.."

echo [DEV] Initializing database schema...
poetry run python -m app.backend.scripts.db_init
if %errorlevel% neq 0 (
    echo [ERROR] Database initialization failed
    pause
    exit /b 1
)

echo [DEV] Verifying routes...
poetry run python -m app.backend.scripts.verify_routes
if %errorlevel% neq 0 (
    echo [ERROR] Route verification failed
    pause
    exit /b 1
)

echo.
echo [DEV] Starting backend with --reload on port 8000...
start "Backend" cmd /c "poetry run uvicorn app.backend.main:app --reload --host 127.0.0.1 --port 8000"

timeout /t 4 /nobreak >nul

echo [DEV] Starting frontend on port 5173...
cd app\frontend
start "Frontend" cmd /c "npm run dev"
cd /d "%~dp0.."

timeout /t 3 /nobreak >nul

echo.
echo ============================================================
echo   Backend API:   http://localhost:8000
echo   Swagger Docs:  http://localhost:8000/docs
echo   Frontend:      http://localhost:5173
echo ============================================================
echo.
echo Press any key to stop both services...
pause >nul

taskkill /f /fi "WINDOWTITLE eq Backend" >nul 2>&1
taskkill /f /fi "WINDOWTITLE eq Frontend" >nul 2>&1
echo [DEV] Services stopped.
