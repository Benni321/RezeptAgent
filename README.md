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
  ├── rag_retriever          → lokale Wissensbasis (temporär aus · RAG_AKTIV) [W3/W4]
  ├── naehrwerte_schaetzen   → kcal/Makros pro Portion → Constraint-Check
  ├── portionen_skalieren    → Mengen exakt auf andere Portionszahl umrechnen
  └── vision_tool            → Kühlschrank-Foto → Zutatenliste (Phase 2c) [W2]

  Memory (Geschmacksprofil + Bewertungen) → als Kontext injiziert, nicht als Tool
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

## Designentscheidungen (warum, nicht nur was)

Wir dokumentieren hier *bewusst* die Begründung hinter jeder relevanten
Entscheidung — inklusive ihrer Grenzen. Ein System, das man nur beschreibt, ist
nicht dasselbe wie eines, das man durchdacht hat.

### Ausbau zum constraint-bewussten Planer

Statt viele lose Einzelfeatures anzuhängen, vertiefen wir gezielt *ein* Verhalten:
Der Agent soll **Vorgaben des Nutzers als Constraints behandeln**, gegen die er
prüft und bei Bedarf neu entscheidet — statt stur einen festen Ablauf zu fahren.
Erster Baustein dafür ist die Nährwert-Schätzung.

