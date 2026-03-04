import sys
import time
import os
import readline
from brain import HyprBrain

# History file setup
HISTORY_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".hypr_ai_history")

def main():
    print("Hey there! Welcome to Hypr-Pilot.")
    print("I'm here to help with Hyprland configs and programming questions.")
    print("Just type 'exit' or 'quit' when you're done.")
    print("-" * 50)

    # Configure readline to handle history
    # This enables arrow key navigation through previous commands
    # and basic line editing features like Ctrl+A, Ctrl+E, etc.
    readline.set_history_length(100)
    
    # Add bindings for Ctrl+Backspace and Ctrl+Delete
    # Different terminals send different codes, so we add the most common ones
    readline.parse_and_bind(r'"\C-h": backward-kill-word')    # Common for Ctrl+Backspace
    readline.parse_and_bind(r'"\e[3;5~": kill-word')         # Common for Ctrl+Delete
    readline.parse_and_bind(r'"\e[1;5C": forward-word')      # Ctrl+Right
    readline.parse_and_bind(r'"\e[1;5D": backward-word')     # Ctrl+Left
    
    if os.path.exists(HISTORY_FILE):
        try:
            readline.read_history_file(HISTORY_FILE)
        except Exception:
            pass # Silent fail if history file is corrupted

    brain = None
    try:
        # Load heavy model during startup once
        brain = HyprBrain()
    except Exception as e:
        print(f"\nOops, I couldn't load the index: {e}")
        print("Please run 'bash setup_index.sh' first!")
        sys.exit(1)

    while True:
        try:
            query = input("\nYou > ")
        except (EOFError, KeyboardInterrupt):
            if brain: brain.unload()
            # Save history on exit
            try:
                readline.write_history_file(HISTORY_FILE)
            except Exception:
                pass
            break
            
        if query.lower() in ["exit", "quit", "q"]:
            if brain: brain.unload()
            # Save history on exit
            try:
                readline.write_history_file(HISTORY_FILE)
            except Exception:
                pass
            break
        
        if not query.strip():
            continue

        print("\nHypr-Pilot > ", end="", flush=True)
        
        # Stream the response
        for token in brain.generate_response(query):
            print(token, end="", flush=True)
        print() # Newline after finished response

if __name__ == "__main__":
    main()
