@echo off
REM Strategist — install autostart on Windows login.
REM
REM Drops a shortcut into the Windows Startup folder so the server boots
REM automatically when you log in. Idempotent. Uninstall with
REM scripts\uninstall-autostart.bat.

setlocal
set "PROJECT_ROOT=%~dp0.."
set "STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "SHORTCUT=%STARTUP_DIR%\Strategist.lnk"
set "TARGET=%PROJECT_ROOT%\scripts\strategist-start.bat"

REM Resolve to absolute paths
for %%I in ("%TARGET%") do set "TARGET=%%~fI"
for %%I in ("%PROJECT_ROOT%") do set "PROJECT_ROOT=%%~fI"

if not exist "%STARTUP_DIR%" (
    echo [strategist] Startup folder not found: %STARTUP_DIR%
    exit /b 1
)

if not exist "%TARGET%" (
    echo [strategist] launcher not found at: %TARGET%
    exit /b 1
)

REM Build the shortcut via a single-line PowerShell command so cmd.exe ^ continuation rules don't break it.
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%SHORTCUT%'); $s.TargetPath = '%TARGET%'; $s.Arguments = ''; $s.WorkingDirectory = '%PROJECT_ROOT%'; $s.WindowStyle = 7; $s.Description = 'Strategist - local AI hedge fund dashboard'; $s.Save()"

if exist "%SHORTCUT%" (
    echo [strategist] OK - autostart installed.
    echo [strategist] Shortcut: %SHORTCUT%
    echo [strategist] On next login, Strategist will boot silently at http://127.0.0.1:8765/
    echo [strategist] To start it right now without rebooting: scripts\strategist-start.bat --open
    exit /b 0
) else (
    echo [strategist] FAILED to create shortcut at %SHORTCUT%
    exit /b 1
)
