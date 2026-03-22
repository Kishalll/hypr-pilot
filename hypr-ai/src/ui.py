"""terminal UI for hypr-pilot — spinners, tool displays, confirmations, all the pretty stuff."""

import sys
import time
import threading
import shutil



class C:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    ITALIC  = "\033[3m"


    BLACK   = "\033[30m"
    RED     = "\033[31m"
    GREEN   = "\033[32m"
    YELLOW  = "\033[33m"
    BLUE    = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN    = "\033[36m"
    WHITE   = "\033[37m"


    BRIGHT_BLACK  = "\033[90m"
    BRIGHT_RED    = "\033[91m"
    BRIGHT_GREEN  = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE   = "\033[94m"
    BRIGHT_MAGENTA= "\033[95m"
    BRIGHT_CYAN   = "\033[96m"
    BRIGHT_WHITE  = "\033[97m"


    BG_BLACK  = "\033[40m"
    BG_RED    = "\033[41m"
    BG_GREEN  = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE   = "\033[44m"
    BG_MAGENTA= "\033[45m"
    BG_CYAN   = "\033[46m"
    BG_WHITE  = "\033[47m"




BOX_H  = "─"
BOX_V  = "│"
BOX_TL = "╭"
BOX_TR = "╮"
BOX_BL = "╰"
BOX_BR = "╯"



def _term_width():
    return min(shutil.get_terminal_size((80, 24)).columns, 100)


def _bar(left, fill, right, width=None):
    w = (width or _term_width()) - 2  # subtract corners
    return f"{left}{fill * w}{right}"




class Spinner:
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




# friendly labels for each tool
TOOL_LABELS = {
    "get_window_class":     ("🔍", "Looking up window class"),
    "get_active_config_paths": ("📂", "Finding config file paths"),
    "list_directory":       ("📁", "Listing directory"),
    "read_file":            ("📄", "Reading file"),
    "write_file":           ("✏️ ", "Writing file"),
    "append_file":          ("📝", "Appending to file"),
    "replace_line":         ("🔄", "Replacing line in file"),
    "execute_command":      ("⚡", "Running command"),
    "make_directory":       ("📁", "Creating directory"),
    "file_exists":          ("🔎", "Checking if path exists"),
    "search_in_files":      ("🔍", "Searching in files"),
    "insert_line":          ("📌", "Inserting line(s)"),
    "delete_lines":         ("🗑️ ", "Deleting line(s)"),
    "validate_file":        ("🔬", "Validating file"),
}

_step_counter = 0

def reset_steps():
    global _step_counter
    _step_counter = 0

def tool_action(name, args, step=None):
    global _step_counter
    _step_counter += 1
    n = step or _step_counter

    icon, label = TOOL_LABELS.get(name, ("🔧", f"Calling {name}"))


    detail = ""
    if name == "get_window_class":
        detail = f"app = {C.BRIGHT_YELLOW}{args.get('app_name', '?')}{C.RESET}"
    elif name == "get_active_config_paths":
        detail = f"{C.DIM}~/.config/hypr/hyprland.conf{C.RESET}"
    elif name == "list_directory":
        detail = f"path = {C.BRIGHT_YELLOW}{args.get('dir_path', '.')}{C.RESET}"
    elif name == "read_file":
        detail = f"path = {C.BRIGHT_YELLOW}{args.get('file_path', '?')}{C.RESET}"
    elif name in ("write_file", "append_file", "replace_line"):
        detail = f"path = {C.BRIGHT_YELLOW}{args.get('file_path', '?')}{C.RESET}"
    elif name == "make_directory":
        detail = f"path = {C.BRIGHT_YELLOW}{args.get('dir_path', '?')}{C.RESET}"
    elif name == "file_exists":
        detail = f"path = {C.BRIGHT_YELLOW}{args.get('file_path', '?')}{C.RESET}"
    elif name == "search_in_files":
        pat = args.get('pattern', '?')
        detail = f"pattern = {C.BRIGHT_YELLOW}{pat}{C.RESET} in {C.DIM}{args.get('dir_path', '.')}{C.RESET}"
    elif name == "insert_line":
        ln = args.get('line_number', '?')
        detail = f"line {C.BRIGHT_YELLOW}{ln}{C.RESET} in {C.DIM}{args.get('file_path', '?')}{C.RESET}"
    elif name == "delete_lines":
        s = args.get('start_line', '?')
        e = args.get('end_line', s)
        detail = f"lines {C.BRIGHT_YELLOW}{s}-{e}{C.RESET} in {C.DIM}{args.get('file_path', '?')}{C.RESET}"
    elif name == "validate_file":
        run_flag = " + run" if args.get('run') else ""
        detail = f"path = {C.BRIGHT_YELLOW}{args.get('file_path', '?')}{C.RESET}{C.DIM}{run_flag}{C.RESET}"
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




