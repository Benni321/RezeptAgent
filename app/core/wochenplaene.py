"""
Gespeicherte Wochenplaene: Ablage + Verwaltung fuer die "Meine Wochenplaene"-Seite
====================================================================================
Ein vom Wochenplan-Workflow (app/core/wochenplan_workflow.py) erzeugter Plan ist
nur eine Chat-Antwort -- ohne diese Ablage waere er nach dem Schliessen der GUI
verloren. Dieses Modul persistiert ihn auf ausdruecklichen Nutzerwunsch (POST
/wochenplan) als eigene JSON-Datei, damit er auf einer eigenen Seite wieder
auftaucht -- genau wie das Kochbuch (app/tools/kochbuch.py), aber ohne Retrieval:
hier gibt es nichts zu durchsuchen, nur eine Liste zum Anzeigen/Loeschen.

Bewusst deterministisch und ohne Agenten-Beteiligung (VL03: Schreiben ist eine
API-Aktion, kein Tool) -- dieselbe Begruendung wie beim Kochbuch-Schreibpfad.
"""

import json
import os
import re
import unicodedata
import uuid
from datetime import datetime
from pathlib import Path

_UMLAUTE = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})


def _wochenplaene_dir() -> Path:
    """Verzeichnis der gespeicherten Wochenplaene. Env WOCHENPLAENE_DIR wird
    bewusst zur LAUFZEIT gelesen (nicht beim Import), damit Tests es pro Lauf
    isoliert setzen koennen (gleiches Muster wie kochbuch._kochbuch_dir)."""
    return Path(os.getenv("WOCHENPLAENE_DIR", "data/wochenplaene"))


def _slug(text: str) -> str:
    s = text.lower().translate(_UMLAUTE)
    s = unicodedata.normalize("NFKD", s)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:40] or "wochenplan"


def lade_alle() -> list[dict]:
    """Liest alle gespeicherten Wochenplaene, neueste zuerst.

    Defensiv wie kochbuch.lade_alle: kaputte/fremde Dateien werden uebersprungen
    (W9-Geist), fehlendes Verzeichnis -> leere Liste.
    """
    verzeichnis = _wochenplaene_dir()
    if not verzeichnis.is_dir():
        return []
    plaene = []
    for pfad in verzeichnis.glob("*.json"):
        try:
            daten = json.loads(pfad.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(daten, dict) and daten.get("id") and isinstance(daten.get("gerichte"), list):
            plaene.append(daten)
    plaene.sort(key=lambda p: p.get("erstellt_am", ""), reverse=True)
    return plaene


def speichere(nachricht: str, antwort: str, gerichte: list[dict], titel: str = "") -> dict:
    """Speichert einen fertig geplanten Wochenplan als eigene JSON-Datei.

    Der Dateiname traegt einen Zeitstempel (anders als beim Kochbuch, das per
    Titel ueberschreibt): mehrere Wochenplaene mit demselben oder leerem Titel
    sollen NEBENEINANDER bestehen bleiben, nicht sich gegenseitig ersetzen.
    """
    verzeichnis = _wochenplaene_dir()
    verzeichnis.mkdir(parents=True, exist_ok=True)
    jetzt = datetime.now()
    titel = titel.strip() or f"Wochenplan vom {jetzt:%d.%m.%Y}"
    plan_id = f"{jetzt:%Y%m%d-%H%M%S}-{_slug(titel)}"
    if (verzeichnis / f"{plan_id}.json").exists():
        # Zwei Speicherungen in derselben Sekunde mit gleichem Titel wuerden sich
        # sonst gegenseitig ueberschreiben -- kurzer Zufalls-Suffix macht die ID
        # eindeutig, ohne die Lesbarkeit des Normalfalls zu verschlechtern.
        plan_id = f"{plan_id}-{uuid.uuid4().hex[:6]}"
    daten = {
        "id": plan_id,
        "titel": titel,
        "erstellt_am": jetzt.isoformat(timespec="seconds"),
        "nachricht": nachricht.strip(),
        "antwort": antwort,
        "gerichte": gerichte,
        "anzahl_gerichte": len(gerichte),
    }
    (verzeichnis / f"{plan_id}.json").write_text(
        json.dumps(daten, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return daten


def loesche(plan_id: str) -> bool:
    """Loescht einen gespeicherten Wochenplan per ID. True, wenn etwas geloescht wurde."""
    # Nur das erwartete ID-Format zulassen (Zeitstempel-Slug) -- kein freier
    # Dateiname aus der API, damit kein Pfad ausserhalb des Verzeichnisses trifft.
    if not re.fullmatch(r"[a-z0-9-]+", plan_id or ""):
        return False
    pfad = _wochenplaene_dir() / f"{plan_id}.json"
    if not pfad.is_file():
        return False
    pfad.unlink()
    return True
