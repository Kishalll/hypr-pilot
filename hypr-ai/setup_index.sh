#!/bin/bash
# setup_index.sh - Set up Hypr-AI environment and build index
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
DATASET_DIR="$SCRIPT_DIR/../datasets"

echo "Setting up dataset directories..."
mkdir -p "$DATASET_DIR/hyde" "$DATASET_DIR/ill-imp" "$DATASET_DIR/m4lw"

TMP_DIR=$(mktemp -d -t hypr-pilot-fetch-XXXXXX)
trap 'rm -rf "$TMP_DIR"' EXIT

echo "Fetching HyDE (Locked to 3c8b0df)..."
git clone --quiet --filter=blob:none https://github.com/prasanthrangan/hyprdots.git "$TMP_DIR/hyde"
(
    cd "$TMP_DIR/hyde" || exit 1
    git checkout --quiet 3c8b0dfb5e7f8e41a67b80463513f10d57cab1a4
    find . -type f -path "*/hypr/*" -name "*.conf" -exec cp --backup=numbered {} "$DATASET_DIR/hyde/" \;
)

echo "Fetching end4/ill-imp (Locked to 6e76977)..."
git clone --quiet --filter=blob:none https://github.com/end-4/dots-hyprland.git "$TMP_DIR/end4"
(
    cd "$TMP_DIR/end4" || exit 1
    git checkout --quiet 6e769779764d476abea3c6c8a195b73b0988679a
    find . -type f -path "*/hypr/*" -name "*.conf" -exec cp --backup=numbered {} "$DATASET_DIR/ill-imp/" \;
)

echo "Fetching ML4W (Locked to bcac864)..."
git clone --quiet --filter=blob:none https://github.com/mylinuxforwork/dotfiles.git "$TMP_DIR/m4lw"
(
    cd "$TMP_DIR/m4lw" || exit 1
    git checkout --quiet bcac864cd1c450cb445c4cac6e3b2c0f678febb5
    find . -type f -path "*/hypr/*" -name "*.conf" -exec cp --backup=numbered {} "$DATASET_DIR/m4lw/" \;
)

echo "Dataset fetching complete."

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
