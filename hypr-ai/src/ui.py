"""
ui.py - Clean terminal UI for Hypr-Pilot (Gemini CLI-inspired)
Provides styled output for tool actions, spinners, confirmations, and responses.
"""

import sys
import time
import threading
import shutil

# ─── ANSI Colors ────────────────────────────────────────────────────────────────

class C:
    """ANSI color codes."""
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    ITALIC  = "\033[3m"

    # Foreground
    BLACK   = "\033[30m"
    RED     = "\033[31m"
    GREEN   = "\033[32m"
    YELLOW  = "\033[33m"
    BLUE    = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN    = "\033[36m"
    WHITE   = "\033[37m"

    # Bright foreground
    BRIGHT_BLACK  = "\033[90m"
    BRIGHT_RED    = "\033[91m"
    BRIGHT_GREEN  = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE   = "\033[94m"
    BRIGHT_MAGENTA= "\033[95m"
    BRIGHT_CYAN   = "\033[96m"
    BRIGHT_WHITE  = "\033[97m"

    # Background
    BG_BLACK  = "\033[40m"
    BG_RED    = "\033[41m"
    BG_GREEN  = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE   = "\033[44m"
    BG_MAGENTA= "\033[45m"
    BG_CYAN   = "\033[46m"
    BG_WHITE  = "\033[47m"


# ─── Unicode Box Chars ──────────────────────────────────────────────────────────

BOX_H  = "─"
BOX_V  = "│"
BOX_TL = "╭"
BOX_TR = "╮"
BOX_BL = "╰"
BOX_BR = "╯"

# ─── Helpers ─────────────────────────────────────────────────────────────────────

def _term_width():
    return min(shutil.get_terminal_size((80, 24)).columns, 100)


def _bar(left, fill, right, width=None):
    w = (width or _term_width()) - 2  # subtract corners
    return f"{left}{fill * w}{right}"


# ─── Spinner ─────────────────────────────────────────────────────────────────────

class Spinner:
    """Animated spinner that runs in a background thread."""
    FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(self, message="Thinking"):
        self.message = message
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        self._stop.clear()
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()

    def _spin(self):
        i = 0
        while not self._stop.is_set():
            frame = self.FRAMES[i % len(self.FRAMES)]
            sys.stderr.write(f"\r  {C.CYAN}{frame}{C.RESET} {C.DIM}{self.message}...{C.RESET}  ")
            sys.stderr.flush()
            i += 1
            time.sleep(0.08)

    def stop(self, clear=True):
        self._stop.set()
        if self._thread:
            self._thread.join()
        if clear:
            sys.stderr.write("\r" + " " * (_term_width()) + "\r")
            sys.stderr.flush()


# ─── Tool Action Display ────────────────────────────────────────────────────────

# Friendly descriptions for each tool
TOOL_LABELS = {
    "get_window_class":     ("🔍", "Looking up window class"),
    "get_active_config_paths": ("📂", "Finding config file paths"),
    "list_directory":       ("📁", "Listing directory"),
    "read_file":            ("📄", "Reading file"),
    "write_file":           ("✏️ ", "Writing file"),
    "append_file":          ("📝", "Appending to file"),
    "execute_command":      ("⚡", "Running command"),
}

_step_counter = 0

def reset_steps():
    global _step_counter
    _step_counter = 0

def tool_action(name, args, step=None):
    """Print a clean, boxed tool action line. Returns the step number used."""
    global _step_counter
    _step_counter += 1
    n = step or _step_counter

    icon, label = TOOL_LABELS.get(name, ("🔧", f"Calling {name}"))

    # Build detail string based on tool type
    detail = ""
    if name == "get_window_class":
        detail = f"app = {C.BRIGHT_YELLOW}{args.get('app_name', '?')}{C.RESET}"
    elif name == "get_active_config_paths":
        detail = f"{C.DIM}~/.config/hypr/hyprland.conf{C.RESET}"
    elif name == "list_directory":
        detail = f"path = {C.BRIGHT_YELLOW}{args.get('dir_path', '.')}{C.RESET}"
    elif name == "read_file":
        detail = f"path = {C.BRIGHT_YELLOW}{args.get('file_path', '?')}{C.RESET}"
    elif name in ("write_file", "append_file"):
        detail = f"path = {C.BRIGHT_YELLOW}{args.get('file_path', '?')}{C.RESET}"
    elif name == "execute_command":
        cmd = args.get('command', '?')
        if len(cmd) > 60:
            cmd = cmd[:57] + "..."
        detail = f"`{C.BRIGHT_YELLOW}{cmd}{C.RESET}`"

    w = _term_width()
    print(f"\n  {C.BRIGHT_BLACK}{BOX_TL}{BOX_H * (w - 4)}{BOX_TR}{C.RESET}")
    print(f"  {C.BRIGHT_BLACK}{BOX_V}{C.RESET} {C.CYAN}{C.BOLD}Step {n}{C.RESET}  {icon}  {label}  {detail}")
    print(f"  {C.BRIGHT_BLACK}{BOX_BL}{BOX_H * (w - 4)}{BOX_BR}{C.RESET}")

    return n


