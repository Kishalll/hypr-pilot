import json
import requests
from config import OLLAMA_URL, LLM_MODEL, SYSTEM_PROMPT, CHAT_SYSTEM_PROMPT, DOMAIN_KEYWORDS
from vectorstore import HyprVectorStore

class HyprBrain:
    def __init__(self):
        self.store = HyprVectorStore()
        self.history = [] # Chat history buffer
        # Initialize index lazily or load it
        try:
            self.store.load_index()
        except:
            print("Warning: Index not loaded. Context unavailable.")

    def needs_context(self, query):
        """Check if the query is likely about Hyprland to fetch context."""
        query_lower = query.lower()
        
        # Check if any domain keyword is present
        for keyword in DOMAIN_KEYWORDS:
            if keyword in query_lower:
                return True
        
        # Heuristic: If last message was a Hyprland query and this is a short follow-up
        if self.history and len(query.split()) < 10:
            last_msg = self.history[-1]["content"].lower()
            if any(k in last_msg for k in DOMAIN_KEYWORDS):
                return True
                
        return False

    def generate_response(self, query):
        system_prompt = SYSTEM_PROMPT
        context_str = ""

        # Retrieve context if needed
        if self.needs_context(query):
            context_chunks = self.store.search(query, k=3)
            for i, chunk in enumerate(context_chunks):
                source_info = f"Source: {chunk['source']}"
                context_str += f"\n--- Context Block {i+1} ({source_info}) ---\n{chunk['content']}\n"
            
            # Augment the system prompt with context
            system_prompt = f"{SYSTEM_PROMPT}\n\nRELEVANT CONTEXT:\n{context_str}"
        else:
            system_prompt = CHAT_SYSTEM_PROMPT

        # Prepare messages for Chat API
        messages = [{"role": "system", "content": system_prompt}]
        # Add history (limit to last 10 messages to keep context window clean)
        messages.extend(self.history[-10:])
        # Add current user query
        messages.append({"role": "user", "content": query})

        # Call Ollama Chat API
        payload = {
            "model": LLM_MODEL,
            "messages": messages,
            "stream": True,
            "keep_alive": -1,
            "options": {
                "temperature": 0.3,
                "num_ctx": 4096
            }
        }

        full_response = ""
        try:
            response = requests.post(OLLAMA_URL, json=payload, timeout=120, stream=True)
            response.raise_for_status()
            for line in response.iter_lines():
                if line:
                    chunk = json.loads(line.decode('utf-8'))
                    message = chunk.get("message", {})
                    token = message.get("content", "")
                    if token:
                        full_response += token
                        yield token
                    if chunk.get("done", False):
                        break
            
            # Save to history after successful generation
            self.history.append({"role": "user", "content": query})
            self.history.append({"role": "assistant", "content": full_response})
            
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
