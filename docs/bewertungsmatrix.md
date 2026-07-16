# Anforderungs-Nachweismatrix — RezeptAgent

*Stand: 2026-07-16 (Abgabe-Endzustand). Diese Datei ist der vom Prof geforderte
„Anforderungs-Nachweis": alle erfüllten Anforderungen mit präzisem, klickbarem
Beleg (Code-Stelle, Evidence-Datei, Test oder Reflexionstext). Es gibt bewusst
nur EINE Statustabelle pro Kategorie. Jeder Link wurde beim Erstellen dieser
Fassung gegen den tatsächlichen Datei-Inhalt verifiziert.*

**Schein vs. Note:** Die folgenden Anforderungen sind die **Mindesthürde für den
Schein** (alle P1–P5 + ≥ 11 von 14 W). Die **Note** ergibt sich separat aus
Qualität, Tiefe und Sinnhaftigkeit — zentrale Begründungs-Dokumente dafür:
[PROJEKTDOKU.md](PROJEKTDOKU.md) (Architektur, Funktionsweise, Grenzen),
[sicherheit.md](sicherheit.md), [evals/README.md](../evals/README.md) und die
drei Reflexionen (W12–W14).

Legende: ✅ erfüllt · 🔧 in Arbeit/offen · ⛔ bewusst nicht umgesetzt

---

## Pflichtanforderungen (P1–P5) — *alle* nötig

