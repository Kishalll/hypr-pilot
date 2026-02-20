import json
import requests
from config import OLLAMA_URL, LLM_MODEL, SYSTEM_PROMPT, WHITELIST_KEYWORDS
from vectorstore import HyprVectorStore

class HyprBrain:
    def __init__(self):
        self.store = HyprVectorStore()
        self.store.load_index()

    def is_domain_query(self, query):
        """Check if the query is within Hyprland domain."""
        query_lower = query.lower()
        return any(keyword in query_lower for keyword in WHITELIST_KEYWORDS)

    def generate_response(self, query):
        if not self.is_domain_query(query):
            yield "I am specialized only in Hyprland configuration. Please ask a Hyprland-related question."
            return

        # Retrieve relevant context
        context_chunks = self.store.search(query, k=5)
        
        # Build context string with priority info
        context_str = ""
        for i, chunk in enumerate(context_chunks):
            source_info = f"Source: {chunk['source']} (Priority {chunk['priority']})"
            context_str += f"\n--- Context Block {i+1} ({source_info}) ---\n{chunk['content']}\n"

        # Create full prompt
        full_prompt = f"{SYSTEM_PROMPT}\n\nCONTEXT FROM DATASETS:\n{context_str}\n\nUSER QUERY: {query}\n\nASSISTANT RESPONSE:"

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
