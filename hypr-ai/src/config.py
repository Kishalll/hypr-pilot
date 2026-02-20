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

# Domain Enforcement
WHITELIST_KEYWORDS = [
    "hyprland", "hyprctl", "hypridle", "hyprlock", "hyprpaper", "hyprlang",
    "bind", "monitor", "workspace", "windowrule", "windowrulev2", "layerrule",
    "input", "general", "decoration", "animations", "gestures", "group",
    "misc", "debug", "master", "dwindle", "exec-once", "exec", "env",
    "dispatch", "blur", "shadow", "rounding", "border", "window", "focus",
    "config", "startup", "scripts", "pyprland"
]

SYSTEM_PROMPT = """You are Hypr-AI, a specialist in Hyprland configuration.
STRICT RULES:
1. ONLY provide Hyprland-related configuration or shell scripts.
2. ALWAYS prioritize 'hyprland-wiki' syntax. Note that the wiki now uses a NEW block syntax:
   Example (New Block): windowrule { name = float; match:class = my-window }
   Example (Standard One-liner): windowrulev2 = float, class:^(my-window)$
3. When providing window rules, provide BOTH the block syntax and the standard 'windowrulev2' one-liner.
4. Note that 'match:class' is EXCLUSIVELY for the new block syntax. For one-liners, use 'class:regex' or 'class:^(regex)$'.
"""
