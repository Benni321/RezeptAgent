"""
Erzeugt den Vision-Nachweis (W2): echtes Kuehlschrank-Foto -> Zutaten -> Rezept.
================================================================================
Fuehrt EINEN realen Lauf mit dem Foto docs/evidence/kuehlschrank_foto.jpg aus
(Groq-VLM fuer die Zutatenerkennung + kompletter Agenten-Lauf) und schreibt den
Nachweis nach docs/evidence/vision_nachweis.md: Foto, erkannte Zutatenliste,
daraus entstandener Rezeptvorschlag, Trace.

Warum ein Skript und kein pytest-Test? Echte Keys + Netz + VLM noetig -> bewusst
NICHT Teil der offline gruenen Testsuite (die Vision-Logik selbst ist in
tests/test_vision.py gemockt getestet), aber jederzeit reproduzierbar.

Nutzung:
    python scripts/erzeuge_vision_evidence.py [pfad/zum/foto.jpg]
"""

import json
import os
import sys
import tempfile
from datetime import date
from pathlib import Path

PROJEKT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJEKT_ROOT))

# Leeres, reproduzierbares Profil (der Nachweis soll das Foto belegen, nicht
# die Personalisierung); Roh-Trace landet neben den Referenz-Traces.
_PROFIL_PFAD = Path(tempfile.gettempdir()) / "rezeptagent_vision_profil.json"
_PROFIL_PFAD.write_text(json.dumps({"ernaehrung": [], "geschmack": [], "wichtig": [],
                                    "bewertungen": {}, "onboarding_done": True}), encoding="utf-8")
os.environ["PRAEFERENZEN_PFAD"] = str(_PROFIL_PFAD)
TRACES_DIR = PROJEKT_ROOT / "docs" / "evidence" / "traces"
os.environ["AGENT_TRACE_DIR"] = str(TRACES_DIR)

from dotenv import load_dotenv  # noqa: E402

load_dotenv(PROJEKT_ROOT / ".env")

from app.core.agent_service import run_rezept_agent  # noqa: E402

FOTO = Path(sys.argv[1]) if len(sys.argv) > 1 else PROJEKT_ROOT / "docs" / "evidence" / "kuehlschrank_foto.jpg"
ZIEL = PROJEKT_ROOT / "docs" / "evidence" / "vision_nachweis.md"
ANFRAGE = "Was kann ich aus meinem Kühlschrank kochen? Nutze, was auf dem Foto zu sehen ist."


def main() -> None:
    if not FOTO.exists():
        raise SystemExit(f"Foto nicht gefunden: {FOTO}")
    print(f"Starte Vision-Lauf mit {FOTO.name} (echte API) ...", flush=True)
    erg = run_rezept_agent(nachricht=ANFRAGE, modus="einkaufsliste",
                           image_bytes=FOTO.read_bytes(), image_mime="image/jpeg")

    quelle = TRACES_DIR / f"{erg['trace_id']}.json"
    ziel_json = TRACES_DIR / "vision_lauf.json"
    if quelle.exists():
        quelle.rename(ziel_json)

    zutaten = erg.get("erkannte_zutaten") or []
    namen = [s.get("name") for s in erg["trace"] if s["art"] == "aktion"]
    dok = f"""# Evidence W2: Multimodale Eingabe — Kühlschrank-Foto → Zutaten → Rezept

*Realer Lauf am {date.today().isoformat()} mit echtem Foto und echten API-Keys
(Groq-VLM `{os.getenv('GROQ_VISION_MODEL', 'meta-llama/llama-4-scout-17b-16e-instruct')}`
für die Zutatenerkennung, danach der normale Agenten-Lauf). Reproduzierbar über
`python scripts/erzeuge_vision_evidence.py`. Leeres Profil, damit der Nachweis
allein die Bildverarbeitung belegt.*

## 1. Eingabe-Foto (echter Kühlschrank)

![Kühlschrank-Foto](kuehlschrank_foto.jpg)

Anfrage dazu: „{ANFRAGE}“

## 2. Vom VLM erkannte Zutaten ({len(zutaten)})

{chr(10).join(f'- {z}' for z in zutaten) if zutaten else '- (keine erkannt)'}

*(Ablauf: Das Vision-Tool wandelt das Foto VOR dem Agenten-Lauf in diese
Zutatenliste um — der Orchestrator bleibt rein text-/tool-basiert, siehe
`app/tools/vision.py`. Die Liste wird der Nachricht angehängt.)*

## 3. Trajektorie des anschließenden Agenten-Laufs

{' → '.join(namen) if namen else '(keine Tool-Aufrufe)'} — Roh-Trace: [traces/vision_lauf.json](traces/vision_lauf.json)

## 4. Daraus entstandener Rezeptvorschlag

{erg['antwort']}
"""
    ZIEL.write_text(dok, encoding="utf-8")
    print(f"OK — {len(zutaten)} Zutaten erkannt, Nachweis: {ZIEL}")


if __name__ == "__main__":
    main()
