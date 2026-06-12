# RezeptAgent — RAG Setup Guide

## Projektstruktur (nach RAG-Integration)

```
RezeptAgent/
├── app/
│   ├── agents/
│   │   └── orchestrator.py      ← UPDATED: enthält jetzt rag_retriever als Tool
│   ├── tools/
│   │   └── web_search.py        ← unverändert
│   └── rag/
│       ├── __init__.py
│       ├── rag_setup.py         ← NEU: Ingestion (einmalig ausführen)
│       └── retriever.py         ← NEU: Query-Tool für LangGraph
├── data/
│   ├── recipes/                 ← NEU: deine Lieblingsrezepte als .md
│   │   ├── pasta_tomaten.md
│   │   ├── risotto_pilze.md
│   │   └── ...
│   └── chroma/                  ← AUTO: wird von rag_setup.py erstellt
├── main.py
└── requirements.txt
```

---

## Setup-Reihenfolge

### Schritt 1: Dependencies installieren

```bash
pip install chromadb sentence-transformers
```

Die restlichen (`langchain`, `langgraph`, `tavily`) hast du bereits.

### Schritt 2: `data/` Ordner anlegen

```bash
mkdir -p data/recipes
```

### Schritt 3: Deine Lieblingsrezepte hinzufügen

Lege jedes Rezept als eigene `.md` Datei in `data/recipes/` ab.
Das Format ist frei — je mehr Details, desto besser die Suchergebnisse.

**Empfohlenes Format (für gutes Retrieval):**
```markdown
# Rezeptname

**Zutaten (X Personen):**
- Zutat 1
- Zutat 2

**Zubereitung:**
1. Schritt 1
2. Schritt 2

**Zeit:** X Minuten | **Schwierigkeit:** Einfach/Mittel/Schwer
**Tags:** tag1, tag2, tag3, ...
```

Die **Tags** am Ende sind wichtig! Sie verbessern das semantische Retrieval erheblich.
Beispiel-Tags: `vegetarisch, vegan, schnell, pasta, suppe, sommer, winter, glutenfrei`

### Schritt 4: ChromaDB befüllen (einmalig)

```bash
python app/rag/rag_setup.py
```

Ausgabe sollte sein:
```
Lade Embedding-Modell: BAAI/bge-m3 ...
[✓] Eingelesen: pasta_tomaten.md
[✓] Eingelesen: risotto_pilze.md
...
[✓] 12 Rezepte erfolgreich in ChromaDB gespeichert!
```

### Schritt 5: Retriever testen (optional)

```bash
python app/rag/retriever.py
```

```
Suchanfrage: vegetarische Pasta
--- Rezept 1 (aus: pasta_tomaten.md) ---
# Pasta mit Tomatensauce
...
```

### Schritt 6: Agent starten

```bash
python main.py
```

```
Du: Zeig mir meine gespeicherten Pasta-Rezepte

[THOUGHT] Ich brauche das Tool: rag_retriever
[ACTION]  Aufruf mit: {'query': 'Pasta gespeicherte Rezepte'}
[OBSERVATION] Tool 'rag_retriever' geantwortet:
  --- Rezept 1 (aus: pasta_tomaten.md) ---
  # Pasta mit Tomatensauce ...

[ANSWER]  Ich habe folgendes Pasta-Rezept in deiner Sammlung gefunden: ...
```

---

## Neue Rezepte hinzufügen (UpdateDatabase-Äquivalent)

Wenn du neue Rezepte ergänzen willst, ohne die gesamte DB neu aufzubauen:

```python
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
```

---

## Warum ChromaDB? (Für deine README / W3-Nachweis)

**ChromaDB wurde gewählt weil:**
- **Lokal & persistent**: kein Cloud-Dienst nötig, kein API-Key, läuft auf jedem Rechner
- **Einfache Python-API**: `collection.add()`, `collection.query()` — du kennst es bereits
- **Kompatibel mit LangChain**: direkte Integration ohne Wrapper
- **Reproduzierbar**: `data/chroma/` kann ins Repository committed werden (klein, da nur Vektoren)
- **Alternativen wären**: Pinecone (Cloud, API-Key), FAISS (kein Persistieren out-of-the-box), Weaviate (komplex)

**BAAI/bge-m3 wurde gewählt weil:**
- **Multilingual**: versteht Deutsch und Englisch gleichzeitig
- **State-of-the-Art** für Dense Retrieval (MTEB Leaderboard Top-5)
- Du hast es bereits in deinen alten Projekten genutzt → kein neues Wissen nötig
- **Alternativ** wäre `text-embedding-3-small` von OpenAI (günstiger, aber API-abhängig)

---

## Anforderungsnachweis

| Anforderung | Nachweis |
|-------------|---------|
| **W3** — RAG-Komponente | `app/rag/rag_setup.py` befüllt ChromaDB mit Rezepten; `app/rag/retriever.py` durchsucht sie |
| **W4** — Agentic RAG | Agent in `orchestrator.py` entscheidet selbst wann `rag_retriever` vs `web_search` → Tool-Call im Log |
| **W5** — Observability | `[RAG] Bereit. X Rezepte` + TAO-Trace in `main.py` |
