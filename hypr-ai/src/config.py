import os

# ─── Paths ──────────────────────────────────────────────────────────────────────

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX_PATH = os.path.join(BASE_DIR, "data", "index", "hypr.index")
METADATA_PATH = os.path.join(BASE_DIR, "data", "index", "metadata.json")

# Datasets Root
DATASETS_ROOT = "/home/gigabyte/hypr-pilot/datasets"

# ─── Model Configuration ────────────────────────────────────────────────────────

EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
LLM_MODEL = "qwen2.5-coder:3b"
OLLAMA_URL = "http://localhost:11434/api/chat"

# ─── Router: Mode Detection ─────────────────────────────────────────────────────
# Agent mode triggers: action verbs that imply the user wants something *done*
AGENT_VERBS = [
    "create", "write", "make", "generate", "build", "add", "set",
    "edit", "change", "modify", "update", "fix", "replace", "remove",
    "delete", "install", "run", "execute", "append", "move", "rename",
    "configure", "setup", "set up", "enable", "disable", "toggle",
    "display", "show", "compile", "test", "open", "save",
]

# Answering mode triggers: question words and explanation requests
ANSWER_PATTERNS = [
    "what is", "what's", "what are", "whats",
    "how does", "how do", "how is", "how to",
    "why does", "why is", "why do", "why can't", "why cant",
    "explain", "describe", "tell me about", "show me",
    "difference between", "compare", "versus", "vs",
    "can i", "can you", "is it possible", "does it",
    "where is", "where are", "where do", "where does", "located",
    "when should", "when do", "when does",
    "which one", "which is",
    "meaning of", "define",
    "list the", "list all",
]

# ─── Router: Domain Detection ───────────────────────────────────────────────────
# Hyprland-specific keywords (tightened — removed generic words like "window",
# "float", "tile", "border", etc. that clash with general coding)
HYPRLAND_KEYWORDS = [
    # Core identifiers — always Hyprland
    "hyprland", "hyprctl", "hypridle", "hyprlock", "hyprpaper", "hyprlang",
    "pyprland", "hyprpicker", "hyprcursor", "hyprutils", "hyprsunset",
    "hyprpolkitagent", "hyprshutdown", "hyprsysteminfo", "aquamarine",
    "xdg-desktop-portal-hyprland", "xdph",

    # Config syntax — unique to Hyprland
    "windowrule", "windowrulev2", "layerrule",
    "exec-once", "exec-shutdown",
    "hyprland.conf", "hyprpaper.conf", "hypridle.conf", "hyprlock.conf",
    "match:class", "match:title", "match:tag",

    # Dispatchers — unique names
    "togglefloating", "setfloating", "settiled",
    "movefocus", "movewindow", "swapwindow",
    "movetoworkspace", "movetoworkspacesilent",
    "togglespecialworkspace", "focusworkspaceoncurrentmonitor",
    "fullscreenstate", "centerwindow",
    "killactive", "forcekillactive",
    "splitratio", "resizeactive", "moveactive",
    "cyclenext", "swapnext",
    "togglegroup", "changegroupactive",
    "togglesplit", "swapsplit",
    "focusmaster", "swapwithmaster",
    "bringactivetotop", "alterzorder",

    # Config sections — unique to Hyprland
    "col.active_border", "col.inactive_border",
    "gaps_in", "gaps_out", "gaps_workspaces",
    "workspace_swipe", "workspace_back_and_forth",
    "disable_hyprland_logo", "disable_splash_rendering",
    "swallow_regex", "enable_swallow",
    "rounding_power", "dim_special",
    "no_hardware_cursors",
    "direct_scanout",

    # Keybind syntax
    "bindl", "bindr", "binde", "bindm", "bindd", "bindel", "bindn",
    "submap", "catchall",

    # Ecosystem tools
    "rofi", "wofi", "fuzzel", "tofi", "bemenu",
    "waybar", "eww", "ironbar", "ags",
    "swww", "mpvpaper", "wpaperd",
    "grim", "slurp", "swappy",
    "mako", "dunst", "swaync",
    "cliphist", "matugen",

    # Wayland-specific
    "wayland", "wl-roots", "wlroots",

    # IPC
    "hyprctl clients", "hyprctl monitors", "hyprctl workspaces",
    "hyprctl activewindow", "hyprctl keyword", "hyprctl reload",
]

