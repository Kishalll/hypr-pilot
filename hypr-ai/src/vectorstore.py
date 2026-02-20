import json
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
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
