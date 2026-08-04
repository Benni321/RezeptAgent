"""
Eval-Runner: fuehrt das Testset gegen den ECHTEN Agenten aus (VL09).
====================================================================
Braucht echte API-Keys (Groq + Tavily) und Netz — ist deshalb bewusst NICHT
Teil von pytest/CI (gleiche Begruendung wie scripts/erzeuge_wochenplan_evidence.py:
die Testsuite bleibt offline gruen, Evidence entsteht per Skript). Die
Verifier-LOGIK ist dagegen ohne Keys getestet (tests/test_eval_verifier.py).

Ablauf pro Fall:
  1. Profil-Fixture aus dem Testset in eine Temp-Datei schreiben und ueber
     PRAEFERENZEN_PFAD injizieren (das echte Nutzerprofil bleibt unberuehrt,
     jeder Fall startet mit definiertem Memory -> reproduzierbar).
  2. run_rezept_agent ausfuehren; Fehler werden als Ergebnis "fehler"
     festgehalten statt den Lauf abzubrechen (ein 429 soll nicht 13 fertige
     Ergebnisse wegwerfen).
  3. Checks aus evals/verifier.py auswerten (ternaer) und den ROH-Trace als
     JSON nach docs/evidence/eval_traces/<id>.json legen.

Der Markdown-Report (docs/evidence/eval_report.md) wird am Ende aus ALLEN
vorhandenen Trace-JSONs neu gebaut. Dadurch kann man einen abgebrochenen Lauf
mit `--nur <id,...>` fortsetzen, ohne fertige Faelle erneut zu bezahlen
(Groq-Free-Tier hat ein Tages-Token-Limit, siehe docs/PROJEKTDOKU.md "Grenzen des Systems").

Nutzung:
    python evals/run_eval.py                 # alle Faelle
    python evals/run_eval.py --nur id1,id2   # Teilmenge / Resume
    python evals/run_eval.py --pause 30      # Sekunden Pause zwischen Faellen
"""

import argparse
import json
import os
import sys
import tempfile
import time
from datetime import date
from pathlib import Path

PROJEKT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJEKT_ROOT))

# Profil-Fixture-Pfad VOR dem App-Import setzen (praeferenzen liest die Env-Variable
# beim Import). Die Datei wird pro Fall neu geschrieben.
_PROFIL_PFAD = Path(tempfile.gettempdir()) / "rezeptagent_eval_profil.json"
os.environ["PRAEFERENZEN_PFAD"] = str(_PROFIL_PFAD)

# Kochbuch-Fixture (RAG-Wissensbasis, W3/W4): pro Fall definiert, sonst LEER --
# damit haengt kein Ergebnis vom lokalen data/rezepte/-Bestand ab (reproduzierbar).
_KOCHBUCH_DIR = Path(tempfile.gettempdir()) / "rezeptagent_eval_kochbuch"
os.environ["KOCHBUCH_DIR"] = str(_KOCHBUCH_DIR)

from dotenv import load_dotenv  # noqa: E402

load_dotenv(PROJEKT_ROOT / ".env")

from evals.verifier import (  # noqa: E402
    BESTANDEN, NEUTRAL, VERLETZT, SYMBOL, fall_status, pruefe_fall,
)

TESTSET = PROJEKT_ROOT / "evals" / "testset.json"
TRACES_DIR = PROJEKT_ROOT / "docs" / "evidence" / "eval_traces"
REPORT = PROJEKT_ROOT / "docs" / "evidence" / "eval_report.md"

# Roh-Traces des Agenten (W5/VL09): Jeder Run schreibt zusaetzlich seine
# <trace_id>.json hierhin — dieselbe Quelle nutzt die Evidence-Erzeugung.
# setdefault: eine bewusst gesetzte Umgebung gewinnt.
os.environ.setdefault("AGENT_TRACE_DIR", str(TRACES_DIR / "runs"))