# Hyprland config-mutation keywords (subset that triggers strict guardrails)
HYPRLAND_RULE_KEYWORDS = [
    # Window rules
    "windowrule", "window rule", "windowrulev2",
    "window class", "wm class", "app class",
    "layerrule", "layer rule", "workspace rule",
    "match:class", "match:title", "match:tag",

    # Rule management phrases
    "add rule", "set rule", "create rule",
    "add keybind", "set keybind", "create keybind",
    "add bind", "set bind",
    "add monitor", "set monitor", "add workspace", "set workspace",

    # Keybinds
    "keybind", "key bind", "unbind",

    # Exec / Autostart
    "exec-once", "exec-shutdown", "autostart",

    # Config editing
    "hyprland.conf", "hyprpaper.conf", "hypridle.conf", "hyprlock.conf",
]

# Legacy alias used by existing code
DOMAIN_KEYWORDS = HYPRLAND_KEYWORDS

# ─── System Prompts (4 variants) ────────────────────────────────────────────────

_PERSONALITY = """You are Hypr-Pilot, a friendly and expert terminal assistant.
- Be concise, direct, and conversational. No corporate cliches.
- Ignore minor typos unless critical to the solution.
- If you don't know something, say so. Don't hallucinate."""

# 1) Hyprland + Answering: explain/discuss Hyprland topics using RAG context
# NOTE: This is a template — {home_dir} is filled at runtime in brain.py
HYPRLAND_ANSWER_PROMPT = """{personality}

You are answering a question about Hyprland or its ecosystem.
Use the provided context chunks to answer accurately.

ENVIRONMENT:
- The user's home directory is: {home_dir}
- Their Hyprland config is at: {home_dir}/.config/hypr/hyprland.conf
- When mentioning config paths, use the REAL path above, not $HOME or generic placeholders.

Always prioritize the 'hyprland-wiki' syntax when showing config examples.
For window rules, show the single-line syntax:
  windowrule = match:class ^(exact_class)$, float on
If the user asks a follow-up like "where do I put this?", assume they mean the previous code you showed.
Do NOT use tools — just answer in plain text."""

# 2) Hyprland + Agent: modify Hyprland config files with tool calls
# NOTE: This is a template — {personality} and {home_dir} are filled at runtime in brain.py
HYPRLAND_AGENT_PROMPT = """{personality}

You are an agent that modifies Hyprland configuration files. You have access to tools.

ENVIRONMENT:
- The user's home directory is: {home_dir}
- Their Hyprland config is at: {home_dir}/.config/hypr/hyprland.conf
- Always use real paths, never $HOME or generic placeholders.

ALWAYS FOLLOW:
0. NEVER OUTPUT MORE THAN ONE TOOL CALL AT A TIME. Output exactly ONE JSON block, wait for the result, then decide the next step.
1. Conversational responses: write plain text. DO NOT output empty JSON `{{}}` blocks.

HYPRLAND CONFIG RULES (MANDATORY):
2. NEVER guess the window class. Use `get_window_class` first to get the precise class name.
3. NEVER guess the config path. Call `get_active_config_paths` — use the >>> RULES FILE it returns.
4. NEVER append directly to `hyprland.conf` — always use the dedicated rules file.
5. Before adding a rule, `read_file` the rules file to check for existing rules for the same class.
6. If an existing rule is found: use `replace_line`. If none exists: use `append_file`.
7. Window rule syntax (single line only):
   windowrule = match:class ^(app_class_here)$, tile on
8. Always prioritize the 'hyprland-wiki' syntax.

WHEN TO STOP:
9. Once you have completed the user's request (e.g. added a rule, fixed a config), write a SHORT summary of what you did in plain text and STOP. Do NOT repeat the same action.
10. NEVER call the same tool with the same arguments twice. If a tool succeeded, move on.
11. Do NOT compile, build, or run anything unless the user explicitly asked you to.

EDITING FILES:
12. To add lines at a specific position, use `insert_line` with a 1-based line number.
13. To remove specific lines, use `delete_lines` with start_line and end_line.
14. After modifying a config file, use `validate_file` to check for syntax errors."""

