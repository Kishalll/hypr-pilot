import json
import requests
import re
import uuid
import os
from config import (
    OLLAMA_URL, LLM_MODEL,
    HYPRLAND_KEYWORDS, HYPRLAND_RULE_KEYWORDS,
    AGENT_VERBS, ANSWER_PATTERNS,
    HYPRLAND_ANSWER_PROMPT, HYPRLAND_AGENT_PROMPT,
    CODING_ANSWER_PROMPT, CODING_AGENT_PROMPT,
    DOMAIN_KEYWORDS, _PERSONALITY,
)
from vectorstore import HyprVectorStore
from schemas import TOOLS, HYPRLAND_TOOLS, CODING_TOOLS
import tools
import ui

# Personality text block for runtime prompt formatting
_PERSONALITY_BLOCK = _PERSONALITY


# ─── Request Context ────────────────────────────────────────────────────────────

class RequestContext:
    """Holds the routing decision for a single user query."""
    __slots__ = ("mode", "domain", "use_rag", "use_tools", "system_prompt", "forced")

    MODE_ANSWER = "answering"
    MODE_AGENT  = "agent"
    DOMAIN_HYPRLAND = "hyprland"
    DOMAIN_CODING   = "coding"
    DOMAIN_GENERAL  = "general"

    def __init__(self, mode, domain, use_rag=False, use_tools=False, system_prompt="", forced=False):
        self.mode = mode
        self.domain = domain
        self.use_rag = use_rag
        self.use_tools = use_tools
        self.system_prompt = system_prompt
        self.forced = forced

    def __repr__(self):
        return f"<Ctx mode={self.mode} domain={self.domain} rag={self.use_rag} tools={self.use_tools}>"


# ─── Router ─────────────────────────────────────────────────────────────────────

def route_query(query, override_mode=None, override_domain=None):
    """Classify a query into (mode, domain) and return a RequestContext."""
    q = query.lower().strip()

    # ── Domain detection ──
    if override_domain:
        domain = override_domain
    else:
        hypr_score = sum(1 for kw in HYPRLAND_KEYWORDS if kw in q)
        # Boost multi-word matches (they're more specific)
        for kw in HYPRLAND_KEYWORDS:
            if " " in kw and kw in q:
                hypr_score += 2
        domain = RequestContext.DOMAIN_HYPRLAND if hypr_score >= 1 else RequestContext.DOMAIN_CODING

    # ── Mode detection ──
    if override_mode:
        mode = override_mode
    else:
        agent_score = 0
        answer_score = 0

        # Check for action verbs (agent signals)
        for verb in AGENT_VERBS:
            # Match verb at word boundary to avoid false positives
            if re.search(r'\b' + re.escape(verb) + r'\b', q):
                agent_score += 1

        # Check for question / explanation patterns (answer signals)
        for pat in ANSWER_PATTERNS:
            if pat in q:
                answer_score += 2  # Stronger weight — question patterns are more distinctive

        # If the query ends with '?' it's likely a question
        if q.rstrip().endswith("?"):
            answer_score += 1

        mode = RequestContext.MODE_AGENT if agent_score > answer_score else RequestContext.MODE_ANSWER

    # ── Select prompt and capabilities ──
    if domain == RequestContext.DOMAIN_HYPRLAND:
        if mode == RequestContext.MODE_AGENT:
            ctx = RequestContext(mode, domain, use_rag=True, use_tools=True,
                                system_prompt=HYPRLAND_AGENT_PROMPT)
        else:
            ctx = RequestContext(mode, domain, use_rag=True, use_tools=False,
                                system_prompt=HYPRLAND_ANSWER_PROMPT)
    else:
        if mode == RequestContext.MODE_AGENT:
            ctx = RequestContext(mode, domain, use_rag=False, use_tools=True,
                                system_prompt=CODING_AGENT_PROMPT)
        else:
            ctx = RequestContext(mode, domain, use_rag=False, use_tools=False,
                                system_prompt=CODING_ANSWER_PROMPT)

    ctx.forced = bool(override_mode or override_domain)
    return ctx


# ─── Hyprland Guardrails ────────────────────────────────────────────────────────

