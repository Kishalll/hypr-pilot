#!/bin/bash
# drops a 'hyprpilot' wrapper into ~/.local/bin so you can launch from anywhere
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
RUN_SCRIPT="$SCRIPT_DIR/run.sh"
BIN_DIR="$HOME/.local/bin"
CMD_NAME="hyprpilot"
CMD_PATH="$BIN_DIR/$CMD_NAME"

if [ ! -f "$RUN_SCRIPT" ]; then
    echo "Error: run.sh not found at $RUN_SCRIPT"
    exit 1
fi

mkdir -p "$BIN_DIR"

cat > "$CMD_PATH" <<EOF
#!/bin/bash
exec "$RUN_SCRIPT" "\$@"
EOF

chmod +x "$CMD_PATH"

echo "'$CMD_NAME' installed to $CMD_PATH"

# not every distro has ~/.local/bin on PATH out of the box
if ! echo "$PATH" | tr ':' '\n' | grep -qx "$BIN_DIR"; then
    echo ""
    echo "Heads up: $BIN_DIR isn't in your PATH yet."
    echo "Toss this into your shell config (~/.bashrc, ~/.zshrc, etc.):"
    echo ""
    echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
    echo ""
    echo "Then restart your terminal or run: source ~/.bashrc"
else
    echo "You can now type '$CMD_NAME' from anywhere to launch Hypr-Pilot."
fi
