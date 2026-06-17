#!/bin/bash
# Dev startup script — kills stale servers, initializes DB, starts with --reload
# Run from: app/ directory

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

echo "[DEV] Stopping any existing backend on port 8000..."
lsof -ti :8000 2>/dev/null | xargs -r kill -9 2>/dev/null || true

echo "[DEV] Stopping any existing frontend on port 5173..."
lsof -ti :5173 2>/dev/null | xargs -r kill -9 2>/dev/null || true

cd "$REPO_ROOT"

echo "[DEV] Initializing database schema..."
.venv/bin/python -m app.backend.scripts.db_init || poetry run python -m app.backend.scripts.db_init

echo "[DEV] Verifying routes..."
.venv/bin/python -m app.backend.scripts.verify_routes || poetry run python -m app.backend.scripts.verify_routes

echo ""
echo "[DEV] Starting backend with --reload on port 8000..."
(.venv/bin/python -m uvicorn app.backend.main:app --reload --host 127.0.0.1 --port 8000 &)
BACKEND_PID=$!

sleep 4

echo "[DEV] Starting frontend on port 5173..."
(cd "$SCRIPT_DIR/frontend" && npm run dev &)
FRONTEND_PID=$!

sleep 3

echo ""
echo "============================================================"
echo "  Backend API:   http://localhost:8000"
echo "  Swagger Docs:  http://localhost:8000/docs"
echo "  Frontend:      http://localhost:5173"
echo "============================================================"
echo ""
echo "Press Ctrl+C to stop both services"

cleanup() {
    echo ""
    echo "[DEV] Stopping services..."
    kill $BACKEND_PID 2>/dev/null || true
    kill $FRONTEND_PID 2>/dev/null || true
    exit 0
}
trap cleanup SIGINT SIGTERM

wait
