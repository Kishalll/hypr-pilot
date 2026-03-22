# Hypr-Pilot

A local, offline-capable AI assistant that lives in your terminal. Built specifically for Hyprland users who want quick help with their configs, window rules, keybindings — but also handles general coding tasks like writing scripts, creating files, and running commands.

It uses RAG (Retrieval-Augmented Generation) to pull relevant information from curated Hyprland documentation and community dotfiles before answering, so the responses are grounded in real config syntax instead of hallucinated nonsense.

## What It Does

- **Answers Hyprland questions** using real context from the Hyprland wiki, HyDE dotfiles, and community configs
- **Modifies your Hyprland config** safely — looks up window classes, finds the right config file, reads it before editing, and asks for confirmation before any write
- **Writes code and scripts** — creates files, validates syntax, runs them if you ask
- **Runs shell commands** with output capture and safety checks
- **Routes queries automatically** — figures out if you're asking a question or requesting an action, and whether it's Hyprland-related or general coding
- **Slash commands** to override the auto-routing: `/agent`, `/chat`, `/hypr`, `/code`, `/auto`

## Features

- Fully local — runs on Ollama, no API keys, no internet needed after setup
- RAG pipeline with FAISS vector search over 4 curated datasets
- Guardrails that prevent blind writes to your Hyprland config (enforces prerequisite tool calls)
- User confirmation prompts for every destructive action
- Syntax validation for Python, C, C++, JavaScript, Go, Rust, Bash, JSON, YAML
- Conversation history that's filtered by mode (agent history doesn't leak into Q&A mode)
- Readline support with persistent history across sessions

## Modes & Slash Commands

Every query you type gets classified along two axes before it reaches the model:

**Domain** — what the question is about:
- **Hyprland** — anything related to Hyprland config, window rules, keybindings, dispatchers, or the Wayland ecosystem. Detected by matching against 100+ Hyprland-specific keywords. When this mode is active, the RAG pipeline kicks in and pulls relevant context from the indexed datasets.
- **Coding** — everything else: general programming, scripts, algorithms, file operations. No RAG context is injected here since the datasets are Hyprland-specific.

**Mode** — what you want done:
- **Answering** — you're asking a question or want something explained. The model responds in plain text, no tools are used. Think "how does X work?" or "what's the syntax for Y?"
- **Agent** — you want something *done*: create a file, edit a config, run a command. The model enters a tool-call loop where it can read files, write files, execute commands, and validate syntax — one step at a time, with your confirmation before anything destructive.

This gives four combinations, each with its own system prompt and capabilities:

| | Hyprland | Coding |
|---|---|---|
| **Answering** | RAG context + plain text answer | Direct LLM answer |
| **Agent** | RAG context + tools + guardrails | Tools only |

Most of the time the auto-detection gets it right. When it doesn't, slash commands let you force a specific mode:

| Command | What it does |
|---------|-------------|
| `/agent` | Forces agent mode — the model will use tools regardless of how the query reads |
| `/chat` | Forces answering mode — plain text only, no tool calls |
| `/hypr` | Forces Hyprland domain — RAG context will be included |
| `/code` | Forces coding domain — no RAG context |
| `/auto` | Resets back to auto-detection (the default) |
| `/help` | Shows the list of available commands |

Overrides are sticky — once you type `/agent`, every query after that runs in agent mode until you type `/auto` or `/chat` to change it.

## System Requirements

### Minimum
- **OS**: Linux (Arch-based recommended, since this is built around Hyprland)
- **RAM**: 4 GB free (the 3B model + embeddings need ~2-3 GB)
- **Disk**: ~3 GB (model weights + Python deps + FAISS index)
- **CPU**: Any modern x86_64 processor
- **Python**: 3.10+
- **Git**: Required by the setup script to fetch datasets
- **Ollama**: Installed and working

### Recommended
- **RAM**: 8 GB+ free
- **CPU**: 4+ cores (speeds up embedding generation during index setup)
- **GPU**: Not required — runs on CPU by default. If you have an NVIDIA GPU and want faster inference, install the CUDA version of PyTorch and Ollama will use it automatically.

## Installation

### 1. Install Ollama

If you don't have Ollama yet:
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

### 2. Pull the LLM model

```bash
ollama pull qwen2.5-coder:3b
```

### 3. Clone the repo

```bash
git clone https://github.com/Kishalll/hypr-pilot.git
cd hypr-pilot
```

### 4. Build the index

This is a one-time setup that requires an internet connection. The script pulls community dotfiles (HyDE, end-4, ML4W) from their original GitHub repositories at pinned commit hashes, extracts the Hyprland config files, creates a virtual environment, installs Python dependencies, and builds the FAISS vector index. Takes a few minutes on first run.

```bash
cd hypr-ai
bash setup_index.sh
```

After this, no internet is needed — everything runs locally.

### 5. Run it

```bash
bash run.sh
```

This starts Ollama in the background (if not already running), activates the venv, and drops you into the Hypr-Pilot prompt.

**To add your own dataset:**

1. Create a new folder under `datasets/`, e.g. `datasets/my-dots/`
2. Drop your `.conf`, `.md`, or `.sh` files in there
3. Open `hypr-ai/src/ingest.py` and add your dataset name to the priority map:
   ```python
   self.priority_map = {
       "hyprland-wiki": 1,
       "hyde": 2,
       "ill-imp": 2,
       "m4lw": 2,
       "my-dots": 2,          # add this line
   }
   ```
   Lower number = higher priority when results are ranked.

4. Rebuild the index:
   ```bash
   cd hypr-ai
   bash setup_index.sh
   ```

**To remove a dataset:** Delete its folder from `datasets/` and rebuild the index.

## How to Change the LLM Model

The model is set in `hypr-ai/src/config.py`:

```python
LLM_MODEL = "qwen2.5-coder:3b"
```

Change it to any model Ollama supports. Make sure to pull it first:

```bash
ollama pull <model-name>
```

Some suggestions:
- `qwen2.5-coder:7b` — better quality, needs more RAM (~5 GB)
- `codellama:7b` — good for coding tasks
- `mistral:7b` — solid general purpose
- `llama3.2:3b` — comparable size, different strengths

The embedding model (used for RAG search, not for chat) is also in the same file:

```python
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
```

If you change this, you need to rebuild the index since the vector dimensions will be different.

## How to Change Custom Instructions

The system prompts that define how the assistant behaves are in `hypr-ai/src/config.py`. There are four, one for each mode:

| Variable | When it's used |
|----------|---------------|
| `HYPRLAND_ANSWER_PROMPT` | Answering Hyprland questions (uses RAG context) |
| `HYPRLAND_AGENT_PROMPT` | Modifying Hyprland configs (uses tools + RAG) |
| `CODING_ANSWER_PROMPT` | Answering general coding questions |
| `CODING_AGENT_PROMPT` | Writing code, creating files, running commands |

All four share a common personality block at the top of the file:

```python
_PERSONALITY = """You are Hypr-Pilot, a friendly and expert terminal assistant.
- Be concise, direct, and conversational. No corporate cliches.
- Ignore minor typos unless critical to the solution.
- If you don't know something, say so. Don't hallucinate."""
```

Edit any of these to change the tone, add rules, or adjust behavior. The agent prompts also contain tool-use instructions — be careful editing those unless you know what you're doing, since the model relies on them to call tools correctly.


