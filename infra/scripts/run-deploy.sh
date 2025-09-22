#!/usr/bin/env bash
# Wrapper to run the PowerShell deployment script from bash/WSL/git-bash
if command -v pwsh >/dev/null 2>&1; then
  pwsh -NoProfile -File "$(dirname "$0")/deploy-infrastructure.ps1" "$@"
else
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$(dirname "$0")/deploy-infrastructure.ps1" "$@"
fi
