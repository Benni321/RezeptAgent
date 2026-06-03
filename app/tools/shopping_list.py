"""
Tool: einkaufsliste_erstellen (Phase 2a)
========================================
Deterministisches Werkzeug: vergleicht die fuer ein Rezept benoetigten Zutaten
mit den beim Nutzer vorhandenen Zutaten und gibt die FEHLENDEN zurueck.

Bewusst KEIN LLM-Aufruf -- reine, nachvollziehbare Logik. Das macht das Ergebnis
reproduzierbar und testbar (W8) und ist die sinnvolle Loesung fuer eine Aufgabe,
die kein Sprachverstaendnis braucht.

Der naive Ansatz "exakter Stringvergleich" scheitert in der Praxis, weil Rezept-
Zutaten Mengen/Einheiten und andere Wortformen enthalten:
  benoetigt "400g Reis"  vs. vorhanden "Reis"     -> sollte als VORHANDEN gelten
  benoetigt "1 rote Zwiebel" vs. vorhanden "Zwiebeln" (Plural)
  Schreibweise "Haehnchen" vs. "Haehnchenbrustfilet"
Daher vergleichen wir auf Ebene normalisierter KERNBEGRIFFE (ohne Zahlen/Einheiten,
mit Umlaut-Faltung und lockerem Praefix-Match fuer Singular/Plural).

Bekannte Grenze (bewusst, fuer die Projekt-Doku): echte Synonyme
("Fruehlingszwiebel" vs. "Zwiebel") werden nicht erkannt -- das braeuchte eine
Zutaten-Ontologie.
"""

import re

from langchain_core.tools import tool

# Mengen-Einheiten und Fuellwoerter, die keine Zutat benennen.
_EINHEITEN = {
    "g", "gr", "kg", "mg", "ml", "l", "el", "tl", "msp", "prise", "prisen",
    "dose", "dosen", "stk", "stueck", "pck", "packung", "bund", "zehe", "zehen",
    "etwas", "nach", "bedarf", "frisch", "frische", "frischer",
}


def _falte_umlaute(text: str) -> str:
    """ae/oe/ue/ss-Normalisierung, damit 'Haehnchen' und 'Haehnchen' zusammenfallen."""
    return (
        text.lower()
        .replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    )


def _kernbegriffe(zutat: str) -> set[str]:
    """Reduziert eine Zutatenangabe auf ihre aussagekraeftigen Wortbestandteile."""
    woerter = re.findall(r"[a-z]+", _falte_umlaute(zutat))
    return {w for w in woerter if w not in _EINHEITEN and len(w) > 2}


def _ist_vorhanden(benoetigt: str, vorhandene_begriffe: set[str]) -> bool:
    """True, wenn ein Kernbegriff der benoetigten Zutat zu den vorhandenen passt.

    Lockerer Praefix-Match in beide Richtungen faengt Singular/Plural und
    Komposita ab: 'zwiebel' <-> 'zwiebeln', 'haehnchen' <-> 'haehnchenbrustfilet'.
    """
    for b in _kernbegriffe(benoetigt):
        for v in vorhandene_begriffe:
            if b == v or b.startswith(v) or v.startswith(b):
                return True
    return False


@tool
def einkaufsliste_erstellen(
    benoetigte_zutaten: list[str],
    vorhandene_zutaten: list[str],
) -> str:
    """Ermittelt, welche Zutaten fuer ein Rezept noch fehlen (Einkaufsliste).

    Nutze dieses Tool im Modus "Einkaufsliste ergaenzen", nachdem du die
    benoetigten Zutaten eines Rezepts kennst.
    Eingabe:
      benoetigte_zutaten: alle Zutaten, die das Rezept braucht (Mengen sind ok).
      vorhandene_zutaten: die Zutaten, die der Nutzer bereits zuhause hat.
    Rueckgabe: die fehlenden Zutaten als Einkaufsliste (oder Hinweis, dass nichts fehlt).
    """
    vorhandene_begriffe: set[str] = set()
    for z in vorhandene_zutaten:
        vorhandene_begriffe |= _kernbegriffe(z)

    fehlend = [z for z in benoetigte_zutaten if not _ist_vorhanden(z, vorhandene_begriffe)]

    if not fehlend:
        return "Es fehlt nichts - alle benoetigten Zutaten sind vorhanden."
    punkte = "\n".join(f"- {z}" for z in fehlend)
    return f"Einkaufsliste (fehlende Zutaten):\n{punkte}"
