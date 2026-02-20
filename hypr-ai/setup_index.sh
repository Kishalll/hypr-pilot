#!/bin/bash
# setup_index.sh - Set up Hypr-AI environment and build index
set -e
SCRIPT_DIR=$(dirname "$(readlink -f "$0")")

# Check if venv exists, create if not
if [ ! -d "$SCRIPT_DIR/venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$SCRIPT_DIR/venv"
fi

source "$SCRIPT_DIR/venv/bin/activate"

echo "Installing dependencies..."
pip install -r "$SCRIPT_DIR/requirements.txt" --quiet

echo "Ingesting datasets and generating chunks..."
python3 "$SCRIPT_DIR/src/ingest.py"

echo "Building FAISS index (this may take a few minutes)..."
python3 "$SCRIPT_DIR/src/vectorstore.py"

echo "Index successfully created."
echo "You can now run 'bash run.sh'"
