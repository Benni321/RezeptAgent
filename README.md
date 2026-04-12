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
  ├── web_search     → Rezeptsuche im Internet (Tavily)
  ├── vision_tool    → Kühlschrank-Foto → Zutatenliste (Phase 2)
  ├── rag_retriever  → Suche in lokaler Rezept-Wissensbasis (Phase 2)
  ├── filter_tool    → Rezepte nach Zutaten filtern (Phase 2)
  └── shopping_list  → Fehlende Zutaten → Einkaufsliste (Phase 2)
```

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
# OPENAI_API_KEY=sk-...
# TAVILY_API_KEY=tvly-...
```

API-Keys besorgen (beide kostenlos):
- Groq: https://console.groq.com
- Tavily: https://tavily.com

### 3. Agent starten

```bash
python main.py
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
│   ├── agents/orchestrator.py   # LangGraph ReAct Agent
│   ├── tools/web_search.py      # Web-Suche via Tavily
│   ├── rag/                     # RAG-Komponente (Phase 2)
│   └── api/                     # FastAPI Endpunkte (Phase 3)
├── tests/                       # Unit- und Integrationstests (Phase 3)
├── docs/
│   ├── evidence/                # TAO-Traces, Screenshots
│   ├── Abstract.md
│   ├── bewertungsmatrix.md
│   └── phasenplan.md
├── main.py                      # Einstiegspunkt
├── requirements.txt
└── .env.example
```

## Anforderungserfüllung

Siehe [docs/bewertungsmatrix.md](docs/bewertungsmatrix.md) für den vollständigen Überblick.