**`naehrwerte_schaetzen` — Nährwerte als Constraint, nicht als Deko.**
- *Warum überhaupt?* Nennt der Nutzer eine Kalorien-/Portionsvorgabe (z. B.
  „max 600 kcal pro Portion"), wird daraus eine **Bedingung**, die der Agent
  aktiv prüft: Passt das Rezept nicht, passt er es an oder sucht ein anderes.
  Genau dieses *situationsabhängige Reagieren* unterscheidet einen Agenten von
  einer festen Pipeline.
- *Warum LLM-Schätzung statt Datenbank?* Der Kursrahmen ist bewusst
  kostenlos/reproduzierbar (kein USDA-/OpenFoodFacts-Konto). Für eine grobe
  Planungs-Größenordnung genügt eine LLM-Schätzung.
- *Warum Tool und kein eigener Agent?* Die Schätzung ist ein abgeschlossener
  Einzelschritt ohne eigenen Mehrschritt-Loop → ein Tool reicht. Ein Sub-Agent
  wäre hier nur Fassade (siehe Grundsatz unten).
- **Ehrliche Grenze:** Die Werte sind *Näherungen*, nicht aus einer verifizierten
  Datenbank, und damit weder exakt noch allergen-/diät-sicher. Sie steuern die
  Planung grob — sie sind keine medizinische oder nährwertrechtliche Auskunft.
  Production-tauglich wäre erst eine Anbindung an eine geprüfte Nährwert-DB.

**`portionen_skalieren` — deterministisch, weil Rechnen kein LLM-Job ist.**
- *Warum überhaupt?* Nennt der Nutzer eine andere Personenzahl als das Rezept,
  rechnet dieses Tool die Mengen exakt um (Faktor = Ziel/Quelle).
- *Warum kein LLM?* Mengen-Arithmetik („375 g × 1,5") muss **exakt und
  reproduzierbar** sein — und genau da verrechnen sich LLMs zuverlässig. Reine
  Logik ist hier die sinnvolle Lösung (gleiche Begründung wie `shopping_list`).
  Im Prompt steht deshalb explizit: *„Rechne Mengen niemals selbst im Kopf."*
- **Ehrliche Grenze:** Nicht alles skaliert linear (Gewürze, Salz, Backtriebmittel).
  Wir skalieren nur die führende Mengenangabe und lassen mengenlose Zutaten
  („Salz nach Bedarf") unverändert — deckt den Normalfall, ersetzt kein Kochwissen.

**Memory (Profil + Bewertungen) — Kontext statt Tool, Standard statt Zwang.**
- *Warum überhaupt?* Beim ersten Start läuft eine kurze **Onboarding-Fragerunde**
  (Geschmacks-Tendenz + „was ist dir bei Gerichten wichtig?"). Das ergibt ein
  dauerhaftes Profil; dazu kommen die **Sterne-Bewertungen** als gelerntes Signal.
  Der Agent **reagiert dadurch unterschiedlich je nach Nutzer** (Memory, Dim 2/6).
- *Warum injiziert, nicht als Tool?* **Lesen = Kontext, Schreiben = Aktion.**
  Das dauerhafte Signal (Prioritäten + Bewertungen) wird in die Eingabe injiziert;
  ein Tool „lies das Profil deines eigenen Nutzers" wäre Pseudo-Agentik. Profil
  setzen und Bewerten sind reines Persistieren → deterministische API-Aktionen
  (`POST /praeferenzen`, `/bewertung`), kein Agenten-Tool.
- *Warum Fragerunde als Formular, nicht als Chat?* Ein strukturiertes Formular
  liefert **validierte, reproduzierbare** Profildaten (W9-Linie) und ist testbar.
  Ein LLM-geführtes Chat-Onboarding wäre „agentischer", aber fragil und als
  maschinenlesbarer Default schlecht nutzbar.
- *Warum JSON statt Datenbank?* Ein Nutzer, wenige Daten → eine transparente,
  versionierbare, testbare Datei (`data/praeferenzen.json`); ein DBMS wäre Overkill.
- **Ehrliche Grenze:** Cold-Start, Overfitting auf wenige Sterne, und der
  Rezept-Titel zum Bewerten wird heuristisch aus der Antwort abgeleitet (kein
  stabiler Schlüssel).

**Geschmack: Standard vs. Tagesform — der Kernpunkt.**
Geschmacksrichtung ist nicht rein dauerhaft (mal hat man Lust auf Süßes). Lösung
ohne Redundanz: Das Profil ist der **Standard**, die Pro-Rezept-Auswahl die
**Tagesform**. Dieselbe Geschmacks-Auswahl wird pro Anfrage aus dem Profil
**vorbelegt** und ist frei änderbar — wählt man nichts Eigenes, gilt das Profil.
Das Profil ist eine **weiche** Vorgabe; der Prompt fordert zusätzlich aktiv
**Abwechslung** ein („schlage nicht immer dasselbe vor").

**Eingabekanäle — getrennt nach Härte und Dauer.**
Die ursprüngliche Pro-Anfrage-Filterliste haben wir bewusst **entfernt**: Diätform
und Unverträglichkeiten sind *dauerhafte Eigenschaften der Person* (vegan = immer
vegan) und gehören damit ins **Onboarding-Profil als harte Dauer-Vorgabe**, nicht
in eine Liste, die man pro Rezept neu anklickt. Situatives („heute schnell") kommt
in den Freitext.

| Kanal | Art | Geltung | Beispiele |
|-------|-----|---------|-----------|
| **Ernährung/Unverträglichkeit** | **hart** (gilt immer) | **dauerhaft** (Profil) | vegan, glutenfrei, laktosefrei |
| **Sonstige Wünsche** (Freitext) | weich, frei | nur diese Anfrage | „wenig Fleisch", „heute schnell" |
| **Geschmacksrichtung** | weich (Standard aus Profil) | diese Anfrage, vorbelegt | scharf, mediterran, süßlich |
| **Profil: Prioritäten + Bewertungen** | weich (wird bevorzugt) | **dauerhaft** (Memory) | „gesund", gut bewertete Rezepte |

So hat jeder Kanal eine eigene, begründbare Rolle — und der Agent bekommt die
Information mit der passenden Verbindlichkeit (im Prompt: Ernährung „NIEMALS
verletzen" als oberste Regel, Geschmack/Profil „bevorzugen, aber für Abwechslung
sorgen").

**Grundsatz – Agent nur bei echtem Mehrwert:** Etwas wird nur dann ein eigener
(Sub-)Agent, wenn Kontext-Isolation echten Mehrwert bringt (wie bei
`recherche_rezepte`: Filtern des Such-„Rauschens"). Alles andere bleibt Tool.
Das hält die Architektur ehrlich statt aufgebläht.

### Bekannte Baustelle: RAG (temporär abgekoppelt)

Das RAG-Tool (`rag_retriever`) ist aktuell **standardmäßig deaktiviert**
(`RAG_AKTIV=false`). Bewusste Entscheidung, weil das Modul den normalen Ablauf
blockierte:
- Es lädt beim ersten Aufruf ein **2,27 GB großes Embedding-Modell** (`BAAI/bge-m3`)
  *im laufenden Request* → der GUI-Timeout (120 s) greift, bevor das Modell da ist
  („Backend nicht erreichbar"). Ein so großes Modell gehört einmalig **vorab**
  geladen, nicht in den Request.
- In `app/rag/retriever.py` sind zwei Namen **undefiniert** (`RERANKER_MODEL`,
  `TOP_K_FINAL`) → das Tool crasht selbst nach dem Download.
- Bei `TOP_K_RETRIEVAL = 1` ist der CrossEncoder-**Reranker sinnlos** (er sortiert
  ein einzelnes Ergebnis um) und lädt ein zweites Modell für nichts.

**Reaktivieren** (nach Fix durch das RAG-Team): `RAG_AKTIV=true` setzen — dann
hängt der Orchestrator das Tool wieder ein. Die schwere Importkette
(`sentence_transformers`) wird nur in diesem Fall geladen, sonst gar nicht.

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
uvicorn app.api.main:app --reload --reload-dir app   # Terminal 1: Backend (http://localhost:8000)
streamlit run streamlit_app.py                       # Terminal 2: GUI (http://localhost:8501)
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
│   │   ├── naehrwerte.py        # kcal/Makros pro Portion (Constraint-Check)
│   │   ├── skalierung.py        # Mengen exakt auf Portionszahl umrechnen
│   │   └── vision.py            # Foto → Zutaten (Groq VLM)             [W2]
│   ├── core/
│   │   ├── agent_service.py     # zentrale Ausführung + TAO-Trace
│   │   ├── praeferenzen.py      # Memory: Geschmacksprofil + Bewertungen
│   │   └── logging_config.py    # strukturiertes JSON-Logging           [W5]
│   ├── api/
│   │   ├── main.py              # FastAPI: /chat, /health, /praeferenzen, /bewertung [W6/W11]
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

