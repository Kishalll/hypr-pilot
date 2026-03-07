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
            if len(content) > 3000:
                return content[:3000] + "\n\n...[FILE TRUNCATED FOR CONTEXT SIZE]..."
            return content
    except Exception as e:
        return f"Error reading file: {e}"

def write_file(file_path, content):
    """Writes or overwrites content to a file."""
    try:
        expanded_path = expand_path(file_path)
        # Ensure directory exists
        if os.path.dirname(expanded_path):
            os.makedirs(os.path.dirname(expanded_path), exist_ok=True)
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
    """Reads hyprland.conf to find where rules are sourced."""
    try:
        base_dir = expand_path("~/.config/hypr")
        path = os.path.join(base_dir, "hyprland.conf")
        if not os.path.exists(path):
            return "Error: ~/.config/hypr/hyprland.conf does not exist."
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        sources = re.findall(r'^\\s*source\\s*=\\s*(.+)', content, re.MULTILINE)
        res = f"Main Config: {path}\\n"
        if sources:
            res += "Sourced Files (WINDOW RULES usually go here!):\\n"
            for s in sources:
                # Resolve relative paths that don't start with / or ~
                s = s.strip()
                if s.startswith('~'):
                    s = expand_path(s)
                elif not s.startswith('/'):
                    s = os.path.join(base_dir, s)
                res += f"- {s}\\n"
        else:
            res += "No sourced files found. Rules must go directly in hyprland.conf."
        return res
    except Exception as e:
        return f"Error reading config: {e}"

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
