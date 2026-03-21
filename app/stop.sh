#!/bin/bash

# AI Hedge Fund Web Application Stop Script
# This script stops the running backend and frontend services

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to stop backend server
stop_backend() {
    print_status "Stopping backend server..."
    
    # Find uvicorn processes running the AI Hedge Fund backend
    local backend_pids=$(ps aux | grep -E "uvicorn.*app\.backend\.main:app|uvicorn.*main:app.*--port.*10000" | grep -v grep | awk '{print $2}')
    
    if [[ -z "$backend_pids" ]]; then
        print_warning "No backend server processes found"
        return 0
    fi
    
    # Kill each backend process
    local count=0
    for pid in $backend_pids; do
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || kill -9 "$pid" 2>/dev/null
            count=$((count + 1))
            print_success "Stopped backend process (PID: $pid)"
        fi
    done
    
    if [[ $count -gt 0 ]]; then
        print_success "Backend server stopped ($count process(es))"
    fi
}

# Function to stop frontend server
stop_frontend() {
    print_status "Stopping frontend server..."
    
    # Find npm/vite processes running the frontend dev server
    local frontend_pids=$(ps aux | grep -E "vite|npm run dev" | grep -E "frontend|5173" | grep -v grep | awk '{print $2}')
    
    if [[ -z "$frontend_pids" ]]; then
        print_warning "No frontend server processes found"
        return 0
    fi
    
    # Kill each frontend process
    local count=0
    for pid in $frontend_pids; do
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || kill -9 "$pid" 2>/dev/null
            count=$((count + 1))
            print_success "Stopped frontend process (PID: $pid)"
        fi
    done
    
    if [[ $count -gt 0 ]]; then
        print_success "Frontend server stopped ($count process(es))"
    fi
}

# Function to check if services are still running
check_services() {
    print_status "Checking if services are stopped..."
    
    local backend_running=$(ps aux | grep -E "uvicorn.*app\.backend\.main:app|uvicorn.*main:app.*--port.*10000" | grep -v grep | wc -l)
    local frontend_running=$(ps aux | grep -E "vite|npm run dev" | grep -E "frontend|5173" | grep -v grep | wc -l)
    
    if [[ $backend_running -gt 0 ]]; then
        print_warning "Backend server may still be running ($backend_running process(es))"
        print_warning "You may need to manually kill these processes"
    fi
    
    if [[ $frontend_running -gt 0 ]]; then
        print_warning "Frontend server may still be running ($frontend_running process(es))"
        print_warning "You may need to manually kill these processes"
    fi
    
    if [[ $backend_running -eq 0 ]] && [[ $frontend_running -eq 0 ]]; then
        print_success "All services stopped successfully!"
    fi
}

# Function to stop services by port
stop_by_port() {
    local port=$1
    print_status "Stopping services on port $port..."
    
    # Find processes using the specified port
    local pids=$(lsof -ti:$port 2>/dev/null || true)
    
    if [[ -z "$pids" ]]; then
        print_warning "No processes found on port $port"
        return 0
    fi
    
    # Kill each process
    local count=0
    for pid in $pids; do
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || kill -9 "$pid" 2>/dev/null
            count=$((count + 1))
            print_success "Stopped process on port $port (PID: $pid)"
        fi
    done
    
    if [[ $count -gt 0 ]]; then
        print_success "Stopped $count process(es) on port $port"
    fi
}

# Main execution
main() {
    echo ""
    print_status "🛑 Stopping AI Hedge Fund Web Application"
    echo ""
    
    # Stop backend and frontend
    stop_backend
    stop_frontend
    
    # Also try to stop by port numbers (as a fallback)
    stop_by_port 10000  # Backend port
    stop_by_port 5173   # Frontend port
    
    # Give processes time to terminate
    sleep 1
    
    # Verify services are stopped
    check_services
    
    echo ""
    print_success "✅ AI Hedge Fund web application stopped!"
    echo ""
}

# Show help if requested
if [[ "$1" == "--help" ]] || [[ "$1" == "-h" ]]; then
    echo "AI Hedge Fund Web Application Stop Script"
    echo ""
    echo "Usage: ./stop.sh"
    echo ""
    echo "This script will:"
    echo "  1. Find and stop the backend API server (uvicorn)"
    echo "  2. Find and stop the frontend development server (vite/npm)"
    echo "  3. Stop any processes on ports 10000 (backend) and 5173 (frontend)"
    echo "  4. Verify all services are stopped"
    echo ""
    echo "Services that will be stopped:"
    echo "  - Backend API server (port 10000)"
    echo "  - Frontend development server (port 5173)"
    echo ""
    exit 0
fi

# Check if script is run with sudo (not needed)
if [[ $EUID -eq 0 ]]; then
    print_warning "This script does not need to be run with sudo"
    print_warning "Running as regular user is recommended"
    echo ""
fi

# Run main function
main
