# Übergabe-Notiz — Stand Phase 2a

*Stand: 2026-06-02 abends. Für: Teampartner (übernimmt Phase 2b = RAG).*

## TL;DR
Der Agent ist von **einem** Agenten auf eine **Multi-Agent-Struktur** umgebaut
(Orchestrator + Recherche-Sub-Agent). Deine Aufgabe (RAG) hat eine fertig
vorbereitete Andockstelle — du musst nur eine Datei ausfüllen und im Orchestrator
zwei Zeilen aktivieren.

## Was jetzt drin ist (Phase 2a — W1, P2)
| Datei | Rolle |
|-------|-------|
| [app/agents/orchestrator.py](../app/agents/orchestrator.py) | **Manager-Agent**: versteht Anfrage, entscheidet Modus, ruft Tools/Sub-Agent auf, formuliert Antwort |
| [app/agents/recherche_agent.py](../app/agents/recherche_agent.py) | **Recherche-Sub-Agent** [W1]: eigener ReAct-Agent mit `web_search`, als Tool `recherche_rezepte` eingebunden (Kontext-Isolation) |
| [app/tools/web_search.py](../app/tools/web_search.py) | Tavily-Websuche (vom Sub-Agenten genutzt) |
| [app/tools/shopping_list.py](../app/tools/shopping_list.py) | `einkaufsliste_erstellen`: deterministisch, fehlende Zutaten |
| [main.py](../main.py) | CLI + sichtbarer TAO-Trace (beschriftet Tool vs. Sub-Agent) |
| [app/rag/retriever.py](../app/rag/retriever.py) | **Deine Andockstelle (Stub)** |

## Architektur in einem Satz
`Nutzer → Orchestrator → (Tool einkaufsliste | Sub-Agent recherche_rezepte → web_search)`.
Vollständiges Bild: [docs/phasenplan.md](phasenplan.md).

## Update 2026-06-03: alles außer RAG ist jetzt gebaut
Zusätzlich zu Phase 2a sind fertig (Code + Tests grün):
- **Vision** `app/tools/vision.py` — Foto → Zutaten via Groq-VLM (W2)
- **Agent-Service** `app/core/agent_service.py` — bündelt Vision+Orchestrator, sammelt TAO-Trace
- **Strukturiertes Logging** `app/core/logging_config.py` (W5)
- **FastAPI** `app/api/main.py` (+ `schemas.py`) — `/chat`, `/health`, Pydantic-Validierung (W6/W9/W11)
- **Streamlit-GUI** `streamlit_app.py` — Text/Foto/Modus/Filter + TAO-Anzeige
- **Tests** `tests/` (W8), **Docker** (W7), **CI** `.github/workflows/ci.yml` (W10)
- **Reflexionen** `docs/reflexion_*.md` (W12–14)

**Dein RAG-Slot ist unverändert** — Andockstelle + TODO unten gelten weiter.

## Starten / Ausprobieren
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt        # installiert auch streamlit/pytest/pillow
cp .env.example .env                   # GROQ_API_KEY + TAVILY_API_KEY eintragen

python main.py                         # A) CLI
# B) API + GUI:
uvicorn app.api.main:app --reload      #   Terminal 1
streamlit run streamlit_app.py         #   Terminal 2
pytest -q                              # Tests
```
Demo-Eingabe, die mehrere TAO-Schritte erzeugt (gut für P2):
> *„Ich habe Hähnchen, Reis und Zwiebeln zuhause. Schlag mir ein Rezept vor und
> sag mir, was ich für eine Variante mit Curry noch einkaufen muss."*

→ Orchestrator: Thought→Action (`recherche_rezepte`) → Observation → Thought→Action
(`einkaufsliste_erstellen`) → Observation → finale Antwort. Der Sub-Agent macht
intern zusätzlich seine eigenen Web-Such-Schritte.

## Deine Aufgabe: Phase 2b — RAG (W3 + W4)
Alles Nötige steht als TODO oben in [app/rag/retriever.py](../app/rag/retriever.py). Kurz:
1. Rezeptdaten ablegen (z. B. `app/rag/rezepte/*.md` oder `rezepte.json`).
2. Ingestion: Dokumente → Chunking → Embedding → Chroma-Index (`app/rag/chroma_db/`,
   schon in `.gitignore`).
3. `rezept_wissensbasis(anfrage)` implementieren: Top-k aus Chroma + Quelle zurückgeben.
4. In [orchestrator.py](../app/agents/orchestrator.py) die **zwei auskommentierten Zeilen**
   aktivieren (`from app.rag.retriever import get_rag_tool` + `get_rag_tool()` in `tools`).
   → Damit ist es **Agentic RAG (W4)**: der Agent entscheidet selbst, ob er die
   Wissensbasis oder die Websuche nutzt.
5. Mind. 1 Test ergänzen (zählt auf W8).

Empfohlen (kostenlos): `langchain-chroma` + lokales Embedding via
`langchain-huggingface` (SentenceTransformers). Beide Bibliotheken sind bereits in
`requirements.txt` vorgesehen (chromadb, langchain-chroma).

## Konventionen, damit wir den Überblick behalten
- **Ein Feature = ein Commit** (für P5: ≥10 Commits inkrementell).
- Jede neue Komponente bekommt einen Docstring mit *Warum* (nicht nur *Was*) —
  der Prof bewertet Sinnhaftigkeit, nicht Menge.
- Etwas wird nur eigener **Agent**, wenn Kontext-Isolation echten Mehrwert bringt;
  sonst **Tool**.
