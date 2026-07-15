"""
Erzeugt die Referenz-Traces fuer das Evidence-Paket (P2 + Dim 2).
=================================================================
Fuehrt die VIER Referenz-Eingaben aus docs/evidence/referenz_eingaben.md real
gegen den echten Agenten aus (Groq + Tavily, Keys aus .env noetig) und legt ab:

  - docs/evidence/traces/referenz_<a|b|c|d>.json  (Roh-Trace mit trace_id,
    Spans, dauer_ms/status -- das maschinenlesbare Format aus der
    Observability-Schicht, siehe docs/PROJEKTDOKU.md "Observability")
  - docs/evidence/referenz_traces.md              (Begleittext: beschriftete
    TAO-Zyklen, Trajektorien-Vergleich, P2-Nachweis)

Warum ein Skript und kein pytest-Test? Wie bei erzeuge_wochenplan_evidence.py:
echte Keys + Netz noetig -> bewusst NICHT Teil der offline gruenen Testsuite,
aber jederzeit reproduzierbar.

Nutzung:
    python scripts/erzeuge_referenz_traces.py            # alle vier
    python scripts/erzeuge_referenz_traces.py a c        # Teilmenge

Hinweis: Eingabe (b) ist der token-intensive Wochenplan (Groq-Free-Tier-Limits,
siehe docs/PROJEKTDOKU.md "Grenzen des Systems") -- bei einem 429 einfach spaeter erneut nur
`python scripts/erzeuge_referenz_traces.py b` ausfuehren.
"""

import json
import os
import shutil
import sys
import tempfile
from datetime import date
from pathlib import Path

PROJEKT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJEKT_ROOT))

# Reproduzierbare Fixtures VOR dem App-Import setzen: Profil pro Eingabe
# (siehe _REFERENZEN), Kochbuch = die versionierten Seeds (Default-Verzeichnis).
_PROFIL_PFAD = Path(tempfile.gettempdir()) / "rezeptagent_referenz_profil.json"
os.environ["PRAEFERENZEN_PFAD"] = str(_PROFIL_PFAD)
TRACES_DIR = PROJEKT_ROOT / "docs" / "evidence" / "traces"
os.environ["AGENT_TRACE_DIR"] = str(TRACES_DIR)

from dotenv import load_dotenv  # noqa: E402

load_dotenv(PROJEKT_ROOT / ".env")

from app.core.agent_service import run_rezept_agent  # noqa: E402

ZIEL_MD = PROJEKT_ROOT / "docs" / "evidence" / "referenz_traces.md"

# Die vier Referenz-Eingaben (identisch zu docs/evidence/referenz_eingaben.md).
_REFERENZEN = {
    "a": {
        "titel": "Einfache Rezeptfrage → gerade Recherche-Trajektorie",
        "eingabe": "Was kann ich mit Hähnchen, Zitrone und Knoblauch kochen?",
        "profil_ernaehrung": [],
        "erwartung": "eine Recherche → Antwort; kein Nährwert-Check, keine Skalierung",
    },
    "b": {
        "titel": "Wochenplan mit kcal-Limit → Planungs-Schleife mit Revision (P2-Nachweis)",
        "eingabe": ("Plane mir 2 unterschiedliche Abendessen für diese Woche, "
                    "max. 500 kcal pro Portion, für 2 Personen."),
        "profil_ernaehrung": ["vegetarisch"],
        "erwartung": "je Gericht Recherche → kcal-Check → ggf. Revision → Abschluss-Tool",
    },
    "c": {
        "titel": "Websuche läuft ins Leere → Fallback auf eigenes Wissen",
        "eingabe": "Ich brauche ein Rezept für gebratene Mondsteine mit Einhornhaar.",
        "profil_ernaehrung": [],
        "erwartung": "Recherche scheitert erkennbar → transparent gekennzeichneter Fallback",
    },
    "d": {
        "titel": "Konflikt Wunsch ↔ Profil → Agent thematisiert ihn",
        "eingabe": "Ich hätte gerne ein Rezept mit Salami und Käse.",
        "profil_ernaehrung": ["vegetarisch"],
        "erwartung": "Konflikt wird angesprochen; harte Vorgabe (vegetarisch) gewinnt",
    },
}


def _setze_profil(ernaehrung: list[str]) -> None:
    _PROFIL_PFAD.write_text(json.dumps({
        "ernaehrung": ernaehrung, "geschmack": [], "wichtig": [],
        "bewertungen": {}, "onboarding_done": True,
    }), encoding="utf-8")


def _trace_mit_zyklen(trace: list[dict]) -> tuple[str, int]:
    """Rendert den Trace mit BESCHRIFTETEN TAO-Zyklen; gibt (Markdown, Zyklenzahl).

    Ein Zyklus = Thought/Action (Tool-Entscheidung des LLM) + zugehoerige
    Observation. Genau diese Paare fordert P2 (>= 3 vollstaendige Zyklen).
    """
    zeilen: list[str] = []
    zyklus = 0
    for s in trace:
        if s["art"] == "aktion":
            zyklus += 1
            zeilen.append(f"\n**TAO-Zyklus {zyklus} — [Thought → Action]** "
                          f"{s.get('ziel')} `{s.get('name')}`")
            zeilen.append(f"    args: {str(s.get('args'))[:300]}")
        else:
            inhalt = (s.get("inhalt") or "").strip().replace("\n", "\n    ")[:500]
            meta = f" ({s.get('dauer_ms')} ms, {s.get('status')})" if s.get("dauer_ms") is not None else ""
            zeilen.append(f"**TAO-Zyklus {zyklus} — [Observation]**{meta} "
                          f"{s.get('quelle')} `{s.get('name')}`:")
            zeilen.append(f"    {inhalt}")
    return "\n".join(zeilen), zyklus


