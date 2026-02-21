import json
import requests
from config import OLLAMA_URL, LLM_MODEL, SYSTEM_PROMPT, DOMAIN_KEYWORDS
from vectorstore import HyprVectorStore

class HyprBrain:
    def __init__(self):
        self.store = HyprVectorStore()
        # Initialize index lazily or load it
        try:
            self.store.load_index()
        except:
            print("Warning: Index not loaded. Context unavailable.")

    def needs_context(self, query):
        """Check if the query is likely about Hyprland to fetch context."""
        query_lower = query.lower()
        # Check if any domain keyword is present as a word or substring
        # Using a simple check for speed
        for keyword in DOMAIN_KEYWORDS:
            if keyword in query_lower:
                return True
        return False

    def generate_response(self, query):
        full_prompt = ""
        
        # Optimization: Only search vector store if query is relevant to Hyprland
        if self.needs_context(query):
            # Retrieve relevant context
            context_chunks = self.store.search(query, k=3) # Reduced k for speed
            
            # Build context string with priority info
            context_str = ""
            for i, chunk in enumerate(context_chunks):
                source_info = f"Source: {chunk['source']} (Priority {chunk['priority']})"
                context_str += f"\n--- Context Block {i+1} ({source_info}) ---\n{chunk['content']}\n"
            
            full_prompt = f"{SYSTEM_PROMPT}\n\nCONTEXT FROM DATASETS:\n{context_str}\n\nUSER QUERY: {query}\n\nASSISTANT RESPONSE:"
        else:
            # Skip context search for general questions (faster)
            full_prompt = f"{SYSTEM_PROMPT}\n\nUSER QUERY: {query}\n\nASSISTANT RESPONSE:"

        # Call Ollama
        payload = {
            "model": LLM_MODEL,
            "prompt": full_prompt,
            "stream": True,
            "keep_alive": -1, # Keep in RAM during session
            "options": {
                "temperature": 0.2,
                "num_ctx": 4096
            }
        }

        try:
            # Use stream=True to get chunks
            response = requests.post(OLLAMA_URL, json=payload, timeout=120, stream=True)
            response.raise_for_status()
            for line in response.iter_lines():
                if line:
                    chunk = json.loads(line.decode('utf-8'))
                    token = chunk.get("response", "")
                    if token:
                        yield token
                    if chunk.get("done", False):
                        break
        except Exception as e:
            yield f"\nError communicating with local LLM: {e}"

    def unload(self):
        """Unload the model from RAM."""
        payload = {
            "model": LLM_MODEL,
            "keep_alive": 0
        }
        try:
            # Short timeout, we don't care about the response
            requests.post(OLLAMA_URL, json=payload, timeout=2)
        except:
            pass

if __name__ == "__main__":
    brain = HyprBrain()
    print("Hypr-AI Brain Initialized.")
