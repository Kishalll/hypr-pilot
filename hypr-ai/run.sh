#!/bin/bash
# run.sh - Manage Ollama lifecycle and start Hypr-AI CLI
SCRIPT_DIR=$(dirname "$(readlink -f "$0")")

# Offline optimizations
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1

# 1. Start Ollama in background if not running
if ! pgrep -x "ollama" > /dev/null; then
    ollama serve > /dev/null 2>&1 &
    OLLAMA_PID=$!
    # Ensure Ollama stops when the script exits
    trap "kill $OLLAMA_PID 2>/dev/null; exit" EXIT INT TERM
    
    # Wait for Ollama to be ready
    MAX_RETRIES=30
    COUNT=0
    until curl -s http://localhost:11434/api/tags > /dev/null || [ $COUNT -eq $MAX_RETRIES ]; do
        sleep 1
        ((COUNT++))
    done

    if [ $COUNT -eq $MAX_RETRIES ]; then
        echo "Error: Ollama service failed to start after ${MAX_RETRIES}s."
        exit 1
    fi
fi

# 2. Run the CLI
source "$SCRIPT_DIR/venv/bin/activate"
python3 "$SCRIPT_DIR/src/cli.py"

# Cleanup happens via trap if we started it
