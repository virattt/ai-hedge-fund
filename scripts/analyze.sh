#!/usr/bin/env bash
#
# Interactive launcher for the AI hedge fund analysis.
# Prompts for one or more stock tickers (comma-separated), then runs the
# analysis via src/main.py. Any extra flags passed to this script are
# forwarded to main.py (e.g. --show-reasoning, --ollama, --model gpt-4o).
#
# Usage:
#   ./scripts/analyze.sh
#   ./scripts/analyze.sh --show-reasoning
#   TICKERS=AAPL,MSFT ./scripts/analyze.sh    # skip the prompt

set -euo pipefail

# Resolve project root (the directory containing this script's parent).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

# Accept tickers from the TICKERS env var, otherwise prompt interactively.
tickers="${TICKERS:-}"
while [[ -z "${tickers// /}" ]]; do
    read -r -p "Which stocks do you want to analyse? (comma-separated, e.g. AAPL,MSFT,GOOGL): " tickers
    if [[ -z "${tickers// /}" ]]; then
        echo "Please enter at least one ticker." >&2
    fi
done

# Normalise: strip spaces around commas and uppercase the symbols.
tickers="$(echo "${tickers}" | tr '[:lower:]' '[:upper:]' | tr -d '[:space:]')"

# Collect extra args passed straight to main.py.
extra_args=("$@")

# If Ollama is installed and the caller hasn't already specified a model
# source, offer to use a local model.
already_specified=false
for a in ${extra_args[@]+"${extra_args[@]}"}; do
    case "$a" in
        --ollama|--model) already_specified=true ;;
    esac
done

if ! ${already_specified} && command -v ollama >/dev/null 2>&1; then
    read -r -p "Use local Ollama model? [Y/n]: " use_ollama
    case "${use_ollama:-Y}" in
        [Nn]*) : ;;
        *) extra_args+=(--ollama) ;;
    esac
fi

echo "Analysing: ${tickers}"
echo

# Time the whole run. Capture the exit code so timing prints even on failure.
SECONDS=0
exit_code=0
# Run through poetry if available, otherwise fall back to python directly.
if command -v poetry >/dev/null 2>&1; then
    poetry run python src/main.py --tickers "${tickers}" ${extra_args[@]+"${extra_args[@]}"} || exit_code=$?
else
    python src/main.py --tickers "${tickers}" ${extra_args[@]+"${extra_args[@]}"} || exit_code=$?
fi

echo
echo "Total execution time: $((SECONDS / 60))m $((SECONDS % 60))s (${SECONDS}s)"
exit "${exit_code}"
