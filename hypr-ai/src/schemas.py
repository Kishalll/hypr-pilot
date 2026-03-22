# ─── Shared tools (available in both domains) ───────────────────────────────────

_TOOL_LIST_DIR = {
    "type": "function",
    "function": {
        "name": "list_directory",
        "description": "Lists files and folders in a specified directory path.",
        "parameters": {
            "type": "object",
            "properties": {
                "dir_path": {
                    "type": "string",
                    "description": "The path to the directory to list. Defaults to current directory if empty."
                }
            }
        }
    }
}

_TOOL_READ_FILE = {
    "type": "function",
    "function": {
        "name": "read_file",
        "description": "Reads and returns the content of a specified file.",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "The path to the file to read."
                }
            },
            "required": ["file_path"]
        }
    }
}

_TOOL_WRITE_FILE = {
    "type": "function",
    "function": {
        "name": "write_file",
        "description": "Creates or overwrites a file with new content. Use this to create new scripts, programs, or config files.",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "The path to the file to write."
                },
                "content": {
                    "type": "string",
                    "description": "The full content to write to the file."
                }
            },
            "required": ["file_path", "content"]
        }
    }
}

_TOOL_APPEND_FILE = {
    "type": "function",
    "function": {
        "name": "append_file",
        "description": "Appends new content to the end of an existing file without replacing the whole file.",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "The path to the file to append to."
                },
                "content": {
                    "type": "string",
                    "description": "The specific content to append."
                }
            },
            "required": ["file_path", "content"]
        }
    }
}

_TOOL_REPLACE_LINE = {
    "type": "function",
    "function": {
        "name": "replace_line",
        "description": "Replaces a specific existing line in a file with a new line. You must provide the exact old line content.",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "The path to the file."
                },
                "old_line": {
                    "type": "string",
                    "description": "The exact existing line to find and replace."
                },
                "new_line": {
                    "type": "string",
                    "description": "The corrected replacement line."
                }
            },
            "required": ["file_path", "old_line", "new_line"]
        }
    }
}

_TOOL_EXECUTE_CMD = {
    "type": "function",
    "function": {
        "name": "execute_command",
        "description": "Runs a shell command and returns its output. Useful for running programs, installing packages, or system operations.",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The bash command to execute."
                }
            },
            "required": ["command"]
        }
    }
}

# hyprland-only tools

_TOOL_GET_WINDOW_CLASS = {
    "type": "function",
    "function": {
        "name": "get_window_class",
        "description": "Finds the accurate window class name for an application (like 'org.pulseaudio.pavucontrol' for 'pavucontrol'). Always use this BEFORE adding a window rule.",
        "parameters": {
            "type": "object",
            "properties": {
                "app_name": {
                    "type": "string",
                    "description": "The common name of the app (e.g. 'pavucontrol', 'firefox')."
                }
            },
            "required": ["app_name"]
        }
    }
}

_TOOL_GET_CONFIG_PATHS = {
    "type": "function",
    "function": {
        "name": "get_active_config_paths",
        "description": "Returns the paths of the main hyprland.conf and any sourced configuration files where window rules should be stored. Use this instead of guessing file paths.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }
}

# coding-only tools

_TOOL_MAKE_DIR = {
    "type": "function",
    "function": {
        "name": "make_directory",
        "description": "Creates a directory (and parent directories) if it doesn't already exist.",
        "parameters": {
            "type": "object",
            "properties": {
                "dir_path": {
                    "type": "string",
                    "description": "The path to the directory to create."
                }
            },
            "required": ["dir_path"]
        }
    }
}

_TOOL_FILE_EXISTS = {
    "type": "function",
    "function": {
        "name": "file_exists",
        "description": "Checks whether a file or directory exists at the given path.",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "The path to check."
                }
            },
            "required": ["file_path"]
        }
    }
}

_TOOL_SEARCH_FILES = {
    "type": "function",
    "function": {
        "name": "search_in_files",
        "description": "Search for a text pattern in files under a directory. Returns matching lines with file paths and line numbers.",
        "parameters": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "The text pattern to search for."
                },
                "dir_path": {
                    "type": "string",
                    "description": "The directory to search in. Defaults to current directory."
                },
                "file_glob": {
                    "type": "string",
                    "description": "File pattern to filter (e.g. '*.py', '*.conf'). Defaults to all files."
                }
            },
            "required": ["pattern"]
        }
    }
}

_TOOL_INSERT_LINE = {
    "type": "function",
    "function": {
        "name": "insert_line",
        "description": "Inserts one or more lines at a specific line number (1-based) in a file. Existing lines shift down. Use this to add code at a precise location without rewriting the whole file.",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "The path to the file."
                },
                "line_number": {
                    "type": "integer",
                    "description": "The 1-based line number where the new content will be inserted."
                },
                "content": {
                    "type": "string",
                    "description": "The text to insert (can contain newlines for multiple lines)."
                }
            },
            "required": ["file_path", "line_number", "content"]
        }
    }
}

_TOOL_DELETE_LINES = {
    "type": "function",
    "function": {
        "name": "delete_lines",
        "description": "Deletes one or more lines from a file by line number (1-based). If end_line is omitted, only deletes the single start_line.",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "The path to the file."
                },
                "start_line": {
                    "type": "integer",
                    "description": "The 1-based first line to delete."
                },
                "end_line": {
                    "type": "integer",
                    "description": "The 1-based last line to delete (inclusive). If omitted, only start_line is deleted."
                }
            },
            "required": ["file_path", "start_line"]
        }
    }
}

_TOOL_VALIDATE_FILE = {
    "type": "function",
    "function": {
        "name": "validate_file",
        "description": "Checks a file for syntax errors using the appropriate language tool (python, gcc, node, bash, etc). If run=true and the file is small (<100 lines), also executes it and returns the output. Always call this after creating or modifying a code file.",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "The path to the file to validate."
                },
                "run": {
                    "type": "boolean",
                    "description": "If true, also execute the file after syntax check (only for small files). Default false."
                }
            },
            "required": ["file_path"]
        }
    }
}


# ─── Assembled tool sets ────────────────────────────────────────────────────────

# Shared tools used by both domains
_SHARED_TOOLS = [
    _TOOL_LIST_DIR,
    _TOOL_READ_FILE,
    _TOOL_WRITE_FILE,
    _TOOL_APPEND_FILE,
    _TOOL_REPLACE_LINE,
    _TOOL_EXECUTE_CMD,
    _TOOL_INSERT_LINE,
    _TOOL_DELETE_LINES,
    _TOOL_VALIDATE_FILE,
]

# hyprland gets the shared set + window class lookup + config path discovery
HYPRLAND_TOOLS = _SHARED_TOOLS + [
    _TOOL_GET_WINDOW_CLASS,
    _TOOL_GET_CONFIG_PATHS,
]

# coding gets the shared set + mkdir, file_exists, grep
CODING_TOOLS = _SHARED_TOOLS + [
    _TOOL_MAKE_DIR,
    _TOOL_FILE_EXISTS,
    _TOOL_SEARCH_FILES,
]

# full combined set (legacy / backward compat)
TOOLS = _SHARED_TOOLS + [
    _TOOL_GET_WINDOW_CLASS,
    _TOOL_GET_CONFIG_PATHS,
    _TOOL_MAKE_DIR,
    _TOOL_FILE_EXISTS,
    _TOOL_SEARCH_FILES,
]