# ─── Confirmation Prompt ─────────────────────────────────────────────────────────

def confirm_action(name, args):
    """Pretty confirmation prompt for destructive actions. Returns 'y', 'n', or 'a'."""
    w = _term_width()

    # Show what will be changed
    if name in ("write_file", "append_file"):
        content = args.get("content", "")
        path = args.get("file_path", "?")
        action_word = "Overwrite" if name == "write_file" else "Append to"

        print(f"\n  {C.YELLOW}{C.BOLD}  ⚠  {action_word}: {path}{C.RESET}")

        # Show content preview in a dim code block
        lines = content.strip().split("\n")
        print(f"  {C.BRIGHT_BLACK}  ┌{'─' * (w - 6)}┐{C.RESET}")
        for line in lines[:10]:
            display_line = line[:w - 8]
            print(f"  {C.BRIGHT_BLACK}  │{C.RESET} {C.GREEN}{display_line}{C.RESET}")
        if len(lines) > 10:
            print(f"  {C.BRIGHT_BLACK}  │{C.RESET} {C.DIM}... ({len(lines) - 10} more lines){C.RESET}")
        print(f"  {C.BRIGHT_BLACK}  └{'─' * (w - 6)}┘{C.RESET}")

    elif name == "execute_command":
        cmd = args.get("command", "?")
        print(f"\n  {C.YELLOW}{C.BOLD}  ⚠  Execute: {C.RESET}{C.BRIGHT_YELLOW}{cmd}{C.RESET}")

    # Prompt
    try:
        choice = input(f"\n  {C.BOLD}  Confirm? {C.RESET}{C.DIM}[{C.RESET}{C.GREEN}y{C.RESET}{C.DIM}/{C.RESET}{C.RED}n{C.RESET}{C.DIM}/{C.RESET}{C.YELLOW}a{C.DIM}bort]{C.RESET} ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        choice = "a"

    return choice if choice in ("y", "n", "a") else "n"


# ─── Result Display ──────────────────────────────────────────────────────────────

def tool_result_success(message="Done"):
    print(f"  {C.GREEN}  ✓  {message}{C.RESET}")


def tool_result_error(message="Failed"):
    print(f"  {C.RED}  ✗  {message}{C.RESET}")


def tool_result_denied(message="Action denied"):
    print(f"  {C.YELLOW}  ⊘  {message}{C.RESET}")


def tool_result_aborted():
    print(f"  {C.YELLOW}  ■  Query aborted by user.{C.RESET}")


# ─── Welcome / Prompt ────────────────────────────────────────────────────────────

def welcome():
    w = _term_width()
    print()
    print(f"  {C.CYAN}{C.BOLD}{'─' * (w - 4)}{C.RESET}")
    print(f"  {C.CYAN}{C.BOLD}  Hypr-Pilot{C.RESET}  {C.DIM}— your Hyprland config assistant{C.RESET}")
    print(f"  {C.CYAN}{C.BOLD}{'─' * (w - 4)}{C.RESET}")
    print(f"  {C.DIM}Type your question, or 'exit' to quit.{C.RESET}")
    print()


def prompt():
    """Display the user input prompt and return input. Raises EOFError on Ctrl-C/D."""
    try:
        return input(f"\n  {C.BRIGHT_GREEN}{C.BOLD}You ❯{C.RESET} ")
    except (EOFError, KeyboardInterrupt):
        raise EOFError


def response_start():
    """Print the assistant response header."""
    print(f"\n  {C.BRIGHT_CYAN}{C.BOLD}Hypr-Pilot ❯{C.RESET} ", end="", flush=True)


def response_token(token):
    """Print a single streamed token."""
    sys.stdout.write(token)
    sys.stdout.flush()


def response_end():
    """Finish the response."""
    print()


def divider():
    w = _term_width()
    print(f"\n  {C.BRIGHT_BLACK}{'─' * (w - 4)}{C.RESET}")
