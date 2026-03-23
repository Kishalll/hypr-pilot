import os
import re
import json
import hashlib
from glob import glob
from config import DATASETS_ROOT, METADATA_PATH

class HyprIngestor:
    def __init__(self):
        self.chunks = []
        self._seen_hashes = set()
        # lower number = more authoritative
        self.priority_map = {
            "hyprland-wiki": 1,
            "hyde": 2,
            "ill-imp": 2,
            "m4lw": 2
        }

    @staticmethod
    def is_junk_file(file_path):
        name = os.path.basename(file_path).lower()
        junk_suffixes = ("~", ".bak", ".orig", ".rej", ".tmp", ".swp")
        if name.startswith("."):
            return True
        if name.endswith(junk_suffixes):
            return True
        if ".~" in name or name.endswith(".disabled"):
            return True
        return False

    @staticmethod
    def normalize_hypr_syntax(text):
        # Normalize common legacy patterns to current docs without forcing specific effects.
        out = text.replace("windowrulev2", "windowrule")
        out = re.sub(r',\s*class:', ', match:class ', out)
        out = re.sub(r',\s*title:', ', match:title ', out)
        out = re.sub(r',\s*xwayland:', ', match:xwayland ', out)
        out = re.sub(r',\s*floating:', ', match:float ', out)
        out = re.sub(r',\s*fullscreen:', ', match:fullscreen ', out)
        out = re.sub(r',\s*workspace:', ', match:workspace ', out)
        return out

    @staticmethod
    def has_unwanted_legacy_syntax(text):
        lowered = text.lower()
        legacy_markers = [
            "windowrulev2",
            ",class:",
            ",title:",
            ",xwayland:",
            ",floating:",
            ",fullscreen:",
            ",workspace:",
        ]
        return any(m in lowered for m in legacy_markers)

    def add_chunk(self, chunk, source, priority, ext, dataset_name):
        content = chunk.strip()
        if len(content) < 20:
            return

        # Normalize syntax once globally.
        content = self.normalize_hypr_syntax(content)

        # For non-wiki community datasets, reject chunks still carrying legacy markers.
        if dataset_name.lower() != "hyprland-wiki" and self.has_unwanted_legacy_syntax(content):
            return

        key = hashlib.sha1(content.encode("utf-8", errors="ignore")).hexdigest()
        if key in self._seen_hashes:
            return
        self._seen_hashes.add(key)

        self.chunks.append({
            "content": content,
            "source": source,
            "priority": priority,
            "type": ext
        })

    def chunk_conf(self, content, source_path):
        """Split .conf into top-level blocks and standalone assignments."""
        blocks = re.findall(r'(\w+\s*\{[\s\S]*?^\})', content, re.MULTILINE)
        
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

            if self.is_junk_file(file_path):
                continue
            
            ext = os.path.splitext(file_path)[1]
            if ext not in (".conf", ".md"):
                continue
            # figure out which dataset this file belongs to
            parts = file_path.split("/")
            try:
                # structure: /path/to/datasets/dataset_name/...
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
                
                for chunk in file_chunks:
                    self.add_chunk(
                        chunk=chunk,
                        source=file_path.replace(DATASETS_ROOT, ""),
                        priority=priority,
                        ext=ext,
                        dataset_name=dataset_name,
                    )
            except Exception as e:
                print(f"Error processing {file_path}: {e}")

    def save_metadata(self):
        os.makedirs(os.path.dirname(METADATA_PATH), exist_ok=True)
        with open(METADATA_PATH, 'w') as f:
            json.dump(self.chunks, f, indent=2)
        print(f"Saved {len(self.chunks)} chunks to {METADATA_PATH}")

if __name__ == "__main__":
    ingestor = HyprIngestor()
    ingestor.process_files()
    ingestor.save_metadata()
