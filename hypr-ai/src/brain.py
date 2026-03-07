import json
import requests
import re
import uuid
import os
from config import OLLAMA_URL, LLM_MODEL, AGENT_SYSTEM_PROMPT, CHAT_SYSTEM_PROMPT, DOMAIN_KEYWORDS
from vectorstore import HyprVectorStore
from schemas import TOOLS
import tools

class HyprBrain:
    def __init__(self):
        self.store = HyprVectorStore()
        self.history = []
        try:
            self.store.load_index()
        except:
            print("Warning: Index not loaded.")

    def needs_context(self, query):
        query_lower = query.lower()
        for keyword in DOMAIN_KEYWORDS:
            if keyword in query_lower:
                return True
        return False

    def call_local_tool(self, name, args):
        print(f"\n🤖 [AGENT THOUGHT] -> Executing: {name}")
        
        if name == "read_file":
            print(f"   Reading file: {args.get('file_path')}")
        elif name == "list_directory":
            print(f"   Listing directory: {args.get('dir_path', '.')}")
        elif name in ["write_file", "append_file", "execute_command"]:
            if name in ["write_file", "append_file"]:
                # Intercept hallucinated paths
                target_path = tools.expand_path(args.get('file_path'))
                if not os.path.exists(target_path):
                    print(f"   ❌ REJECTED: The file path '{target_path}' does NOT exist. You hallucinated it.")
                    
                    # Search for actual conf files to suggest
                    import glob
                    base_hypr = tools.expand_path("~/.config/hypr")
                    conf_files = glob.glob(f"{base_hypr}/**/*.conf", recursive=True)
                    suggestions = "\n".join(conf_files) if conf_files else "No .conf files found in ~/.config/hypr"
                    
                    return f"Action denied: The file '{target_path}' does not exist.\n\nHere are the actual configuration files available in ~/.config/hypr:\n{suggestions}\n\nPlease check `~/.config/hypr/hyprland.conf` to see which of these are `source`d for windowrules."

            if name == "execute_command":
                print(f"   Running command: `{args.get('command')}`")
            elif name == "write_file":
                print(f"   ⚠️ WARNING: OVERWRITING file: {args.get('file_path')}")
                print(f"   --- Content to write ---\n{args.get('content')}\n   ------------------------")
            elif name == "append_file":
                print(f"   Appending to file: {args.get('file_path')}")
                print(f"   --- Content to append ---\n{args.get('content')}\n   -------------------------")
                
            confirm = input("   Confirm execution? (y/n/a): ").strip().lower()
            if confirm == 'a':
                print("   Action aborted by user.")
                return "ABORT_QUERY"
            elif confirm != 'y':
                print("   Action denied via user override.")
                return "User denied execution."

        func = getattr(tools, name, None)
        if func:
            try:
                return func(**args)
            except Exception as e:
                return f"Error: {e}"
        return f"Error: Tool '{name}' not found."

    def parse_tool_calls_from_text(self, text):
        """Finds any JSON-like tool call structure in the text robustly using bracket matching."""
        if not text: return [], text
        
        tool_calls = []
        start_idx = 0
        while True:
            # Find the first opening brace
            start = text.find('{', start_idx)
            if start == -1:
                break
                
            # Count braces to find the matching closing brace
            brace_count = 0
            end = -1
            for i in range(start, len(text)):
                if text[i] == '{':
                    brace_count += 1
                elif text[i] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        end = i
                        break
            
            if end != -1:
                json_str = text[start:end+1]
                try:
                    data = json.loads(json_str)
                    if "name" in data and "arguments" in data:
                        tool_calls.append({"id": f"call_{uuid.uuid4().hex[:8]}", "type": "function", "function": data})
                        # FORCE SINGLE EXECUTION: truncate hallucinated trailing tool calls
                        return tool_calls, text[:end+1]
                except json.JSONDecodeError:
                    pass
                start_idx = end + 1
            else:
                break
                
        return tool_calls, text

    def generate_response(self, query):
        context_str = ""
        is_agent_mode = True # Always stay in agent mode for now to ensure autonomy

        # Base system prompt that doesn't get mutated permanently
        base_system_prompt = AGENT_SYSTEM_PROMPT
        
        # Inject RAG context dynamically for THIS turn only
        if self.needs_context(query):
            context_chunks = self.store.search(query, k=3)
            if context_chunks:
                for i, chunk in enumerate(context_chunks):
                    source_info = f"Source: {chunk['source']}"
                    context_str += f"\n--- Reference Example {i+1} ({source_info}) ---\n{chunk['content']}\n"
                
                # We prepend it to the current query as a system instruction
                query = f"[SYSTEM: Here is relevant context. Use it if applicable to answer the user query.]\n{context_str}\n\n[USER QUERY]: {query}"

        messages = [{"role": "system", "content": base_system_prompt}]
        messages.extend(self.history[-10:])
        
        # Enforce rules at the end of the user prompt so RAG or history doesn't override them
        query += "\n\n[CRITICAL REMINDER]: 1. MUST use get_window_class tool first. 2. MUST use get_active_config_paths tool first to find rules file. 3. MUST use single-line syntax: windowrule = match:class ^(exact_class)$, tile on. 4. If chatting, write plaintext NOT {}."
        
        messages.append({"role": "user", "content": query})

        max_iterations = 10 # More turns for complex tasks
        for _ in range(max_iterations):
            payload = {
                "model": LLM_MODEL,
                "messages": messages,
                "tools": TOOLS,
                "stream": False,
                "options": {"temperature": 0.0, "num_ctx": 4096} # Kept slightly lower to avoid hardware-level timeouts on long contexts
            }

            try:
                response = requests.post(OLLAMA_URL, json=payload, timeout=120)
                response.raise_for_status()
                result = response.json()
                message = result.get("message", {})
                content = message.get("content", "")
                tool_calls = message.get("tool_calls", [])

                # Aggressive tool call extraction from text
                text_tool_calls, cleaned_content = self.parse_tool_calls_from_text(content)
                if text_tool_calls:
                    tool_calls.extend(text_tool_calls)
                    content = cleaned_content

                if content:
                    yield content

                # Record the assistant message
                message["content"] = content if content else None
                message["tool_calls"] = tool_calls if tool_calls else None
                messages.append(message)

                if not tool_calls:
                    self.history.append({"role": "user", "content": query})
                    self.history.append({"role": "assistant", "content": content})
                    break
                
                abort_all = False
                for tool_call in tool_calls:
                    func_name = tool_call["function"]["name"]
                    func_args = tool_call["function"]["arguments"]
                    call_id = tool_call.get("id", f"call_{uuid.uuid4().hex[:8]}")

                    yield f" [Tool: {func_name}] "
                    tool_result = self.call_local_tool(func_name, func_args)
                    
                    if tool_result == "ABORT_QUERY":
                        yield "\n[Query Aborted by User.]\n"
                        abort_all = True
                        break

                    messages.append({
                        "role": "tool",
                        "content": str(tool_result),
                        "tool_call_id": call_id
                    })
                    
                    # FORCE SEQUENTIAL EXECUTION: Evaluate one tool, then let the LLM see the result
                    break 
                    
                if abort_all:
                    break

            except Exception as e:
                error_msg = f"System Error: {e}"
                yield f"\n{error_msg}"
                messages.append({"role": "user", "content": error_msg})
                # We don't break immediately, let the loop try to recover on the next iteration
                continue

    def unload(self):
        try: requests.post(OLLAMA_URL, json={"model": LLM_MODEL, "keep_alive": 0}, timeout=2)
        except: pass
