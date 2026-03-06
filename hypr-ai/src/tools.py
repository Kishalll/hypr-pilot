import os
import subprocess

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
            return f.read()
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

def execute_command(command):
    """Runs a shell command and returns the output."""
    try:
        # Commands already handle ~ in shell=True, but we'll keep it consistent
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
        output = result.stdout if result.stdout else ""
        error = result.stderr if result.stderr else ""
        return f"STDOUT:\n{output}\nSTDERR:\n{error}"
    except Exception as e:
        return f"Error executing command: {e}"
