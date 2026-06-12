# app/rag/update_recipes.py
import chromadb
from sentence_transformers import SentenceTransformer

client = chromadb.PersistentClient(path="data/chroma")
collection = client.get_collection(name="rezepte")
model = SentenceTransformer("BAAI/bge-m3")

# Neues Rezept
neues_rezept = """
# Zitronenhähnchen

**Zutaten:** ...
**Tags:** hähnchen, zitrone, schnell, mediterran
"""

embedding = model.encode([neues_rezept])
collection.add(
    documents=[neues_rezept],
    embeddings=embedding,
    metadatas=[{"filename": "zitronenhaehnchen.md"}],
    ids=[f"rezept_{collection.count() + 1:04d}"],
)
print(f"Rezept hinzugefügt. Gesamt: {collection.count()}")
