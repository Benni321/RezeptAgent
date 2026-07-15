"""
Kochbuch-RAG: persoenliche Rezept-Wissensbasis + Retriever-Tool  [W3][W4]
=========================================================================
Die Wissensbasis ist das "Kochbuch-Gedaechtnis" des Agenten: Rezepte, die der
Nutzer mit >= 4 Sternen bewertet, werden automatisch gespeichert (plus ein paar
Seed-Rezepte fuer den Kaltstart). Der Retriever (rag_retriever) durchsucht sie
als Tool im TAO-Zyklus -> Agentic RAG (W4): Der Orchestrator entscheidet
situationsabhaengig, ob er ZUERST im eigenen Kochbuch sucht (Bezug auf
Bewaehrtes/Favoriten) und faellt bei RAG-LEER transparent auf die Websuche zurueck.

Designentscheidungen (bewusst -- ausfuehrlich in docs/PROJEKTDOKU.md begruendet):
- INHALT: Die Basis enthaelt nur, was Websuche/LLM NICHT wissen koennen -- die
  eigenen, bewaehrten Rezepte des Nutzers. Ein Spiegel von Web-Rezepten waere
  Checkbox-RAG ohne Mehrwert ("Sinnhaftigkeit vor Checkbox"). Das verbindet
  Memory (Bewertungen) und Wissensbasis: Continual Learning konkret (W13).
- RETRIEVAL: BM25 (lexikalisch, selbst implementiert, ~40 Zeilen) statt
  Embedding-Modell + Vektor-DB. Gruende: (1) Der Korpus ist klein (waechst pro
  gekochtem Gericht um 1) -- Embedding-Vorteile sind da minimal, die Kosten real
  (2,27-GB-Modell-Download war der Blocker des alten Moduls). (2) VL-Erkenntnis:
  lexikalische Suche + agentische Query-Umformulierung schlaegt naive Vektorsuche;
  die "Semantik" liefert das LLM, indem es bei RAG-LEER Synonyme probiert.
  (3) Deterministisch, offline testbar, kein Download -> Kursrahmen bleibt intakt.
- FEHLERBILD: kein Treffer/leeres Kochbuch -> "RAG-LEER"-Observation statt
  Exception (etabliertes Muster: Fehler werden zur Entscheidung, nicht zum Absturz).
- MINIMALE RECHTE (VL03): Das Tool liest nur; geschrieben wird ausschliesslich
  ueber den deterministischen API-Pfad (POST /bewertung), nie vom Agenten.

Ehrliche Grenzen: BM25 ist lexikalisch (findet "Sahnesauce" nicht bei "was
Cremiges" -- das muss die Umformulierung des Agenten leisten); die Zutaten-
Extraktion aus der Antwort ist heuristisch (Listenzeilen); Komposita werden nur
per Teilwort-Match (>= 5 Zeichen) angenaehert. Bei grossem Korpus oder echten
Bedeutungs-Queries waere ein Embedding-Modell der dokumentierte Ausbauschritt.
"""

import json
import math
import os
import re
import unicodedata
from pathlib import Path

from langchain_core.tools import tool

# Praefix, an dem der Orchestrator einen erfolglosen Kochbuch-Zugriff erkennt
# (und dann transparent zur Websuche wechselt / die Query umformuliert).
LEER_PRAEFIX = "RAG-LEER"

_UMLAUTE = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})

# Minimale deutsche Fuellwoerter, damit "was kann ich heute kochen" nicht auf
# Fuellwoerter matcht. Bewusst kurz gehalten (kein NLP-Anspruch).
_STOPWOERTER = {
    "der", "die", "das", "ein", "eine", "und", "mit", "ohne", "fuer", "ich",
    "mir", "mich", "was", "kann", "will", "gern", "gerne", "heute", "mal",
    "bitte", "etwas", "aus", "wie", "von", "im", "am", "zum", "zur", "auf",
    "rezept", "rezepte", "kochen", "gericht", "essen",
}


def _kochbuch_dir() -> Path:
    """Verzeichnis der Wissensbasis. Env KOCHBUCH_DIR wird bewusst zur LAUFZEIT
    gelesen (nicht beim Import), damit Tests/Eval-Runner es pro Lauf setzen koennen."""
    return Path(os.getenv("KOCHBUCH_DIR", "data/rezepte"))


