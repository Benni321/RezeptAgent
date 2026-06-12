# Anforderungs-Nachweismatrix — RezeptAgent

*Stand: 2026-06-02. Diese Datei ist gleichzeitig der vom Prof geforderte
„Anforderungs-Nachweis" (klare Auflistung aller erfüllten Anforderungen mit Beleg).*

**Schein vs. Note:** Die folgenden Anforderungen sind die **Mindesthürde für den Schein**
(alle P1–P5 + ≥ 11 von 14 W). Die **Note** des Semesterprojekts ergibt sich separat aus
Qualität, Tiefe und Sinnhaftigkeit der Umsetzung — wir bauen daher nur, was für einen
Rezept-Agenten fachlich Sinn ergibt.

Legende: ✅ erfüllt · 🔧 in Arbeit · 🟡 geplant · ⛔ bewusst weggelassen

---

## Pflichtanforderungen (P1–P5) — *alle* nötig

| ID | Anforderung | Status | Beleg / Plan |
|----|-------------|--------|--------------|
| P1 | Echter Agent mit Tool-Use | ✅ | `web_search`-Tool (Tavily) wird vom Agenten aufgerufen → Log/Terminal |
| P2 | TAO sichtbar, ≥ 3 Iterationen | 🔧 | `main.py` druckt TAO; repräsentative Eingabe definieren, die ≥3 Zyklen auslöst (Multi-Tool/Sub-Agent) → Screenshot in `docs/evidence/` |
| P3 | Etabliertes Framework + Begründung | ✅ | LangGraph; Import in `app/agents/orchestrator.py`, Begründung im README |
| P4 | README (Beschreibung, Architektur, Installation, Beispiel) | 🔧 | vorhanden; `OPENAI_KEY`→`GROQ_KEY` angleichen, Links prüfen |
| P5 | Git-Historie ≥ 10 Commits, inkrementell | 🔧 | aktuell 1 Commit → ab jetzt feature-weise committen |

---

## Wahlpflichtanforderungen (W1–W14) — ≥ 11 nötig

| ID | Anforderung | Ziel | Sinnhaftigkeit für Rezept-Agent | Geplanter Nachweis |
|----|-------------|------|---------------------------------|--------------------|
| W1 | Multi-Agent (Orchestrator + Subagent) | ✅ | **Hoch** — Recherche-Agent isoliert das „Rauschen" der Websuche; Orchestrator bleibt schlank | Code + Architektur-Diagramm + Trace der Delegation |
| W2 | Multimodale Eingabe | ✅ | **Hoch** — Kühlschrank-Foto ist Kern des Abstracts | Foto-Input → erkannte Zutatenliste (Screenshot) |
| W3 | RAG (eigene Wissensbasis) | ✅ | **Hoch** — kuratierte Rezeptsammlung als „eigenes Wissen" neben der Websuche | Abfrage gegen Chroma-Index, Quellenangabe |
| W4 | Agentic RAG (Retriever als Tool) | ✅ | **Hoch** — Agent entscheidet selbst: RAG oder Websuche | Tool-Call `rag_retriever` im Trace |
| W5 | Observability (Tracing/Logging) | ✅ | **Mittel-Hoch** — Debugging + Sicherheit (VL3) | strukturierte Logs / Tracing-Ausgabe |
| W6 | Prediction Service (HTTP-API) | ✅ | **Hoch** — die Streamlit-GUI ist der echte Konsument der API | FastAPI `/chat` (Text + Bild) |
| W7 | Containerisierung (`docker compose up`) | ✅ | **Mittel-Hoch** — reproduzierbarer Start (Prof verlangt Reproduzierbarkeit) | `docker compose up` startet App + Chroma |
| W8 | ≥ 5 automatisierte Tests | ✅ | **Hoch** — Regressionsschutz für Tools/Filterlogik | `pytest`-Lauf grün, ≥5 Tests |
| W9 | Input-Validierung & Fehlerbehandlung | ✅ | **Hoch** — leere Anfrage / Nicht-Essen-Foto / Timeout abfangen | Negativ-Tests + graceful Fehlermeldungen |
| W10 | CI/CD (Schritt bei Push) | ✅ | **Mittel-Hoch** — gute Praxis, geringer Aufwand | GitHub-Actions-Run grün |
| W11 | Monitoring-Endpoint (`/health`) | ✅ | **Mittel-Hoch** — gehört zur API, zeigt Betriebsbereitschaft | `/health`-Route im FastAPI-Backend |
| W12 | Reflexion: Data/Concept Drift | ✅ | **Hoch** — saisonale/Trend-Drift bei Rezepten ist real | `docs/reflexion_drift.md` (½ Seite) |
| W13 | Konzept: Continual Learning | ✅ | **Hoch** — Nutzer-Feedback → neue Rezepte in die Wissensbasis | `docs/reflexion_continual.md` (½ Seite) |
| W14 | Reflexion: Responsible AI | ✅ | **Hoch** — Allergene, Ernährungssicherheit, Küchen-Bias, Halluzination | `docs/reflexion_responsible_ai.md` (½ Seite) |

## Umsetzungsstand (2026-06-03)

| Bereich | Stand |
|---------|-------|
| **P1** Tool-Use | ✅ erfüllt |
| **P2** TAO ≥3 sichtbar | ✅ erfüllt (Orchestrator-Tool-Zyklen + Sub-Agent + TAO im Terminal/GUI) |
| **P3** Framework | ✅ erfüllt (LangGraph) |
| **P4** README | ✅ erfüllt (inkl. Architektur, Start, Beispiel) |
| **P5** ≥10 Commits | ⏳ offen — noch zu committen |
| **W1** Multi-Agent | ✅ Orchestrator + Recherche-Sub-Agent |
| **W2** Vision | ✅ Code fertig (`app/tools/vision.py`); visueller Nachweis mit Foto noch erbringen |
| **W3/W4** RAG / Agentic RAG | 🟡 Andockstelle steht — Implementierung durch Kollegen (Phase 2b) |
| **W5** Observability | ✅ strukturiertes JSON-Logging |
| **W6** HTTP-API | ✅ FastAPI `/chat` |
| **W7** Container | ✅ Dockerfile + `docker compose up` |
| **W8** Tests | ✅ 14 Tests (shopping_list, vision, service, api) |
| **W9** Input-Validierung | ✅ Pydantic + Bild-/Fehlerbehandlung |
| **W10** CI/CD | ✅ GitHub Actions (Tests bei Push) |
| **W11** `/health` | ✅ vorhanden |
| **W12/13/14** Reflexionen | ✅ `docs/reflexion_*.md` |

**Erfüllt bzw. code-fertig: 12 von 14 W** (alle außer W3/W4, die der Kollege baut) — plus
alle Pflichtanforderungen außer der noch ausstehenden Commit-Historie (P5).

---

**Ursprüngliches Zielbild:** alle **14 von 14 W** — jedes fachlich begründet. Auslöser: Wir bauen
eine **Streamlit-GUI** mit getrenntem **FastAPI-Backend**; dadurch sind W6 (HTTP-API) und
W11 (`/health`) keine aufgesetzten Features mehr, sondern haben mit der GUI einen echten
Konsumenten. Falls Zeit knapp wird, sind W6/W11 die ersten Kandidaten zum Streichen — die
übrigen 12 liegen weiterhin klar über der 11er-Hürde.
