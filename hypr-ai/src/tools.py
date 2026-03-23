import os
import subprocess
import re

_WINDOW_PROPS = {
    "match:class", "match:title", "match:initial_class", "match:initial_title",
    "match:tag", "match:xwayland", "match:float", "match:fullscreen",
    "match:pin", "match:focus", "match:group", "match:modal",
    "match:fullscreen_state_client", "match:fullscreen_state_internal",
    "match:workspace", "match:content", "match:xdg_tag",
}

_LAYER_PROPS = {"match:namespace"}

_WINDOW_EFFECTS_MIN_ARGS = {
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

_LAYER_EFFECTS_MIN_ARGS = {
    "no_anim": 1, "blur": 1, "blur_popups": 1, "ignore_alpha": 1,
    "dim_around": 1, "xray": 1, "animation": 1, "order": 1,
    "above_lock": 1, "no_screen_share": 1,
}

_WINDOW_BOOL_EFFECTS = {
    "float", "tile", "fullscreen", "maximize", "center", "pseudo", "pin",
    "no_initial_focus", "persistent_size", "no_max_size", "stay_focused",
    "allows_input", "dim_around", "decorate", "focus_on_activate",
    "keep_aspect_ratio", "nearest_neighbor", "no_anim", "no_blur",
    "no_dim", "no_focus", "no_follow_mouse", "no_shadow",
    "no_shortcuts_inhibit", "no_screen_share", "no_vrr", "opaque",
    "force_rgbx", "sync_fullscreen", "immediate", "xray", "render_unfocused",
}

_LAYER_BOOL_EFFECTS = {
    "no_anim", "blur", "blur_popups", "dim_around", "no_screen_share",
}


def _normalize_on_off(value):
    v = (value or "").strip().lower()
    if v in ("on", "true", "yes", "1"):
        return "on"
    if v in ("off", "false", "no", "0"):
        return "off"
    return None

def expand_path(path):
    return os.path.expanduser(os.path.expandvars(path))

def list_directory(dir_path="."):
    try:
        expanded_path = expand_path(dir_path)
        items = os.listdir(expanded_path)
        return "\n".join(items) if items else "Directory is empty."
    except Exception as e:
        return f"Error listing directory: {e}"

def read_file(file_path):
    try:
        expanded_path = expand_path(file_path)
        with open(expanded_path, 'r', encoding='utf-8') as f:
            content = f.read()
            if len(content) > 8000:
                return content[:8000] + "\n\n...[FILE TRUNCATED FOR CONTEXT SIZE]..."
            return content
    except Exception as e:
        return f"Error reading file: {e}"

def _fix_over_escaped_content(content, file_path):
    """The 3b model loves double-escaping quotes in JSON tool calls.
    \\\" becomes literal \" after parsing, which breaks code.
    We detect and selectively fix this per-line."""
    if '\\"' not in content:
        return content  # nothing to fix

    ext = os.path.splitext(file_path)[1].lower()
    
    # only worth auto-fixing in code files
    fixable_exts = {'.c', '.cpp', '.h', '.hpp', '.py', '.js', '.ts', '.java',
                    '.go', '.rs', '.sh', '.bash', '.rb', '.lua', '.php'}
    if ext not in fixable_exts:
        return content

    # per-line heuristic: if removing \ before " gives balanced quotes, apply the fix
    fixed_lines = []
    for line in content.split('\n'):
        if '\\"' in line:
            candidate = line.replace('\\"', '"')
            # balanced quotes = probably safe to fix
            quote_count = candidate.count('"') - candidate.count('\\"')
            if quote_count % 2 == 0:
                fixed_lines.append(candidate)
            else:
                fixed_lines.append(line)  # leave it alone if it'd unbalance things
        else:
            fixed_lines.append(line)
    return '\n'.join(fixed_lines)


def write_file(file_path, content):
    try:
        expanded_path = expand_path(file_path)
        # make sure parent dirs exist
        if os.path.dirname(expanded_path):
            os.makedirs(os.path.dirname(expanded_path), exist_ok=True)
        # fix the model's escape addiction before writing
        content = _fix_over_escaped_content(content, file_path)
        with open(expanded_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"Successfully wrote to {file_path}"
    except Exception as e:
        return f"Error writing file: {e}"

def append_file(file_path, content):
    try:

        expanded_path = expand_path(file_path)
        if not os.path.exists(expanded_path):
            return f"Error: File {file_path} does not exist to append to."
        content = _fix_over_escaped_content(content, file_path)
        with open(expanded_path, 'a', encoding='utf-8') as f:
            # start on a new line if file isn't empty
            if os.path.getsize(expanded_path) > 0:
                f.write("\n")
            f.write(content)
        return f"Successfully appended to {file_path}"
    except Exception as e:
        return f"Error appending to file: {e}"

def get_window_class(app_name):
    """Looks up the real WM class for an app via hyprctl and .desktop files."""
    try:
        import json
        import shutil

        original_name = app_name
        app_name = (app_name or "").strip()

        term_aliases = ["terminal", "term", "my terminal", "current terminal"]
        term_markers = [
            "kitty", "alacritty", "wezterm", "foot", "gnome-terminal",
            "konsole", "terminator", "xterm", "urxvt", "st",
            "tilix", "lxterminal", "xfce4-terminal",
        ]

        def is_terminal_class(cls):
            c = (cls or "").lower()
            return any(m in c for m in term_markers)

        # For one-to-one intents like "terminal", prefer active window class first.
        if app_name.lower() in term_aliases:
            active = subprocess.run("hyprctl activewindow -j", shell=True, capture_output=True, text=True)
            if active.returncode == 0 and active.stdout.strip():
                data = json.loads(active.stdout)
                cls = data.get("class")
                if cls and is_terminal_class(cls):
                    return f"SUCCESS: Active window class detected as '{cls}'"

            # If active window is not a terminal (e.g. code), pick from running terminal windows.
            result_clients = subprocess.run("hyprctl clients -j", shell=True, capture_output=True, text=True)
            if result_clients.returncode == 0 and result_clients.stdout.strip():
                clients = json.loads(result_clients.stdout)
                terminal_classes = []
                seen = set()
                for c in clients:
                    cls = c.get('class', '')
                    if cls and is_terminal_class(cls) and cls.lower() not in seen:
                        seen.add(cls.lower())
                        terminal_classes.append(cls)
                if len(terminal_classes) == 1:
                    return f"SUCCESS: Detected running terminal class '{terminal_classes[0]}'"
                if len(terminal_classes) > 1:
                    return f"SUCCESS: Detected running terminal class '{terminal_classes[0]}'"
        
        if app_name.lower() in term_aliases:
            term_env = os.environ.get("TERM", "").lower()
            common_terms = ["kitty", "alacritty", "wezterm", "foot", "gnome-terminal", "konsole", "terminator", "st", "urxvt"]
            for ct in common_terms:
                if ct in term_env:
                    app_name = ct
                    break
            if app_name.lower() in term_aliases:
                for ct in common_terms:
                    if shutil.which(ct):
                        app_name = ct
                        break
                        
        result = subprocess.run("hyprctl clients -j", shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            clients = json.loads(result.stdout)

            # exact class match first
            for c in clients:
                cls = c.get('class', '')
                if cls and app_name.lower() == cls.lower():
                    return f"SUCCESS: Exact running class match found: '{cls}'"

            for c in clients:
                if app_name.lower() in c.get('class', '').lower() or app_name.lower() in c.get('title', '').lower():
                    return f"SUCCESS: App is running. The exact class is '{c.get('class')}'"
    except:
        pass
    
    try:
        import glob
        dirs = ['/usr/share/applications', expand_path('~/.local/share/applications')]
        all_desktops = []
        for d in dirs:
            if os.path.exists(d):
                all_desktops.extend(glob.glob(os.path.join(d, '*.desktop')))
                
        base_name = re.split(r'[- _]', app_name)[0].lower()
        search_terms = [app_name.lower()]
        if base_name and base_name != app_name.lower():
            search_terms.append(base_name)
            
        for term in search_terms:
            for file_path in all_desktops:
                filename = os.path.basename(file_path).lower()
                is_match = term in filename
                
                if not is_match:
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        if re.search(f'^(Name|Exec)=.*{re.escape(term)}', content, re.IGNORECASE | re.MULTILINE):
                            is_match = True
                    except:
                        continue
                
                if is_match:
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        match = re.search(r'^StartupWMClass=(.+)', content, re.MULTILINE)
                        if match:
                            return f"SUCCESS: Found in desktop file. The exact class is '{match.group(1).strip()}'"
                        else:
                            fallback_class = os.path.basename(file_path).replace('.desktop', '')
                            return f"SUCCESS: Found in desktop file (fallback). The exact class is '{fallback_class}'"
                    except:
                        continue
                        
        return f"Could not find exact class for '{original_name}'. Ask the user directly."
    except Exception as e:
        return f"Error finding class: {e}"

def get_active_config_paths():
    """Finds the main hyprland.conf and any sourced files, figures out where rules live."""
    try:
        base_dir = expand_path("~/.config/hypr")
        path = os.path.join(base_dir, "hyprland.conf")
        if not os.path.exists(path):
            return "Error: ~/.config/hypr/hyprland.conf does not exist."
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()

        sources = re.findall(r'^\s*source\s*=\s*(.+)', content, re.MULTILINE)
        resolved = []
        rules_file = None
        for s in sources:
            s = s.strip()
            if s.startswith('~'):
                s = expand_path(s)
            elif not s.startswith('/'):
                s = os.path.join(base_dir, s)
            resolved.append(s)
            # prefer custom/rules over hyprland/rules if both exist
            if 'rules' in os.path.basename(s).lower():
                if rules_file is None or 'custom' in s.lower():
                    rules_file = s

        res = f"Main Config: {path}\n"
        if resolved:
            res += "Sourced Files:\n"
            for s in resolved:
                exists = os.path.exists(s)
                marker = "" if exists else " [MISSING]"
                res += f"  - {s}{marker}\n"
        else:
            res += "No sourced files found.\n"

        if rules_file and os.path.exists(rules_file):
            res += f"\n>>> RULES FILE (use this for window rules): {rules_file}\n"
        elif rules_file:
            res += f"\n>>> RULES FILE (referenced but missing): {rules_file}\n"
            res += f">>> You MUST use `mkdir` to create the parent directories, then use `write_file` to create this rules file.\n"
        else:
            res += f"\n>>> No dedicated rules file found. Append rules directly to {path}\n"

        return res
    except Exception as e:
        return f"Error reading config: {e}"


def _parse_match_segments(matches):
    if not isinstance(matches, str):
        return None, "`matches` must be a string"

    parts = [p.strip() for p in matches.split(',') if p.strip()]
    if not parts:
        return None, "`matches` must include at least one match:* segment"

    parsed = []
    seen = set()
    for p in parts:
        tokens = p.split()
        if len(tokens) < 2:
            return None, f"match segment '{p}' is missing a value"
        key = tokens[0].lower()
        value = " ".join(tokens[1:]).strip()
        if not key.startswith("match:"):
            return None, f"match segment '{p}' must start with match:*"
        if key in seen:
            return None, f"duplicate match prop '{key}' is not allowed"
        seen.add(key)
        parsed.append((key, value))
    return parsed, None


def build_hypr_rule_line(rule_type, effect, effect_args, matches):
    rule_type = (rule_type or "").strip().lower()
    effect = (effect or "").strip().lower()
    effect_args = (effect_args or "").strip()

    if rule_type not in ("windowrule", "layerrule"):
        return None, "`rule_type` must be 'windowrule' or 'layerrule'"

    parsed_matches, err = _parse_match_segments(matches)
    if err:
        return None, err

    if rule_type == "windowrule":
        allowed_props = _WINDOW_PROPS
        effects_min_args = _WINDOW_EFFECTS_MIN_ARGS
    else:
        allowed_props = _LAYER_PROPS
        effects_min_args = _LAYER_EFFECTS_MIN_ARGS

    for key, _ in parsed_matches:
        if key not in allowed_props:
            return None, f"unknown prop '{key}' for {rule_type}"

    if effect not in effects_min_args:
        return None, f"unknown effect '{effect}' for {rule_type}"

    arg_count = len(effect_args.split()) if effect_args else 0
    min_required = effects_min_args[effect]
    if arg_count < min_required:
        return None, f"effect '{effect}' requires at least {min_required} argument(s)"

    arg_tokens = effect_args.split() if effect_args else []

    if rule_type == "windowrule" and effect in _WINDOW_BOOL_EFFECTS:
        if len(arg_tokens) != 1:
            return None, f"effect '{effect}' requires exactly one boolean value (on/off)"
        normalized = _normalize_on_off(arg_tokens[0])
        if normalized is None:
            return None, f"effect '{effect}' expects a boolean value (on/off)"
        effect_args = normalized

    if rule_type == "layerrule" and effect in _LAYER_BOOL_EFFECTS:
        if len(arg_tokens) != 1:
            return None, f"effect '{effect}' requires exactly one boolean value (on/off)"
        normalized = _normalize_on_off(arg_tokens[0])
        if normalized is None:
            return None, f"effect '{effect}' expects a boolean value (on/off)"
        effect_args = normalized

    if rule_type == "layerrule" and effect == "xray":
        if len(arg_tokens) != 1:
            return None, "effect 'xray' requires exactly one argument (on/off/0/1/unset)"
        val = arg_tokens[0].lower()
        if val in ("0", "1", "unset"):
            effect_args = val
        else:
            normalized = _normalize_on_off(val)
            if normalized is None:
                return None, "effect 'xray' expects on/off/0/1/unset"
            effect_args = "1" if normalized == "on" else "0"

    match_str = ", ".join([f"{k} {v}" for k, v in parsed_matches])
    effect_segment = f"{effect} {effect_args}".strip()
    line = f"{rule_type} = {effect_segment}, {match_str}"
    return line, None


def upsert_hypr_rule(file_path, rule_type, effect, effect_args, matches):
    """Build a validated Hyprland rule line and append if not already present."""
    try:
        expanded_path = expand_path(file_path)
        if not os.path.exists(expanded_path):
            return f"Error: File {file_path} does not exist."

        line, err = build_hypr_rule_line(rule_type, effect, effect_args, matches)
        if err:
            return f"Error: {err}"

        with open(expanded_path, 'r', encoding='utf-8') as f:
            existing_lines = [l.rstrip('\n') for l in f.readlines()]

        if any(l.strip() == line.strip() for l in existing_lines):
            return f"Rule already exists in {file_path}: {line}"

        with open(expanded_path, 'a', encoding='utf-8') as f:
            if os.path.getsize(expanded_path) > 0:
                f.write("\n")
            f.write(line)

        return f"Successfully upserted rule in {file_path}: {line}"
    except Exception as e:
        return f"Error upserting rule: {e}"

def replace_line(file_path, old_line, new_line):
    """Swaps out one specific line in a file (exact match)."""
    try:
        expanded_path = expand_path(file_path)
        if not os.path.exists(expanded_path):
            return f"Error: File {file_path} does not exist."

        with open(expanded_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        old_stripped = old_line.strip()
        found = False
        for i, line in enumerate(lines):
            if line.strip() == old_stripped:
                lines[i] = new_line.rstrip('\n') + '\n'
                found = True
                break

        if not found:
            return f"Error: Could not find the line to replace. Looked for: {old_line}"

        with open(expanded_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        return f"Successfully replaced line in {file_path}"
    except Exception as e:
        return f"Error replacing line: {e}"

def execute_command(command):
    """Runs a shell command and captures the output."""
    # hard no on anything that could nuke the system
    dangerous = ["rm -rf /", "mkfs", "dd if="]
    for d in dangerous:
        if d in command:
            return f"Error: Command '{command}' is considered unsafe and blocked."
            
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=15)
        
        output = result.stdout if result.stdout else ""
        error = result.stderr if result.stderr else ""
        
        # cap output so it doesn't blow up the context window
        if len(output) > 2000:
            output = output[:2000] + "\n...[OUTPUT TRUNCATED]..."
        if len(error) > 2000:
            error = error[:2000] + "\n...[ERROR TRUNCATED]..."
            
        return f"STDOUT:\n{output}\nSTDERR:\n{error}"
    except subprocess.TimeoutExpired:
        return "Error: Command timed out after 15 seconds."
    except Exception as e:
        return f"Error executing command: {e}"


# ─── New General Coding Tools ────────────────────────────────────────────────────

def make_directory(dir_path):
    """Creates a directory (and parents) if it doesn't exist."""
    try:
        expanded = expand_path(dir_path)
        os.makedirs(expanded, exist_ok=True)
        return f"Directory created: {dir_path}"
    except Exception as e:
        return f"Error creating directory: {e}"

def file_exists(file_path):
    expanded = expand_path(file_path)
    if os.path.isfile(expanded):
        return f"EXISTS (file): {file_path}"
    elif os.path.isdir(expanded):
        return f"EXISTS (directory): {file_path}"
    else:
        return f"NOT FOUND: {file_path}"

def search_in_files(pattern, dir_path=".", file_glob="*"):
    try:
        expanded = expand_path(dir_path)
        cmd = f'grep -rn --include="{file_glob}" "{pattern}" "{expanded}" 2>/dev/null | head -50'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        output = result.stdout.strip()
        if not output:
            return f"No matches found for '{pattern}' in {dir_path}"
        if len(output) > 3000:
            output = output[:3000] + "\n...[TRUNCATED]..."
        return output
    except subprocess.TimeoutExpired:
        return "Error: Search timed out."
    except Exception as e:
        return f"Error searching: {e}"


def insert_line(file_path, line_number, content):
    try:
        expanded = expand_path(file_path)
        if not os.path.exists(expanded):
            return f"Error: File {file_path} does not exist."
        content = _fix_over_escaped_content(content, file_path)
        with open(expanded, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        idx = max(0, min(line_number - 1, len(lines)))  # clamp to valid range
        new_lines = content.split('\n')
        for i, nl in enumerate(new_lines):
            lines.insert(idx + i, nl + '\n')
        with open(expanded, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        return f"Inserted {len(new_lines)} line(s) at line {line_number} in {file_path}. File now has {len(lines)} lines."
    except Exception as e:
        return f"Error inserting line: {e}"


def delete_lines(file_path, start_line, end_line=None):
    try:
        expanded = expand_path(file_path)
        if not os.path.exists(expanded):
            return f"Error: File {file_path} does not exist."
        with open(expanded, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        if end_line is None:
            end_line = start_line
        s = max(1, start_line) - 1  # 0-based
        e = min(len(lines), end_line)
        if s >= len(lines):
            return f"Error: start_line {start_line} is beyond end of file ({len(lines)} lines)."
        deleted = lines[s:e]
        del lines[s:e]
        with open(expanded, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        deleted_preview = ''.join(deleted).strip()
        if len(deleted_preview) > 200:
            deleted_preview = deleted_preview[:200] + "..."
        return f"Deleted lines {start_line}-{end_line} from {file_path}. Removed:\n{deleted_preview}\nFile now has {len(lines)} lines."
    except Exception as e:
        return f"Error deleting lines: {e}"


# extension -> syntax check command
_VALIDATORS = {
    '.py':  'python3 -c "import py_compile; py_compile.compile(\'{path}\', doraise=True)"',
    '.c':   'gcc -fsyntax-only "{path}"',
    '.cpp': 'g++ -fsyntax-only "{path}"',
    '.js':  'node --check "{path}"',
    '.ts':  'npx tsc --noEmit "{path}" 2>&1 || true',
    '.sh':  'bash -n "{path}"',
    '.rs':  'rustc --edition 2021 "{path}" --crate-type lib -Z parse-only 2>&1 || true',
    '.go':  'gofmt -e "{path}" > /dev/null',
    '.json': 'python3 -c "import json; json.load(open(\'{path}\'))"',
    '.yaml': 'python3 -c "import yaml; yaml.safe_load(open(\'{path}\'))"',
    '.yml': 'python3 -c "import yaml; yaml.safe_load(open(\'{path}\'))"',
}

# extensions we can also try running (small files only)
_RUNNABLE = {
    '.py':  'python3 "{path}"',
    '.sh':  'bash "{path}"',
    '.js':  'node "{path}"',
    '.c':   None,  # needs compile step, handled specially
    '.cpp': None,
}


def validate_file(file_path, run=False):
    """Syntax-check a file. Optionally run it too (small files only)."""
    try:
        expanded = expand_path(file_path)
        if not os.path.exists(expanded):
            return f"Error: File {file_path} does not exist."

        ext = os.path.splitext(expanded)[1].lower()
        report_parts = []

        # syntax check
        validator_cmd = _VALIDATORS.get(ext)
        if validator_cmd:
            cmd = validator_cmd.replace('{path}', expanded)
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
            if result.returncode == 0:
                report_parts.append(f"SYNTAX CHECK: ✓ No errors found in {file_path}")
            else:
                stderr = result.stderr.strip() or result.stdout.strip()
                if len(stderr) > 1500:
                    stderr = stderr[:1500] + "\n...[TRUNCATED]..."
                report_parts.append(f"SYNTAX CHECK: ✗ Errors found in {file_path}:\n{stderr}")
                # no point running if syntax failed
                return "\n".join(report_parts)
        else:
            report_parts.append(f"SYNTAX CHECK: No validator available for '{ext}' files. Skipped.")

        # optional: run it
        if run:
            with open(expanded, 'r', encoding='utf-8') as f:
                line_count = sum(1 for _ in f)
            if line_count > 100:
                report_parts.append(f"RUN: Skipped — file has {line_count} lines (limit: 100).")
            else:
                run_cmd = _RUNNABLE.get(ext)
                # C/C++ needs a compile step first
                if ext in ('.c', '.cpp'):
                    compiler = 'gcc' if ext == '.c' else 'g++'
                    tmp_bin = expanded + '.out'
                    compile_cmd = f'{compiler} "{expanded}" -o "{tmp_bin}"'
                    comp_result = subprocess.run(compile_cmd, shell=True, capture_output=True, text=True, timeout=15)
                    if comp_result.returncode != 0:
                        err = comp_result.stderr.strip()
                        report_parts.append(f"COMPILE: ✗ Failed:\n{err}")
                        return "\n".join(report_parts)
                    report_parts.append("COMPILE: ✓ Success")
                    run_cmd = f'"{tmp_bin}"'

                if run_cmd:
                    cmd = run_cmd.replace('{path}', expanded)
                    try:
                        exec_result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
                        stdout = exec_result.stdout.strip()
                        stderr = exec_result.stderr.strip()
                        if len(stdout) > 1500:
                            stdout = stdout[:1500] + "\n...[TRUNCATED]..."
                        if exec_result.returncode == 0:
                            report_parts.append(f"RUN: ✓ Exit code 0\nOUTPUT:\n{stdout}")
                        else:
                            report_parts.append(f"RUN: ✗ Exit code {exec_result.returncode}\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}")
                    finally:
                        # clean up temp binary for C/C++
                        tmp_bin = expanded + '.out'
                        if os.path.exists(tmp_bin):
                            os.remove(tmp_bin)
                elif run_cmd is None and ext not in ('.c', '.cpp'):
                    report_parts.append(f"RUN: Not supported for '{ext}' files.")

        return "\n".join(report_parts)
    except subprocess.TimeoutExpired:
        return f"Error: Validation timed out for {file_path}."
    except Exception as e:
        return f"Error validating file: {e}"