def _tokens(text: str) -> list[str]:
    """Zerlegt Text in Suchtokens: klein, Umlaute gefaltet, ohne Fuellwoerter."""
    norm = (text or "").lower().translate(_UMLAUTE)
    norm = unicodedata.normalize("NFKD", norm)
    return [t for t in re.split(r"[^a-z0-9]+", norm) if len(t) >= 2 and t not in _STOPWOERTER]


def _passt(term: str, token: str) -> bool:
    """Term-Match inkl. Komposita-Annaeherung: exakt ODER Teilwort ab 5 Zeichen
    ('haehnchen' trifft 'haehnchenbrust' -- und umgekehrt)."""
    if term == token:
        return True
    return (len(term) >= 5 and term in token) or (len(token) >= 5 and token in term)


# ---------------------------------------------------------------------------
# Wissensbasis: laden + speichern (deterministisch, JSON-Dateien)
# ---------------------------------------------------------------------------

def lade_alle() -> list[dict]:
    """Liest alle Rezepte der Wissensbasis. Defensiv: kaputte Dateien werden
    uebersprungen (W9-Geist), fehlendes Verzeichnis -> leere Liste."""
    verzeichnis = _kochbuch_dir()
    if not verzeichnis.is_dir():
        return []
    rezepte = []
    for pfad in sorted(verzeichnis.glob("*.json")):
        try:
            daten = json.loads(pfad.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(daten, dict) and daten.get("titel") and isinstance(daten.get("zutaten"), list):
            rezepte.append(daten)
    return rezepte


def _slug(titel: str) -> str:
    s = titel.lower().translate(_UMLAUTE)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:60] or "rezept"


def speichere_rezept(titel: str, zutaten: list[str], sterne: int | None = None,
                     kcal: float | None = None, quelle: str = "bewertung") -> Path:
    """Legt ein Rezept in der Wissensbasis ab (bzw. aktualisiert es per Titel-Slug).

    Wird NUR vom deterministischen API-Pfad aufgerufen (Bewertung >= 4 Sterne),
    nie vom Agenten selbst (VL03: Schreiben ist keine Agenten-Aktion).
    Gelernte Rezepte bekommen das Praefix 'gelernt_', Seeds heissen 'seed_*' --
    so bleibt sichtbar, was mitgeliefert und was wirklich gelernt wurde.
    """
    verzeichnis = _kochbuch_dir()
    verzeichnis.mkdir(parents=True, exist_ok=True)
    praefix = "seed_" if quelle == "seed" else "gelernt_"
    daten = {
        "titel": titel.strip(),
        "zutaten": [z.strip() for z in zutaten if z.strip()],
        "sterne": sterne,
        "kcal_pro_portion": kcal,
        "quelle": quelle,
    }
    pfad = verzeichnis / f"{praefix}{_slug(titel)}.json"
    pfad.write_text(json.dumps(daten, ensure_ascii=False, indent=2), encoding="utf-8")
    return pfad


_LISTEN_ZEILE = re.compile(r"^\s*(?:[-*•]|\d+\.)\s+(.*)$")
_KCAL = re.compile(r"(\d{2,4})\s*kcal", re.IGNORECASE)


def rezept_aus_antwort(titel: str, antwort: str) -> dict | None:
    """Extrahiert Zutaten (+ kcal, falls genannt) heuristisch aus einer Agent-Antwort.

    Heuristik: Listenzeilen VOR dem Zubereitungs-Abschnitt gelten als Zutaten
    (typisches Antwortformat des Orchestrators). Nichts gefunden -> None, dann
    wird nur die Sterne-Bewertung gespeichert, kein Kochbuch-Eintrag (ehrliche
    Grenze: lieber kein Eintrag als ein falscher).
    """
    if not titel.strip() or not antwort:
        return None
    zutaten: list[str] = []
    for zeile in antwort.splitlines():
        if re.search(r"zubereitung|anleitung|schritte", zeile, re.IGNORECASE):
            break
        m = _LISTEN_ZEILE.match(zeile)
        if m and m.group(1).strip():
            zutaten.append(m.group(1).strip()[:100])
    if not zutaten:
        return None
    kcal_treffer = _KCAL.search(antwort)
    return {
        "titel": titel.strip(),
        "zutaten": zutaten[:25],
        "kcal": float(kcal_treffer.group(1)) if kcal_treffer else None,
    }