| ID | Anforderung | Status | Beleg |
|----|-------------|--------|-------|
| P1 | Echter Agent mit Tool-Use | ✅ | Agent + Tool-Set: [`create_orchestrator`](../app/agents/orchestrator.py#L98) (5 Tools, Zeile 120–126). Reale Tool-Aufrufe in echten Läufen: [referenz_traces.md](evidence/referenz_traces.md) (Sub-Agent + Tools im Trace), [eval_report.md](evidence/eval_report.md) (Trajektorien-Spalte je Fall). |
| P2 | TAO sichtbar, ≥ 3 Iterationen | ✅ | [referenz_traces.md, Eingabe (b)](evidence/referenz_traces.md): realer Lauf mit **9 beschrifteten TAO-Zyklen** (P2-Nachweis-Absatz dort), Roh-JSON [traces/referenz_b.json](evidence/traces/referenz_b.json) — dieser Lauf geht über den code-orchestrierten Wochenplan-Pfad (Struktur garantiert der Code, Inhalte entscheidet das LLM, [PROJEKTDOKU § 2.4](PROJEKTDOKU.md#24-wochenplan-workflow--bewusste-korrektur-nach-gescheitertem-ansatz)). **Voll agentisch** zusätzlich belegt: [eval_traces/kcal_limit_einzelrezept.json](evidence/eval_traces/kcal_limit_einzelrezept.json) (3 Zyklen: Recherche → Nährwert-Check → Skalierung, Tool-Wahl durch den Orchestrator). Beschriftet sichtbar in [main.py](../main.py)/GUI; durcherzählt in [PROJEKTDOKU § 3](PROJEKTDOKU.md#3-funktionsweise-der-tao-zyklus-an-einem-echten-lauf). |
| P3 | Etabliertes Framework + Begründung | ✅ | Import: [orchestrator.py:32](../app/agents/orchestrator.py#L32) (`from langgraph.prebuilt import create_react_agent`). Begründung: [README „Framework"](../README.md) + ausführlich [PROJEKTDOKU § 2.2](PROJEKTDOKU.md#22-orchestrator-langgraph-react--framework--und-modellwahl) (inkl. erwogener Alternative smolagents). |
| P4 | README (Beschreibung, Architektur, Installation, Beispiel) | ✅ | [README.md](../README.md): Beschreibung (Kopf + „Was kann das System?"), „Architektur", „Setup" (3 Startvarianten), „Beispiel" — alle vier Punkte vorhanden. |
| P5 | Git-Historie ≥ 10 Commits, inkrementell | 🔧 | Zahl bitte mit `git log --oneline \| wc -l` bestätigen und hier eintragen (letzter bekannter Stand: 6 Commits, seither mehrere Arbeitspakete offen zum Committen: Doku-Serie, Reflexionen, Matrix). |

---

## Wahlpflichtanforderungen (W1–W14) — ≥ 11 nötig

| ID | Anforderung | Status | Sinnhaftigkeit für Rezept-Agent | Beleg |
|----|-------------|--------|----------------------------------|-------|
| W1 | Multi-Agent (Orchestrator + Subagent) | ✅ | **Hoch** — Recherche-Agent isoliert das „Rauschen" der Websuche; Orchestrator bleibt schlank | [orchestrator.py](../app/agents/orchestrator.py) + [`recherche_rezepte`](../app/agents/recherche_agent.py#L79) (Sub-Agent mit eigenem Kontext); als `Sub-Agent`-Ziel im Trace: [referenz_traces.md](evidence/referenz_traces.md) |
| W2 | Multimodale Eingabe | ✅ | **Hoch** — Kühlschrank-Foto ist Kern des Abstracts | [`erkenne_zutaten_aus_bild`](../app/tools/vision.py#L68) (Groq-VLM); realer Nachweis mit echtem Foto: [vision_nachweis.md](evidence/vision_nachweis.md) (Foto → 10 Zutaten → Rezept), Roh-Trace [traces/vision_lauf.json](evidence/traces/vision_lauf.json) |
| W3 | RAG (eigene Wissensbasis) | ✅ | **Hoch** — Basis enthält, was Web/LLM nicht wissen: die eigenen, gut bewerteten Rezepte | Wissensbasis `data/rezepte/` + BM25-Retrieval: [`suche`](../app/tools/kochbuch.py#L167); Schreibpfad ≥ 4 Sterne: [`POST /bewertung`](../app/api/main.py#L141); Tests: [test_kochbuch.py](../tests/test_kochbuch.py); Begründung: [PROJEKTDOKU § 2.6](PROJEKTDOKU.md#26-kochbuch-rag--die-wissensbasis-die-der-agent-sich-selbst-kocht-w3w4) |
| W4 | Agentic RAG (Retriever als Tool) | ✅ | **Hoch** — Orchestrator entscheidet situationsabhängig: Kochbuch ZUERST bei Bezug auf Bewährtes, bei `RAG-LEER` transparent zur Websuche | [`rag_retriever`](../app/tools/kochbuch.py#L213) im Tool-Set + Prompt-Regel 2b: [orchestrator.py:56](../app/agents/orchestrator.py#L56); **gemessen** im Eval-Fall `favoriten_rag` (`tool_reihenfolge`-Check ✓): [eval_report.md](evidence/eval_report.md) |
| W5 | Observability (Tracing/Logging) | ✅ | **Mittel-Hoch** — Debugging + Audit der Tool-Calls (VL03) | `trace_id`/Spans: [logging_config.py](../app/core/logging_config.py), Mitschnitt je Schritt: [agent_service.py](../app/core/agent_service.py); Schema-Test: [test_trace_schema.py](../tests/test_trace_schema.py); realer Roh-Trace mit `trace_id`/`dauer_ms`/`status`: [traces/referenz_b.json](evidence/traces/referenz_b.json) |
| W6 | Prediction Service (HTTP-API) | ✅ | **Hoch** — die Streamlit-GUI ist der echte Konsument der API | [`POST /chat`](../app/api/main.py#L45); Konsument: [streamlit_app.py](../streamlit_app.py); API-Tests: [test_api.py](../tests/test_api.py) |
| W7 | Containerisierung (`docker compose up`) | ✅ | **Mittel-Hoch** — reproduzierbarer Start | [Dockerfile](../Dockerfile) + [docker-compose.yml](../docker-compose.yml) (Dienste `api`+`ui`). Real getestet am 2026-07-16: `docker compose up` baut und startet beide Dienste — API `healthy` auf 8000 (`GET /health` → `{"status":"ok"}`), GUI erreichbar auf 8501 (HTTP 200) |
| W8 | ≥ 5 automatisierte Tests | ✅ | **Hoch** — Regressionsschutz für Tools/Filterlogik | **106 Tests** in [tests/](../tests/) (15 Testdateien); `pytest -q` am 2026-07-16 zweifach grün verifiziert — auch mit explizit **entfernten** API-Keys (`GROQ_API_KEY`/`TAVILY_API_KEY`/`GROQ_MODEL`/`RAG_AKTIV`) |
| W9 | Input-Validierung & Fehlerbehandlung | ✅ | **Hoch** — leere Anfrage / falscher Bildtyp / Agentenfehler abfangen | Pydantic-Schemas: [schemas.py](../app/api/schemas.py); Bildtyp-Prüfung + try/except um den Agentenlauf: [api/main.py](../app/api/main.py); Tool-Fehler als Observation statt Crash: [test_fehlerhandling.py](../tests/test_fehlerhandling.py) |
| W10 | CI/CD (Schritt bei Push) | ✅ | **Mittel-Hoch** — gute Praxis, geringer Aufwand | [ci.yml](../.github/workflows/ci.yml): installiert `requirements.txt`, führt `pytest -q` (Zeile 25) bei jedem Push/PR aus — möglich, weil die Suite keyfrei grün ist (W8) |
| W11 | Monitoring-Endpoint (`/health`) | ✅ | **Mittel-Hoch** — gehört zur API, zeigt Betriebsbereitschaft | [`GET /health`](../app/api/main.py#L39); Test: `test_health_ok` in [test_api.py](../tests/test_api.py#L12) |
| W12 | Reflexion: Data/Concept Drift | ✅ | **Hoch** — saisonale/Trend-Drift bei Rezepten ist real | [reflexion_drift.md](reflexion_drift.md) — je Drift-Art mit konkreter Merk-Metrik (Eval-Quote, Span-Status, Schrittzahl-Korridore) |
| W13 | Konzept: Continual Learning | ✅ | **Hoch** — Nutzer-Feedback → neue Rezepte in die Wissensbasis | [reflexion_continual.md](reflexion_continual.md); der Loop ist zusätzlich **implementiert**: [`speichere_rezept`](../app/tools/kochbuch.py#L108) (Bewertung ≥ 4 Sterne → `data/rezepte/`) |
| W14 | Reflexion: Responsible AI | ✅ | **Hoch** — Allergene, Ernährungssicherheit, Küchen-Bias, Halluzination | [reflexion_responsible_ai.md](reflexion_responsible_ai.md) — mit konkretem Schadensszenario (verstecktes Gluten) und Eval-Zahlen |

**Zwischenstand: 14 von 14 W erfüllt** — deutlich über der 11er-Schwelle.
Zusammen mit P1–P4 ✅ ist P5 (Commit-Anzahl) der einzige offene Schein-Punkt.

---

## Offene Punkte vor Abgabe

1. **P5:** Commit-Anzahl mit `git log --oneline | wc -l` bestätigen und oben
   eintragen; die noch nicht committeten Arbeitspakete (PROJEKTDOKU, Reflexionen,
   Matrix, Aufräum-Paket vom 2026-07-16) als separate, inkrementelle Commits pushen.
2. **Prof-Material aus Git:** `docs/semesterprojekt_bewertung (1).pdf` ist jetzt
   in `.gitignore` — falls die Datei bereits getrackt ist, zusätzlich
   `git rm --cached "docs/semesterprojekt_bewertung (1).pdf"` ausführen.
   Gleiches mit `git ls-files | grep -iE 'HEIC|DS_Store|chroma|recipes|app/rag'`
   für die am 2026-07-16 entfernten Altlasten prüfen.

---

## Verlauf (kondensiert, je real verifiziert)

- **2026-07-16 (Abgabe-Review):** Prüfer-Simulation komplett durchlaufen:
  frisches venv nach README + `pytest -q` ohne API-Keys (**106 grün**),
  realer CLI-Lauf, `docker compose up` real getestet (W7, s. o.).
  Aufräum-Paket: verwaistes Alt-RAG-Modul (`app/rag/` inkl. veralteter
  W3/W4-Hinweise), `data/chroma/`, `data/recipes/`, HEIC-Original und
  `https:/`-Ordner entfernt; P2-Beleg um voll agentischen Trace ergänzt;
  GUI-Hinweis zum Foto-Versand an das externe VLM ergänzt (W14).
- **2026-07-16:** [PROJEKTDOKU.md](PROJEKTDOKU.md) als zentrales
  Bewertungsdokument erstellt, README auf Quickstart+Überblick verschlankt;
  Reflexionen W12–W14 auf Dimension-5-Tiefe überarbeitet (konkrete Eval-Bezüge);
  veraltete Angaben korrigiert (`recursion_limit`, Testset-Größe, Eval-Zahlen).
  `pytest -q`: **106 Tests grün, auch ohne API-Keys.**
- **2026-07-15:** Eval-Harness (VL09) in [evals/](../evals/): 15 Fälle (3 bewusst
  schwere), ternärer programmatischer Verifier (Antwort- + Trajektorien-Ebene).
  Realer Lauf: **39/45 Checks bestanden (87 %)** →
  [eval_report.md](evidence/eval_report.md). Kochbuch-RAG (W3/W4) aktiv;
  Observability auf Trace/Span-Niveau; Referenz-Traces (P2: 9 TAO-Zyklen) erzeugt.
- **2026-07-13:** Wochenplaner als code-orchestrierter Workflow (bewusste
  Korrektur nach gescheitertem voll-agentischem Ansatz →
  [PROJEKTDOKU § 2.4](PROJEKTDOKU.md#24-wochenplan-workflow--bewusste-korrektur-nach-gescheitertem-ansatz));
  Sicherheits-Threat-Model nach VL03 ([sicherheit.md](sicherheit.md));
  Modellwechsel `llama-3.3-70b` → `qwen/qwen3-32b` (defektes Tool-Call-Format).
- **2026-07-05:** Reproduzierbarkeits-Audit: realer End-to-End-Lauf (harte
  Profil-Vorgabe durchgesetzt), `.env.example` gegen Code abgeglichen,
  `main.py`-Docstring-Fehler behoben.

---

## Beobachtungen ohne Auswirkung auf Schein/Note (zur Kenntnis)

- `requirements.txt` pinnt nur Mindestversionen (`>=`). Die Tests laufen mit den
  aktuellen 1.x-Ständen von LangChain/LangGraph grün; unkontrollierte spätere
  Updates bleiben ein Risiko (siehe
  [PROJEKTDOKU § 5.7](PROJEKTDOKU.md#5-grenzen-des-systems)).
- Die am 2026-07-05 beobachtete Doppel-Recherche (Orchestrator rief
  `recherche_rezepte` 2× trotz „HÖCHSTENS EINMAL") tritt im aktuellen Eval nicht
  mehr auf: Fall `einfach_tomate_mozzarella` zeigt genau 1 Aufruf
  ([eval_report.md](evidence/eval_report.md)).
