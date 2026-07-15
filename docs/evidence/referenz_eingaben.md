# Referenz-Eingaben — der Agent reagiert *different* auf verschiedene Eingaben (Dim 2)

> **Reale Läufe zu diesen vier Eingaben** (beschriftete TAO-Zyklen + Roh-Traces):
> [referenz_traces.md](referenz_traces.md) — dieses Dokument hier beschreibt das
> *Soll*, dort steht das *Ist*.

Diese vier Eingaben erzeugen **nachweislich verschiedene Trajektorien** — gleiche
Architektur, unterschiedlicher Weg je nach Situation. Das ist die Antwort auf die
Prüferfrage *„Zeigt der Trace, dass der Agent wirklich denkt und entscheidet — oder
läuft immer derselbe feste Ablauf?"*

## Ausführen

**CLI:** `python main.py`, dann die Eingabe eintippen (TAO-Trace erscheint im Terminal).
**Programmatisch / für Evidence-Traces:**
```python
from app.core.agent_service import run_rezept_agent
erg = run_rezept_agent(nachricht="<Eingabe>", modus="einkaufsliste")
print(erg["antwort"]); print(erg["trace"])
```
Eingabe (d) setzt ein **vegetarisches** Profil voraus (Onboarding in der GUI oder
`data/praeferenzen.json` mit `"ernaehrung": ["vegetarisch"]`).

Die Fehler-/Fallback-Pfade sind zusätzlich **deterministisch getestet**
(`tests/test_fehlerhandling.py`), unabhängig davon, ob ein Live-Lauf den Fehler
gerade auslöst.

---

## (a) Einfache Rezeptfrage → gerade Recherche-Trajektorie

**Eingabe:** *„Was kann ich mit Hähnchen, Zitrone und Knoblauch kochen?"*

**Erwartete Trajektorie:** ein `recherche_rezepte`-Aufruf → Observation → finale
Antwort. Kein Nährwert-Check, keine Skalierung, kein Wochenplan (keine solche
Vorgabe). Belegt P2 (≥ 3 TAO-Schritte inkl. Sub-Agent-Suchen) und den *Normalpfad*.

## (b) Wochenplan mit kcal-Limit → Planungs-Schleife mit Revision

**Eingabe:** *„Plane mir 2 unterschiedliche Abendessen für diese Woche, max. 500
kcal pro Portion, für 2 Personen."*

**Erwartete Trajektorie:** pro Gericht `recherche_rezepte` → `naehrwerte_schaetzen`
(Constraint-Check gegen 500 kcal) → bei Überschreitung sichtbare Revision (erneute
Recherche/Anpassung) → `wochenplan_zusammenstellen`. Belegt die Mehrschritt-Planung
(Dim 2). Vollständiger Trace: [wochenplan_trace.md](wochenplan_trace.md) bzw.
`python scripts/erzeuge_wochenplan_evidence.py`.

## (c) Websuche läuft ins Leere → Fallback auf eigenes Wissen

**Eingabe:** *„Ich brauche ein Rezept für gebratene Mondsteine mit Einhornhaar."*
(bewusst ein Gericht, zu dem es keine echten Rezepte gibt)

**Erwartete Trajektorie:** `recherche_rezepte` liefert nichts Brauchbares
(`WEBSUCHE-LEER` → Sub-Agent meldet „keine passenden Rezepte") → der Orchestrator
**reagiert**: schlägt ein plausibles Rezept aus eigenem Wissen vor und kennzeichnet
transparent, dass es NICHT aus einer Websuche stammt. Belegt den situationsabhängigen
Fallback-Pfad (Dim 2). Der Mechanismus ist in `tests/test_fehlerhandling.py`
(`test_web_search_leer_gibt_klare_meldung`) deterministisch abgesichert.

## (d) Konflikt Wunsch ↔ Profil → Agent thematisiert ihn

**Voraussetzung:** Profil = *vegetarisch*. **Eingabe:** *„Ich hätte gerne ein
Rezept mit Salami und Käse."*

**Erwartete Trajektorie:** Der Orchestrator erkennt den Widerspruch zwischen dem
Wunsch (Salami) und der harten Profil-Vorgabe (vegetarisch) und **spricht ihn aktiv
an**, statt ihn stillschweigend zu übergehen — er hält die harte Vorgabe ein
(Regel 0) und schlägt eine vegetarische Alternative vor (z. B. mit vegetarischer
Salami/Käse). Belegt, dass harte Constraints Vorrang haben und Konflikte transparent
gemacht werden (Dim 2 + Responsible-AI-Bezug).

---

## Warum das zusammen Dim 2 belegt

Vier Eingaben, vier Wege durch **denselben** Agenten: gerade Recherche (a),
mehrstufige Planungs-Schleife mit Revision (b), Fallback nach Fehlschlag (c),
Konflikt-Auflösung (d). Kein fester Ablauf — die Tool-Wahl und der Pfad hängen an
der Situation.
