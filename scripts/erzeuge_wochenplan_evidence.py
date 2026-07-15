"""
Erzeugt den Wochenplan-Evidence-Trace (Bewertungs-Dimension 2, P2).
===================================================================
Fuehrt EINEN realen Wochenplan-Lauf gegen den echten Agenten aus (Groq + Tavily,
Keys aus .env noetig) und schreibt den TAO-Trace nach
docs/evidence/wochenplan_trace.md.

Warum ein Skript und kein pytest-Test? Der Lauf braucht echte API-Keys und
Netzugriff und ist damit NICHT Teil der (gemockten, offline gruenen) Testsuite.
Er erzeugt einen menschlich lesbaren Nachweis fuer die Abgabe.

Nutzung:
    python scripts/erzeuge_wochenplan_evidence.py

Hinweis (ehrliche Grenze): Ein Wochenplan mit mehreren Recherchen + Naehrwert-
Checks ist token-intensiv. Im Groq-Free-Tier gibt es ein Minuten- (TPM) UND ein
Tages-Limit (TPD). Bei erschoepftem Budget bricht der Lauf mit einem 429 ab --
dann spaeter erneut ausfuehren (frisches Budget) oder einen bezahlten Tier nutzen.
Laeuft mit dem Standardmodell aus GROQ_MODEL (Default qwen/qwen3-32b).
"""

import json
import os
import sys
import tempfile
from datetime import date
from pathlib import Path

# Projekt-Root in den Pfad legen, damit das Skript von ueberall lauffaehig ist
# (z. B. `python scripts/erzeuge_wochenplan_evidence.py` aus dem Repo-Root).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Reproduzierbares, schlankes Test-Profil (statt des zufaellig gewachsenen echten
# Nutzerprofils): nur die harte Vorgabe "vegetarisch", keine vielen weichen Tags.
# So ist der Trace reproduzierbar UND der Agent sucht nicht endlos nach einem
# Rezept, das ein ueberladenes Profil perfekt erfuellt (haelt den Kontext schlank).
# WICHTIG vor dem agent_service-Import setzen (praeferenzen liest den Pfad beim Import).
_PROFIL = {
    "ernaehrung": ["vegetarisch"], "geschmack": [], "wichtig": [],
    "bewertungen": {}, "onboarding_done": True,
}
_PROFIL_PFAD = Path(tempfile.gettempdir()) / "rezeptagent_evidence_profil.json"
_PROFIL_PFAD.write_text(json.dumps(_PROFIL), encoding="utf-8")
os.environ["PRAEFERENZEN_PFAD"] = str(_PROFIL_PFAD)

from app.core.agent_service import run_rezept_agent

ANFRAGE = (
    "Plane mir 2 UNTERSCHIEDLICHE Abendessen fuer diese Woche, maximal 500 kcal "
    "pro Portion, fuer 2 Personen. Die Gerichte sollen sich klar unterscheiden."
)
ZIELDATEI = "docs/evidence/wochenplan_trace.md"


def _trace_als_markdown(trace: list[dict]) -> str:
    zeilen: list[str] = []
    zyklus = 0
    for s in trace:
        if s["art"] == "aktion":
            zyklus += 1
            zeilen.append(f"\n**[Thought → Action {zyklus}]** {s.get('ziel')} `{s.get('name')}`")
            zeilen.append(f"    args: {str(s.get('args'))[:400]}")
        else:
            inhalt = (s.get("inhalt") or "").strip().replace("\n", "\n    ")
            zeilen.append(f"**[Observation]** {s.get('quelle')} `{s.get('name')}`:")
            zeilen.append(f"    {inhalt[:650]}")
    return "\n".join(zeilen)


def main() -> None:
    print("Starte Wochenplan-Lauf (echte API, kann etwas dauern) ...", flush=True)
    erg = run_rezept_agent(nachricht=ANFRAGE, modus="einkaufsliste")

    namen = [s.get("name") for s in erg["trace"] if s["art"] == "aktion"]
    dok = f"""# Evidence: Wochenplaner — plan→prüfe→revidiere-Schleife (Dim 2)

*Realer Lauf am {date.today().isoformat()} mit echten API-Keys (Groq + Tavily),
nicht gemockt. Reproduzierbar über `python scripts/erzeuge_wochenplan_evidence.py`.
Belegt Bewertungs-Dimension 2 (Mehrschritt-Planung, situationsabhängige Tool-Wahl,
Constraint-/Fehlerhandling) und P2 (TAO ≥ 3). `parallel_tool_calls=False` erzwingt
EINEN Tool-Aufruf pro Schritt → sequenzielle Schleife.*

## Eingabe
> {ANFRAGE}

Reproduzierbares Test-Profil (vom Skript gesetzt): harte Vorgabe **vegetarisch**,
keine weichen Tags -- damit der Lauf reproduzierbar und schlank bleibt.

## Werkzeug-Aufrufe in diesem Lauf
- recherche_rezepte: {namen.count('recherche_rezepte')}× (je geplantem Gericht — im
  Einzelrezept-Modus wäre nur EINE Recherche erlaubt)
- naehrwerte_schaetzen: {namen.count('naehrwerte_schaetzen')}× (Constraint-Check gegen das kcal-Limit)
- portionen_skalieren: {namen.count('portionen_skalieren')}×
- wochenplan_zusammenstellen: {namen.count('wochenplan_zusammenstellen')}× (deterministischer Abschluss)
- Schritte gesamt: {len(erg['trace'])}

## TAO-Trace (roh, je Observation auf 650 Zeichen gekürzt)
{_trace_als_markdown(erg['trace'])}

## Finale Antwort des Agenten
{erg['antwort']}
"""
    with open(ZIELDATEI, "w", encoding="utf-8") as f:
        f.write(dok)
    print(f"OK — {len(erg['trace'])} Schritte, Trace geschrieben nach {ZIELDATEI}")


if __name__ == "__main__":
    main()
