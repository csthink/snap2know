#!/bin/bash
# ==================================================
#  Snap2Know Device Agent - One-Key Start Script
# ==================================================
# Usage: ./start_agent.sh
#        ./start_agent.sh --help
# 
# This script activates the virtual environment and
# runs the device agent with proper error handling.
# ==================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
VENV_PATH="$PROJECT_ROOT/.venv"
MAIN_PY="$SCRIPT_DIR/main.py"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_banner() {
    echo "=================================================="
    echo "  Snap2Know Device Agent v3.0"
    echo "=================================================="
}

check_requirements() {
    # Check if venv exists
    if [ ! -d "$VENV_PATH" ]; then
        echo -e "${RED}[ERROR] Virtual environment not found at: $VENV_PATH${NC}"
        echo "Please run: python -m venv $VENV_PATH && pip install -r requirements.txt"
        exit 1
    fi
    
    # Check if main.py exists
    if [ ! -f "$MAIN_PY" ]; then
        echo -e "${RED}[ERROR] main.py not found at: $MAIN_PY${NC}"
        exit 1
    fi
}

start_agent() {
    echo -e "${GREEN}[INFO] Activating virtual environment...${NC}"
    source "$VENV_PATH/bin/activate"
    
    echo -e "${GREEN}[INFO] Starting Device Agent...${NC}"
    echo -e "${YELLOW}[TIP] Press Ctrl+C to stop${NC}"
    echo ""
    
    # Run main.py with unbuffered output
    cd "$SCRIPT_DIR"
    python -u main.py "$@"
}

show_help() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --help      Show this help message"
    echo "  --check     Check requirements only, don't start"
    echo ""
    echo "Environment:"
    echo "  Project Root: $PROJECT_ROOT"
    echo "  Venv Path:    $VENV_PATH"
    echo "  Main Script:  $MAIN_PY"
}

# Main
case "$1" in
    --help|-h)
        show_help
        exit 0
        ;;
    --check)
        print_banner
        check_requirements
        echo -e "${GREEN}[OK] All requirements met${NC}"
        exit 0
        ;;
    *)
        print_banner
        check_requirements
        start_agent "$@"
        ;;
esac
