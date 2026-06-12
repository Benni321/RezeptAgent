"""
Praeferenz-Store (Ausbau "Wochenplaner" -- Memory: Profil + Bewertung)
=====================================================================
Persistiert Nutzer-Praeferenzen ueber Sessions hinweg:
  - geschmack:       dauerhafte Geschmacks-Tendenz (z. B. "mediterran", "scharf").
                     Dient als STANDARD-Vorbelegung der Pro-Rezept-Auswahl.
  - wichtig:         was dem Nutzer bei Gerichten generell wichtig ist
                     (z. B. "gesund", "schnell", "viel Gemuese").
  - bewertungen:     Rezept -> Sterne (1-5), das gelernte Signal.
  - onboarding_done: ob die anfaengliche Fragerunde durchlaufen wurde.

Designentscheidungen (bewusst -- in der README begruendet):
- PROFIL = STANDARD, PRO REZEPT UEBERSCHREIBBAR. Die dauerhafte Geschmacks-Tendenz
  ist nur die Vorbelegung; fuer die einzelne Anfrage waehlt der Nutzer neu (mal
  Lust auf Suesses). So ist Geschmack weder rein dauerhaft noch wird er doppelt
  abgefragt. Deshalb wird `geschmack` NICHT als Kontext-Text injiziert, sondern
  als Default an die Pro-Rezept-Auswahl gereicht (siehe agent_service.py).
- LESEN = Kontext, SCHREIBEN = deterministische Aktion (kein LLM). `wichtig` und
  die Bewertungen sind das DAUERHAFTE Signal und werden injiziert; das Setzen
  laeuft ueber schlanke API-Endpunkte, nicht ueber ein Agenten-Tool.
- Persistenz als schlichte JSON-Datei (kein DBMS): ein Nutzer, wenige Daten ->
  transparent, versionierbar, testbar; eine Datenbank waere Overkill.
- Defensiv: fehlende/kaputte Datei -> leeres Profil; Sterne werden auf 1..5
  geklemmt, damit ungueltige Eingaben nie in den Store gelangen (W9-Geist).

Pfad ueber Env PRAEFERENZEN_PFAD konfigurierbar (Default data/praeferenzen.json).
"""

import json
import os
from pathlib import Path
from typing import Optional

_DEFAULT_PFAD = os.getenv("PRAEFERENZEN_PFAD", "data/praeferenzen.json")


def _leeres_profil() -> dict:
    return {"ernaehrung": [], "geschmack": [], "wichtig": [], "bewertungen": {}, "onboarding_done": False}


def _pfad(pfad: Optional[str]) -> Path:
    return Path(pfad or _DEFAULT_PFAD)


def _tags(roh) -> list[str]:
    """Normalisiert eine Tag-Liste: getrimmt, dedupliziert, ohne Leere, sortiert."""
    return sorted({str(t).strip() for t in roh if str(t).strip()})


def lade(pfad: Optional[str] = None) -> dict:
    """Liest das Profil. Fehlt die Datei oder ist sie kaputt -> leeres Profil."""
    p = _pfad(pfad)
    if not p.exists():
        return _leeres_profil()
    try:
        daten = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return _leeres_profil()
    if not isinstance(daten, dict):
        return _leeres_profil()
    return {
        "ernaehrung": _tags(daten.get("ernaehrung", [])),
        "geschmack": _tags(daten.get("geschmack", [])),
        "wichtig": _tags(daten.get("wichtig", [])),
        "bewertungen": {
            str(r): int(s)
            for r, s in dict(daten.get("bewertungen", {})).items()
            if isinstance(s, (int, float))
        },
        "onboarding_done": bool(daten.get("onboarding_done", False)),
    }


def _speichere(daten: dict, pfad: Optional[str]) -> None:
    p = _pfad(pfad)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(daten, ensure_ascii=False, indent=2), encoding="utf-8")


def setze_profil(
    geschmack: list[str],
    wichtig: list[str],
    ernaehrung: Optional[list[str]] = None,
    pfad: Optional[str] = None,
) -> dict:
    """Setzt Ernaehrung + Geschmacks-Tendenz + Prioritaeten, markiert Onboarding als erledigt.

    `ernaehrung` (vegan, vegetarisch, glutenfrei ...) sind DAUERHAFTE, HARTE Vorgaben
    der Person -- sie gelten bei jeder Anfrage und werden vom Service als Muss-Vorgabe
    injiziert (siehe agent_service.py).
    """
    daten = lade(pfad)
    daten["ernaehrung"] = _tags(ernaehrung or [])
    daten["geschmack"] = _tags(geschmack)
    daten["wichtig"] = _tags(wichtig)
    daten["onboarding_done"] = True
    _speichere(daten, pfad)
    return daten


def speichere_bewertung(rezept: str, sterne: int, pfad: Optional[str] = None) -> dict:
    """Speichert eine Rezept-Bewertung (1..5 Sterne, geklemmt)."""
    daten = lade(pfad)
    daten["bewertungen"][rezept.strip()] = max(1, min(5, int(sterne)))
    _speichere(daten, pfad)
    return daten


def als_kontext_text(pfad: Optional[str] = None) -> str:
    """Rendert das DAUERHAFTE Signal (Prioritaeten + Bewertungen) als Kontext.

    Bewusst OHNE die Geschmacks-Tendenz -- die wird als Default an die
    Pro-Rezept-Auswahl gereicht (sonst doppelt). Kompakt gehalten, damit der
    Agent personalisiert, ohne den Kontext zu fluten.
    """
    daten = lade(pfad)
    teile: list[str] = []
    if daten["wichtig"]:
        teile.append("Dem Nutzer ist bei Gerichten generell wichtig: " + ", ".join(daten["wichtig"]) + ".")

    bewertungen = daten["bewertungen"]
    if bewertungen:
        gut = sorted(
            [(r, s) for r, s in bewertungen.items() if s >= 4],
            key=lambda x: x[1],
            reverse=True,
        )[:5]
        if gut:
            liste = ", ".join(f"{r} ({s} Sterne)" for r, s in gut)
            teile.append("Frueher gut bewertet (Aehnliches bevorzugen): " + liste + ".")
        schlecht = [r for r, s in bewertungen.items() if s <= 2][:5]
        if schlecht:
            teile.append("Frueher schlecht bewertet (eher meiden): " + ", ".join(schlecht) + ".")

    return "\n".join(teile)
