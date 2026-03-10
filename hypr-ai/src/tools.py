import os
import subprocess
import re

def expand_path(path):
    """Expands ~ and environment variables in a path."""
    return os.path.expanduser(os.path.expandvars(path))

def list_directory(dir_path="."):
    """Lists files and folders in a given directory."""
    try:
        expanded_path = expand_path(dir_path)
        items = os.listdir(expanded_path)
        return "\n".join(items) if items else "Directory is empty."
    except Exception as e:
        return f"Error listing directory: {e}"

def read_file(file_path):
    """Reads the content of a file."""
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
    """Fix content where the LLM double-escaped quotes in JSON tool calls.
    
    The 3b model often outputs \\\" in JSON instead of \", which after JSON
    parsing becomes literal \" in the string. This produces broken code like:
        printf(\" %d\", nextTerm);   ← wrong
    instead of:
        printf(" %d", nextTerm);    ← correct
    
    We detect this by checking if the file has syntax errors with stray
    backslashes, then selectively fix over-escaped quotes.
    """
    if '\\"' not in content:
        return content  # nothing to fix

    ext = os.path.splitext(file_path)[1].lower()
    
    # Only auto-fix for code files where \" outside string literals is wrong
    fixable_exts = {'.c', '.cpp', '.h', '.hpp', '.py', '.js', '.ts', '.java',
                    '.go', '.rs', '.sh', '.bash', '.rb', '.lua', '.php'}
    if ext not in fixable_exts:
        return content

    # Strategy: replace \" with " but preserve legitimate escaped quotes.
    # In correctly-formed code, \" only appears INSIDE string literals.
    # The over-escaping pattern puts \" where " should be (at string boundaries).
    #
    # Heuristic: process line by line. If a line has \" and removing the
    # backslashes produces valid-looking code (balanced quotes), apply the fix.
    fixed_lines = []
    for line in content.split('\n'):
        if '\\"' in line:
            candidate = line.replace('\\"', '"')
            # Count quotes in the candidate — if balanced (even count), the fix is likely correct
            quote_count = candidate.count('"') - candidate.count('\\"')
            if quote_count % 2 == 0:
                fixed_lines.append(candidate)
            else:
                fixed_lines.append(line)  # leave as-is if fix would unbalance
        else:
            fixed_lines.append(line)
    return '\n'.join(fixed_lines)


