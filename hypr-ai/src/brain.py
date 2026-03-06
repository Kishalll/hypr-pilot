import json
import requests
import re
from config import OLLAMA_URL, LLM_MODEL, AGENT_SYSTEM_PROMPT, CHAT_SYSTEM_PROMPT, DOMAIN_KEYWORDS
from vectorstore import HyprVectorStore
from schemas import TOOLS
import tools

class HyprBrain:
    def __init__(self):
        self.store = HyprVectorStore()
        self.history = [] # Chat history buffer
        try:
            self.store.load_index()
        except:
            print("Warning: Index not loaded. Context unavailable.")

    def needs_context(self, query):
        """Check if the query is likely about Hyprland to fetch context."""
        query_lower = query.lower()
        for keyword in DOMAIN_KEYWORDS:
            if keyword in query_lower:
                return True
        if self.history and len(query.split()) < 10:
            last_msg = self.history[-1]["content"].lower()
            if any(k in last_msg for k in DOMAIN_KEYWORDS):
                return True
        return False

    def call_local_tool(self, name, args):
        """Executes a local tool function with a confirmation prompt for sensitive actions."""
        if name in ["write_file", "execute_command"]:
            print(f"\n⚡ [AGENT ACTION: {name}]")
            print(f"   Args: {args}")
            confirm = input("   Confirm execution? (y/n): ").strip().lower()
            if confirm != 'y':
                return "User denied execution."

        func = getattr(tools, name, None)
        if func:
            try:
                return func(**args)
            except Exception as e:
                return f"Error: {e}"
        return f"Error: Tool '{name}' not found."

    def parse_tool_calls_from_text(self, text):
        """Attempts to parse tool calls from a JSON code block in text if native tool calling failed."""
        import uuid
        json_match = re.search(r'```json\s*(\{.*?\})\s*```', text, re.DOTALL)
        if not json_match:
            json_match = re.search(r'(\{.*?\})', text, re.DOTALL)
        
        if json_match:
            try:
                data = json.loads(json_match.group(1))
                if "name" in data and "arguments" in data:
                    return [{"id": f"call_{uuid.uuid4().hex[:8]}", "type": "function", "function": data}]
            except:
                pass
        return []

    def generate_response(self, query):
        context_str = ""
        is_agent_mode = self.needs_context(query) or any(word in query.lower() for word in ["read", "write", "file", "run", "list"])

        if is_agent_mode:
            system_prompt = AGENT_SYSTEM_PROMPT
            if self.needs_context(query):
                context_chunks = self.store.search(query, k=3)
                for i, chunk in enumerate(context_chunks):
                    source_info = f"Source: {chunk['source']}"
                    context_str += f"\n--- RAG Context Block {i+1} ({source_info}) ---\n{chunk['content']}\n"
                system_prompt += f"\n\nRELEVANT RAG CONTEXT:\n{context_str}"
        else:
            system_prompt = CHAT_SYSTEM_PROMPT

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(self.history[-10:])
        messages.append({"role": "user", "content": query})

        max_iterations = 5
        for _ in range(max_iterations):
            payload = {
                "model": LLM_MODEL,
                "messages": messages,
                "tools": TOOLS if is_agent_mode else None,
                "stream": False,
                "keep_alive": -1,
                "options": {"temperature": 0.1, "num_ctx": 8192}
            }

            try:
                response = requests.post(OLLAMA_URL, json=payload, timeout=120)
                response.raise_for_status()
                result = response.json()
                message = result.get("message", {})
                content = message.get("content", "")
                tool_calls = message.get("tool_calls", [])

                # Fallback to parsing if needed
                if not tool_calls and is_agent_mode:
                    tool_calls = self.parse_tool_calls_from_text(content)
                    if tool_calls:
                        content = ""
                        # Sync the message object to include tool_calls for the model's history
                        message["tool_calls"] = tool_calls
                        message["content"] = None # IMPORTANT: Clear content to avoid model confusion

                if content:
                    yield content

                # Add assistant message to history
                messages.append(message)

                if not tool_calls:
                    self.history.append({"role": "user", "content": query})
                    self.history.append({"role": "assistant", "content": content})
                    break
                # Handle tool calls
                for tool_call in tool_calls:
                    func_name = tool_call["function"]["name"]
                    func_args = tool_call["function"]["arguments"]
                    call_id = tool_call.get("id", "call_default_id")

                    yield f" [Tool: {func_name}] "
                    tool_result = self.call_local_tool(func_name, func_args)

                    messages.append({
                        "role": "tool",
                        "content": str(tool_result),
                        "tool_call_id": call_id
                    })


            except Exception as e:
                yield f"\nError in Agent Loop: {e}"
                break

    def unload(self):
        payload = {"model": LLM_MODEL, "keep_alive": 0}
        try:
            requests.post(OLLAMA_URL, json=payload, timeout=2)
        except:
            pass
