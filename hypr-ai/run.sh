#!/bin/bash
# starts ollama (if needed) and drops you into the hypr-pilot prompt
SCRIPT_DIR=$(dirname "$(readlink -f "$0")")

# skip network calls for model/tokenizer loading
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1

if ! pgrep -x "ollama" > /dev/null; then
    ollama serve > /dev/null 2>&1 &
    OLLAMA_PID=$!
    trap "kill $OLLAMA_PID 2>/dev/null; exit" EXIT INT TERM
    
    # wait for ollama to come alive
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

source "$SCRIPT_DIR/venv/bin/activate"
python3 "$SCRIPT_DIR/src/cli.py"
