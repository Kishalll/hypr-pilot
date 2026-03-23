import json
import requests
import re
import uuid
import os
from config import (
    OLLAMA_URL, LLM_MODEL,
    HYPRLAND_KEYWORDS, HYPRLAND_RULE_KEYWORDS, CODING_KEYWORDS,
    AGENT_VERBS, ANSWER_PATTERNS,
    HYPRLAND_ANSWER_PROMPT, HYPRLAND_AGENT_PROMPT,
    GENERAL_ANSWER_PROMPT,
    CODING_ANSWER_PROMPT, CODING_AGENT_PROMPT,
    DOMAIN_KEYWORDS, _PERSONALITY,
)
from vectorstore import HyprVectorStore
from schemas import TOOLS, HYPRLAND_TOOLS, CODING_TOOLS
import tools
import ui

_PERSONALITY_BLOCK = _PERSONALITY




class RequestContext:
    """Routing decision for a single query."""
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




def route_query(query, override_mode=None, override_domain=None):
    """Figure out what the user wants and where to send it."""
    q = query.lower().strip()
    q_norm = re.sub(r'\s+', ' ', q).strip()

    def _looks_like_hypr_nl_intent(text):
        actions = ("float", "tile", "center", "move", "resize", "pin", "fullscreen", "opacity", "blur")
        targets = (
            "window", "terminal", "browser", "workspace", "monitor", "app", "client",
            "special workspace", "scratchpad",
            "kitty", "alacritty", "wezterm", "foot", "gnome-terminal", "konsole", "xterm",
            "firefox", "chromium", "brave", "google-chrome", "zen-browser",
            "vscode", "code", "neovide", "zed",
            "discord", "spotify", "steam", "mpv", "vlc", "obs",
            "nautilus", "thunar", "dolphin",
            "rofi", "wofi", "fuzzel", "waybar", "eww",
        )

        has_action = any(re.search(rf'\b{a}\b', text) for a in actions)
        has_target = any(re.search(rf'\b{t}\b', text) for t in targets)
        has_imperative = bool(re.search(r'\b(make|set|toggle|change|move|resize|center|pin)\b', text))
        return (has_action and has_target) or (has_imperative and has_target)

    # what is this about?
    if override_domain:
        domain = override_domain
    else:
        hypr_score = sum(1 for kw in HYPRLAND_KEYWORDS if kw in q_norm)
        # multi-word matches are more specific, weight them higher
        for kw in HYPRLAND_KEYWORDS:
            if " " in kw and kw in q_norm:
                hypr_score += 2

        if _looks_like_hypr_nl_intent(q_norm):
            hypr_score += 3

        if hypr_score >= 1:
            domain = RequestContext.DOMAIN_HYPRLAND
        else:
            coding_score = sum(1 for kw in CODING_KEYWORDS if kw in q_norm)
            if re.search(r'\b(def|class|import|#include|fn|let|const|var|select|insert|update)\b', query, flags=re.IGNORECASE):
                coding_score += 2
            domain = RequestContext.DOMAIN_CODING if coding_score >= 1 else RequestContext.DOMAIN_GENERAL

    # do they want an answer or an action?
    if override_mode:
        mode = override_mode
    else:
        agent_score = 0
        answer_score = 0

        for verb in AGENT_VERBS:
            if re.search(r'\b' + re.escape(verb) + r'\b', q):
                agent_score += 1

        # question patterns get heavier weight since they're more distinctive
        for pat in ANSWER_PATTERNS:
            if pat in q:
                answer_score += 2

        if q.rstrip().endswith("?"):
            answer_score += 1

        mode = RequestContext.MODE_AGENT if agent_score > answer_score else RequestContext.MODE_ANSWER

    # pair up the right prompt + capabilities
    if domain == RequestContext.DOMAIN_HYPRLAND:
        if mode == RequestContext.MODE_AGENT:
            ctx = RequestContext(mode, domain, use_rag=True, use_tools=True,
                                system_prompt=HYPRLAND_AGENT_PROMPT)
        else:
            ctx = RequestContext(mode, domain, use_rag=True, use_tools=False,
                                system_prompt=HYPRLAND_ANSWER_PROMPT)
    elif domain == RequestContext.DOMAIN_CODING:
        if mode == RequestContext.MODE_AGENT:
            ctx = RequestContext(mode, domain, use_rag=False, use_tools=True,
                                system_prompt=CODING_AGENT_PROMPT)
        else:
            ctx = RequestContext(mode, domain, use_rag=False, use_tools=False,
                                system_prompt=CODING_ANSWER_PROMPT)
    else:
        # No dedicated general-agent workflow: route action requests to coding agent.
        if mode == RequestContext.MODE_AGENT:
            ctx = RequestContext(mode, RequestContext.DOMAIN_CODING, use_rag=False, use_tools=True,
                                system_prompt=CODING_AGENT_PROMPT)
        else:
            ctx = RequestContext(mode, domain, use_rag=False, use_tools=False,
                                system_prompt=GENERAL_ANSWER_PROMPT)

    ctx.forced = bool(override_mode or override_domain)
    return ctx




