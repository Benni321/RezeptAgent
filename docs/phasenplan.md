# Phasenplan — RezeptAgent

*Stand: 2026-06-02 · Applied AI SS26 · HTWG Konstanz*

## Leitprinzip

> **Sinnhaftigkeit vor Checkbox.** Wir erfüllen eine Anforderung nur, wenn sie für
> einen Rezept-Agenten *wirklich* sinnvoll ist. Lieber wenige Komponenten sauber,
> begründet und verstanden, als viele Pseudo-Features.

Zwei Ziele, die wir auseinanderhalten:

1. **Schein bestehen** → Mindestmaß: alle Pflicht-Anforderungen **P1–P5** + **≥ 11 von 14**
   Wahlpflicht-Anforderungen. Das ist eine *Hürde*, keine Note.
2. **Gute Note** → Qualität, Tiefe und nachvollziehbare Designentscheidungen. Jede
   Funktionalität muss logisch begründbar sein („Warum dieser Agent? Warum dieses Tool?").

Detaillierte Anforderungsabdeckung: siehe [bewertungsmatrix.md](bewertungsmatrix.md).

---

## Zielarchitektur

Der Use-Case zerfällt in echte Teilaufgaben mit unterschiedlicher Expertise — genau
das Kriterium aus VL4, *wann* Multi-Agent sinnvoll ist (klar trennbare Schritte +
Kontext-Isolation). Wir bauen daher **bewusst minimal**: ein Orchestrator + ein
spezialisierter Recherche-Sub-Agent. Vision, RAG und Einkaufslogik bleiben **Tools**.
Davor eine **Oberfläche**, die dem Nutzer strukturierte Eingabe ermöglicht und dem
Agenten dadurch saubere, eindeutige Eingaben liefert.

```
   Nutzer (Browser)
       │  Text · Foto-Upload · Umschalter "vorhanden ↔ Einkaufsliste" · Filter
       ▼
 ┌──────────────────────┐
 │  Streamlit-GUI        │  strukturierte Eingabe + Rezept-/TAO-Anzeige
 └──────────┬───────────┘
            │  HTTP:  POST /chat   ·   GET /health
            ▼
 ┌──────────────────────┐
 │  FastAPI-Backend      │  [W6, W11] · Eingabe-Validierung mit Pydantic [W9]
 └──────────┬───────────┘
            ▼
 ┌────────────────────────────────┐
 │  Orchestrator-Agent             │  plant, entscheidet "vorhanden vs.
 │  LangGraph StateGraph           │  Einkaufsliste", ruft Tools auf,
 └───────────────┬─────────────────┘  fasst Ergebnis zusammen
   Tools           │ delegiert (echte Kontext-Isolation)
 ┌──────────┬──────┴──────┐      ▼
 ▼          ▼            ▼    ┌────────────────────────────┐
 vision_   rag_         shopping_   │ Recherche-Sub-Agent [W1]    │
 tool      retriever    list        │ iterative Websuche (Tavily), │
 Foto→     lokale Re-   fehlende    │ aggregiert in eigenem        │
 Zutaten   zept-Wissens-Zutaten →   │ Kontext → strukturierte      │
 (VLM)[W2] basis(Chroma)Liste       │ Rezeptliste zurück           │
           [W3/W4]                  └────────────────────────────┘
```

**Warum diese Aufteilung sinnvoll ist (nicht nur, um Anforderungen abzuhaken):**
- **Multi-Agent [W1]:** Die Websuche erzeugt viel „Rauschen" (mehrere Treffer, Seiteninhalte).
  Ein **isolierter Recherche-Agent** verarbeitet das in eigenem Kontext und gibt dem
  Orchestrator nur eine saubere Zusammenfassung → Orchestrator-Kontext bleibt schlank
  (VL4: Kontext-Isolation). Vision/RAG/Einkauf brauchen keinen Mehrschritt-Loop → bleiben
  **Tools** (VL5/VL7-Muster). Kein Agent um des Agenten willen.
- **GUI + API [W6/W11]:** Eine getrennte Oberfläche braucht einen echten Konsumenten der
  API — `GUI → FastAPI /chat → Orchestrator`. Dadurch sind API und `/health` *fachlich
  begründet*, nicht aufgesetzt. Die strukturierte GUI (Umschalter, Foto-Upload, Filter)
  liefert dem Agenten eindeutige Eingaben und verhindert malformte Eingaben von vornherein
  (zahlt auf [W9] ein).

**Stack (alles kostenlos / reproduzierbar):** Streamlit (GUI) · FastAPI (Backend) ·
LangGraph (Agenten) · Groq (Text `llama-3.3-70b`, Vision = multimodales Llama-4-Modell) ·
Tavily (Web) · Chroma (Vektor-DB).

---

## Aktueller Stand (Phase 1 — erledigt)

- LangGraph-ReAct-Agent (`create_react_agent`), Modell Groq `llama-3.3-70b`.
- Ein echtes Tool: `web_search` (Tavily) → **P1** erfüllt.
- TAO-Zyklus wird im Terminal sichtbar ausgegeben (`main.py`).
- README mit Framework-Begründung → **P3/P4** weitgehend erfüllt.

**Offene Baustellen aus Phase 1:**
- TAO zeigt bei einer einzelnen Suche nur ~1 Zyklus → für **P2** (≥3 Iterationen) eine
  repräsentative Eingabe definieren, die mehrere TAO-Schritte auslöst.
- Erst **1 Commit** → ab jetzt feature-weise committen (**P5**: ≥10).
- README-Inkonsistenz: nennt `OPENAI_API_KEY`, Code nutzt Groq → angleichen.

---

## Phasen

> Granularität: **jede Teilaufgabe = ein Commit**. Damit erfüllt sich P5 nebenbei und
> die Historie zeigt echten inkrementellen Fortschritt.

### Phase 2 — Fachlicher Kern
- **2a · Multi-Agent + sichtbarer TAO [W1, P2]** — Orchestrator als LangGraph-Graph,
  Recherche-Sub-Agent ausgliedern. Repräsentative Demo-Eingabe mit ≥3 TAO-Schritten.
- **2b · RAG + Agentic RAG [W3, W4]** — kleine kuratierte Rezept-Wissensbasis (Chroma),
  Retriever als Tool, das der Agent selbst aufruft. *(Owner: Kollege, ab 2026-06-03)*
- **2c · Vision [W2]** — Kühlschrank-Foto → Zutatenliste über Groq-VLM, fließt als Tool
  in den Orchestrator. Erkannte Zutaten werden dem Nutzer zur Bestätigung gezeigt
  (Human-in-the-Loop gegen VLM-Halluzination, VL5).

### Phase 3 — Service & Oberfläche
- **3a · FastAPI-Backend [W6, W11]** — `POST /chat` (Text + optional Bild), `GET /health`.
  Ruft den Orchestrator auf.
- **3b · Eingabe-Validierung & Fehlerbehandlung [W9]** — Pydantic-Schemas; leere Anfrage,
  Nicht-Essen-Foto, unlesbares Bild, API-Timeout → graceful mit klarer Nutzermeldung.
- **3c · Streamlit-GUI** — strukturierte Eingabe (Text/Zutaten, Foto-Upload, Umschalter
  „vorhanden ↔ Einkaufsliste", Filter), Rezept-Anzeige und **aufklappbarer TAO-Trace**
  (zeigt P2 anschaulich). Spricht das FastAPI-Backend an.
- **3d · Observability [W5]** — strukturiertes Logging des TAO + jedes Tool-Aufrufs
  (JSON-Logs/Tracing). Dient Debugging *und* Sicherheit (VL3).

### Phase 4 — Qualität & Ops
- **4a · Tests [W8]** — ≥5 sinnvolle Unit-/Integrationstests (Tool-Verträge, Filterlogik,
  Validierung, RAG-Retrieval, API-Endpunkt/`/health`).
- **4b · Container [W7]** — Dockerfile + `docker-compose.yml` (GUI + API + Chroma), startet
  via `docker compose up`.
- **4c · CI/CD [W10]** — GitHub Actions: bei Push Tests + Lint automatisch ausführen.

### Phase 5 — Doku & Reflexion (Abgabe)
- Ausführliche **Projektdoku** (Markdown): Architektur, Designentscheidungen, Funktionsweise,
  Grenzen.
- **Anforderungs-Nachweistabelle** aktualisieren ([bewertungsmatrix.md](bewertungsmatrix.md))
  inkl. Belege (Screenshots/Logs in `docs/evidence/`).
- **Reflexionstexte** [W12 Drift, W13 Continual Learning, W14 Responsible AI] — für den
  Rezept-Agenten konkret (saisonale/Trend-Drift; Nutzer-Feedback → neue Rezepte; Allergene/
  Ernährungssicherheit, Küchen-Bias, halluzinierte Rezepte).

**Mit GUI + API decken wir bis zu 14 von 14 W ab** — alle fachlich begründet.

---

## Was wir morgen im Fortschritts-Check zeigen
1. **Stand:** Phase 1 läuft (Live-Terminal: Anfrage → TAO → Rezept).
2. **Plan:** diese Zielarchitektur + Phasenplan (dieses Dokument), inkl. GUI-Vision.
3. **Nächster Schritt:** RAG (2b) startet, Multi-Agent (2a) parallel.
