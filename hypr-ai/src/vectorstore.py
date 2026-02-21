import os
import json
import faiss
import numpy as np
import logging

# Suppress noisy model loading reports and library logs
os.environ['TRANSFORMERS_VERBOSITY'] = 'error'
os.environ['TRANSFORMERS_NO_ADVISORY_WARNINGS'] = '1'
os.environ['HF_HUB_DISABLE_SYMLINKS_WARNING'] = '1'

# Silencing logging from libraries
logging.getLogger("transformers").setLevel(logging.ERROR)
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
logging.getLogger("sentence_transformers").setLevel(logging.ERROR)

from sentence_transformers import SentenceTransformer
from transformers import logging as transformers_logging
transformers_logging.set_verbosity_error()

# Global disable for tqdm (to hide "Loading weights")
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
        
        # Convert to float32 for FAISS
        embeddings = np.array(embeddings).astype('float32')
        
        # Initialize FAISS IndexFlatL2
        dimension = embeddings.shape[1]
        self.index = faiss.IndexFlatL2(dimension)
        self.index.add(embeddings)
        
        # Save index
        faiss.write_index(self.index, INDEX_PATH)
        print(f"Index saved to {INDEX_PATH}")

    def load_index(self):
        self.index = faiss.read_index(INDEX_PATH)
        self.load_metadata()

    def search(self, query, k=5):
        if self.index is None:
            self.load_index()
        
        query_vector = self.model.encode([query]).astype('float32')
        distances, indices = self.index.search(query_vector, k)
        
        results = []
        for idx in indices[0]:
            if idx < len(self.metadata):
                results.append(self.metadata[idx])
        
        # Sort results by priority (Wiki first)
        results.sort(key=lambda x: x['priority'])
        return results

if __name__ == "__main__":
    store = HyprVectorStore()
    store.load_metadata()
    store.create_index()
