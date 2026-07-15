# Evidence-Index: Welcher Nachweis belegt welche Anforderung?

*Alle Nachweise stammen aus **realen Läufen** gegen den echten Agenten (Groq +
Tavily) und sind über die genannten Skripte reproduzierbar. Nichts hier ist
handgeschrieben „behauptet“ — die Traces sind Rohdaten der Observability-Schicht
(`trace_id`, Spans mit `dauer_ms`/`status`, siehe README „Observability“).*

## Pflichtanforderungen

| Anforderung | Nachweis | Kontext (1 Satz) |
|-------------|----------|------------------|
| **P1** Echter Agent mit Tool-Use | [referenz_traces.md](referenz_traces.md), Roh-Traces in [traces/](traces/) | Reale Läufe, in denen der Orchestrator situationsabhängig Sub-Agent und Tools aufruft (`recherche_rezepte`, `naehrwerte_schaetzen`, `einkaufsliste_erstellen` …). |
| **P2** TAO sichtbar, ≥ 3 Zyklen | [referenz_traces.md](referenz_traces.md), Eingabe (b) | Der Wochenplan-Trace enthält die geforderten ≥ 3 vollständigen Thought→Action→Observation-Zyklen, im Begleittext einzeln beschriftet; ergänzend [wochenplan_trace.md](wochenplan_trace.md). |
| **P3** Framework + Begründung | README-Abschnitt „Framework“, `app/agents/orchestrator.py` | LangGraph (`create_react_agent`) mit dokumentierter Begründung — kein Evidence-Lauf nötig, im Code prüfbar. |
| **P4** README vollständig | [../../README.md](../../README.md) | Beschreibung, Architektur, Installation, Beispiel + Designentscheidungen mit Warum. |
| **P5** Git-Historie ≥ 10 Commits | Git-Log des Repos | Per `git log --oneline` prüfbar (nicht Teil dieses Ordners). |

## Wahlpflichtanforderungen (Auswahl mit Lauf-Nachweis)

| Anforderung | Nachweis | Kontext (1 Satz) |
|-------------|----------|------------------|
| **W1** Multi-Agent | [referenz_traces.md](referenz_traces.md) (a)/(b) | Die Recherche läuft sichtbar als `Sub-Agent recherche_rezepte` mit isoliertem Kontext, koordiniert vom Orchestrator. |
| **W2** Multimodale Eingabe | [vision_nachweis.md](vision_nachweis.md) + [kuehlschrank_foto.jpg](kuehlschrank_foto.jpg) | Echtes Kühlschrank-Foto → vom Groq-VLM erkannte Zutatenliste → daraus entstandener Rezeptvorschlag, ein durchgehender Lauf. |
| **W3/W4** RAG + Agentic RAG | [eval_report.md](eval_report.md), Fall `favoriten_rag` + [eval_traces/favoriten_rag.json](eval_traces/favoriten_rag.json) | Realer Lauf: Bei Bezug auf Favoriten ruft der Agent `rag_retriever` (Kochbuch, BM25) VOR jeder Websuche auf — per `tool_reihenfolge`-Check verifiziert. |
| **W5** Observability | beliebiger Roh-Trace in [traces/](traces/) oder [eval_traces/runs/](eval_traces/runs/) | Jeder Lauf ist eine zusammenhängende JSON-Datei mit `trace_id` und Span-Feldern (`dauer_ms`, `status`) über alle Schritte. |
| **W8** Automatisierte Tests | `pytest -q` (106 grün, ohne API-Keys), CI: `.github/workflows/ci.yml` | Die Testsuite läuft offline; die Eval-Verifier-Logik ist zusätzlich separat getestet. |
| **W9** Fehlerbehandlung | [referenz_traces.md](referenz_traces.md) (c) + `tests/test_fehlerhandling.py` | Realer Fallback-Lauf (leere Suche → eigenes Wissen, transparent gekennzeichnet), deterministisch abgesichert in den Tests. |
| **W12–W14** Reflexionen | [../reflexion_drift.md](../reflexion_drift.md), [../reflexion_continual.md](../reflexion_continual.md), [../reflexion_responsible_ai.md](../reflexion_responsible_ai.md) | Konzept-/Reflexionsdokumente (kein Lauf-Nachweis nötig). |

Vollständige Anforderungsübersicht mit Status: [../bewertungsmatrix.md](../bewertungsmatrix.md).

## Qualität des Agentenverhaltens (Bewertungs-Dimension 2)

| Frage des Prüfers | Nachweis |
|-------------------|----------|
| „Reagiert der Agent different auf verschiedene Eingaben?“ | [referenz_traces.md](referenz_traces.md): vier Eingaben, vier verschiedene Trajektorien durch denselben Agenten (inkl. Vergleich). |
| „Plant er mehrschrittig und revidiert er?“ | [wochenplan_trace.md](wochenplan_trace.md) + Eingabe (b): plan→prüfe→revidiere sichtbar im Trace. |
| „Wie oft hält er Constraints wirklich ein?“ | [eval_report.md](eval_report.md): 15 Fälle, ternäre programmatische Checks auf Antwort- UND Trajektorien-Ebene (39/45 bestanden, 87 %) — inklusive der ehrlich dokumentierten Fehlschläge. |
| „Wo scheitert er?“ | Die drei `schwer_*`-Fälle im [eval_report.md](eval_report.md) (bewusst so gebaut) + Roh-Traces in [eval_traces/](eval_traces/); Verifier-Grenzen in [../../evals/README.md](../../evals/README.md). |

## Verzeichnis-Übersicht

- `referenz_eingaben.md` — die vier Referenz-Eingaben mit erwarteten Trajektorien (Soll)
- `referenz_traces.md` — die realen Läufe dazu mit beschrifteten TAO-Zyklen (Ist)
- `traces/` — Roh-Traces (JSON, `trace_id` + Spans) der Referenz- und Vision-Läufe
- `vision_nachweis.md` + `kuehlschrank_foto.jpg` — W2-Nachweis mit echtem Foto
- `wochenplan_trace.md` — ausführlicher Wochenplan-Lauf (P2/Dim 2)
- `eval_report.md` + `eval_traces/` — Offline-Eval: Report, Fall-JSONs, Run-Traces
- Reproduktion: `scripts/erzeuge_referenz_traces.py`, `scripts/erzeuge_vision_evidence.py`, `scripts/erzeuge_wochenplan_evidence.py`, `evals/run_eval.py`

## Ergänzende Screenshots (optional, sekundär)

Primärer Nachweis ist bewusst Text/JSON (maschinenlesbar für die
Code-Agent-Bewertung). Zwei ergänzende Screenshots (GUI mit Trace-Expander,
grüner CI-Run auf GitHub) können als `screenshot_gui.png` /
`screenshot_ci.png` hier abgelegt werden — sie belegen nichts, was die
Text-Nachweise nicht schon belegen.
