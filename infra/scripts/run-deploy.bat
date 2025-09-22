@echo off
REM Wrapper to run the PowerShell deployment script from any shell (avoids backtick/quoting issues)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0deploy-infrastructure.ps1" %*