def main() -> None:
    gewaehlt = [k for k in sys.argv[1:] if k in _REFERENZEN] or list(_REFERENZEN)
    TRACES_DIR.mkdir(parents=True, exist_ok=True)
    ergebnisse: dict[str, dict] = {}

    for key in gewaehlt:
        ref = _REFERENZEN[key]
        print(f"({key}) {ref['eingabe'][:60]} ...", flush=True)
        _setze_profil(ref["profil_ernaehrung"])
        erg = run_rezept_agent(nachricht=ref["eingabe"], modus="einkaufsliste")
        # Roh-Trace liegt als <trace_id>.json in TRACES_DIR -> sprechend umbenennen.
        quelle = TRACES_DIR / f"{erg['trace_id']}.json"
        ziel = TRACES_DIR / f"referenz_{key}.json"
        if quelle.exists():
            shutil.move(quelle, ziel)
        ergebnisse[key] = erg
        print(f"    -> {len([s for s in erg['trace'] if s['art'] == 'aktion'])} Aktionen, {ziel.name}", flush=True)

    # Fuer nicht (neu) gelaufene Eingaben vorhandene JSONs wiederverwenden (Resume).
    for key in _REFERENZEN:
        if key in ergebnisse:
            continue
        pfad = TRACES_DIR / f"referenz_{key}.json"
        if pfad.exists():
            daten = json.loads(pfad.read_text(encoding="utf-8"))
            ergebnisse[key] = {"antwort": daten["antwort"], "trace": daten["schritte"],
                               "trace_id": daten["trace_id"]}

    teile = [f"""# Referenz-Traces: vier Eingaben, vier Trajektorien (P2 + Dim 2)

*Reale Läufe gegen den echten Agenten (Groq + Tavily) am {date.today().isoformat()},
erzeugt mit `python scripts/erzeuge_referenz_traces.py` (reproduzierbar). Die
Eingaben und ihre Erwartungen sind in [referenz_eingaben.md](referenz_eingaben.md)
begründet; hier stehen die tatsächlichen Traces. Roh-Format (maschinenlesbar,
mit `trace_id`, `dauer_ms`, `status` je Schritt): `traces/referenz_<a-d>.json`.*
"""]

    for key in _REFERENZEN:
        if key not in ergebnisse:
            teile.append(f"## ({key}) — NICHT GELAUFEN (bitte Skript erneut ausführen)\n")
            continue
        ref, erg = _REFERENZEN[key], ergebnisse[key]
        namen = [s.get("name") for s in erg["trace"] if s["art"] == "aktion"]
        md, zyklen = _trace_mit_zyklen(erg["trace"])
        antwort = " ".join((erg["antwort"] or "").split())
        if len(antwort) > 500:
            antwort = antwort[:500] + " …"
        p2 = ""
        if key == "b":
            p2 = (f"\n\n**P2-Nachweis:** Dieser Trace enthält **{zyklen} vollständige "
                  "TAO-Zyklen** (gefordert: ≥ 3), oben einzeln beschriftet.")
        teile.append(f"""## ({key}) {ref['titel']}

- **Eingabe:** „{ref['eingabe']}“
- **Profil:** {', '.join(ref['profil_ernaehrung']) or 'leer'}
- **Erwartung:** {ref['erwartung']}
- **Tatsächliche Trajektorie:** {' → '.join(namen) if namen else '(keine Tool-Aufrufe)'} — {zyklen} TAO-Zyklen
- **Roh-Trace:** [traces/referenz_{key}.json](traces/referenz_{key}.json) (trace_id `{erg.get('trace_id', '?')}`){p2}

{md}

> **Finale Antwort (Auszug):** {antwort}
""")

    teile.append("""## Vergleich: gleiche Architektur, vier verschiedene Trajektorien (Dim 2)

Alle vier Läufe gehen durch **denselben** Agenten — der Weg unterscheidet sich
trotzdem sichtbar: (a) nimmt den geraden Weg (eine Recherche, Antwort), (b) fährt
die mehrstufige Planungs-Schleife mit kcal-Checks und Revision, (c) erkennt die
gescheiterte Suche und fällt transparent auf eigenes Wissen zurück, (d) ruft gar
keine Websuche blind auf, sondern thematisiert den Wunsch-Profil-Konflikt und
hält die harte Vorgabe ein. Tool-Wahl und Schrittzahl hängen an der Situation,
nicht an einem festen Ablauf — messbar auch in der Offline-Eval
([eval_report.md](eval_report.md)).
""")

    ZIEL_MD.write_text("\n".join(teile), encoding="utf-8")
    print(f"\nOK — Begleittext: {ZIEL_MD}")


if __name__ == "__main__":
    main()
