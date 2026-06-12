"""
Tool: portionen_skalieren  (Ausbau "Wochenplaner" -- Personen/Portionen)
========================================================================
Rechnet die Zutatenmengen eines Rezepts exakt auf eine andere Portionszahl um
(z. B. Rezept fuer 2 -> gewuenscht fuer 4). Damit kann der Agent auf die vom
Nutzer genannte Personenzahl reagieren, statt nur ein festes Rezept auszugeben.

Designentscheidung (bewusst -- in der README begruendet):
- BEWUSST DETERMINISTISCH, kein LLM. Mengen-Arithmetik ("375 g * 1,5") muss exakt
  und reproduzierbar sein; LLMs verrechnen sich hier zuverlaessig. Gleiche
  Begruendung wie shopping_list.py: eine Aufgabe ohne Sprachverstaendnis loest man
  mit klarer Logik, nicht mit einem Modell.
- Eigenes Tool (statt im Prompt rechnen zu lassen), damit die Umrechnung testbar
  und im TAO-Trace nachvollziehbar ist.

Bekannte Grenze (bewusst, fuer die Doku): nicht alle Zutaten skalieren linear
(Gewuerze, Salz, Backtriebmittel). Wir skalieren nur die fuehrende Mengenangabe
und lassen Zutaten ohne erkennbare Menge ("Salz nach Bedarf") unveraendert --
das deckt den Normalfall ab, ersetzt aber kein Kochwissen.
"""

import re

from langchain_core.tools import tool


def _zahl_format(x: float) -> str:
    """Formatiert eine Menge huebsch: ganze Zahl ohne Nachkomma, sonst mit Komma."""
    if abs(x - round(x)) < 1e-9:
        return str(int(round(x)))
    return f"{x:.2f}".rstrip("0").rstrip(".").replace(".", ",")


def _skaliere_menge(zutat: str, faktor: float) -> str:
    """Multipliziert die FUEHRENDE Mengenangabe einer Zutat mit dem Faktor.

    Erkennt Brueche ("1/2 TL"), Dezimalzahlen mit Punkt oder Komma ("1,5 EL") und
    Ganzzahlen ("400g", "2 Zwiebeln"). Zutaten ohne fuehrende Zahl ("Salz nach
    Bedarf") bleiben unveraendert -- so wird nichts Sinnloses hochskaliert.
    """
    z = zutat.strip()
    bruch = re.match(r"^(\d+)\s*/\s*(\d+)(.*)$", z)
    if bruch:
        menge = int(bruch.group(1)) / int(bruch.group(2))
        rest = bruch.group(3)
    else:
        dezimal = re.match(r"^(\d+(?:[.,]\d+)?)(.*)$", z)
        if not dezimal:
            return zutat
        menge = float(dezimal.group(1).replace(",", "."))
        rest = dezimal.group(2)
    return f"{_zahl_format(menge * faktor)}{rest}"


@tool
def portionen_skalieren(zutaten: list[str], von_portionen: int, auf_portionen: int) -> str:
    """Rechnet die Zutatenmengen eines Rezepts auf eine andere Portionszahl um.

    Nutze dieses Tool, wenn der Nutzer ein Rezept fuer eine ANDERE Personen-/
    Portionszahl moechte als angegeben (z. B. Rezept fuer 2, gewuenscht fuer 4).
    Die Umrechnung ist exakt und deterministisch.
    Eingabe:
      zutaten: Zutatenliste mit Mengen (z. B. "400g Reis", "2 Zwiebeln", "1/2 TL Salz").
      von_portionen: Portionszahl, fuer die das Rezept aktuell gilt.
      auf_portionen: gewuenschte Portionszahl.
    Rueckgabe: die Zutatenliste mit umgerechneten Mengen. Zutaten ohne erkennbare
    Menge (z. B. "Salz nach Bedarf") bleiben unveraendert.
    """
    von = von_portionen if von_portionen and von_portionen > 0 else 1
    auf = auf_portionen if auf_portionen and auf_portionen > 0 else 1
    faktor = auf / von
    skaliert = [_skaliere_menge(z, faktor) for z in zutaten]
    kopf = (
        f"Zutaten skaliert von {von} auf {auf} Portionen "
        f"(Faktor {_zahl_format(faktor)}):"
    )
    punkte = "\n".join(f"- {z}" for z in skaliert)
    return f"{kopf}\n{punkte}"
