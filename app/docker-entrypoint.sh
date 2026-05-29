#!/bin/bash
# AI Hedge Fund Web App - Docker Entrypoint
# Starts both backend (FastAPI) and frontend (Vite) services

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Cleanup function
cleanup() {
    print_status "Shutting down services..."
    if [[ -n "$BACKEND_PID" ]] && kill -0 "$BACKEND_PID" 2>/dev/null; then
        kill "$BACKEND_PID" 2>/dev/null || true
    fi
    if [[ -n "$FRONTEND_PID" ]] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
        kill "$FRONTEND_PID" 2>/dev/null || true
    fi
    print_success "Services stopped."
    exit 0
}

trap cleanup SIGINT SIGTERM

# Check .env file
if [[ ! -f "/app/.env" ]]; then
    print_warning "No .env file found at /app/.env"
    print_warning "Some features requiring API keys may not work."
fi

# Start backend (FastAPI on 0.0.0.0:8000)
print_status "Starting backend server (FastAPI)..."
cd /app
uvicorn app.backend.main:app --host 0.0.0.0 --port 8000 > /tmp/backend.log 2>&1 &
BACKEND_PID=$!
print_success "Backend started (PID: $BACKEND_PID) on http://0.0.0.0:8000"

# Wait for backend to be ready
sleep 3
if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    print_error "Backend failed to start! Logs:"
    cat /tmp/backend.log
    exit 1
fi

# Start frontend (Vite dev server on 0.0.0.0:5173)
print_status "Starting frontend server (Vite)..."
cd /app/app/frontend
npx vite --host 0.0.0.0 --port 5173 > /tmp/frontend.log 2>&1 &
FRONTEND_PID=$!
print_success "Frontend started (PID: $FRONTEND_PID) on http://0.0.0.0:5173"

# Wait for frontend to be ready
sleep 3
if ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
    print_error "Frontend failed to start! Logs:"
    cat /tmp/frontend.log
    cleanup
    exit 1
fi

echo ""
print_success "============================================="
print_success "  AI Hedge Fund Web App is running!"
print_success "============================================="
print_status "Frontend: http://localhost:5173"
print_status "Backend:  http://localhost:8000"
print_status "API Docs: http://localhost:8000/docs"
echo ""
print_status "Press Ctrl+C to stop"
echo ""

# Monitor both processes
while true; do
    if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
        print_error "Backend process died unexpectedly!"
        cat /tmp/backend.log
        cleanup
        exit 1
    fi
    if ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
        print_error "Frontend process died unexpectedly!"
        cat /tmp/frontend.log
        cleanup
        exit 1
    fi
    sleep 2
done