# ---------------------------------------------------------------------------
# Retrieval: BM25 (Okapi), bewusst selbst implementiert statt Bibliothek/Modell
# ---------------------------------------------------------------------------

def suche(anfrage: str, k: int = 3) -> list[dict]:
    """BM25-Ranking der Wissensbasis fuer eine Anfrage; nur Treffer mit Score > 0.

    Dokumenttext = Titel + Zutaten (dort steckt die Information; Mengenangaben
    stoeren dank Tokenisierung nicht). k1/b sind die ueblichen Okapi-Defaults.
    """
    rezepte = lade_alle()
    if not rezepte:
        return []
    doku_tokens = [_tokens(f"{r['titel']} {' '.join(r['zutaten'])}") for r in rezepte]
    n = len(rezepte)
    avg_laenge = sum(len(t) for t in doku_tokens) / n
    k1, b = 1.5, 0.75

    bewertet = []
    for rezept, tokens in zip(rezepte, doku_tokens):
        score = 0.0
        for term in set(_tokens(anfrage)):
            df = sum(1 for dt in doku_tokens if any(_passt(term, t) for t in dt))
            if df == 0:
                continue
            tf = sum(1 for t in tokens if _passt(term, t))
            if tf == 0:
                continue
            idf = math.log((n - df + 0.5) / (df + 0.5) + 1)
            score += idf * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * len(tokens) / avg_laenge))
        if score > 0:
            bewertet.append((score, rezept))
    bewertet.sort(key=lambda x: x[0], reverse=True)
    return [r for _, r in bewertet[:k]]


def _formatiere_treffer(rezepte: list[dict]) -> str:
    zeilen = ["Aus deinem persoenlichen Kochbuch (frueher gespeicherte/bewaehrte Rezepte):"]
    for r in rezepte:
        extras = []
        if r.get("sterne"):
            extras.append(f"{r['sterne']} Sterne")
        if r.get("kcal_pro_portion"):
            extras.append(f"~{r['kcal_pro_portion']:g} kcal/Portion")
        extras.append("Seed-Rezept" if r.get("quelle") == "seed" else "vom Nutzer gelernt")
        zeilen.append(f"- {r['titel']} ({', '.join(extras)}): {', '.join(r['zutaten'])}")
    return "\n".join(zeilen)


@tool
def rag_retriever(anfrage: str) -> str:
    """Durchsucht das persoenliche Kochbuch des Nutzers (gespeicherte, gut
    bewertete Rezepte) nach passenden Treffern.

    Nutze dieses Tool ZUERST (vor recherche_rezepte), wenn der Nutzer sich auf
    Bewaehrtes bezieht: eigene/gespeicherte/Lieblings-Rezepte, "wie letztes Mal",
    "was ich schon mal gekocht habe". Eingabe: Stichworte zum Gericht/zu Zutaten.
    Rueckgabe: bis zu 3 gespeicherte Rezepte mit Zutaten -- oder "RAG-LEER", wenn
    nichts passt. Bei RAG-LEER: probiere EINMAL andere Stichworte (Synonyme) oder
    wechsle transparent zur Websuche.
    """
    if not (anfrage or "").strip():
        return f"{LEER_PRAEFIX}: leere Anfrage - nenne Stichworte zum Gericht."
    if not lade_alle():
        return (f"{LEER_PRAEFIX}: das Kochbuch ist noch leer. Es fuellt sich, "
                "wenn der Nutzer Rezepte mit 4+ Sternen bewertet. Nutze die Websuche.")
    treffer = suche(anfrage)
    if not treffer:
        return (f"{LEER_PRAEFIX}: keine gespeicherten Rezepte zu '{anfrage.strip()}'. "
                "Probiere andere Stichworte oder nutze die Websuche.")
    return _formatiere_treffer(treffer)
