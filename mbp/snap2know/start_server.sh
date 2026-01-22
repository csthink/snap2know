#!/bin/bash
cd "$(dirname "$0")"

print_color() {
    echo -e "\033[1;32m$1\033[0m"
}

print_color "Stopping existing backend..."
pkill -f "uvicorn main:app" || true

print_color "Starting Snap2Know MBP Backend..."
source .venv/bin/activate

# Use uvicorn with reload for development
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