class HyprlandGuard:
    """Makes sure the model does its homework before touching hyprland configs."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.got_config_paths = False
        self.got_window_class = False
        self.read_rules_file = False
        self.require_rule_syntax = False
        self.write_applied = False
        self.user_denied_write = False
        self._rules_file_path = None

    def record_tool(self, name, args, result):
        if name == "get_active_config_paths":
            self.got_config_paths = True
            # grab the rules file path from the output
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
        elif name in ("write_file", "append_file", "replace_line", "insert_line", "delete_lines", "upsert_hypr_rule"):
            if isinstance(result, str) and (
                result.lower().startswith("success")
                or result.lower().startswith("rule already exists")
            ):
                self.write_applied = True

    def check_write(self, name, args):
        """Block writes to hyprland config if the model skipped the prerequisite steps."""
        if name not in ("write_file", "append_file", "replace_line", "insert_line", "delete_lines", "upsert_hypr_rule"):
            return None

        target = tools.expand_path(args.get("file_path", ""))
        hypr_dir = tools.expand_path("~/.config/hypr")

        # only care about writes inside ~/.config/hypr/
        if not target.startswith(hypr_dir):
            return None

        if self.require_rule_syntax and self.write_applied:
            return "GUARDRAIL BLOCKED: A rule mutation has already been applied for this request. Do not write again; summarize completion."

        errors = []
        if not self.got_config_paths:
            errors.append("You must call `get_active_config_paths` first to find the correct rules file.")
        if not self.read_rules_file:
            creating_missing_rules_file = (
                name == "write_file"
                and bool(self._rules_file_path)
                and target == tools.expand_path(self._rules_file_path)
                and not os.path.exists(target)
            )
            if not creating_missing_rules_file:
                errors.append("You must `read_file` the rules file before modifying it.")

        if self._rules_file_path and target != tools.expand_path(self._rules_file_path):
            errors.append("You must modify only the discovered rules file, not other Hyprland config files.")

        # windowrule edits also need the actual window class first
        content = "\n".join([
            str(args.get("content", "")),
            str(args.get("new_line", "")),
            str(args.get("old_line", "")),
            str(args.get("rule_type", "")),
            str(args.get("effect", "")),
            str(args.get("effect_args", "")),
            str(args.get("matches", "")),
        ])
        if "windowrule" in content.lower() and not self.got_window_class:
            errors.append("You must call `get_window_class` first before adding window rules.")

        if name in ("write_file", "append_file", "replace_line", "insert_line"):
            lowered_raw = content.lower()
            if "windowrule" in lowered_raw or "layerrule" in lowered_raw:
                errors.append("Use `upsert_hypr_rule` for window/layer rule mutations instead of raw file write tools.")

        if self.require_rule_syntax:
            lowered = content.lower()
            if "[global]" in lowered:
                errors.append("Invalid Hyprland format for this task: do not write INI sections like [global].")

            window_props = {
                "match:class", "match:title", "match:initial_class", "match:initial_title",
                "match:tag", "match:xwayland", "match:float", "match:fullscreen",
                "match:pin", "match:focus", "match:group", "match:modal",
                "match:fullscreen_state_client", "match:fullscreen_state_internal",
                "match:workspace", "match:content", "match:xdg_tag",
            }
            layer_props = {"match:namespace"}

            # value = minimum number of required args for the effect
            window_effects_min_args = {
                "float": 1, "tile": 1, "fullscreen": 1, "maximize": 1,
                "fullscreen_state": 2, "move": 2, "size": 2, "center": 1,
                "pseudo": 1, "monitor": 1, "workspace": 1, "no_initial_focus": 1,
                "pin": 1, "group": 0, "suppress_event": 1, "content": 1,
                "no_close_for": 1,

                "persistent_size": 1, "no_max_size": 1, "stay_focused": 1,
                "animation": 1, "border_color": 1, "idle_inhibit": 1,
                "opacity": 1, "tag": 1, "max_size": 2, "min_size": 2,
                "border_size": 1, "rounding": 1, "rounding_power": 1,
                "allows_input": 1, "dim_around": 1, "decorate": 1,
                "focus_on_activate": 1, "keep_aspect_ratio": 1,
                "nearest_neighbor": 1, "no_anim": 1, "no_blur": 1,
                "no_dim": 1, "no_focus": 1, "no_follow_mouse": 1,
                "no_shadow": 1, "no_shortcuts_inhibit": 1, "no_screen_share": 1,
                "no_vrr": 1, "opaque": 1, "force_rgbx": 1,
                "sync_fullscreen": 1, "immediate": 1, "xray": 1,
                "render_unfocused": 1, "scroll_mouse": 1, "scroll_touchpad": 1,
                "scrolling_width": 1,
            }

            layer_effects_min_args = {
                "no_anim": 1, "blur": 1, "blur_popups": 1, "ignore_alpha": 1,
                "dim_around": 1, "xray": 1, "animation": 1, "order": 1,
                "above_lock": 1, "no_screen_share": 1,
            }

            def validate_rule_line(line):
                l = line.strip()
                m = re.match(r'^(windowrule|layerrule)\s*=\s*(.+)$', l)
                if not m:
                    return None

                kind = m.group(1).lower()
                rhs = m.group(2).strip()
                parts = [p.strip() for p in rhs.split(',') if p.strip()]

                if len(parts) < 2:
                    return "rule must contain at least one prop and one effect, separated by commas"

                if kind == "windowrule":
                    allowed_props = window_props
                    effects_min_args = window_effects_min_args
                else:
                    allowed_props = layer_props
                    effects_min_args = layer_effects_min_args

                seen_props = set()
                prop_count = 0
                effect_count = 0

                for part in parts:
                    tokens = part.split()
                    if not tokens:
                        continue
                    key = tokens[0].lower()
                    args = tokens[1:]

                    if key.startswith("match:"):
                        if key not in allowed_props:
                            return f"unknown prop '{key}' for {kind}"
                        if key in seen_props:
                            return f"duplicate prop '{key}' is not allowed"
                        if len(args) < 1:
                            return f"prop '{key}' is missing its argument"
                        seen_props.add(key)
                        prop_count += 1
                    else:
                        if key not in effects_min_args:
                            return f"unknown effect '{key}' for {kind}"
                        if len(args) < effects_min_args[key]:
                            need = effects_min_args[key]
                            return f"effect '{key}' requires at least {need} argument(s)"
                        effect_count += 1

                if prop_count < 1:
                    return "rule must include at least one match:* prop"
                if effect_count < 1:
                    return "rule must include at least one effect"

                return None

            for line in content.splitlines():
                err = validate_rule_line(line)
                if err:
                    errors.append(f"Invalid rule syntax in '{line.strip()}': {err}.")
                    break

            if name != "delete_lines":
                has_rule_line = any(k in lowered for k in ("windowrule", "layerrule"))
                if not has_rule_line:
                    errors.append("For this request, writes must use `windowrule` or `layerrule` syntax.")

                if re.search(r'^\s*(float|tile)\s*=\s*', content, flags=re.IGNORECASE | re.MULTILINE):
                    errors.append("Invalid rule syntax: use `windowrule = ...` rather than `float =` / `tile =` assignments.")

        if errors:
            return "GUARDRAIL BLOCKED: " + " ".join(errors)
        return None


class HyprBrain:
    def __init__(self):
        self.store = HyprVectorStore()
        self.history = []
        self._override_mode = None
        self._override_domain = None
        try:
            self.store.load_index()
        except:
            pass  # index might not be built yet, that's fine

    # --- slash command overrides ---

    def set_override(self, mode=None, domain=None):

        self._override_mode = mode
        self._override_domain = domain

    def clear_overrides(self):
        self._override_mode = None
        self._override_domain = None

    # the 3b model mixes up arg names when tools have similar signatures,
    # so we fix the most common mistakes before passing them through
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
        fixes = self._PARAM_FIXES.get(name)
        if not fixes:
            return args
        fixed = {}
        for k, v in args.items():
            if k in fixes:
                mapped = fixes[k]
                if mapped is None:
                    continue
                fixed[mapped] = v
            else:
                fixed[k] = v
        return fixed

    def call_local_tool(self, name, args, ctx=None, guard=None):
        args = self._normalize_args(name, args)

        # guardrail check (hard-enforced, not just prompt instructions)
        if ctx and ctx.domain == RequestContext.DOMAIN_HYPRLAND and guard:
            block_msg = guard.check_write(name, args)
            if block_msg:
                if ui.is_debug_mode():
                    ui.tool_result_error(block_msg)
                else:
                    ui.tool_result_error("Guardrail blocked this action.")
                return block_msg

        ui.tool_action(name, args)

        # path validation for file writes
        if name in ("write_file", "append_file", "replace_line", "insert_line", "delete_lines", "upsert_hypr_rule"):
            target_path = tools.expand_path(args.get('file_path', ''))
            if name in ("append_file", "replace_line", "insert_line", "delete_lines", "upsert_hypr_rule"):
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

        # make sure the line actually exists before asking user to confirm
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

        # running code needs explicit user permission
        if name == "validate_file" and args.get("run"):
            choice = ui.confirm_action(name, args)
            if choice == 'a':
                ui.tool_result_aborted()
                return "ABORT_QUERY"
            elif choice != 'y':
                ui.tool_result_denied("Skipped by user.")
                # still do the syntax check, just don't execute
                args = dict(args)
                args["run"] = False

        # anything destructive gets a confirmation prompt
        if name in ("write_file", "append_file", "replace_line", "insert_line", "delete_lines", "upsert_hypr_rule", "execute_command"):
            choice = ui.confirm_action(name, args)
            if choice == 'a':
                ui.tool_result_aborted()
                return "ABORT_QUERY"
            elif choice != 'y':
                ui.tool_result_denied("Skipped by user.")
                if guard and name in ("write_file", "append_file", "replace_line", "insert_line", "delete_lines", "upsert_hypr_rule"):
                    guard.user_denied_write = True
                return "User denied execution."

        # actually run the thing
        func = getattr(tools, name, None)
        if func:
            try:
                result = func(**args)
                ui.tool_result_success()

                if guard:
                    guard.record_tool(name, args, result)
                return result
            except Exception as e:
                ui.tool_result_error(str(e))
                return f"Error: {e}"
        ui.tool_result_error(f"Tool '{name}' not found.")
        return f"Error: Tool '{name}' not found."

    # --- json parsing helpers ---

    def _try_parse_json(self, json_str):
        r"""Try parsing JSON, fix common escape mistakes if it fails."""
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
        """Hunt for tool call JSON in the model's text output (bracket matching)."""
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

    # --- main response loop ---

    def generate_response(self, query):
        ui.reset_steps()

        ctx = route_query(query, self._override_mode, self._override_domain)
        
        # Continuity inheritance: if the user gives a short answer to a question
        if len(query.split()) <= 12 and self.history:
            last_entry = self.history[-1]
            if last_entry["role"] == "assistant" and "?" in last_entry["content"]:
                ctx.mode = last_entry.get("_mode", ctx.mode)
                ctx.domain = last_entry.get("_domain", ctx.domain)
                ctx.use_tools = (ctx.mode == RequestContext.MODE_AGENT)
                ctx.use_rag = (ctx.domain == RequestContext.DOMAIN_HYPRLAND)
                # re-apply the correct system prompt for the inherited context
                if ctx.domain == RequestContext.DOMAIN_HYPRLAND:
                    ctx.system_prompt = HYPRLAND_AGENT_PROMPT if ctx.use_tools else HYPRLAND_ANSWER_PROMPT
                elif ctx.domain == RequestContext.DOMAIN_GENERAL:
                    ctx.system_prompt = GENERAL_ANSWER_PROMPT
                else:
                    ctx.system_prompt = CODING_AGENT_PROMPT if ctx.use_tools else CODING_ANSWER_PROMPT
                
        ui.show_mode(ctx.mode, ctx.domain)

        # fresh guardrail tracker per query
        guard = HyprlandGuard() if ctx.domain == RequestContext.DOMAIN_HYPRLAND else None

        # inject real paths into the system prompt
        system_prompt = ctx.system_prompt
        _home = os.path.expanduser("~")
        _cwd = os.getcwd()
        if ctx.mode == RequestContext.MODE_AGENT and ctx.domain != RequestContext.DOMAIN_HYPRLAND:
            system_prompt = system_prompt.format(
                personality=_PERSONALITY_BLOCK,
                home_dir=_home,
                cwd=_cwd,
            )
        elif ctx.domain == RequestContext.DOMAIN_HYPRLAND:
            system_prompt = system_prompt.format(
                personality=_PERSONALITY_BLOCK,
                home_dir=_home,
            )
        messages = [{"role": "system", "content": system_prompt}]

        # include history for continuity. answer gets less history to stay focused, agent gets more.
        history_limit = 6 if ctx.mode == RequestContext.MODE_ANSWER else 10
        for entry in self.history[-history_limit:]:
            messages.append({"role": entry["role"], "content": entry["content"]})

        # RAG injection for hyprland queries
        user_query = query
        if ctx.use_rag:
            context_chunks = self.store.search(query, k=3)
            if context_chunks:
                context_str = ""
                for i, chunk in enumerate(context_chunks):
                    source_info = f"Source: {chunk['source']}"
                    # Rewrite deprecated syntax in RAG chunks to the current Hyprland format
                    clean_content = chunk['content'].replace("windowrulev2", "windowrule")
                    # old: `float,class:` → new: `float on, match:class`
                    # Step 1: fix comma-class separator to use match:class
                    clean_content = re.sub(r',\s*class:', ', match:class ', clean_content)
                    # Step 2: only add `on` for known boolean effects — never touch opacity, rounding, etc.
                    _bool_effects = r'(?:float|tile|center|pin|pseudo|fullscreen|maximize|no_blur|no_dim|no_shadow|no_focus|no_anim|opaque|stay_focused)'
                    clean_content = re.sub(
                        rf'(windowrule\s*=\s*)({_bool_effects})(\s*,)',
                        lambda m: f"{m.group(1)}{m.group(2)} on{m.group(3)}",
                        clean_content,
                        flags=re.IGNORECASE
                    )
                    context_str += f"\n--- Reference {i+1} ({source_info}) ---\n{clean_content}\n"
                query = f"[SYSTEM: Here is relevant Hyprland context. Use it if applicable.]\n{context_str}\n\n[USER QUERY]: {query}"

        # when the user says something short like "run it", give the model
        # context from the previous exchange so it knows what "it" means
        if ctx.mode == RequestContext.MODE_AGENT and len(user_query.split()) <= 8:
            last_agent_entries = [e for e in self.history if e.get("_mode") == RequestContext.MODE_AGENT]
            if last_agent_entries:
                last_assistant = [e for e in last_agent_entries if e["role"] == "assistant"]
                if last_assistant:
                    prev_context = last_assistant[-1]["content"]

                    path_matches = re.findall(r'(/[\w./~-]+\.\w+)', prev_context)
                    if path_matches:
                        paths_str = ", ".join(path_matches[:3])
                        query += f"\n\n[CONTEXT from previous task: files involved: {paths_str}]"

        force_stop_tools = False
        is_hypr_mutation = ctx.domain == RequestContext.DOMAIN_HYPRLAND and ctx.mode == RequestContext.MODE_AGENT
        if is_hypr_mutation:
            
            generic_apps = [
                "browser", "code editor", "editor", "music player", "video player",
                "file manager", "launcher", "chat app", "mail app", "app", "application",
            ]
            q_user = user_query.lower()
            has_generic_app = any(re.search(rf'\b{re.escape(g)}\b', q_user) for g in generic_apps)

            if has_generic_app:
                query += "\n\n[CRITICAL STOP]: The user stated a generic app type. You MUST ask them WHICH specific app they are using via plain text. You have NO tools available for this turn. Do NOT make up an app name!"
                force_stop_tools = True
            else:
                q_lower = user_query.lower()
                
                # If we're following up on a short answer, inherit the intent from the original query
                if len(user_query.split()) <= 12 and len(self.history) >= 2:
                    last_asst = self.history[-1]
                    last_user = self.history[-2]
                    if last_asst["role"] == "assistant" and "?" in last_asst["content"] and last_user["role"] == "user":
                        q_lower += " " + last_user["content"].lower()

                needs_rule_guard = any(kw in q_lower for kw in HYPRLAND_RULE_KEYWORDS)
                
                # Catch natural language overrides that also imply window rule changes
                if any(kw in q_lower for kw in ["tile", "float", "center", "move", "resize", "pin", "blur", "opacity"]):
                    needs_rule_guard = True
                    
                if needs_rule_guard:
                    if guard:
                        guard.require_rule_syntax = True
                    reminder = "\n\n[CRITICAL REMINDER]: 1. MUST use get_window_class tool first. 2. MUST use get_active_config_paths tool first to find rules file. 3. MUST read_file the rules file before modifying. 4. Use new syntax: `windowrule = <effect> <value>, match:class ^(exact_class)$`. Replace <effect> and <value> with the requested action."
                    query += reminder
        elif ctx.mode == RequestContext.MODE_AGENT:
            query += "\n\n[REMINDER]: Use tools to complete the task. Write plain text for conversational answers. DO NOT output empty {} blocks."

        messages.append({"role": "user", "content": query})

        # pick the right toolset
        if not ctx.use_tools or force_stop_tools:
            active_tools = None
        elif ctx.domain == RequestContext.DOMAIN_HYPRLAND:
            active_tools = HYPRLAND_TOOLS
        else:
            active_tools = CODING_TOOLS

        # answering mode: one-shot, no tool loop
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
                self.history.append({"role": "user", "content": user_query, "_mode": ctx.mode, "_domain": ctx.domain})
                self.history.append({"role": "assistant", "content": content, "_mode": ctx.mode, "_domain": ctx.domain})
            except Exception as e:
                spinner.stop()
                yield f"\nSystem Error: {e}"
            return

        # agent mode: tool-call loop
        max_iterations = 10
        _prev_tool_key = None  # for duplicate detection
        _same_tool_streak = 0  # counts consecutive repeats of the exact same tool+args
        _no_tool_streak = 0    # counts assistant text-only turns when a mutation is still required
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

                # sometimes the model jams tool calls into its text response
                text_tool_calls, cleaned_content = self.parse_tool_calls_from_text(content)
                if text_tool_calls:
                    tool_calls.extend(text_tool_calls)
                    content = ""

                message["content"] = content if content else None
                message["tool_calls"] = tool_calls if tool_calls else None
                messages.append(message)

                if not tool_calls:
                    if (
                        is_hypr_mutation
                        and guard
                        and guard.require_rule_syntax
                        and not guard.write_applied
                        and not guard.user_denied_write
                    ):
                        _no_tool_streak += 1
                        if _no_tool_streak >= 3:
                            final_msg = (
                                "I could not complete the mutation because the model kept responding without issuing the required tool call. "
                                "Please retry the same command once; the safety state has been reset."
                            )
                            yield final_msg
                            self.history.append({"role": "user", "content": user_query, "_mode": ctx.mode, "_domain": ctx.domain})
                            self.history.append({"role": "assistant", "content": final_msg, "_mode": ctx.mode, "_domain": ctx.domain})
                            break

                        missing_steps = []
                        if not guard.got_config_paths:
                            missing_steps.append("get_active_config_paths")
                        if not guard.read_rules_file:
                            missing_steps.append("read_file on discovered RULES FILE")
                        if not guard.got_window_class:
                            missing_steps.append("get_window_class")

                        if missing_steps:
                            instruction = (
                                "[INCOMPLETE TASK] Do not answer in prose. Return exactly one tool call for the next missing prerequisite: "
                                + ", then ".join(missing_steps)
                                + "."
                            )
                        else:
                            instruction = (
                                "[INCOMPLETE TASK] Do not answer in prose. Return exactly one tool call to `upsert_hypr_rule` "
                                "for the discovered rules file and resolved class, then continue."
                            )

                        messages.append({
                            "role": "user",
                            "content": instruction
                        })
                        continue

                    _no_tool_streak = 0
                    if content:
                        yield content

                    self.history.append({"role": "user", "content": user_query, "_mode": ctx.mode, "_domain": ctx.domain})
                    self.history.append({"role": "assistant", "content": content, "_mode": ctx.mode, "_domain": ctx.domain})
                    break

                _no_tool_streak = 0
                
                abort_all = False
                loop_break = False
                for tool_call in tool_calls:
                    func_name = tool_call["function"]["name"]
                    func_args = tool_call["function"]["arguments"]
                    call_id = tool_call.get("id", f"call_{uuid.uuid4().hex[:8]}")

                    # catch the model if it's stuck in a loop
                    tool_key = (func_name, json.dumps(func_args, sort_keys=True))
                    if tool_key == _prev_tool_key:
                        _same_tool_streak += 1
                        # allow one immediate retry (useful during guardrail recovery),
                        # but stop if the same call keeps repeating with no progress.
                        if _same_tool_streak >= 2:
                            ui.tool_result_error("Duplicate tool call loop detected — stopping loop.")
                            yield "\nStopped. (Same action repeated multiple times without progress.)"
                            loop_break = True
                            break
                    else:
                        _same_tool_streak = 0
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

                    # Help the model recover deterministically after guardrail blocks.
                    if ctx.domain == RequestContext.DOMAIN_HYPRLAND and isinstance(tool_result, str) and tool_result.startswith("GUARDRAIL BLOCKED:"):
                        if "Invalid rule syntax" in tool_result:
                            recovery_steps = [
                                "The last rule line syntax was invalid.",
                                "Regenerate a valid anonymous rule using wiki order: windowrule = <effect> <arg>, match:<prop> <value>.",
                                "Ensure every effect has required args (e.g. float on, move x y, max_size w h).",
                                "Then retry the write in the discovered rules file only.",
                                "Do not apologize. Continue with the next required tool call.",
                            ]
                        else:
                            recovery_steps = [
                                "If not done yet: call get_active_config_paths.",
                                "Then read_file on the discovered >>> RULES FILE path.",
                                "If windowrule is being added/changed and class is unknown: call get_window_class.",
                                "Then retry the config edit in the rules file only.",
                                "Do not apologize. Continue with the next required tool call.",
                            ]
                        messages.append({
                            "role": "user",
                            "content": "[GUARDRAIL RECOVERY] " + " ".join(recovery_steps)
                        })
                    
                    break  # one tool at a time, always
                    
                if abort_all or loop_break:
                    self.history.append({"role": "user", "content": user_query, "_mode": ctx.mode, "_domain": ctx.domain})
                    self.history.append({"role": "assistant", "content": content or "Task completed.", "_mode": ctx.mode, "_domain": ctx.domain})
                    break

            except Exception as e:
                spinner.stop()
                error_msg = f"System Error: {e}"
                yield f"\n{error_msg}"
                messages.append({"role": "user", "content": error_msg})
                continue
        else:  # hit the iteration ceiling
            self.history.append({"role": "user", "content": user_query, "_mode": ctx.mode, "_domain": ctx.domain})
            self.history.append({"role": "assistant", "content": "Task completed (iteration limit reached).", "_mode": ctx.mode, "_domain": ctx.domain})

    def unload(self):
        try: requests.post(OLLAMA_URL, json={"model": LLM_MODEL, "keep_alive": 0}, timeout=2)
        except: pass
