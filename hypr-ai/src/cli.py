import sys
import time
from brain import HyprBrain

def main():
    print("Hey there! Welcome to Hypr-Pilot.")
    print("I'm here to help with Hyprland configs and programming questions.")
    print("Just type 'exit' or 'quit' when you're done.")
    print("-" * 50)
    
    brain = None
    try:
        # Load heavy model during startup once
        print("Loading my knowledge base...", end="", flush=True)
        brain = HyprBrain()
        print(" done!")
    except Exception as e:
        print(f"\nOops, I couldn't load the index: {e}")
        print("Please run 'bash setup_index.sh' first!")
        sys.exit(1)

    while True:
        try:
            query = input("\nYou > ")
        except (EOFError, KeyboardInterrupt):
            if brain: brain.unload()
            break
            
        if query.lower() in ["exit", "quit", "q"]:
            if brain: brain.unload()
            break
        
        if not query.strip():
            continue

        print("\nHypr-AI: ", end="", flush=True)
        
        # Stream the response
        for token in brain.generate_response(query):
            print(token, end="", flush=True)
        print() # Newline after finished response

if __name__ == "__main__":
    main()