def write_file(file_path, content):
    """Writes or overwrites content to a file."""
    try:
        expanded_path = expand_path(file_path)
        # Ensure directory exists
        if os.path.dirname(expanded_path):
            os.makedirs(os.path.dirname(expanded_path), exist_ok=True)
        # Fix common LLM over-escaping before writing
        content = _fix_over_escaped_content(content, file_path)
        with open(expanded_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"Successfully wrote to {file_path}"
    except Exception as e:
        return f"Error writing file: {e}"

def append_file(file_path, content):
    """Appends content to the end of a file."""
    try:

        expanded_path = expand_path(file_path)
        if not os.path.exists(expanded_path):
            return f"Error: File {file_path} does not exist to append to."
        content = _fix_over_escaped_content(content, file_path)
        with open(expanded_path, 'a', encoding='utf-8') as f:
            # ensure it starts on a new line if not empty
            if os.path.getsize(expanded_path) > 0:
                f.write("\n")
            f.write(content)
        return f"Successfully appended to {file_path}"
    except Exception as e:
        return f"Error appending to file: {e}"

def get_window_class(app_name):
    """Finds the accurate window class name for an application by checking running clients and desktop files."""
    try:
        import json
        result = subprocess.run("hyprctl clients -j", shell=True, capture_output=True, text=True)
        clients = json.loads(result.stdout)
        for c in clients:
            if app_name.lower() in c.get('class', '').lower() or app_name.lower() in c.get('title', '').lower():
                return f"SUCCESS: App is running. The exact class is '{c.get('class')}'"
    except:
        pass
    
    try:
        cmd = f'grep -i -E "Name=.*{app_name}|Exec=.*{app_name}" /usr/share/applications/*.desktop ~/.local/share/applications/*.desktop 2>/dev/null'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        output = result.stdout
        if output:
            for line in output.split('\\n'):
                if not line.strip(): continue
                file_path = line.split(':')[0]
                if file_path.endswith('.desktop'):
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            match = re.search(r'^StartupWMClass=(.+)', content, re.MULTILINE)
                            if match:
                                return f"SUCCESS: Found in desktop file. The exact class is '{match.group(1).strip()}'"
                            else:
                                # Fallback to the desktop file name (standard for modern Wayland apps)
                                fallback_class = os.path.basename(file_path).replace('.desktop', '')
                                return f"SUCCESS: Found in desktop file (fallback). The exact class is '{fallback_class}'"
                    except:
                        continue
            return f"Found desktop files but couldn't isolate StartupWMClass. Need human intervention."
        return f"Could not find exact class for '{app_name}'. Ask the user directly."
    except Exception as e:
        return f"Error finding class: {e}"

def get_active_config_paths():
    """Reads hyprland.conf to find where rules are sourced, and identifies the rules file."""
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
            # Identify the rules file (prefer custom/rules over hyprland/rules)
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
            res += f"\n>>> Rules file referenced but MISSING: {rules_file}\n"
            res += f">>> Fallback: append rules directly to {path}\n"
        else:
            res += f"\n>>> No dedicated rules file found. Append rules directly to {path}\n"

        return res
    except Exception as e:
        return f"Error reading config: {e}"

def replace_line(file_path, old_line, new_line):
    """Replaces a specific line in a file. Use this to fix existing broken rules instead of appending duplicates."""
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
    """Runs a shell command and returns the output."""
    dangerous = ["rm -rf /", "mkfs", "dd if="]
    for d in dangerous:
        if d in command:
            return f"Error: Command '{command}' is considered unsafe and blocked."
            
    try:
        # Commands already handle ~ in shell=True, but we'll keep it consistent
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=15)
        
        output = result.stdout if result.stdout else ""
        error = result.stderr if result.stderr else ""
        
        # Limit output length to prevent breaking context window
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
    """Checks whether a file or directory exists at the given path."""
    expanded = expand_path(file_path)
    if os.path.isfile(expanded):
        return f"EXISTS (file): {file_path}"
    elif os.path.isdir(expanded):
        return f"EXISTS (directory): {file_path}"
    else:
        return f"NOT FOUND: {file_path}"

def search_in_files(pattern, dir_path=".", file_glob="*"):
    """Search for a text pattern in files under a directory. Returns matching lines."""
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
    """Inserts one or more lines at a specific line number (1-based). Existing lines shift down."""
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
    """Deletes line(s) from a file. Lines are 1-based. If end_line is omitted, deletes only start_line."""
    try:
        expanded = expand_path(file_path)
        if not os.path.exists(expanded):
            return f"Error: File {file_path} does not exist."
        with open(expanded, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        if end_line is None:
            end_line = start_line
        s = max(1, start_line) - 1  # convert to 0-based
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


# Map file extension to syntax-check command
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

# Extensions where we allow "try running" for small files
_RUNNABLE = {
    '.py':  'python3 "{path}"',
    '.sh':  'bash "{path}"',
    '.js':  'node "{path}"',
    '.c':   None,  # needs compile step, handled specially
    '.cpp': None,
}


def validate_file(file_path, run=False):
    """
    Checks a file for syntax errors using the appropriate language tool.
    If run=True AND the file is small (<100 lines), also executes it and returns output.
    For C/C++: compiles to a temp binary and runs it.
    Returns a report string.
    """
    try:
        expanded = expand_path(file_path)
        if not os.path.exists(expanded):
            return f"Error: File {file_path} does not exist."

        ext = os.path.splitext(expanded)[1].lower()
        report_parts = []

        # ── Syntax check ──
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
                # Don't try running if syntax check failed
                return "\n".join(report_parts)
        else:
            report_parts.append(f"SYNTAX CHECK: No validator available for '{ext}' files. Skipped.")

        # ── Optional execution ──
        if run:
            with open(expanded, 'r', encoding='utf-8') as f:
                line_count = sum(1 for _ in f)
            if line_count > 100:
                report_parts.append(f"RUN: Skipped — file has {line_count} lines (limit: 100).")
            else:
                run_cmd = _RUNNABLE.get(ext)
                # Special handling for C/C++
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
                        # Clean up temp binary for C/C++
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
