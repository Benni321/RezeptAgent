# Anforderungs-Nachweismatrix — RezeptAgent

*Stand: 2026-07-05 (Reproduzierbarkeits-Audit). Diese Datei ist gleichzeitig der
vom Prof geforderte „Anforderungs-Nachweis" (klare Auflistung aller erfüllten
Anforderungen mit Beleg). Es gibt bewusst nur EINE Statustabelle pro Kategorie
(P bzw. W) — frühere Fassungen hatten zwei Tabellen, die sich widersprachen
(z. B. W3/W4 hier ✅, dort 🟡). Das wurde konsolidiert.*

**Schein vs. Note:** Die folgenden Anforderungen sind die **Mindesthürde für den Schein**
(alle P1–P5 + ≥ 11 von 14 W). Die **Note** des Semesterprojekts ergibt sich separat aus
Qualität, Tiefe und Sinnhaftigkeit der Umsetzung — wir bauen daher nur, was für einen
Rezept-Agenten fachlich Sinn ergibt.

Legende: ✅ erfüllt · 🔧 in Arbeit/offen · 🟡 geplant · ⛔ bewusst (noch) nicht umgesetzt

---

## Update (2026-07-15) — Eval-Harness, Observability, Kochbuch-RAG

- **Eval-Harness (VL09)** (`evals/`): Testset (15 Fälle, davon 3 bewusst schwere),
  programmatischer ternärer Verifier (Antwort- + Trajektorien-Ebene), Runner gegen
  den echten Agenten. Realer Lauf, Stand 2026-07-15: **39/45 Checks bestanden (87 %)**,
  Report `docs/evidence/eval_report.md`, Roh-Traces `docs/evidence/eval_traces/`.
  Grenzen/Reward-Hacking/LLM-Judge-Begründung: `evals/README.md`. → Dim 2/5.
- **Observability auf Trace/Span-Niveau (VL09)**: `trace_id` pro Run (ContextVar),
  Span-Logs (`span_typ`, `dauer_ms`, `status`), optionale Run-Persistenz als eine
  JSON-Datei (`AGENT_TRACE_DIR`). → W5, VL03 (Audit der Tool-Calls).
- **Kochbuch-RAG (W3/W4) — RAG ist jetzt umgesetzt und AKTIV**: persönliche
  Wissensbasis aus 4+-Sterne-Bewertungen (+ Seeds), BM25-Retriever als Tool
  (`app/tools/kochbuch.py`), Orchestrator nutzt es situationsabhängig ZUERST bei
  Bezug auf Bewährtes (Agentic RAG; Eval-Fall `favoriten_rag`). Ersetzt das
  blockierte Embedding-Modul (`app/rag/`), Begründung `docs/PROJEKTDOKU.md` „Kochbuch-RAG“.
- **Tests: 106 grün ohne API-Keys** (zuvor 65).

---

## Update (2026-07-13) — Tiefen-Ausbau & Härtung