_LEERES_PROFIL = {"ernaehrung": [], "geschmack": [], "wichtig": [], "bewertungen": {}}


def _setze_profil(profil: dict | None) -> None:
    """Schreibt die Profil-Fixture des Falls (oder ein leeres Profil) in die Temp-Datei."""
    daten = dict(profil or _LEERES_PROFIL)
    daten["onboarding_done"] = True
    _PROFIL_PFAD.write_text(json.dumps(daten, ensure_ascii=False), encoding="utf-8")


def _setze_kochbuch(rezepte: list[dict]) -> None:
    """Richtet die Kochbuch-Fixture des Falls ein (vorher leeren -> kein Zustand
    schwappt zwischen Faellen ueber). Schreibt die JSONs direkt im Store-Format."""
    _KOCHBUCH_DIR.mkdir(parents=True, exist_ok=True)
    for alt in _KOCHBUCH_DIR.glob("*.json"):
        alt.unlink()
    for i, r in enumerate(rezepte):
        eintrag = {"titel": r["titel"], "zutaten": r["zutaten"],
                   "sterne": r.get("sterne"), "kcal_pro_portion": r.get("kcal"),
                   "quelle": "eval-fixture"}
        (_KOCHBUCH_DIR / f"fixture_{i}.json").write_text(
            json.dumps(eintrag, ensure_ascii=False), encoding="utf-8")


def fuehre_fall_aus(fall: dict) -> dict:
    """Fuehrt EINEN Testfall gegen den echten Agenten aus und verifiziert ihn."""
    from app.core.agent_service import run_rezept_agent  # lazy: erst nach Env-Setup

    _setze_profil(fall.get("profil"))
    _setze_kochbuch(fall.get("kochbuch") or [])
    eingabe = fall["eingabe"]
    start = time.monotonic()
    ergebnis: dict = {
        "id": fall["id"],
        "beschreibung": fall["beschreibung"],
        "erwartet_schwer": bool(fall.get("erwartet_schwer")),
        "warum_schwer": fall.get("warum_schwer"),
        "eingabe": eingabe,
        "profil": fall.get("profil"),
        "kochbuch": fall.get("kochbuch"),
        "modell": os.getenv("GROQ_MODEL", "qwen/qwen3.6-27b"),
        # Modell-Split: Recherche-Sub-Agent und Naehrwert-Schaetzung laufen auf
        # einem eigenen (kleinen) Modell. Beide protokollieren, sonst waere bei
        # einem Deprecation-/Verhaltenswechsel des kleinen Modells im Report nur
        # das grosse zu sehen (siehe docs/reflexion_drift.md, Punkt 2b).
        "modell_klein": os.getenv("GROQ_MODEL_KLEIN", "llama-3.1-8b-instant"),
        "datum": date.today().isoformat(),
    }
    try:
        lauf = run_rezept_agent(
            nachricht=eingabe["nachricht"],
            modus=eingabe.get("modus", "einkaufsliste"),
            anmerkungen=eingabe.get("anmerkungen", ""),
        )
        antwort, trace = lauf["antwort"], lauf["trace"]
        checks = pruefe_fall(fall, antwort, trace)
        ergebnis.update({
            "fehler": None,
            "trace_id": lauf.get("trace_id"),  # verweist auf eval_traces/runs/<trace_id>.json
            "antwort": antwort,
            "trace": trace,
            "checks": [{"typ": c.typ, "status": c.status, "detail": c.detail} for c in checks],
            "fall_status": fall_status(checks),
        })
    except Exception as exc:  # Lauf-Fehler festhalten, restliche Faelle weiterlaufen lassen
        ergebnis.update({
            "fehler": f"{type(exc).__name__}: {exc}",
            "antwort": "", "trace": [], "checks": [], "fall_status": "fehler",
        })
    ergebnis["dauer_s"] = round(time.monotonic() - start, 1)
    return ergebnis


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def _zaehle(checks: list[dict], status: str) -> int:
    return sum(1 for c in checks if c["status"] == status)