# 3) General Coding + Answering: explain code, algorithms, concepts
CODING_ANSWER_PROMPT = f"""{_PERSONALITY}

You are answering a general programming or technical question.
Provide clear, accurate explanations with code examples when helpful.
Use proper formatting: wrap code in markdown fences with the language tag.
Do NOT use tools — just answer in plain text."""

# 4) General Coding + Agent: create files, write code, run commands
# NOTE: This prompt is a template — {home_dir} and {cwd} are filled at runtime in brain.py
CODING_AGENT_PROMPT = """{personality}

You are a coding agent that can create files, write programs, and run commands.

ENVIRONMENT (use these real paths — NEVER guess usernames or directories):
- Home directory: {home_dir}
- Current directory: {cwd}
- When the user says "home folder", use: {home_dir}
- Use ~ or {home_dir} for paths, NEVER /home/your_username or /home/user.

TOOLS (use exact argument names shown):
- write_file(file_path, content) — create or overwrite a file with full content.
- read_file(file_path) — read a file.
- replace_line(file_path, old_line, new_line) — replace ONE existing line. Needs the EXACT old text.
- insert_line(file_path, line_number, content) — insert text at a 1-based line number.
- delete_lines(file_path, start_line, end_line) — delete a range of lines.
- validate_file(file_path, run) — syntax-check a file. Set run=true ONLY if user asked to run it.
- append_file(file_path, content) — add text to end of file.
- execute_command(command) — run a shell command.
- list_directory(dir_path), make_directory(dir_path), file_exists(file_path), search_in_files(pattern).

ALWAYS FOLLOW:
0. NEVER OUTPUT MORE THAN ONE TOOL CALL AT A TIME. Output exactly ONE JSON block, wait for the result, then decide the next step.
1. Conversational responses: write plain text. DO NOT output empty JSON `{{}}` blocks.
2. When creating code files, write clean, COMPLETE, working code. Include all necessary imports and logic.
3. When the user asks to create a program, use write_file to create it directly.
4. For Python scripts, use proper shebang (#!/usr/bin/env python3) when creating executable scripts.
5. Do NOT touch Hyprland config files (~/.config/hypr/) unless the user explicitly asks.

WHEN TO STOP:
6. After write_file succeeds, call validate_file(file_path) to syntax-check it, then write a SHORT summary and STOP.
7. NEVER call the same tool with the same arguments twice. If a tool succeeded, move on.
8. Do NOT compile, build, or run code unless the user EXPLICITLY said "run it" or "compile it". Just create the file, validate, summarize.
9. Do NOT rewrite or modify a file you just successfully created unless validate_file reported errors.
10. Do NOT call validate_file with run=true unless the user explicitly asked to run the program.

EDITING EXISTING FILES:
11. To edit an existing file, prefer `insert_line` or `delete_lines` or `replace_line` over rewriting the whole file.
12. replace_line needs: file_path, old_line (exact text), new_line (replacement text). It does NOT take line_number.
13. insert_line needs: file_path, line_number (1-based), content (text to insert). It does NOT take old_line/new_line."""

# Legacy aliases for backward compat during transition
AGENT_SYSTEM_PROMPT = HYPRLAND_AGENT_PROMPT
CHAT_SYSTEM_PROMPT = CODING_ANSWER_PROMPT