class HyprlandGuard:
    """Enforces mandatory tool-call ordering for Hyprland config mutations."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.got_config_paths = False
        self.got_window_class = False
        self.read_rules_file = False
        self._rules_file_path = None

    def record_tool(self, name, args, result):
        """Track which prerequisite tools have been called."""
        if name == "get_active_config_paths":
            self.got_config_paths = True
            # Extract the rules file path from the result
            for line in str(result).split("\n"):
                if ">>> RULES FILE" in line:
                    parts = line.split(":", 1)
                    if len(parts) > 1:
                        self._rules_file_path = parts[1].strip()
        elif name == "get_window_class":
            self.got_window_class = True
        elif name == "read_file":
            path = args.get("file_path", "")
            if self._rules_file_path and tools.expand_path(path) == tools.expand_path(self._rules_file_path):
                self.read_rules_file = True

    def check_write(self, name, args):
        """Returns an error string if a write to Hyprland config is attempted without prerequisites.
        Returns None if the write is allowed."""
        if name not in ("write_file", "append_file", "replace_line"):
            return None

        target = tools.expand_path(args.get("file_path", ""))
        hypr_dir = tools.expand_path("~/.config/hypr")

        # Only guard writes inside ~/.config/hypr/
        if not target.startswith(hypr_dir):
            return None

        errors = []
        if not self.got_config_paths:
            errors.append("You must call `get_active_config_paths` first to find the correct rules file.")
        if not self.read_rules_file:
            errors.append("You must `read_file` the rules file before modifying it.")

        # For windowrule-related content, also require get_window_class
        content = args.get("content", "") + args.get("new_line", "")
        if "windowrule" in content.lower() and not self.got_window_class:
            errors.append("You must call `get_window_class` first before adding window rules.")

        if errors:
            return "GUARDRAIL BLOCKED: " + " ".join(errors)
        return None


# ─── Brain ──────────────────────────────────────────────────────────────────────

class HyprBrain:
    def __init__(self):
        self.store = HyprVectorStore()
        self.history = []  # Clean history: only user/assistant text pairs, no tool messages
        self._override_mode = None
        self._override_domain = None
        try:
            self.store.load_index()
        except:
            pass  # Index may not exist yet

    # ── Slash command overrides ──

    def set_override(self, mode=None, domain=None):
        """Set a sticky override for mode/domain. Pass None to clear."""
        self._override_mode = mode
        self._override_domain = domain

    def clear_overrides(self):
        self._override_mode = None
        self._override_domain = None

    # ── Tool execution ──

    # ── Parameter normalization for small-model mistakes ──
    # The 3b model frequently sends wrong arg names when tools have similar signatures.
    _PARAM_FIXES = {
        "replace_line": {
            # Model sends insert_line args to replace_line
            "line_number": None,   # drop — replace_line doesn't use line numbers
            "content": "new_line", # rename
        },
        "insert_line": {
            # Model sends replace_line args to insert_line
            "old_line": None,      # drop
            "new_line": "content", # rename
        },
    }

    def _normalize_args(self, name, args):
        """Fix common parameter name mismatches from the small LLM."""
        fixes = self._PARAM_FIXES.get(name)
        if not fixes:
            return args
        fixed = {}
        for k, v in args.items():
            if k in fixes:
                mapped = fixes[k]
                if mapped is None:
                    continue  # drop this arg
                fixed[mapped] = v
            else:
                fixed[k] = v
        return fixed

    def call_local_tool(self, name, args, ctx=None, guard=None):
        """Execute a tool call with validation and user confirmation."""
        args = self._normalize_args(name, args)
        ui.tool_action(name, args)

        # ── Hyprland guardrails (Python-enforced, not just prompt-based) ──
        if ctx and ctx.domain == RequestContext.DOMAIN_HYPRLAND and guard:
            block_msg = guard.check_write(name, args)
            if block_msg:
                ui.tool_result_error("Guardrail: prerequisite tools not called yet.")
                return block_msg

        # ── Path validation for file writes ──
        if name in ("write_file", "append_file", "replace_line", "insert_line", "delete_lines"):
            target_path = tools.expand_path(args.get('file_path', ''))
            if name in ("append_file", "replace_line", "insert_line", "delete_lines"):
                if not os.path.exists(target_path):
                    ui.tool_result_error(f"Path does not exist: {target_path}")
                    import glob
                    base_hypr = tools.expand_path("~/.config/hypr")
                    conf_files = glob.glob(f"{base_hypr}/**/*.conf", recursive=True)
                    suggestions = "\n".join(conf_files) if conf_files else "No .conf files found in ~/.config/hypr"
                    return f"Action denied: The file '{target_path}' does not exist.\n\nActual config files in ~/.config/hypr:\n{suggestions}\n\nPlease check `~/.config/hypr/hyprland.conf` to see which are `source`d for windowrules."
            else:
                parent_dir = os.path.dirname(target_path)
                if parent_dir and not os.path.exists(parent_dir):
                    ui.tool_result_error(f"Directory does not exist: {parent_dir}")
                    return f"Action denied: The directory '{parent_dir}' does not exist. Please use an existing directory."

        # ── replace_line: verify old line exists before confirming ──
        if name == "replace_line":
            target_path = tools.expand_path(args.get('file_path', ''))
            old_line = args.get('old_line', '').strip()
            try:
                with open(target_path, 'r', encoding='utf-8') as f:
                    file_lines = [l.strip() for l in f.readlines()]
                if old_line not in file_lines:
                    ui.tool_result_error(f"Line not found in file: {old_line}")
                    return f"Error: The line '{old_line}' does NOT exist in {args.get('file_path')}. You may have hallucinated it from RAG context. Please re-read the file and check what lines actually exist, then decide whether to use replace_line or append_file."
            except Exception as e:
                ui.tool_result_error(str(e))
                return f"Error reading file: {e}"

        # ── validate_file with run=True needs user permission ──
        if name == "validate_file" and args.get("run"):
            choice = ui.confirm_action(name, args)
            if choice == 'a':
                ui.tool_result_aborted()
                return "ABORT_QUERY"
            elif choice != 'y':
                ui.tool_result_denied("Skipped by user.")
                # Still do syntax check, just skip the run
                args = dict(args)
                args["run"] = False

        # ── User confirmation for destructive actions ──
        if name in ("write_file", "append_file", "replace_line", "insert_line", "delete_lines", "execute_command"):
            choice = ui.confirm_action(name, args)
            if choice == 'a':
                ui.tool_result_aborted()
                return "ABORT_QUERY"
            elif choice != 'y':
                ui.tool_result_denied("Skipped by user.")
                return "User denied execution."

        # ── Execute ──
        func = getattr(tools, name, None)
        if func:
            try:
                result = func(**args)
                ui.tool_result_success()
                # Track for Hyprland guardrails
                if guard:
                    guard.record_tool(name, args, result)
                return result
            except Exception as e:
                ui.tool_result_error(str(e))
                return f"Error: {e}"
        ui.tool_result_error(f"Tool '{name}' not found.")
        return f"Error: Tool '{name}' not found."

    # ── JSON parsing helpers (unchanged from original) ──

    def _try_parse_json(self, json_str):
        r"""Parse JSON with fallback repairs for common LLM escape mistakes."""
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            fixed = re.sub(r'\\(?!["\\bfnrtu/])', r'\\\\', json_str)
            try:
                return json.loads(fixed)
            except json.JSONDecodeError:
                fixed2 = fixed.replace('\\\\"', '\\\\\\"')
                try:
                    return json.loads(fixed2)
                except json.JSONDecodeError:
                    return None

    def parse_tool_calls_from_text(self, text):
        """Finds any JSON-like tool call structure in the text robustly using bracket matching."""
        if not text: return [], text

        fence_match = re.search(r'```(?:json)?\s*\n(.+?)\n```', text, re.DOTALL)
        if fence_match:
            json_str = fence_match.group(1).strip()
            data = self._try_parse_json(json_str)
            if data and "name" in data and "arguments" in data:
                call = {"id": f"call_{uuid.uuid4().hex[:8]}", "type": "function", "function": data}
                return [call], ""

        tool_calls = []
        start_idx = 0
        while True:
            start = text.find('{', start_idx)
            if start == -1:
                break

            brace_count = 0
            end = -1
            in_string = False
            i = start
            while i < len(text):
                c = text[i]
                if in_string:
                    if c == '\\':
                        i += 2
                        continue
                    elif c == '"':
                        in_string = False
                else:
                    if c == '"':
                        in_string = True
                    elif c == '{':
                        brace_count += 1
                    elif c == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            end = i
                            break
                i += 1

            if end == -1 and brace_count > 0:
                json_str = text[start:] + ('}' * brace_count)
                data = self._try_parse_json(json_str)
                if data and "name" in data and "arguments" in data:
                    call = {"id": f"call_{uuid.uuid4().hex[:8]}", "type": "function", "function": data}
                    return [call], ""
                break
            
            if end != -1:
                json_str = text[start:end+1]
                data = self._try_parse_json(json_str)
                if data and "name" in data and "arguments" in data:
                    tool_calls.append({"id": f"call_{uuid.uuid4().hex[:8]}", "type": "function", "function": data})
                    return tool_calls, text[:end+1]
                start_idx = end + 1
            else:
                break
                
        return tool_calls, text

    # ── Main response generation ──

    def generate_response(self, query):
        """Route the query, select prompt/tools, call LLM, enforce guardrails."""
        ui.reset_steps()

        # ── Route ──
        ctx = route_query(query, self._override_mode, self._override_domain)
        ui.show_mode(ctx.mode, ctx.domain)

        # ── Hyprland guardrail tracker (per-query) ──
        guard = HyprlandGuard() if ctx.domain == RequestContext.DOMAIN_HYPRLAND else None

        # ── Build messages (inject real paths into prompt) ──
        system_prompt = ctx.system_prompt
        _home = os.path.expanduser("~")
        _cwd = os.getcwd()
        if ctx.mode == RequestContext.MODE_AGENT and ctx.domain != RequestContext.DOMAIN_HYPRLAND:
            # Coding agent prompt is a template with {personality}, {home_dir}, {cwd}
            system_prompt = system_prompt.format(
                personality=_PERSONALITY_BLOCK,
                home_dir=_home,
                cwd=_cwd,
            )
        elif ctx.domain == RequestContext.DOMAIN_HYPRLAND:
            # Hyprland prompts are templates with {personality}, {home_dir}
            system_prompt = system_prompt.format(
                personality=_PERSONALITY_BLOCK,
                home_dir=_home,
            )
        messages = [{"role": "system", "content": system_prompt}]

        # ── History injection (filtered by mode to prevent cross-contamination) ──
        # Agent-mode history (tool calls, file creation) should NOT leak into answering mode.
        # For answering mode: only include answering-mode history entries.
        # For agent mode: include all recent history for continuity (e.g. "run it" follow-ups).
        filtered_history = []
        for entry in self.history:
            entry_mode = entry.get("_mode", "answer")
            if ctx.mode == RequestContext.MODE_ANSWER:
                # Only include previous answering-mode exchanges
                if entry_mode == RequestContext.MODE_ANSWER:
                    filtered_history.append(entry)
            else:
                # Agent mode: include everything for continuity
                filtered_history.append(entry)
        history_limit = 6 if ctx.mode == RequestContext.MODE_ANSWER else 10
        for entry in filtered_history[-history_limit:]:
            # Send only role+content to the LLM (strip our metadata)
            messages.append({"role": entry["role"], "content": entry["content"]})

        # ── RAG injection (only for Hyprland domain) ──
        user_query = query  # Keep original for history
        if ctx.use_rag:
            context_chunks = self.store.search(query, k=3)
            if context_chunks:
                context_str = ""
                for i, chunk in enumerate(context_chunks):
                    source_info = f"Source: {chunk['source']}"
                    context_str += f"\n--- Reference {i+1} ({source_info}) ---\n{chunk['content']}\n"
                query = f"[SYSTEM: Here is relevant Hyprland context. Use it if applicable.]\n{context_str}\n\n[USER QUERY]: {query}"

        # ── Follow-up enrichment for short agent queries ──
        # When the user says things like "run it", "compile it", "yes do it",
        # inject context from the last agent exchange so the model knows what "it" refers to.
        if ctx.mode == RequestContext.MODE_AGENT and len(user_query.split()) <= 8:
            last_agent_entries = [e for e in self.history if e.get("_mode") == RequestContext.MODE_AGENT]
            if last_agent_entries:
                last_assistant = [e for e in last_agent_entries if e["role"] == "assistant"]
                if last_assistant:
                    prev_context = last_assistant[-1]["content"]
                    # Extract file paths from previous assistant message
                    path_matches = re.findall(r'(/[\w./~-]+\.\w+)', prev_context)
                    if path_matches:
                        paths_str = ", ".join(path_matches[:3])
                        query += f"\n\n[CONTEXT from previous task: files involved: {paths_str}]"

        # ── Hyprland config-mutation reminder ──
        is_hypr_mutation = ctx.domain == RequestContext.DOMAIN_HYPRLAND and ctx.mode == RequestContext.MODE_AGENT
        if is_hypr_mutation:
            # Check if this is specifically about rules/config changes
            q_lower = user_query.lower()
            needs_rule_guard = any(kw in q_lower for kw in HYPRLAND_RULE_KEYWORDS)
            if needs_rule_guard:
                query += "\n\n[CRITICAL REMINDER]: 1. MUST use get_window_class tool first. 2. MUST use get_active_config_paths tool first to find rules file. 3. MUST read_file the rules file before modifying. 4. Use single-line syntax: windowrule = match:class ^(exact_class)$, tile on."
        elif ctx.mode == RequestContext.MODE_AGENT:
            query += "\n\n[REMINDER]: Use tools to complete the task. Write plain text for conversational answers. DO NOT output empty {} blocks."

        messages.append({"role": "user", "content": query})

        # ── Select tool set ──
        if not ctx.use_tools:
            active_tools = None  # No tools in answering mode
        elif ctx.domain == RequestContext.DOMAIN_HYPRLAND:
            active_tools = TOOLS  # Full set including Hyprland-specific tools
        else:
            active_tools = CODING_TOOLS  # General coding tools only

        # ── Answering mode: single LLM call, no tool loop ──
        if ctx.mode == RequestContext.MODE_ANSWER:
            payload = {
                "model": LLM_MODEL,
                "messages": messages,
                "stream": False,
                "options": {"temperature": 0.1, "num_ctx": 4096}
            }
            spinner = ui.Spinner("Thinking")
            spinner.start()
            try:
                response = requests.post(OLLAMA_URL, json=payload, timeout=120)
                response.raise_for_status()
                spinner.stop()
                result = response.json()
                content = result.get("message", {}).get("content", "")
                if content:
                    yield content
                self.history.append({"role": "user", "content": user_query, "_mode": ctx.mode})
                self.history.append({"role": "assistant", "content": content, "_mode": ctx.mode})
            except Exception as e:
                spinner.stop()
                yield f"\nSystem Error: {e}"
            return

        # ── Agent mode: iterative tool-call loop ──
        max_iterations = 10
        _prev_tool_key = None  # Track (name, args_key) to detect duplicate calls
        for iteration in range(max_iterations):
            payload = {
                "model": LLM_MODEL,
                "messages": messages,
                "stream": False,
                "options": {"temperature": 0.0, "num_ctx": 4096}
            }
            if active_tools:
                payload["tools"] = active_tools

            spinner = ui.Spinner("Thinking")
            spinner.start()
            try:
                response = requests.post(OLLAMA_URL, json=payload, timeout=120)
                response.raise_for_status()
                spinner.stop()
                result = response.json()
                message = result.get("message", {})
                content = message.get("content", "")
                tool_calls = message.get("tool_calls", [])

                # Extract tool calls from text if model put them inline
                text_tool_calls, cleaned_content = self.parse_tool_calls_from_text(content)
                if text_tool_calls:
                    tool_calls.extend(text_tool_calls)
                    content = ""

                if content:
                    yield content

                message["content"] = content if content else None
                message["tool_calls"] = tool_calls if tool_calls else None
                messages.append(message)

                if not tool_calls:
                    self.history.append({"role": "user", "content": user_query, "_mode": ctx.mode})
                    self.history.append({"role": "assistant", "content": content, "_mode": ctx.mode})
                    break
                
                abort_all = False
                loop_break = False
                for tool_call in tool_calls:
                    func_name = tool_call["function"]["name"]
                    func_args = tool_call["function"]["arguments"]
                    call_id = tool_call.get("id", f"call_{uuid.uuid4().hex[:8]}")

                    # ── Duplicate detection: break if model repeats the same call ──
                    tool_key = (func_name, json.dumps(func_args, sort_keys=True))
                    if tool_key == _prev_tool_key:
                        ui.tool_result_error("Duplicate tool call detected — stopping loop.")
                        yield "\nDone. (Stopped because the same action was about to repeat.)"
                        loop_break = True
                        break
                    _prev_tool_key = tool_key

                    tool_result = self.call_local_tool(func_name, func_args, ctx=ctx, guard=guard)
                    
                    if tool_result == "ABORT_QUERY":
                        abort_all = True
                        break

                    messages.append({
                        "role": "tool",
                        "content": str(tool_result),
                        "tool_call_id": call_id
                    })
                    
                    # FORCE SEQUENTIAL: one tool at a time
                    break 
                    
                if abort_all or loop_break:
                    # Still save clean history so the model remembers what happened
                    self.history.append({"role": "user", "content": user_query, "_mode": ctx.mode})
                    self.history.append({"role": "assistant", "content": content or "Task completed.", "_mode": ctx.mode})
                    break

            except Exception as e:
                spinner.stop()
                error_msg = f"System Error: {e}"
                yield f"\n{error_msg}"
                messages.append({"role": "user", "content": error_msg})
                continue
        else:
            # max_iterations reached — save history anyway
            self.history.append({"role": "user", "content": user_query, "_mode": ctx.mode})
            self.history.append({"role": "assistant", "content": "Task completed (iteration limit reached).", "_mode": ctx.mode})

    def unload(self):
        try: requests.post(OLLAMA_URL, json={"model": LLM_MODEL, "keep_alive": 0}, timeout=2)
        except: pass