def _tool_zusammenfassung(trace: list[dict]) -> str:
    namen = [s.get("name") for s in trace if s.get("art") == "aktion"]
    if not namen:
        return "—"
    return ", ".join(f"{n} {namen.count(n)}×" for n in dict.fromkeys(namen))


def baue_report(faelle_reihenfolge: list[str]) -> str:
    """Baut den Markdown-Report aus allen vorhandenen Trace-JSONs (in Testset-Reihenfolge)."""
    ergebnisse: list[dict] = []
    for fall_id in faelle_reihenfolge:
        pfad = TRACES_DIR / f"{fall_id}.json"
        if pfad.exists():
            ergebnisse.append(json.loads(pfad.read_text(encoding="utf-8")))

    alle_checks = [c for e in ergebnisse for c in e["checks"]]
    n_b, n_n, n_v = (_zaehle(alle_checks, s) for s in (BESTANDEN, NEUTRAL, VERLETZT))
    faelle_ok = sum(1 for e in ergebnisse if e["fall_status"] == BESTANDEN)
    faelle_fehler = sum(1 for e in ergebnisse if e["fall_status"] == "fehler")
    datum = max((e.get("datum", "") for e in ergebnisse), default=date.today().isoformat())
    modell = ergebnisse[0]["modell"] if ergebnisse else "?"
    modell_klein = ergebnisse[0].get("modell_klein", "?") if ergebnisse else "?"

    z = [
        "# Eval-Report: Constraint-Treue des RezeptAgenten (VL09)",
        "",
        f"*Reale Laeufe gegen den echten Agenten (Groq `{modell}` fuer Orchestrator/Wochenplan,*",
        f"*`{modell_klein}` fuer Recherche-Sub-Agent und Naehrwert-Schaetzung + Tavily), Stand {datum}.*",
        f"*Erzeugt mit `python evals/run_eval.py`; Checks: `evals/verifier.py` (programmatisch,*",
        "*ternaer, kein LLM-Judge — Begruendung in `evals/README.md`). Roh-Traces mit voller*",
        "*Antwort und allen TAO-Schritten: `docs/evidence/eval_traces/<fall-id>.json`.*",
        "",
        "## Gesamtquoten",
        "",
        f"- **Faelle:** {len(ergebnisse)} gelaufen, davon {faelle_ok} ohne Verletzung"
        + (f", {faelle_fehler} mit Lauf-Fehler" if faelle_fehler else ""),
        f"- **Checks:** {len(alle_checks)} gesamt — {SYMBOL[BESTANDEN]} {n_b} bestanden · "
        f"{SYMBOL[NEUTRAL]} {n_n} neutral · {SYMBOL[VERLETZT]} {n_v} verletzt",
        f"- **Bestanden-Quote (ohne neutral):** "
        + (f"{n_b}/{n_b + n_v} = {100 * n_b / (n_b + n_v):.0f}%" if (n_b + n_v) else "—"),
        "",
        "Legende: ✓ bestanden · ○ neutral (nicht entscheidbar/anwendbar) · ✗ verletzt.",
        "„Schwer“ = bewusst so gebaut, dass der Agent voraussichtlich scheitert",
        "(Material fuer die ehrliche Reflexion, siehe Testset).",
        "",
        "## Uebersicht",
        "",
        "| Fall | Schwer? | ✓ | ○ | ✗ | Aktionen | Dauer | Gesamt |",
        "|------|---------|---|---|---|----------|-------|--------|",
    ]
    for e in ergebnisse:
        aktionen = sum(1 for s in e["trace"] if s.get("art") == "aktion")
        gesamt = {"fehler": "⚠ Fehler"}.get(e["fall_status"], SYMBOL.get(e["fall_status"], "?"))
        z.append(
            f"| `{e['id']}` | {'ja' if e['erwartet_schwer'] else '—'} "
            f"| {_zaehle(e['checks'], BESTANDEN)} | {_zaehle(e['checks'], NEUTRAL)} "
            f"| {_zaehle(e['checks'], VERLETZT)} | {aktionen} | {e.get('dauer_s', '?')} s | {gesamt} |"
        )

    z += ["", "## Ergebnisse im Detail", ""]
    for e in ergebnisse:
        z.append(f"### `{e['id']}`" + (" — *bewusst schwerer Fall*" if e["erwartet_schwer"] else ""))
        z.append("")
        z.append(f"{e['beschreibung']}")
        if e.get("warum_schwer"):
            z.append(f"\n*Warum schwer:* {e['warum_schwer']}")
        z.append("")
        z.append(f"- **Eingabe:** „{e['eingabe']['nachricht']}“ (Modus `{e['eingabe'].get('modus', 'einkaufsliste')}`)")
        if e.get("profil"):
            z.append(f"- **Profil-Fixture:** `{json.dumps(e['profil'], ensure_ascii=False)}`")
        if e.get("kochbuch"):
            z.append("- **Kochbuch-Fixture:** " + ", ".join(r["titel"] for r in e["kochbuch"]))
        z.append(f"- **Trajektorie:** {_tool_zusammenfassung(e['trace'])}")
        if e["fehler"]:
            z.append(f"- **Lauf-Fehler:** `{e['fehler']}`")
            z.append("")
            continue
        z += ["", "| Check | Status | Detail |", "|-------|--------|--------|"]
        for c in e["checks"]:
            detail = c["detail"].replace("|", "\\|")
            z.append(f"| `{c['typ']}` | {SYMBOL[c['status']]} {c['status']} | {detail} |")
        auszug = " ".join((e["antwort"] or "").split())
        if len(auszug) > 320:
            auszug = auszug[:320] + " …"
        z += ["", f"> **Antwort (Auszug):** {auszug}", ""]
    return "\n".join(z) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Fuehrt das Eval-Testset gegen den echten Agenten aus.")
    parser.add_argument("--nur", help="Kommagetrennte Fall-IDs (Teilmenge/Resume)", default=None)
    parser.add_argument("--pause", type=float, default=20.0,
                        help="Sekunden Pause zwischen Faellen (schont das Groq-TPM-Limit)")
    args = parser.parse_args()

    testset = json.loads(TESTSET.read_text(encoding="utf-8"))
    faelle = testset["faelle"]
    reihenfolge = [f["id"] for f in faelle]
    if args.nur:
        gewaehlt = {s.strip() for s in args.nur.split(",")}
        unbekannt = gewaehlt - set(reihenfolge)
        if unbekannt:
            raise SystemExit(f"Unbekannte Fall-IDs: {sorted(unbekannt)}")
        faelle = [f for f in faelle if f["id"] in gewaehlt]

    TRACES_DIR.mkdir(parents=True, exist_ok=True)
    for i, fall in enumerate(faelle):
        print(f"[{i + 1}/{len(faelle)}] {fall['id']} ...", flush=True)
        ergebnis = fuehre_fall_aus(fall)
        (TRACES_DIR / f"{fall['id']}.json").write_text(
            json.dumps(ergebnis, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        status = ergebnis["fall_status"]
        print(f"    -> {status}" + (f" ({ergebnis['fehler']})" if ergebnis["fehler"] else "")
              + f", {ergebnis['dauer_s']} s", flush=True)
        if i + 1 < len(faelle) and args.pause > 0:
            time.sleep(args.pause)

    REPORT.write_text(baue_report(reihenfolge), encoding="utf-8")
    print(f"\nReport geschrieben: {REPORT}")
    print(f"Roh-Traces: {TRACES_DIR}/")


if __name__ == "__main__":
    main()
