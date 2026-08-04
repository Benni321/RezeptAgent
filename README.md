# RezeptAgent

Ein KI-gestützter Rezept-Assistent auf Basis eines Multi-Agent-Systems.
Der Agent hilft Nutzern dabei, passende Rezepte zu finden — per Texteingabe oder
Kühlschrank-Foto — und behandelt Nutzer-Vorgaben (kcal-Limit, Personenzahl,
vegan/glutenfrei) als **Constraints**, gegen die er prüft und bei Bedarf neu
entscheidet.

> **Ausführliche Doku:** Architektur mit allen Designentscheidungen (warum, welche
> Alternativen, ehrliche Grenzen), Funktionsweise am echten Trace und
> Konzept→Kurs-Mapping stehen in **[docs/PROJEKTDOKU.md](docs/PROJEKTDOKU.md)**.
> Anforderungs-Nachweis: [docs/bewertungsmatrix.md](docs/bewertungsmatrix.md).

## Was kann das System?

- Rezepte per Texteingabe suchen (Web-Recherche über einen eigenen Sub-Agenten)
- Kühlschrank-Foto hochladen → Zutaten erkennen → Rezept vorschlagen
- Zwischen „nur vorhandene Zutaten" und „Einkaufsliste ergänzen" wählen
- Kalorien-Vorgaben prüfen (`naehrwerte_schaetzen`) und Mengen exakt auf die
  Personenzahl umrechnen (`portionen_skalieren`)
- Wochenplan: mehrere Gerichte mit garantierter `plan→prüfe→revidiere`-Schleife
  und einer gemeinsamen Einkaufsliste — speicherbar und später wieder abrufbar
- Wochenplan **ohne Agenten**: Gerichte selbst aus dem Kochbuch wählen, angeben
  was zuhause ist → Einkaufsliste sofort, ganz ohne LLM-Aufruf (0 Tokens)
- Persönliches Kochbuch (RAG): gut bewertete Rezepte (≥ 4 Sterne) werden
  Wissensbasis und bei Bezug auf Bewährtes zuerst durchsucht; eigene Rezepte
  lassen sich manuell anlegen und wieder löschen
- Memory: Onboarding-Profil (harte Ernährungs-Vorgaben, weiche Vorlieben) +
  Sterne-Bewertungen
- Mehrseiten-GUI: Rezept finden · Mein Kochbuch · Meine Wochenpläne · Mein Profil

## Architektur

```
Nutzer  (Text / Kühlschrank-Foto)
  │        Foto → vision_tool → Zutatenliste (Groq-VLM) [W2]
  ▼
agent_service  ──►  Wochenplan-Anfrage (mehrere Gerichte)?
  │                   │ ja
  │                   ▼
  │            Wochenplan-Workflow (code-orchestriert)
  │              pro Gericht: recherche_rezepte → kcal-Check → ggf. Revision
  │              danach: wochenplan_zusammenstellen → eine Einkaufsliste
  │ nein (Einzelrezept)
  ▼
Orchestrator-Agent (LangGraph ReAct, voll agentisch)
  ├── recherche_rezepte      → Sub-Agent: Web-Rezeptrecherche (Tavily)   [W1]
  ├── rag_retriever          → persönliches Kochbuch (BM25, gelernt aus
  │                            4+-Sterne-Bewertungen + Seeds)            [W3/W4]
  ├── einkaufsliste_erstellen → fehlende Zutaten → Einkaufsliste
  ├── naehrwerte_schaetzen   → kcal/Makros pro Portion → Constraint-Check
  └── portionen_skalieren    → Mengen exakt auf andere Portionszahl umrechnen

  Memory (Geschmacksprofil + Bewertungen) → als Kontext injiziert, nicht als Tool
  Bewertung ≥ 4 Sterne → Rezept wandert in data/rezepte/ (Kochbuch-Wissensbasis)
```

