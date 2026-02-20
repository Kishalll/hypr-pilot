import os
import re
import json
from glob import glob
from config import DATASETS_ROOT, METADATA_PATH

class HyprIngestor:
    def __init__(self):
        self.chunks = []
        # Priority mapping: lower is more authoritative
        self.priority_map = {
            "hyprland-wiki": 1,
            "hyde": 2,
            "ill-imp": 2,
            "m4lw": 2
        }

    def chunk_conf(self, content, source_path):
        """Split .conf by top-level blocks { ... } and standalone assignments."""
        # Capture blocks like input { ... }
        blocks = re.findall(r'(\w+\s*\{[\s\S]*?^\})', content, re.MULTILINE)
        
        # Capture top-level assignments outside blocks (simplified)
        standalone = re.findall(r'^(\w+\s*=\s*.*)$', content, re.MULTILINE)
        
        return blocks + standalone

    def chunk_md(self, content):
        """Split markdown by headers."""
        sections = re.split(r'^(#+\s+.*)$', content, flags=re.MULTILINE)
        chunks = []
        for i in range(1, len(sections), 2):
            header = sections[i]
            body = sections[i+1] if i+1 < len(sections) else ""
            chunks.append(f"{header}\n{body}")
        return chunks

    def process_files(self):
        print(f"Scanning {DATASETS_ROOT}...")
        all_files = glob(f"{DATASETS_ROOT}/**/*", recursive=True)
        
        for file_path in all_files:
            if os.path.isdir(file_path):
                continue
            
            ext = os.path.splitext(file_path)[1]
            # Adjust path splitting for local structure
            parts = file_path.split("/")
            try:
                # Assuming structure: /path/to/datasets/dataset_name/...
                idx = parts.index("datasets")
                dataset_name = parts[idx+1]
            except (ValueError, IndexError):
                dataset_name = "unknown"
                
            priority = self.priority_map.get(dataset_name.lower(), 3)
            
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                file_chunks = []
                if ext == ".conf":
                    file_chunks = self.chunk_conf(content, file_path)
                elif ext == ".md":
                    file_chunks = self.chunk_md(content)
                elif ext == ".sh":
                    # Simple line-block chunking for scripts
                    file_chunks = [content[i:i+500] for i in range(0, len(content), 500)]
                
                for chunk in file_chunks:
                    if len(chunk.strip()) < 20: continue
                    self.chunks.append({
                        "content": chunk.strip(),
                        "source": file_path.replace(DATASETS_ROOT, ""),
                        "priority": priority,
                        "type": ext
                    })
            except Exception as e:
                print(f"Error processing {file_path}: {e}")

    def save_metadata(self):
        with open(METADATA_PATH, 'w') as f:
            json.dump(self.chunks, f, indent=2)
        print(f"Saved {len(self.chunks)} chunks to {METADATA_PATH}")

if __name__ == "__main__":
    ingestor = HyprIngestor()
    ingestor.process_files()
    ingestor.save_metadata()
