import json
import requests
import re
import uuid
import os
from config import OLLAMA_URL, LLM_MODEL, AGENT_SYSTEM_PROMPT, CHAT_SYSTEM_PROMPT, DOMAIN_KEYWORDS
from vectorstore import HyprVectorStore
from schemas import TOOLS
import tools
import ui

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
        # Display the clean tool action box
        ui.tool_action(name, args)

        # For write/append, intercept hallucinated paths before confirming
        if name in ("write_file", "append_file"):
            target_path = tools.expand_path(args.get('file_path'))
            if not os.path.exists(target_path):
                ui.tool_result_error(f"Path does not exist: {target_path}")
                import glob
                base_hypr = tools.expand_path("~/.config/hypr")
                conf_files = glob.glob(f"{base_hypr}/**/*.conf", recursive=True)
                suggestions = "\n".join(conf_files) if conf_files else "No .conf files found in ~/.config/hypr"
                return f"Action denied: The file '{target_path}' does not exist.\n\nActual config files in ~/.config/hypr:\n{suggestions}\n\nPlease check `~/.config/hypr/hyprland.conf` to see which are `source`d for windowrules."

        # Confirm destructive actions
        if name in ("write_file", "append_file", "execute_command"):
            choice = ui.confirm_action(name, args)
            if choice == 'a':
                ui.tool_result_aborted()
                return "ABORT_QUERY"
            elif choice != 'y':
                ui.tool_result_denied("Skipped by user.")
                return "User denied execution."

        # Execute the tool
        func = getattr(tools, name, None)
        if func:
            try:
                result = func(**args)
                ui.tool_result_success()
                return result
            except Exception as e:
                ui.tool_result_error(str(e))
                return f"Error: {e}"
        ui.tool_result_error(f"Tool '{name}' not found.")
        return f"Error: Tool '{name}' not found."

    def _try_parse_json(self, json_str):
        r"""Parse JSON with fallback for invalid escape sequences (e.g. \. in regex)."""
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            # Fix invalid escapes: \. \( \) \^ \$ etc. that LLMs put in regex patterns
            fixed = re.sub(r'\\(?!["\\\\bfnrtu/])', r'\\\\', json_str)
            try:
                return json.loads(fixed)
            except json.JSONDecodeError:
                return None

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
                data = self._try_parse_json(json_str)
                if data and "name" in data and "arguments" in data:
                    tool_calls.append({"id": f"call_{uuid.uuid4().hex[:8]}", "type": "function", "function": data})
                    # FORCE SINGLE EXECUTION: truncate hallucinated trailing tool calls
                    return tool_calls, text[:end+1]
                start_idx = end + 1
            else:
                break
                
        return tool_calls, text

    def generate_response(self, query):
        context_str = ""
        is_agent_mode = True # Always stay in agent mode for now to ensure autonomy
        ui.reset_steps()  # Reset step counter for each new query

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

            # Show spinner while waiting for the LLM
            spinner = ui.Spinner("Thinking")
            spinner.start()
            try:
                response = requests.post(OLLAMA_URL, json=payload, timeout=120)
                response.raise_for_status()
                spinner.stop()
                result = response.json()
                message = result.get("message", {})
                content = message.get("content", "")
                tool_calls = message.get("tool_calls", [])

                # Aggressive tool call extraction from text
                text_tool_calls, cleaned_content = self.parse_tool_calls_from_text(content)
                if text_tool_calls:
                    tool_calls.extend(text_tool_calls)
                    # Don't show raw JSON tool calls to the user
                    content = ""

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

                    # No more inline [Tool: ...] text — ui.tool_action handles display
                    tool_result = self.call_local_tool(func_name, func_args)
                    
                    if tool_result == "ABORT_QUERY":
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
                spinner.stop()
                error_msg = f"System Error: {e}"
                yield f"\n{error_msg}"
                messages.append({"role": "user", "content": error_msg})
                # We don't break immediately, let the loop try to recover on the next iteration
                continue

    def unload(self):
        try: requests.post(OLLAMA_URL, json={"model": LLM_MODEL, "keep_alive": 0}, timeout=2)
        except: pass
