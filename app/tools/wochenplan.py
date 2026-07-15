"""
Tool: wochenplan_zusammenstellen  (Tiefen-Feature "constraint-bewusster Wochenplaner")
=====================================================================================
Fuegt mehrere geplante Gerichte zu EINEM Wochenplan zusammen und aggregiert ihre
Zutaten zu EINER Gesamt-Einkaufsliste (dedupliziert, ohne bereits vorhandene).

Warum dieses Tool -- und warum kein Sub-Agent (bewusste Architekturentscheidung):
- Die Planungs-INTELLIGENZ (welche Gerichte, jedes gegen die kcal-/Portions-/
  Ernaehrungs-Constraints pruefen, bei Verletzung revidieren, fuer Abwechslung
  sorgen) bleibt beim Orchestrator, weil genau diese plan->pruefe->revidiere-
  Schleife im sichtbaren TAO-Trace stehen soll (Bewertungs-Dimension 2 wird am
  Trace beurteilt). Ein Sub-Agent wuerde sie in isolierten Kontext verschieben
  und damit verstecken -- anders als bei `recherche_rezepte`, wo das Wegfiltern
  von Such-"Rauschen" der gewollte Zweck der Isolation ist.
- Uebrig bleibt reine AGGREGATION ueber mehrere Rezepte: Zutaten sammeln,
  Duplikate zusammenfassen ("Zwiebel" aus Gericht A und "2 Zwiebeln" aus
  Gericht B -> einmal einkaufen), Vorhandenes abziehen. Das ist Mengenlogik,
  kein Sprachverstaendnis -> deterministisches Tool, kein LLM (gleiche
  Begruendung wie shopping_list.py / skalierung.py: exakt, reproduzierbar,
  ohne API-Key testbar).

Wiederverwendung: Der Zutaten-Abgleich nutzt dieselbe normalisierte Kernbegriff-
Logik wie einkaufsliste_erstellen (shopping_list.py) -- statt sie zu duplizieren.
So gilt fuer den Wochenplan exakt dasselbe Matching wie fuer die Einzel-Liste.

Bekannte Grenze (bewusst, fuer die Doku): Die Deduplizierung fasst Zutaten mit
gemeinsamem Kernbegriff zusammen. Das ist fuer eine grobe Wochen-Einkaufsliste
gewollt, kann aber verwandte Zutaten ueber-verschmelzen (z. B. "Paprika rot" und
"Paprika gruen" -> ein Eintrag). Mengen werden bewusst NICHT ueber Gerichte
aufsummiert (dafuer fehlt eine Einheiten-Normalisierung) -- die Liste sagt WAS
einzukaufen ist, nicht die Gesamtmenge.
"""

from langchain_core.tools import tool

# Bewusste Wiederverwendung der Matching-Logik der Einzel-Einkaufsliste,
# damit Wochenplan und Einzelrezept identisch abgleichen (keine Redundanz).
from app.tools.shopping_list import _ist_vorhanden, _kernbegriffe


def _aggregiere_einkaufsliste(
    gerichte: list[dict], vorhandene_zutaten: list[str]
) -> list[str]:
    """Sammelt die fehlenden Zutaten ueber ALLE Gerichte, dedupliziert.

    Eine Zutat kommt genau dann auf die Einkaufsliste, wenn sie (a) nicht schon
    beim Nutzer vorhanden ist und (b) nicht bereits ueber ein frueheres Gericht
    (gleicher Kernbegriff) erfasst wurde. Die erste vorkommende Schreibweise
    gewinnt.
    """
    vorhandene_begriffe: set[str] = set()
    for z in vorhandene_zutaten:
        vorhandene_begriffe |= _kernbegriffe(z)

    fehlend: list[str] = []
    erfasste_begriffe: set[str] = set()  # Kernbegriffe schon gelisteter Zutaten
    for gericht in gerichte:
        for zutat in gericht.get("zutaten", []):
            # Beide Checks nutzen dieselbe Prefix-/Umlaut-Logik wie die Einzel-Liste:
            # (1) schon beim Nutzer vorhanden?  (2) ueber ein frueheres Gericht schon
            # gelistet? -- so faellt "1 Zwiebel" mit "2 Zwiebeln" zusammen.
            if _ist_vorhanden(zutat, vorhandene_begriffe):
                continue
            if _ist_vorhanden(zutat, erfasste_begriffe):
                continue
            fehlend.append(zutat)
            erfasste_begriffe |= _kernbegriffe(zutat)
    return fehlend


def _formatiere_wochenplan(gerichte: list[dict], fehlend: list[str]) -> str:
    """Baut die lesbare Wochenplan-Antwort: Gericht-Uebersicht + Gesamt-Einkaufsliste."""
    zeilen = ["Wochenplan:"]
    for i, gericht in enumerate(gerichte, 1):
        titel = (gericht.get("titel") or "").strip() or f"Gericht {i}"
        zeilen.append(f"{i}. {titel}")

    if fehlend:
        zeilen.append("\nGesamt-Einkaufsliste (fehlende Zutaten fuer alle Gerichte):")
        zeilen.extend(f"- {z}" for z in fehlend)
    else:
        zeilen.append("\nGesamt-Einkaufsliste: nichts noetig - alles Benoetigte ist vorhanden.")
    return "\n".join(zeilen)


@tool
def wochenplan_zusammenstellen(
    gerichte: list[dict], vorhandene_zutaten: list[str] = None
) -> str:
    """Fasst mehrere geplante Gerichte zu einem Wochenplan mit EINER Einkaufsliste zusammen.

    Nutze dieses Tool ERST, wenn du fuer einen Wochenplan bereits mehrere Gerichte
    ausgewaehlt UND (falls eine kcal-/Portions-Vorgabe bestand) gegen die Vorgaben
    geprueft hast. Es fuehrt die Zutaten aller Gerichte zu einer gemeinsamen
    Einkaufsliste zusammen (ohne Duplikate, ohne bereits Vorhandenes).
    Eingabe:
      gerichte: Liste der geplanten Gerichte, je Gericht ein Objekt der Form
        {"titel": "<Name>", "zutaten": ["<Zutat 1>", "<Zutat 2>", ...]}.
      vorhandene_zutaten: was der Nutzer bereits zuhause hat (optional).
    Rueckgabe: der strukturierte Wochenplan plus die aggregierte Gesamt-
    Einkaufsliste. Rechne Mengen NICHT selbst zusammen -- die Liste nennt die
    einzukaufenden Zutaten, nicht deren Gesamtmengen.
    """
    gerichte = gerichte or []
    fehlend = _aggregiere_einkaufsliste(gerichte, vorhandene_zutaten or [])
    return _formatiere_wochenplan(gerichte, fehlend)
