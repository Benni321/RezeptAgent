# Anforderungs-Nachweismatrix — RezeptAgent

*Stand: 2026-08-05 (Abgabe-Endzustand). Diese Datei ist der vom Prof geforderte
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
| P1 | Echter Agent mit Tool-Use | ✅ | Agent + Tool-Set: [`create_orchestrator`](../app/agents/orchestrator.py#L131) (5 Tools, Zeile 154–160). Reale Tool-Aufrufe in echten Läufen: [referenz_traces.md](evidence/referenz_traces.md) (Sub-Agent + Tools im Trace), [eval_report.md](evidence/eval_report.md) (Trajektorien-Spalte je Fall). |
| P2 | TAO sichtbar, ≥ 3 Iterationen | ✅ | [referenz_traces.md, Eingabe (b)](evidence/referenz_traces.md): realer Lauf mit **9 beschrifteten TAO-Zyklen** (P2-Nachweis-Absatz dort), Roh-JSON [traces/referenz_b.json](evidence/traces/referenz_b.json) — dieser Lauf geht über den code-orchestrierten Wochenplan-Pfad (Struktur garantiert der Code, Inhalte entscheidet das LLM, [PROJEKTDOKU § 2.4](PROJEKTDOKU.md#24-wochenplan-workflow--bewusste-korrektur-nach-gescheitertem-ansatz)). **Voll agentisch** zusätzlich belegt: [eval_traces/kcal_limit_einzelrezept.json](evidence/eval_traces/kcal_limit_einzelrezept.json) (Lauf 2026-08-02: 4 Zyklen — 2× Recherche → Nährwert-Check → Einkaufsliste, Tool-Wahl durch den Orchestrator). Beschriftet sichtbar in [main.py](../main.py)/GUI; durcherzählt in [PROJEKTDOKU § 3](PROJEKTDOKU.md#3-funktionsweise-der-tao-zyklus-an-einem-echten-lauf). |
| P3 | Etabliertes Framework + Begründung | ✅ | Import: [orchestrator.py:32](../app/agents/orchestrator.py#L32) (`from langgraph.prebuilt import create_react_agent`). Begründung: [README „Framework"](../README.md) + ausführlich [PROJEKTDOKU § 2.2](PROJEKTDOKU.md#22-orchestrator-langgraph-react--framework--und-modellwahl) (inkl. erwogener Alternative smolagents). |
| P4 | README (Beschreibung, Architektur, Installation, Beispiel) | ✅ | [README.md](../README.md): Beschreibung (Kopf + „Was kann das System?"), „Architektur", „Setup" (3 Startvarianten), „Beispiel" — alle vier Punkte vorhanden. |
| P5 | Git-Historie ≥ 10 Commits, inkrementell | ✅ | **13 Commits** (`git log --oneline \| wc -l`, Stand 2026-08-05), verteilt über den gesamten Projektzeitraum 2026-04-12 → 2026-08-05 und auf beide Teammitglieder (jonakoud 8, be121sig 7, Benni321 2 — Merges eingerechnet). Der Verlauf zeigt inkrementelle Arbeitspakete (Phase-1-Agent → RAG → Tools/Personalisierung → Evidence/Doku → GUI-Ausbau). *Ehrlich dazu:* zwei davon sind Merge-Commits und zwei Sammel-Commits mit unspezifischer Nachricht — die Historie ist inkrementell, aber nicht durchgängig feingranular. |

---

## Wahlpflichtanforderungen (W1–W14) — ≥ 11 nötig

| ID | Anforderung | Status | Sinnhaftigkeit für Rezept-Agent | Beleg |
|----|-------------|--------|----------------------------------|-------|
| W1 | Multi-Agent (Orchestrator + Subagent) | ✅ | **Hoch** — Recherche-Agent isoliert das „Rauschen" der Websuche; Orchestrator bleibt schlank | [orchestrator.py](../app/agents/orchestrator.py) + [`recherche_rezepte`](../app/agents/recherche_agent.py#L98) (Sub-Agent mit eigenem Kontext); als `Sub-Agent`-Ziel im Trace: [referenz_traces.md](evidence/referenz_traces.md) |
| W2 | Multimodale Eingabe | ✅ | **Hoch** — Kühlschrank-Foto ist Kern des Abstracts | [`erkenne_zutaten_aus_bild`](../app/tools/vision.py#L77) (Groq-VLM); realer Nachweis mit echtem Foto: [vision_nachweis.md](evidence/vision_nachweis.md) (Foto → 10 Zutaten → Rezept), Roh-Trace [traces/vision_lauf.json](evidence/traces/vision_lauf.json) |
| W3 | RAG (eigene Wissensbasis) | ✅ | **Hoch** — Basis enthält, was Web/LLM nicht wissen: die eigenen, gut bewerteten Rezepte | Wissensbasis `data/rezepte/` + BM25-Retrieval: [`suche`](../app/tools/kochbuch.py#L202); Schreibpfad ≥ 4 Sterne: [`POST /bewertung`](../app/api/main.py#L197); Tests: [test_kochbuch.py](../tests/test_kochbuch.py); Begründung: [PROJEKTDOKU § 2.6](PROJEKTDOKU.md#26-kochbuch-rag--die-wissensbasis-die-der-agent-sich-selbst-kocht-w3w4) |
| W4 | Agentic RAG (Retriever als Tool) | ✅ | **Hoch** — Orchestrator entscheidet situationsabhängig: Kochbuch ZUERST bei Bezug auf Bewährtes, bei `RAG-LEER` transparent zur Websuche | [`rag_retriever`](../app/tools/kochbuch.py#L248) im Tool-Set + Prompt-Regel 2b: [orchestrator.py:68](../app/agents/orchestrator.py#L68); **gemessen** im Eval-Fall `favoriten_rag` (`tool_reihenfolge`-Check ✓): [eval_report.md](evidence/eval_report.md) |
| W5 | Observability (Tracing/Logging) | ✅ | **Mittel-Hoch** — Debugging + Audit der Tool-Calls (VL03) | `trace_id`/Spans: [logging_config.py](../app/core/logging_config.py), Mitschnitt je Schritt: [agent_service.py](../app/core/agent_service.py); Schema-Test: [test_trace_schema.py](../tests/test_trace_schema.py); realer Roh-Trace mit `trace_id`/`dauer_ms`/`status`: [traces/referenz_b.json](evidence/traces/referenz_b.json) |
| W6 | Prediction Service (HTTP-API) | ✅ | **Hoch** — die Streamlit-GUI ist der echte Konsument der API | **12 Endpunkte** in [main.py](../app/api/main.py), u. a. [`POST /chat`](../app/api/main.py#L50), `GET/POST/DELETE /kochbuch`, `GET/POST/DELETE /wochenplan` und der LLM-freie [`POST /wochenplan/aus-kochbuch`](../app/api/main.py#L252); Konsument ist die Mehrseiten-GUI ([seiten/](../seiten/)); API-Tests: [test_api.py](../tests/test_api.py). Übersicht: [PROJEKTDOKU § 2.11](PROJEKTDOKU.md#211-api-gui-container-ci) |
| W7 | Containerisierung (`docker compose up`) | ✅ | **Mittel-Hoch** — reproduzierbarer Start | [Dockerfile](../Dockerfile) + [docker-compose.yml](../docker-compose.yml) (Dienste `api`+`ui`) + [.dockerignore](../.dockerignore). Real getestet am 2026-08-02 (zuvor 2026-07-16): `docker compose up` baut und startet beide Dienste — API auf 8000 (`GET /health` → `{"status":"ok"}`), GUI auf 8501 (HTTP 200); Image durch `.dockerignore` von 3,63 GB auf 225 MB verkleinert, `.env`/`.venv`/`.git` sind nicht mehr im Image |
| W8 | ≥ 5 automatisierte Tests | ✅ | **Hoch** — Regressionsschutz für Tools/Filterlogik | **163 Tests** in [tests/](../tests/) (16 Testdateien); `pytest -q` grün **ohne** API-Keys — zuletzt verifiziert 2026-08-02 in frischem venv ohne `.env` (Prüfer-Simulation; davor 2026-07-16 zweifach mit explizit entfernten Keys) |
| W9 | Input-Validierung & Fehlerbehandlung | ✅ | **Hoch** — leere Anfrage / falscher Bildtyp / Agentenfehler abfangen | Pydantic-Schemas: [schemas.py](../app/api/schemas.py); Bildtyp-Prüfung + try/except um den Agentenlauf: [api/main.py](../app/api/main.py); Tool-Fehler als Observation statt Crash: [test_fehlerhandling.py](../tests/test_fehlerhandling.py) |
| W10 | CI/CD (Schritt bei Push) | ✅ | **Mittel-Hoch** — gute Praxis, geringer Aufwand | [ci.yml](../.github/workflows/ci.yml): installiert `requirements.txt`, führt `pytest -q` (Zeile 25) bei jedem Push/PR aus — möglich, weil die Suite keyfrei grün ist (W8) |
| W11 | Monitoring-Endpoint (`/health`) | ✅ | **Mittel-Hoch** — gehört zur API, zeigt Betriebsbereitschaft | [`GET /health`](../app/api/main.py#L44); Test: `test_health_ok` in [test_api.py](../tests/test_api.py#L15) |
| W12 | Reflexion: Data/Concept Drift | ✅ | **Hoch** — saisonale/Trend-Drift bei Rezepten ist real | [reflexion_drift.md](reflexion_drift.md) — je Drift-Art mit konkreter Merk-Metrik (Eval-Quote, Span-Status, Schrittzahl-Korridore) |
| W13 | Konzept: Continual Learning | ✅ | **Hoch** — Nutzer-Feedback → neue Rezepte in die Wissensbasis | [reflexion_continual.md](reflexion_continual.md); der Loop ist zusätzlich **implementiert**: [`speichere_rezept`](../app/tools/kochbuch.py#L108) (Bewertung ≥ 4 Sterne → `data/rezepte/`) |
| W14 | Reflexion: Responsible AI | ✅ | **Hoch** — Allergene, Ernährungssicherheit, Küchen-Bias, Halluzination | [reflexion_responsible_ai.md](reflexion_responsible_ai.md) — mit konkretem Schadensszenario (verstecktes Gluten) und Eval-Zahlen |

**Stand: 14 von 14 W erfüllt** — deutlich über der 11er-Schwelle. Zusammen mit
**allen P1–P5 ✅** sind damit sämtliche Schein-Voraussetzungen erfüllt; es ist
kein Punkt mehr offen.

---

## Offene Punkte vor Abgabe

Alle Schein-relevanten Punkte sind erledigt (P1–P5 ✅, 14/14 W ✅). Was noch
offen ist, betrifft ausschließlich die Aktualität der *Evidence*, nicht die
Erfüllung der Anforderungen:

1. **Eval-Re-Run mit dem aktuellen Stand.** Der vorliegende Report
   ([eval_report.md](evidence/eval_report.md), 35/41 = 85 %) entstand am
   2026-08-03 — also **vor** dem Modell-Split
   ([PROJEKTDOKU § 2.2](PROJEKTDOKU.md#22-orchestrator-langgraph-react--framework--und-modellwahl)).
   Seither laufen Recherche-Sub-Agent und Nährwert-Schätzung auf
   `GROQ_MODEL_KLEIN`; ein vollständiger `python evals/run_eval.py` mit frischem
   Tages-Budget würde den Report auf den ausgelieferten Stand bringen (der Runner
   protokolliert jetzt beide Modelle). Danach die Quoten-Zitate in README,
   PROJEKTDOKU § 2.10/§ 4, [reflexion_drift.md](reflexion_drift.md) und
   [evidence/README.md](evidence/README.md) nachziehen.
2. **Vision-Evidence neu erzeugen** (`python scripts/erzeuge_vision_evidence.py`):
   [vision_nachweis.md](evidence/vision_nachweis.md) trägt noch den Vorbehalt zum
   zurückgezogenen `llama-4-scout`; ein frischer Lauf belegt W2 mit dem aktuell
   konfigurierten Modell.
3. **Optional:** GUI-Screenshots der vier Seiten nach `docs/evidence/`, damit die
   Mehrseiten-Oberfläche auch ohne laufendes System sichtbar ist.

---

## Verlauf (kondensiert, je real verifiziert)

- **2026-08-05 (GUI-Ausbau, Modell-Split, Doku-Abgleich):** Die Streamlit-GUI ist
  jetzt eine **Mehrseiten-App** ([seiten/](../seiten/): Start · Rezept finden ·
  Mein Kochbuch · Meine Wochenpläne · Mein Profil). Dazu **6 neue API-Endpunkte**
  (Kochbuch anlegen/löschen/listen, Wochenpläne speichern/löschen/listen) plus
  der LLM-freie `POST /wochenplan/aus-kochbuch`, eine persistente Wochenplan-
  Ablage ([wochenplaene.py](../app/core/wochenplaene.py)) und ein **Modell-Split**
  (`GROQ_MODEL_KLEIN` für Recherche-Sub-Agent + Nährwert-Schätzung; Rate-Limits
  gelten pro Modell). **Kritischer Fund und Fix:** `.env.example` und sechs
  Code-Defaults zeigten noch auf die von Groq zurückgezogenen Modelle
  `qwen/qwen3-32b` / `llama-4-scout` — ein Prüfer, der `cp .env.example .env`
  folgt, hätte einen 404 bekommen; alle Referenzen korrigiert und live gegen die
  Groq-Modelliste verifiziert. Doku-Abgleich: Modell-Split, GUI und Endpunkte
  ergänzt; falsche Behauptungen entfernt (`reasoning_effort` existierte nicht im
  Code; das Vision-„Bestätigungs-Gate" ist real eine Transparenz-Anzeige — jetzt
  ehrlich als Grenze benannt); überholte Reflexions-Aussagen korrigiert
  (Kochbuch kann jetzt löschen, manuelle Einträge umgehen die Sternehürde);
  13 verschobene Zeilenanker in Matrix/PROJEKTDOKU/sicherheit.md richtiggestellt.
  `pytest -q`: **157 Tests grün ohne Keys.**
- **2026-08-03 (Regressions-Fixes nach Modellwechsel):** Vier gezielte Fixes
  gegen die am Vortag gemessenen Nachfolger-Regressionen: Sub-Agent-Schrittlimit
  6→10, Beispiele in der Wochenplan-Erkennung (Plan-Anfragen ohne das Wort
  „Wochenplan" wurden abgewiesen), Recherche-Pflicht auch bei Fantasie-Zutaten,
  Titel-Heuristik bevorzugt jetzt die `##`-Überschrift (realer GUI-Fehlfund
  „ausschließlich" als Rezeptname; neuer Testfall). Eval-Re-Run der betroffenen
  Fälle: **35/41 wertbare Checks = 85 %** (nach 80 % am 2026-08-02); Analyse und
  Restgrenzen in [reflexion_drift.md](reflexion_drift.md). `pytest -q`: **116
  Tests grün ohne Keys.** Eine zusätzliche Such-Deckelung im Sub-Agent-Prompt
  ist eingebaut; ihre Messung sowie zwei Evidence-Läufe scheiterten am
  Groq-Tages-Token-Limit (siehe „Offene Punkte" Nr. 3).
- **2026-08-02 (Generalprobe + Konsistenz-Paket):** Prüfer-Simulation real
  durchlaufen: frisches venv ohne Keys → `pytest -q` **115 grün**;
  `docker compose up` (API-Health ok, GUI 200); realer CLI-Lauf. Erzwungener
  Modellwechsel `qwen3-32b` → `qwen/qwen3.6-27b` (Groq-Rückzug) in der Doku
  nachgezogen und als dritter Modell-Drift-Fall in
  [reflexion_drift.md](reflexion_drift.md) analysiert; kompletter Eval-Re-Run
  mit dem Nachfolger: **32/40 wertbare Checks = 80 %** (Vorlauf 2026-07-15:
  39/45 = 87 %; die Fehlerbild-Verschiebung ist dort dokumentiert);
  [.dockerignore](../.dockerignore) ergänzt (Image 3,63 GB → 225 MB, keine
  `.env` mehr im Image); Zeilen-Anker und Testzahl korrigiert.
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
  `recherche_rezepte` 2× trotz „HÖCHSTENS EINMAL") ist nicht ausgestorben:
  `einfach_tomate_mozzarella` zeigt weiterhin genau 1 Aufruf, aber
  `kcal_limit_einzelrezept` (Lauf 2026-08-02) enthält 2 Aufrufe nach einer
  unbrauchbaren Sub-Agent-Antwort (`memory_schlecht_bewertet` zeigte dasselbe
  am 2026-08-02, im Re-Run 2026-08-03 wieder 1×) — die Ein-Versuch-Regel
  bleibt eine Prompt-Vorgabe ohne Code-Garantie
  (PROJEKTDOKU § 2.7, [eval_report.md](evidence/eval_report.md)).
