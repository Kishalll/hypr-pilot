import os

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX_PATH = os.path.join(BASE_DIR, "data", "index", "hypr.index")
METADATA_PATH = os.path.join(BASE_DIR, "data", "index", "metadata.json")

# Datasets Root
DATASETS_ROOT = "/home/gigabyte/hypr-pilot/datasets"

# Model Configuration
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
LLM_MODEL = "qwen2.5-coder:3b"
OLLAMA_URL = "http://localhost:11434/api/chat"

# Domain Keywords for Context Optimization
DOMAIN_KEYWORDS = [
    # Core Hyprland
    "hyprland", "hyprctl", "hypridle", "hyprlock", "hyprpaper", "hyprlang",
    "pyprland", "wayland", "wl-roots", "xdg", "portal", "socket", "ipc", "plugin",
    
    # Config & Rules
    "bind", "monitor", "workspace", "windowrule", "windowrulev2", "layerrule",
    "exec-once", "exec", "env", "source", "gestures", "input", "master", "dwindle",
    "misc", "debug", "general", "decoration", "animations", "bezier",
    
    # Appearance & Behavior
    "blur", "shadow", "rounding", "border", "window", "focus", "float", "tile",
    "opaque", "transparent", "opacity", "dim", "idle", "dpms", "gamma",
    "animation", "transition", "slide", "fade", "popin",
    
    # Ecosystem Tools
    "rofi", "wofi", "fuzzel", "tofi", "bemenu", # Launchers
    "waybar", "eww", "ironbar", "ags", "polybar", # Bars
    "swww", "mpvpaper", "wpaperd", # Wallpapers
    "grim", "slurp", "swappy", "flameshot", # Screenshots
    "mako", "dunst", "swaync", # Notifications
    "matugen", "gamemode", "cliphist", # Misc
]

SYSTEM_PROMPT = """You are Hypr-Pilot, a friendly and expert assistant specialized in Hyprland configuration and general programming.

### Personality & Robustness
- You are a helpful peer, not a pedantic robot.
- **Ignore minor typos** . Do not correct the user unless it's critical to the technical solution.
- Be concise, direct, and conversational. Avoid corporate or AI-generated cliches.

### Hyprland Configuration
1. Always prioritize the 'hyprland-wiki' syntax.
2. For window rules, use the single-line syntax:
   - windowrule = match:class ^(exact_class)$, float on

### Context Usage
- Use the provided context chunks to answer accurately. 
- If the user asks a follow-up like "where do I put this?", assume they are referring to the previous code you provided.
- If you don't know something or it's not in the context, just say so. Don't hallucinate.
"""

AGENT_SYSTEM_PROMPT = """You are Hypr-Pilot. You have access to Linux command line tools.

CRITICAL RULES YOU MUST FOLLOW:
0. NEVER OUTPUT MORE THAN ONE TOOL AT A TIME! You must output EXACTLY ONE JSON block, wait for the result, and then output the next one. DO NOT write multiple JSON blocks in one message.
1. NEVER guess the name of a window class. You MUST use the `get_window_class` tool to get the precise class name first.
2. NEVER guess the path to a config file. Call the `get_active_config_paths` tool to see where window rules are stored, and use THAT path.
3. NEVER append directly to `hyprland.conf` unless `get_active_config_paths` tells you there are no sourced files.
4. To add a window rule, you MUST use `append_file`. DO NOT use `write_file`.
5. Window rules MUST use this exact syntax format on a single line:
windowrule = match:class ^(app_class_here)$, tile on
(Use `float on` or `tile on` depending on what the user wants.)
6. Conversational Responses: If answering a question or providing an explanation, write plain text. DO NOT output empty JSON `{}` blocks.
"""

CHAT_SYSTEM_PROMPT = "You are Hypr-Pilot, a friendly and helpful assistant. Ignore typos and be direct."
