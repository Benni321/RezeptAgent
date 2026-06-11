# RezeptAgent

Ein KI-gestützter Rezept-Assistent auf Basis eines Multi-Agent-Systems.
Der Agent hilft Nutzern dabei, passende Rezepte zu finden — per Texteingabe oder Kühlschrank-Foto.

---

## Was kann das System?

- Rezepte per Texteingabe suchen (z. B. "Was kann ich mit Tomaten und Mozzarella kochen?")
- Kühlschrank-Foto hochladen → Zutaten erkennen → Rezept vorschlagen *(Phase 2)*
- Zwischen "nur vorhandene Zutaten" und "Einkaufsliste ergänzen" wählen *(Phase 2)*
- Rezepte aus einer lokalen Wissensbasis abrufen (RAG) *(Phase 2)*

## Architektur

```
Nutzer
  │
  ▼
Orchestrator-Agent (LangGraph ReAct)
  ├── recherche_rezepte      → Sub-Agent: Web-Rezeptrecherche (Tavily)   [W1]
  ├── einkaufsliste_erstellen → fehlende Zutaten → Einkaufsliste
  ├── rag_retriever          → lokale Rezept-Wissensbasis (Phase 2b)     [W3/W4]
  └── vision_tool            → Kühlschrank-Foto → Zutatenliste (Phase 2c) [W2]
```

Der Orchestrator ("Manager") delegiert die Web-Recherche an einen **eigenen
Sub-Agenten** (`recherche_rezepte`), der in isoliertem Kontext sucht und nur eine
kompakte Rezeptliste zurückgibt — so bleibt der Orchestrator-Kontext schlank
(Multi-Agent-Prinzip aus VL4).

Der Agent arbeitet im **TAO-Zyklus** (Thought → Action → Observation),
der vollständig im Terminal ausgegeben wird.

**Framework:** [LangGraph](https://github.com/langchain-ai/langgraph)
— gewählt wegen seiner nativen ReAct-Unterstützung, einfacher Tool-Integration
und guter Erweiterbarkeit für Multi-Agent-Setups.

## Setup

### 1. Abhängigkeiten installieren

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Umgebungsvariablen setzen

```bash
cp .env.example .env
# Dann .env öffnen und API-Keys eintragen:
# GROQ_API_KEY=gsk-...
# TAVILY_API_KEY=tvly-...
```

API-Keys besorgen (beide kostenlos):
- Groq: https://console.groq.com
- Tavily: https://tavily.com

### 3. Starten

**Variante A — Terminal (CLI):**
```bash
python main.py
```

**Variante B — API + grafische Oberfläche (empfohlen):**
```bash
uvicorn app.api.main:app --reload     # Terminal 1: Backend (http://localhost:8000)
streamlit run streamlit_app.py        # Terminal 2: GUI (http://localhost:8501)
```

**Variante C — alles containerisiert:**
```bash
docker compose up        # startet API (8000) + GUI (8501)
```

### Tests

```bash
pytest -q
```

## Beispiel

```
Du: Was kann ich mit Hähnchen, Zitrone und Knoblauch kochen?

[THOUGHT] Ich brauche das Tool: web_search
[ACTION]  Aufruf mit: {'query': 'Hähnchen Zitrone Knoblauch Rezept'}
[OBSERVATION] Tool 'web_search' geantwortet: ...

[ANSWER]  Hier ist ein passendes Rezept: Zitronenhähnchen mit Knoblauch ...
```

## Projektstruktur

```
RezeptAgent/
├── app/
│   ├── agents/
│   │   ├── orchestrator.py      # Manager-Agent (LangGraph ReAct)        [W1]
│   │   └── recherche_agent.py   # Recherche-Sub-Agent (Web)             [W1]
│   ├── tools/
│   │   ├── web_search.py        # Web-Suche via Tavily
│   │   ├── shopping_list.py     # Einkaufsliste (deterministisch)
│   │   └── vision.py            # Foto → Zutaten (Groq VLM)             [W2]
│   ├── core/
│   │   ├── agent_service.py     # zentrale Ausführung + TAO-Trace
│   │   └── logging_config.py    # strukturiertes JSON-Logging           [W5]
│   ├── api/
│   │   ├── main.py              # FastAPI: /chat, /health          [W6/W11]
│   │   └── schemas.py           # Pydantic-Validierung                  [W9]
│   └── rag/retriever.py         # RAG-Andockstelle (Phase 2b)        [W3/W4]
├── streamlit_app.py             # grafische Oberfläche (GUI)
├── tests/                       # Unit-/Integrationstests               [W8]
├── docs/                        # Plan, Matrix, Handover, Reflexionen
├── Dockerfile, docker-compose.yml                                       # [W7]
├── .github/workflows/ci.yml                                             # [W10]
├── main.py                      # CLI-Einstiegspunkt
└── requirements.txt
```

