#!/bin/bash
# grabs hyprland dotfiles from community repos and builds the FAISS index
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
DATASET_DIR="$SCRIPT_DIR/../datasets"

copy_clean_hypr_confs() {
    local repo_root="$1"
    local dataset_out="$2"

    mkdir -p "$dataset_out"
    while IFS= read -r -d '' src; do
        rel="${src#./}"
        dest="$dataset_out/$rel"
        mkdir -p "$(dirname "$dest")"
        cp "$src" "$dest"
    done < <(
        cd "$repo_root" && find . -type f -path "*/hypr/*" -name "*.conf" \
            ! -name "*~" ! -name "*.bak" ! -name "*.orig" ! -name "*.rej" -print0
    )
}

echo "Setting up dataset directories..."
mkdir -p "$DATASET_DIR/hyde" "$DATASET_DIR/ill-imp" "$DATASET_DIR/m4lw"

HAS_EXISTING_DATASETS=false
if find "$DATASET_DIR/hyde" "$DATASET_DIR/ill-imp" "$DATASET_DIR/m4lw" -type f -name "*.conf" -print -quit | grep -q .; then
    HAS_EXISTING_DATASETS=true
fi

REINSTALL_DATASETS=true
if [ "$HAS_EXISTING_DATASETS" = true ]; then
    while true; do
        read -rp "Datasets already found. Reinstall and refetch from pinned commits? (y/n/c): " REINSTALL_CHOICE
        case "$REINSTALL_CHOICE" in
            [Yy])
                REINSTALL_DATASETS=true
                break
                ;;
            [Nn])
                REINSTALL_DATASETS=false
                break
                ;;
            [Cc])
                echo "Setup cancelled by user."
                exit 0
                ;;
            *)
                echo "Please enter y (reinstall), n (keep existing), or c (cancel)."
                ;;
        esac
    done
fi

if [ "$REINSTALL_DATASETS" = true ]; then
    echo "Reinstalling datasets from pinned commits..."
    rm -rf "$DATASET_DIR/hyde"/* "$DATASET_DIR/ill-imp"/* "$DATASET_DIR/m4lw"/*
else
    echo "Keeping existing datasets. Skipping dataset refetch."
fi

# temp folder that auto-cleans on exit
TMP_DIR=$(mktemp -d -t hypr-pilot-fetch-XXXXXX)
trap 'rm -rf "$TMP_DIR"' EXIT

if [ "$REINSTALL_DATASETS" = true ]; then
    echo "Fetching HyDE (Locked to 3c8b0df)..."
    git clone --quiet --filter=blob:none https://github.com/prasanthrangan/hyprdots.git "$TMP_DIR/hyde"
    (
        cd "$TMP_DIR/hyde" || exit 1
        git checkout --quiet 3c8b0dfb5e7f8e41a67b80463513f10d57cab1a4
        copy_clean_hypr_confs "$PWD" "$DATASET_DIR/hyde"
    )

    echo "Fetching end4/ill-imp (Locked to 6e76977)..."
    git clone --quiet --filter=blob:none https://github.com/end-4/dots-hyprland.git "$TMP_DIR/end4"
    (
        cd "$TMP_DIR/end4" || exit 1
        git checkout --quiet 6e769779764d476abea3c6c8a195b73b0988679a
        copy_clean_hypr_confs "$PWD" "$DATASET_DIR/ill-imp"
    )

    echo "Fetching ML4W (Locked to bcac864)..."
    git clone --quiet --filter=blob:none https://github.com/mylinuxforwork/dotfiles.git "$TMP_DIR/m4lw"
    (
        cd "$TMP_DIR/m4lw" || exit 1
        git checkout --quiet bcac864cd1c450cb445c4cac6e3b2c0f678febb5
        copy_clean_hypr_confs "$PWD" "$DATASET_DIR/m4lw"
    )

    echo "Dataset fetching complete."
fi

# venv setup
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
echo ""

# offer to set up the global 'hyprpilot' command
read -rp "Set up the 'hyprpilot' command so you can launch from anywhere? (y/n): " SETUP_ALIAS
if [[ "$SETUP_ALIAS" =~ ^[Yy]$ ]]; then
    bash "$SCRIPT_DIR/setup_alias.sh"
else
    echo "Skipped. You can always set it up later by running: bash setup_alias.sh"
fi

echo ""
echo "You can now run 'bash run.sh' to start Hypr-Pilot."
