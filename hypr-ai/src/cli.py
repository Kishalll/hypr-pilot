import sys
import time
from brain import HyprBrain

def main():
    print("Welcome to Hypr-AI - Local Hyprland Specialist")
    print("Type 'exit' to quit.")
    print("-" * 50)
    
    brain = None
    try:
        # Load heavy model during startup once
        print("Initializing Knowledge Base (Loading Embeddings)...", end="", flush=True)
        brain = HyprBrain()
        print(" Ready.")
    except Exception as e:
        print(f"\nError loading FAISS index: {e}")
        print("Run 'bash setup_index.sh' first!")
        sys.exit(1)

    while True:
        try:
            query = input("\nQuery > ")
        except (EOFError, KeyboardInterrupt):
            if brain: brain.unload()
            break
            
        if query.lower() in ["exit", "quit", "q"]:
            if brain: brain.unload()
            break
        
        if not query.strip():
            continue

        print("\nASSISTANT: ", end="", flush=True)
        
        # Stream the response
        for token in brain.generate_response(query):
            print(token, end="", flush=True)
        print() # Newline after finished response

if __name__ == "__main__":
    main()
