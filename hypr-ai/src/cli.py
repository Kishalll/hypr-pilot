import sys
import time
import os
import readline
from brain import HyprBrain
import ui

# History file setup
HISTORY_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".hypr_ai_history")

def main():
    ui.welcome()

    # Configure readline to handle history
    readline.set_history_length(100)
    readline.parse_and_bind(r'"\C-h": backward-kill-word')
    readline.parse_and_bind(r'"\e[3;5~": kill-word')
    readline.parse_and_bind(r'"\e[1;5C": forward-word')
    readline.parse_and_bind(r'"\e[1;5D": backward-word')
    
    if os.path.exists(HISTORY_FILE):
        try:
            readline.read_history_file(HISTORY_FILE)
        except Exception:
            pass

    brain = None
    spinner = ui.Spinner("Loading model")
    spinner.start()
    try:
        brain = HyprBrain()
        spinner.stop()
    except Exception as e:
        spinner.stop()
        ui.tool_result_error(f"Couldn't load the index: {e}")
        print(f"  {ui.C.DIM}Run 'bash setup_index.sh' first!{ui.C.RESET}")
        sys.exit(1)

    while True:
        try:
            query = ui.prompt()
        except EOFError:
            if brain: brain.unload()
            try:
                readline.write_history_file(HISTORY_FILE)
            except Exception:
                pass
            print()
            break
            
        if query.lower() in ["exit", "quit", "q"]:
            if brain: brain.unload()
            try:
                readline.write_history_file(HISTORY_FILE)
            except Exception:
                pass
            break
        
        if not query.strip():
            continue

        # Spinner is managed inside brain.generate_response per LLM call
        response_started = False
        
        for token in brain.generate_response(query):
            # Only show response header before the first real text token
            if token.strip() and not response_started:
                ui.response_start()
                response_started = True
            if response_started:
                ui.response_token(token)

        if response_started:
            ui.response_end()

if __name__ == "__main__":
    main()