- **Wochenplaner als code-orchestrierter Workflow** (`app/core/wochenplan_workflow.py`):
  garantierte `plan→prüfe→revidiere`-Schleife (Recherche → kcal-Check → Revision →
  Abschluss). Bewusste Korrektur, nachdem sich der rein agentische Prompt-Ansatz als
  modellunabhängig unzuverlässig erwies (`docs/PROJEKTDOKU.md` „Wochenplan-Workflow"). → stärkt Dim 1/2.
  Realer Trace: `docs/evidence/wochenplan_trace.md`.
- **Fehlerhandling & situationsabhängige Pfade** (`tests/test_fehlerhandling.py`):
  leere/fehlgeschlagene Suche → Fallback auf eigenes Wissen; Nährwert-Fehler → nicht
  als „erfüllt"; Vision-Fehler graceful. 4 Referenz-Eingaben:
  `docs/evidence/referenz_eingaben.md`. → stützt W9, Dim 2.
- **Sicherheit nach VL03** (`docs/sicherheit.md`, `tests/test_sicherheit.py`):
  Lethal-Trifecta-Analyse, Anti-Injection-Delimiter, Excessive-Agency-Check. → Dim 6.
- **Modellwechsel**: `llama-3.3-70b` (auf Groq defektes Tool-Call-Format) →
  `qwen/qwen3-32b` (schnell, zuverlässiges Tool-Calling; Reasoning gefiltert).
- **Tests: 65 grün ohne API-Keys** (zuvor 36). → W8.

---

## Heute verifiziert (2026-07-05)

- Realer End-to-End-Lauf mit echten API-Keys (`app/core/agent_service.run_rezept_agent`,
  Beispiel-Eingabe aus `docs/handover.md`): Orchestrator ruft den Recherche-Sub-Agenten
  und `einkaufsliste_erstellen` auf, harte Ernährungs-Vorgabe aus dem Profil
  ("vegetarisch") wird korrekt gegen die genannte Zutat ("Hähnchen") durchgesetzt.
  → belegt P1, P2, W1, W5, W9.
- `pytest -q` mit **entfernten** `GROQ_API_KEY`/`TAVILY_API_KEY`/`GROQ_MODEL`/`RAG_AKTIV`:
  **36 Tests grün**, keine Tests brauchen echte Keys. → belegt W8, stützt W9.
- `.env.example` gegen den Code abgeglichen: `GROQ_VISION_MODEL` und `RAG_AKTIV`
  wurden dort ergänzt (fehlten, obwohl `app/tools/vision.py` bzw.
  `app/agents/orchestrator.py` sie lesen).
- `main.py`-Docstring nannte fälschlich `OPENAI_API_KEY` statt `GROQ_API_KEY` —
  behoben (betraf nur den Kommentar, nicht die Funktion).
- **Noch offen aus diesem Audit:** `docker compose up` real durchtesten (auf
  Wunsch in dieser Session zurückgestellt); aktuelle Commit-Anzahl für P5
  bestätigen (`git log --oneline | wc -l`); Löschung des versehentlichen,
  nicht getrackten Ordners `https:/` im Projekt-Root (bereits in `.gitignore`,
  aber noch physisch vorhanden).

---

## Pflichtanforderungen (P1–P5) — *alle* nötig

| ID | Anforderung | Status | Beleg |
|----|-------------|--------|-------|
| P1 | Echter Agent mit Tool-Use | ✅ | Realer Lauf heute: `recherche_rezepte` (Sub-Agent → Tavily) und `einkaufsliste_erstellen` werden vom Orchestrator aufgerufen (`app/core/agent_service.py`). |
| P2 | TAO sichtbar, ≥ 3 Iterationen | ✅ | `docs/evidence/referenz_traces.md`, Eingabe (b): realer Lauf mit **9 beschrifteten TAO-Zyklen** (+ Roh-JSON in `docs/evidence/traces/`); live sichtbar in `main.py`/GUI. |
| P3 | Etabliertes Framework + Begründung | ✅ | `from langgraph.prebuilt import create_react_agent` in `app/agents/orchestrator.py`; Begründung in README ("Framework"-Abschnitt). |
| P4 | README (Beschreibung, Architektur, Installation, Beispiel) | ✅ | Alle vier Punkte vorhanden; einzige gefundene Inkonsistenz (`main.py`-Docstring nannte `OPENAI_API_KEY`) heute behoben. |
| P5 | Git-Historie ≥ 10 Commits, inkrementell | 🔧 | Letzter bekannter Stand: 6 Commits (Anfang dieser Session, vor der Sicherheits-/Tiefen-Ausbau-Serie) — noch unter dem Ziel ≥10. Bitte mit `git log --oneline | wc -l` aktuell bestätigen und Zahl hier eintragen. |

---

## Wahlpflichtanforderungen (W1–W14) — ≥ 11 nötig

| ID | Anforderung | Status | Sinnhaftigkeit für Rezept-Agent | Beleg |
|----|-------------|--------|----------------------------------|-------|
| W1 | Multi-Agent (Orchestrator + Subagent) | ✅ | **Hoch** — Recherche-Agent isoliert das „Rauschen" der Websuche; Orchestrator bleibt schlank | `app/agents/orchestrator.py` + `app/agents/recherche_agent.py`; im heutigen Lauf als `Sub-Agent`-Ziel im Trace sichtbar |
| W2 | Multimodale Eingabe | ✅ | **Hoch** — Kühlschrank-Foto ist Kern des Abstracts | `app/tools/vision.py` (Groq-VLM); realer Nachweis mit echtem Foto: `docs/evidence/vision_nachweis.md` (Foto → 10 Zutaten → Rezept) |
| W3 | RAG (eigene Wissensbasis) | ✅ | **Hoch** — Basis enthält, was Web/LLM nicht wissen: die eigenen, gut bewerteten Rezepte (Kochbuch) | `app/tools/kochbuch.py` (Wissensbasis `data/rezepte/`, BM25-Retrieval, kein Modell-Download); Schreibpfad `POST /bewertung` ≥ 4 Sterne; Tests `tests/test_kochbuch.py`; Begründung `docs/PROJEKTDOKU.md` „Kochbuch-RAG" |
| W4 | Agentic RAG (Retriever als Tool) | ✅ | **Hoch** — Orchestrator entscheidet situationsabhängig: Kochbuch ZUERST bei Bezug auf Bewährtes, bei `RAG-LEER` transparent zur Websuche | `rag_retriever` fest im Tool-Set (`app/agents/orchestrator.py`), Prompt-Regel 2b; gemessen im Eval-Fall `favoriten_rag` (`tool_reihenfolge`-Check) |
| W5 | Observability (Tracing/Logging) | ✅ | **Mittel-Hoch** — Debugging + Sicherheit (VL3) | `app/core/logging_config.py`, strukturierte JSON-Logs im heutigen Lauf verifiziert |
| W6 | Prediction Service (HTTP-API) | ✅ | **Hoch** — die Streamlit-GUI ist der echte Konsument der API | `app/api/main.py`, Endpunkt `/chat` |
| W7 | Containerisierung (`docker compose up`) | ✅ | **Mittel-Hoch** — reproduzierbarer Start | Dockerfile + `docker-compose.yml` vorhanden (Dienste `api`+`ui`; die dritte, auskommentierte `chroma`-Instanz ist NICHT aktiv — Text dazu korrigiert). Realer `docker compose up`-Testlauf in dieser Session zurückgestellt, vor Abgabe erneut prüfen. |
| W8 | ≥ 5 automatisierte Tests | ✅ | **Hoch** — Regressionsschutz für Tools/Filterlogik | `pytest -q`: 36 Tests, heute ohne API-Keys grün verifiziert |
| W9 | Input-Validierung & Fehlerbehandlung | ✅ | **Hoch** — leere Anfrage / falscher Bildtyp / Agentenfehler abfangen | Pydantic-Schemas (`app/api/schemas.py`), Bildtyp-/Lesbarkeitsprüfung + try/except um den Agentenlauf in `app/api/main.py` |
| W10 | CI/CD (Schritt bei Push) | ✅ | **Mittel-Hoch** — gute Praxis, geringer Aufwand | `.github/workflows/ci.yml`: installiert `requirements.txt`, führt `pytest -q` bei jedem Push/PR aus |
| W11 | Monitoring-Endpoint (`/health`) | ✅ | **Mittel-Hoch** — gehört zur API, zeigt Betriebsbereitschaft | `/health`-Route in `app/api/main.py` |
| W12 | Reflexion: Data/Concept Drift | ✅ | **Hoch** — saisonale/Trend-Drift bei Rezepten ist real | `docs/reflexion_drift.md` |
| W13 | Konzept: Continual Learning | ✅ | **Hoch** — Nutzer-Feedback → neue Rezepte in die Wissensbasis | `docs/reflexion_continual.md` |
| W14 | Reflexion: Responsible AI | ✅ | **Hoch** — Allergene, Ernährungssicherheit, Küchen-Bias, Halluzination | `docs/reflexion_responsible_ai.md` |

**Zwischenstand: 14 von 14 W erfüllt** (W3/W4 seit 2026-07-15 durch das
Kochbuch-RAG) — deutlich über der 11er-Schwelle. Zusammen mit P1–P4 ✅ und P5 als
einzigem offenen Punkt (Commit-Anzahl erhöhen) ist der Schein bei aktuellem Stand
in Reichweite, sobald P5 erfüllt ist.

---

## Beobachtungen ohne Auswirkung auf Schein/Note (zur Kenntnis)

- `requirements.txt` pinnt nur Mindestversionen (`>=`) ohne Obergrenze. Ein
  frischer `pip install` zieht heute z. B. `langchain 1.x`/`langgraph 1.x`
  statt der ursprünglich getesteten 0.2/0.3-Reihe. Alle 36 Tests laufen mit
  den neueren Versionen grün, das System scheint kompatibel — als Risiko für
  spätere, nicht mehr kontrollierte Updates aber im Hinterkopf behalten.
- Im heutigen Testlauf rief der Orchestrator `recherche_rezepte` zweimal auf,
  obwohl der System-Prompt „HÖCHSTENS EINMAL" vorschreibt. Kein Schein-Risiko,
  aber ein Kandidat für die Prompt-Schärfung in der Tiefen-Ausbau-Serie
  (Dimension 2: „reagiert der Agent kontrolliert/regelkonform?").
