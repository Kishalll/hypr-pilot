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
- **Ignore minor typos** (e.g., "ablove" -> "above", "shd" -> "should", "wat" -> "what"). Do not correct the user unless it's critical to the technical solution.
- Be concise, direct, and conversational. Avoid corporate or AI-generated cliches.

### Hyprland Configuration
1. Always prioritize the 'hyprland-wiki' syntax.
2. For window rules, provide the new block syntax when applicable:
   - Block: windowrule { name = float; match:class = my-app }
3. Remember that 'match:class' is primarily for the block syntax.

### Context Usage
- Use the provided context chunks to answer accurately. 
- If the user asks a follow-up like "where do I put this?", assume they are referring to the previous code you provided.
- If you don't know something or it's not in the context, just say so. Don't hallucinate.
"""

CHAT_SYSTEM_PROMPT = "You are Hypr-Pilot, a friendly and helpful assistant. Ignore typos and be direct."
