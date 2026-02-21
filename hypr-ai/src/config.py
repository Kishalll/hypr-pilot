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
OLLAMA_URL = "http://localhost:11434/api/generate"

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

### Style & Tone
- Speak naturally and directly, like a fellow developer. Avoid robotic phrasing.
- Keep your responses concise and focused.
- If you're explaining code or a function, make it sound like a human wrote it—clear, logical, and easy to read.

### Hyprland Configuration
1. Always prioritize the 'hyprland-wiki' syntax.
2. For window rules, provide the new block syntax :
   - Block: windowrule { name = float; match:class = my-app }
3. Remember that 'match:class' is only for the block syntax.

### Programming & Functions
- When asked about programming or specific functions, explain them clearly. 
- Break down what the function does, what it takes in, and what it returns.
- Only use the provided context if it's actually relevant to the question. If you're asked a general programming question or just greeted, use your own knowledge.

### Integrity
- **No hallucinations.** If you aren't sure about something, just say so. It's better to be honest than to give wrong advice.
"""
