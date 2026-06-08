@echo off
REM Strategist — remove autostart shortcut. Server stays running until next restart.
setlocal
set "SHORTCUT=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\Strategist.lnk"
if exist "%SHORTCUT%" (
    del /Q "%SHORTCUT%" && echo [strategist] OK — autostart removed.
) else (
    echo [strategist] no autostart shortcut found at %SHORTCUT%
)
endlocal & exit /b 0
