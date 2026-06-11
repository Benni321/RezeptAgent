"""
RAG Retriever Tool für RezeptAgent
====================================
Dieser Retriever läuft zur Laufzeit (Query-Phase).
Er ist als LangGraph @tool registriert, damit der Orchestrator
selbst entscheiden kann, WANN er die lokale Wissensbasis nutzt.

Das ist AGENTIC RAG (W4): der Agent steuert den Retrieval-Schritt
selbst als Tool – er ist NICHT hartcodiert.

Hinweis zu deinem alten Code:
- Du hast in Query.py bereits ChromaDB + BAAI/bge-m3 + CrossEncoder benutzt
- Hier wird das genau so weiterverwendet, nur als LangGraph-Tool verpackt
"""

import chromadb
from langchain_core.tools import tool
from sentence_transformers import SentenceTransformer, CrossEncoder


# ─── Konfiguration (muss mit rag_setup.py übereinstimmen!) ───────────────────

CHROMA_PATH     = "data/chroma"
COLLECTION_NAME = "rezepte"
EMBEDDING_MODEL = "BAAI/bge-m3"          # Dasselbe wie beim Setup!
TOP_K_RETRIEVAL = 1                      # Wie viele Treffer aus ChromaDB holen


# ─── Modelle & DB (einmal laden, dann wiederverwenden) ────────────────────────
# Lazy loading: wird nur initialisiert wenn das Tool wirklich aufgerufen wird

_embedding_model = None
_reranker_model  = None
_chroma_client   = None
_collection      = None


def _get_resources():
    """Initialisiert Modelle und DB beim ersten Aufruf (Lazy Loading)."""
    global _embedding_model, _reranker_model, _chroma_client, _collection

    if _collection is None:
        print("[RAG] Lade Embedding-Modell und ChromaDB...")
        _embedding_model = SentenceTransformer(EMBEDDING_MODEL)
        _reranker_model  = CrossEncoder(RERANKER_MODEL)
        _chroma_client   = chromadb.PersistentClient(path=CHROMA_PATH)
        _collection      = _chroma_client.get_collection(name=COLLECTION_NAME)
        print(f"[RAG] Bereit. {_collection.count()} Rezepte in der Wissensbasis.")

    return _embedding_model, _reranker_model, _collection


# ─── LangGraph Tool ───────────────────────────────────────────────────────────

@tool
def rag_retriever(query: str) -> str:
    """
    Sucht in der lokalen Rezept-Wissensbasis nach passenden Rezepten.
    Nutze dieses Tool wenn der Nutzer nach Lieblingsrezepten fragt
    oder nach gespeicherten/eigenen Rezepten sucht.
    Gibt die Top-1 relevantesten Rezepte als Text zurück.
    """
    try:
        embedding_model, reranker, collection = _get_resources()

        # 1. Query embedden (genauso wie in deinem alten Query.py!)
        query_embedding = embedding_model.encode(query)

        # 2. ChromaDB-Suche (Vektor-Ähnlichkeit)
        results = collection.query(
            query_embeddings=query_embedding,
            n_results=TOP_K_RETRIEVAL,
        )

        if not results["ids"] or results["ids"] == [[]]:
            return "Keine passenden Rezepte in der lokalen Wissensbasis gefunden."

        # 3. Reranking (CrossEncoder – genau wie in deinem Query.py!)
        treffer = list(zip(
            results["ids"][0],
            results["metadatas"][0],
            results["documents"][0],
        ))
        paare    = [(query, doc) for (_, _, doc) in treffer]
        scores   = reranker.predict(paare)

        gerankt = sorted(
            [(doc_id, meta, text, score)
             for (doc_id, meta, text), score in zip(treffer, scores)],
            key=lambda x: x[3],
            reverse=True,
        )

        # 4. Top-K Ergebnisse als Text zusammenbauen
        top_rezepte = gerankt[:TOP_K_FINAL]
        ausgabe_teile = []
        for i, (doc_id, meta, text, score) in enumerate(top_rezepte, 1):
            dateiname = meta.get("filename", "Unbekannt")
            ausgabe_teile.append(
                f"--- Rezept {i} (aus: {dateiname}) ---\n{text}"
            )

        return "\n\n".join(ausgabe_teile)

    except Exception as e:
        return f"Fehler beim Abrufen der Wissensbasis: {str(e)}"


# ─── Zum direkten Testen des Tools (python app/rag/retriever.py) ──────────────

if __name__ == "__main__":
    print("RAG Retriever — Direkttest")
    print("=" * 50)
    while True:
        anfrage = input("\nSuchanfrage (oder 'exit'): ").strip()
        if anfrage.lower() in ("exit", "q"):
            break
        if not anfrage:
            continue
        ergebnis = rag_retriever.invoke({"query": anfrage})
        print("\n" + ergebnis)