**Zwei Verarbeitungswege, bewusst getrennt:** Einzelrezept-Anfragen bearbeitet der
**voll agentische** Orchestrator (situationsabhängige Tool-Wahl im TAO-Zyklus,
sichtbar in Terminal/GUI). **Wochenpläne** laufen über einen
**code-orchestrierten Workflow**, weil Modelle die Mehrschritt-Koordination nicht
zuverlässig per Prompt befolgen — eine bewusste Korrektur nach einem gescheiterten
voll-agentischen Ansatz (ausführlich:
[PROJEKTDOKU § Wochenplan-Workflow](docs/PROJEKTDOKU.md#24-wochenplan-workflow--bewusste-korrektur-nach-gescheitertem-ansatz)).
Die Web-Recherche ist an einen **eigenen Sub-Agenten** delegiert, der in
isoliertem Kontext sucht und nur eine kompakte Rezeptliste zurückgibt
(Kontext-Isolation, VL4).

**Framework:** [LangGraph](https://github.com/langchain-ai/langgraph) — gewählt
wegen nativer ReAct-Unterstützung, einfacher Tool-Integration und guter
Erweiterbarkeit für Multi-Agent-Setups.

**Modelle (bewusster Split):** Orchestrator, Wochenplan-Workflow und die
Recherche laufen auf Groq `qwen/qwen3.6-27b` (`GROQ_MODEL`) — multimodal, deckt
also auch die Bilderkennung ab. Die **Nährwert-Schätzung** nutzt dagegen das
kleine `llama-3.1-8b-instant` (`GROQ_MODEL_KLEIN`): ein Prompt, ein JSON, kein
Tool-Calling — und **Groqs Rate-Limits gelten pro Modell**, der Split entlastet
also das Budget des Hauptmodells. Dass der Recherche-Sub-Agent *nicht* auf dem
kleinen Modell läuft, ist ein gemessenes Ergebnis, kein Versehen (A/B-Vergleich
in [PROJEKTDOKU § 2.2](docs/PROJEKTDOKU.md#22-orchestrator-langgraph-react--framework--und-modellwahl)). Die Modellwahl selbst ist
erarbeitet, nicht geraten: `llama-3.3-70b` erzeugte auf Groq ein defektes
Tool-Call-Format, `gpt-oss-120b` war für den Wochenplan zu langsam, und das
zuvor genutzte `qwen/qwen3-32b` hat Groq im Juli 2026 zurückgezogen
(Modell-Drift, siehe [reflexion_drift](docs/reflexion_drift.md)). Details:
[PROJEKTDOKU § 2.2](docs/PROJEKTDOKU.md#22-orchestrator-langgraph-react--framework--und-modellwahl).

## Designentscheidungen — wo sie stehen

Jede relevante Entscheidung ist mit *Warum*, erwogenen Alternativen und ehrlichen
Grenzen dokumentiert — zentral in der
[PROJEKTDOKU](docs/PROJEKTDOKU.md#2-architektur):

| Thema | Kurzfassung | Ausführlich |
|-------|-------------|-------------|
| Wochenplaner als Workflow | Code steuert die Schleife, LLM entscheidet Inhalte („Workflow für die Struktur, Agent für den Inhalt") | [§ 2.4](docs/PROJEKTDOKU.md#24-wochenplan-workflow--bewusste-korrektur-nach-gescheitertem-ansatz) |
| Tools deterministisch vs. LLM | Rechnen/Aggregieren im Code, Schätzen/Formulieren im LLM | [§ 2.5](docs/PROJEKTDOKU.md#25-die-tools--und-warum-jedes-seine-form-hat) |
| Kochbuch-RAG | eigene bewährte Rezepte als Wissensbasis; BM25 statt Embeddings | [§ 2.6](docs/PROJEKTDOKU.md#26-kochbuch-rag--die-wissensbasis-die-der-agent-sich-selbst-kocht-w3w4) |
| Memory | Lesen = Kontext, Schreiben = deterministische API-Aktion | [§ 2.7](docs/PROJEKTDOKU.md#27-memory-profil--bewertungen--kontext-statt-tool) |
| Sicherheit (VL03) | minimale Angriffsfläche statt Prompt-Vertrauen | [docs/sicherheit.md](docs/sicherheit.md) |
| Observability | trace_id + Spans, OTel-angelehnt | [§ 2.9](docs/PROJEKTDOKU.md#29-observability-traces--spans-statt-loser-log-zeilen-w5-vl09) |
| Evaluation (VL09) | 15 Fälle, ternärer Verifier, realer Lauf 35/41 = 85 % (4 neutral; Stand 2026-08-03) | [docs/evidence/eval_report.md](docs/evidence/eval_report.md), [evals/README.md](evals/README.md) |
| Grenzen des Systems | Nährwerte ≈ Schätzung, Heuristik-Matching, Injection nur mitigiert, … | [§ 5](docs/PROJEKTDOKU.md#5-grenzen-des-systems) |

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
pytest -q                # läuft komplett ohne API-Keys (LLM/HTTP gemockt)
```

## Beispiel

```
Du: Was kann ich mit Hähnchen, Zitrone und Knoblauch kochen?

[THOUGHT] Zyklus 1: Ich brauche Sub-Agent: recherche_rezepte
[ACTION]  Aufruf mit: {'anfrage': 'Rezepte mit Hähnchen, Zitrone und Knoblauch'}
[OBSERVATION] Sub-Agent 'recherche_rezepte' antwortete: ...

[ANSWER]  Hier ist ein passendes Rezept: Zitronenhähnchen mit Knoblauch ...
```

Ein vollständiger echter Lauf mit 9 TAO-Zyklen inkl. Constraint-Revision ist in
[docs/PROJEKTDOKU.md § 3](docs/PROJEKTDOKU.md#3-funktionsweise-der-tao-zyklus-an-einem-echten-lauf)
durcherzählt (Roh-Trace: [docs/evidence/](docs/evidence/)).

## Projektstruktur

```
RezeptAgent/
├── app/
│   ├── agents/
│   │   ├── orchestrator.py      # Manager-Agent (LangGraph ReAct)        [W1]
│   │   └── recherche_agent.py   # Recherche-Sub-Agent (Web)             [W1]
│   ├── tools/
│   │   ├── web_search.py        # Web-Suche via Tavily (untrusted-Delimiter) [VL03]
│   │   ├── kochbuch.py          # Kochbuch-RAG: Wissensbasis + BM25-Retriever [W3/W4]
│   │   ├── shopping_list.py     # Einkaufsliste (deterministisch)
│   │   ├── naehrwerte.py        # kcal/Makros pro Portion (Constraint-Check)
│   │   ├── skalierung.py        # Mengen exakt auf Portionszahl umrechnen
│   │   ├── wochenplan.py        # mehrere Gerichte → eine Einkaufsliste (deterministisch)
│   │   └── vision.py            # Foto → Zutaten (Groq VLM)             [W2]
│   ├── core/
│   │   ├── agent_service.py       # zentrale Ausführung + Routing + TAO-Trace
│   │   ├── wochenplan_workflow.py # code-orchestrierter Wochenplan (plan→prüfe→revidiere)
│   │   ├── praeferenzen.py        # Memory: Geschmacksprofil + Bewertungen
│   │   ├── wochenplaene.py        # Ablage gespeicherter Wochenpläne (JSON pro Plan)
│   │   ├── text_utils.py          # Reasoning-Filter (<think>) + Rezepttitel-Extraktion
│   │   └── logging_config.py      # strukturiertes JSON-Logging          [W5]
│   └── api/
│       ├── main.py              # FastAPI: 12 Endpunkte (/chat, /health, /kochbuch, /wochenplan …) [W6/W11]
│       └── schemas.py           # Pydantic-Validierung                  [W9]
├── seiten/                      # Streamlit-Mehrseiten-GUI
│   ├── start.py                 #   Startseite: was das System kann
│   ├── rezept_finden.py         #   Anfrage an den Agenten + TAO-Trace + Bewertung
│   ├── mein_kochbuch.py         #   Wissensbasis ansehen / anlegen / löschen [W3]
│   ├── meine_wochenplaene.py    #   Pläne ansehen + Plan aus dem Kochbuch (ohne LLM)
│   ├── mein_profil.py           #   Profil bearbeiten + Bewertungen
│   └── _gemeinsam.py            #   API_URL, Auswahl-Listen, Gericht-Anzeige
├── data/
│   ├── rezepte/                 # Kochbuch-Wissensbasis: seed_* (mitgeliefert) + gelernt_*/manuell
│   └── wochenplaene/            # gespeicherte Wochenpläne (Laufzeit-Daten)
├── streamlit_app.py             # GUI-Einstiegspunkt (st.navigation)
├── .streamlit/config.toml       # GUI-Theme
├── scripts/                     # Evidence-Generatoren (Referenz-/Vision-/Wochenplan-Traces)
├── evals/                       # Offline-Eval: Testset, Verifier, Runner (VL09)
├── tests/                       # Unit-/Integrationstests               [W8]
├── docs/                        # PROJEKTDOKU, Matrix, Sicherheit, Evidence, Reflexionen
├── Dockerfile, docker-compose.yml                                       # [W7]
├── .github/workflows/ci.yml                                             # [W10]
├── main.py                      # CLI-Einstiegspunkt
└── requirements.txt
```
