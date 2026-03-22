import os
import json
import faiss
import numpy as np
import logging

# shut up, libraries
os.environ['TRANSFORMERS_VERBOSITY'] = 'error'
os.environ['TRANSFORMERS_NO_ADVISORY_WARNINGS'] = '1'
os.environ['HF_HUB_DISABLE_SYMLINKS_WARNING'] = '1'


logging.getLogger("transformers").setLevel(logging.ERROR)
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
logging.getLogger("sentence_transformers").setLevel(logging.ERROR)

from sentence_transformers import SentenceTransformer
from transformers import logging as transformers_logging
transformers_logging.set_verbosity_error()

# kill tqdm progress bars (the "loading weights" noise)
from tqdm import tqdm
from functools import partialmethod
tqdm.__init__ = partialmethod(tqdm.__init__, disable=True)

from config import EMBED_MODEL, INDEX_PATH, METADATA_PATH

class HyprVectorStore:
    def __init__(self):
        self.model = SentenceTransformer(EMBED_MODEL)
        self.index = None
        self.metadata = []

    def load_metadata(self):
        with open(METADATA_PATH, 'r') as f:
            self.metadata = json.load(f)

    def create_index(self):
        print(f"Generating embeddings for {len(self.metadata)} chunks...")
        contents = [item['content'] for item in self.metadata]
        embeddings = self.model.encode(contents, show_progress_bar=True)
        
        embeddings = np.array(embeddings).astype('float32')
        
        dimension = embeddings.shape[1]
        self.index = faiss.IndexFlatL2(dimension)
        self.index.add(embeddings)
        
        faiss.write_index(self.index, INDEX_PATH)
        print(f"Index saved to {INDEX_PATH}")

    def load_index(self):
        try:
            self.index = faiss.read_index(INDEX_PATH)
            self.load_metadata()
            return True
        except Exception as e:
            print(f"Warning: Could not load index from {INDEX_PATH}: {e}")
            return False

    def search(self, query, k=5):
        if self.index is None:
            if not self.load_index():
                return []
        
        query_vector = self.model.encode([query]).astype('float32')
        distances, indices = self.index.search(query_vector, k)
        
        results = []
        for idx in indices[0]:
            if idx < len(self.metadata):
                results.append(self.metadata[idx])
        
        # wiki first, community dotfiles after
        results.sort(key=lambda x: x['priority'])
        return results

if __name__ == "__main__":
    store = HyprVectorStore()
    store.load_metadata()
    store.create_index()
