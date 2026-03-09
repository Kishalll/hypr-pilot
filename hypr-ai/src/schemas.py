TOOLS = [
    {
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
    },
    {
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
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "Lists files and folders in a specified directory path. Useful for exploring the filesystem.",
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
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Reads and returns the content of a specified file. Use this to analyze configuration files.",
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
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Overwrites a file with new content. Use this to apply changes to dotfiles or create new scripts.",
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
    },
    {
        "type": "function",
        "function": {
            "name": "append_file",
            "description": "Appends new content to the end of an existing file. Use this for adding new rules or lines without replacing the whole file.",
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
    },
    {
        "type": "function",
        "function": {
            "name": "replace_line",
            "description": "Replaces a specific existing line in a file with a new line. Use this to fix broken or incorrect rules instead of appending duplicates. You must provide the exact old line content.",
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
    },
    {
        "type": "function",
        "function": {
            "name": "execute_command",
            "description": "Runs a shell command and returns its output. Useful for system operations like 'hyprctl reload'.",
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
]