def confirm_action(name, args):
    w = _term_width()


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

    elif name == "replace_line":
        path = args.get("file_path", "?")
        old_line = args.get("old_line", "?")
        new_line = args.get("new_line", "?")

        print(f"\n  {C.YELLOW}{C.BOLD}  ⚠  Replace in: {path}{C.RESET}")
        print(f"  {C.BRIGHT_BLACK}  ┌{'─' * (w - 6)}┐{C.RESET}")
        print(f"  {C.BRIGHT_BLACK}  │{C.RESET} {C.RED}- {old_line.strip()[:w - 10]}{C.RESET}")
        print(f"  {C.BRIGHT_BLACK}  │{C.RESET} {C.GREEN}+ {new_line.strip()[:w - 10]}{C.RESET}")
        print(f"  {C.BRIGHT_BLACK}  └{'─' * (w - 6)}┘{C.RESET}")

    elif name == "insert_line":
        path = args.get("file_path", "?")
        ln = args.get("line_number", "?")
        content = args.get("content", "")
        print(f"\n  {C.YELLOW}{C.BOLD}  ⚠  Insert at line {ln}: {path}{C.RESET}")
        lines = content.strip().split("\n")
        print(f"  {C.BRIGHT_BLACK}  ┌{'─' * (w - 6)}┐{C.RESET}")
        for line in lines[:10]:
            display_line = line[:w - 8]
            print(f"  {C.BRIGHT_BLACK}  │{C.RESET} {C.GREEN}+ {display_line}{C.RESET}")
        if len(lines) > 10:
            print(f"  {C.BRIGHT_BLACK}  │{C.RESET} {C.DIM}... ({len(lines) - 10} more lines){C.RESET}")
        print(f"  {C.BRIGHT_BLACK}  └{'─' * (w - 6)}┘{C.RESET}")

    elif name == "delete_lines":
        path = args.get("file_path", "?")
        s = args.get("start_line", "?")
        e = args.get("end_line", s)
        print(f"\n  {C.YELLOW}{C.BOLD}  ⚠  Delete lines {s}-{e} in: {path}{C.RESET}")

    elif name == "validate_file":
        path = args.get("file_path", "?")
        run_flag = " and RUN" if args.get("run") else ""
        print(f"\n  {C.YELLOW}{C.BOLD}  ⚠  Validate{run_flag}: {path}{C.RESET}")

    elif name == "execute_command":
        cmd = args.get("command", "?")
        print(f"\n  {C.YELLOW}{C.BOLD}  ⚠  Execute: {C.RESET}{C.BRIGHT_YELLOW}{cmd}{C.RESET}")


    try:
        choice = input(f"\n  {C.BOLD}  Confirm? {C.RESET}{C.DIM}[{C.RESET}{C.GREEN}y{C.RESET}{C.DIM}/{C.RESET}{C.RED}n{C.RESET}{C.DIM}/{C.RESET}{C.YELLOW}a{C.DIM}bort]{C.RESET} ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        choice = "a"

    return choice if choice in ("y", "n", "a") else "n"




def tool_result_success(message="Done"):
    print(f"  {C.GREEN}  ✓  {message}{C.RESET}")


def tool_result_error(message="Failed"):
    print(f"  {C.RED}  ✗  {message}{C.RESET}")


def tool_result_denied(message="Action denied"):
    print(f"  {C.YELLOW}  ⊘  {message}{C.RESET}")


def tool_result_aborted():
    print(f"  {C.YELLOW}  ■  Query aborted by user.{C.RESET}")




def welcome():
    w = _term_width()
    print()
    print(f"  {C.CYAN}{C.BOLD}{'─' * (w - 4)}{C.RESET}")
    print(f"  {C.CYAN}{C.BOLD}  Hypr-Pilot{C.RESET}  {C.DIM}— Hyprland expert & coding assistant{C.RESET}")
    print(f"  {C.CYAN}{C.BOLD}{'─' * (w - 4)}{C.RESET}")
    print(f"  {C.DIM}Ask anything — Hyprland config, coding, or general questions.{C.RESET}")
    print(f"  {C.DIM}Commands: /agent /chat /hypr /code /auto /help — or 'exit' to quit.{C.RESET}")
    print()


def prompt():
    # \x01/\x02 = readline's invisible char markers. without them,
    # readline miscounts prompt width and cursor movement breaks.
    rl = lambda s: f"\x01{s}\x02"
    prompt_str = f"\n  {rl(C.BRIGHT_GREEN + C.BOLD)}You ❯{rl(C.RESET)} "
    try:
        return input(prompt_str)
    except (EOFError, KeyboardInterrupt):
        raise EOFError


def response_start():
    print(f"\n  {C.BRIGHT_CYAN}{C.BOLD}Hypr-Pilot ❯{C.RESET} ", end="", flush=True)


def response_token(token):
    sys.stdout.write(token)
    sys.stdout.flush()


def response_end():
    """Print a newline after the streamed response."""
    print()




def show_mode(mode, domain):
    mode_color = C.BRIGHT_MAGENTA if mode == "agent" else C.BRIGHT_BLUE
    domain_color = C.BRIGHT_CYAN if domain == "hyprland" else C.BRIGHT_GREEN
    print(f"  {C.DIM}[{C.RESET}{mode_color}{mode}{C.RESET}{C.DIM} | {C.RESET}{domain_color}{domain}{C.RESET}{C.DIM}]{C.RESET}")


def show_slash_help():
    print(f"""
  {C.BOLD}Slash Commands:{C.RESET}
  {C.BRIGHT_YELLOW}/agent{C.RESET}   — Force agent mode (tool use, file creation)
  {C.BRIGHT_YELLOW}/chat{C.RESET}    — Force answering mode (plain text answers)
  {C.BRIGHT_YELLOW}/hypr{C.RESET}    — Force Hyprland domain
  {C.BRIGHT_YELLOW}/code{C.RESET}    — Force general coding domain
  {C.BRIGHT_YELLOW}/auto{C.RESET}    — Reset to auto-detection (default)
  {C.BRIGHT_YELLOW}/help{C.RESET}    — Show this help
""")


def show_override_set(label):
    print(f"  {C.GREEN}✓{C.RESET} {C.DIM}Mode override:{C.RESET} {C.BOLD}{label}{C.RESET}")


def response_end():
    print()


def divider():
    w = _term_width()
    print(f"\n  {C.BRIGHT_BLACK}{'─' * (w - 4)}{C.RESET}")
