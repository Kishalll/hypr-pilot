import sys
import time
import os
import readline
from brain import HyprBrain, RequestContext
import ui

HISTORY_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".hypr_ai_history")


def handle_slash_command(query, brain):
    """Returns True if cmd was handled, False otherwise."""
    cmd = query.strip().lower()

    if cmd == "/help":
        ui.show_slash_help()
        return True
    elif cmd == "/agent":
        brain.set_override(mode=RequestContext.MODE_AGENT)
        ui.show_override_set("Agent mode (forced)")
        return True
    elif cmd == "/chat":
        brain.set_override(mode=RequestContext.MODE_ANSWER)
        ui.show_override_set("Answering mode (forced)")
        return True
    elif cmd == "/hypr":
        brain.set_override(domain=RequestContext.DOMAIN_HYPRLAND)
        ui.show_override_set("Hyprland domain (forced)")
        return True
    elif cmd == "/code":
        brain.set_override(domain=RequestContext.DOMAIN_CODING)
        ui.show_override_set("Coding domain (forced)")
        return True
    elif cmd == "/auto":
        brain.clear_overrides()
        ui.show_override_set("Auto-detection (default)")
        return True

    return False


def main():
    ui.welcome()

    # readline niceties
    readline.set_history_length(100)
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

        if query.strip().startswith("/"):
            if handle_slash_command(query, brain):
                continue

        response_started = False
        
        for token in brain.generate_response(query):
            # show header only before the first real text token
            if token.strip() and not response_started:
                ui.response_start()
                response_started = True
            if response_started:
                ui.response_token(token)

        if response_started:
            ui.response_end()

if __name__ == "__main__":
    main()
