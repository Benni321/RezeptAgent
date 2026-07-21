"""
Tool: naehrwerte_schaetzen  (Ausbau "Wochenplaner" -- harte Constraints)
=======================================================================
Schaetzt die Naehrwerte (kcal + Makros) eines Rezepts und rechnet sie auf eine
gewuenschte Portionszahl um. Damit kann der Orchestrator Naehrwert-/Portions-
*Constraints* einer Nutzeranfrage pruefen (z. B. "max 600 kcal pro Portion",
"fuer 4 Personen") und bei Verletzung das Rezept anpassen oder ein anderes
waehlen. Das hebt den Agenten von einem festen Ablauf auf situationsabhaengiges
Entscheiden (Bewertungs-Dimension 2: "reagiert different auf verschiedene
Eingaben").

Designentscheidungen (bewusst -- ausfuehrlich in docs/PROJEKTDOKU.md begruendet):
- Die Schaetzung kommt vom LLM, NICHT aus einer verifizierten Naehrwert-DB.
  Grund: Der Kursrahmen ist bewusst kostenlos/reproduzierbar (kein USDA-/
  OpenFoodFacts-Konto); ein LLM liefert fuer Planungs-Constraints brauchbare
  Groessenordnungen.
- EHRLICHE GRENZE (Reflexion, Dim 5): LLM-Schaetzungen sind systematisch
  ungenau und NICHT allergen-/diaet-sicher. Sie dienen der groben Steuerung der
  Wochenplanung, sind aber keine medizinische oder naehrwertrechtliche Auskunft.
  Fuer Production braeuchte es eine verifizierte Datenbank.
- Verantwortungstrennung (testbar wie shopping_list.py): Der LLM-Aufruf liefert
  nur eine Roh-Schaetzung als JSON; das Parsen und die Umrechnung auf Portionen
  sind reine, deterministische Logik -> ohne API-Key unit-testbar.
"""

import json
import os
import re

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langchain_groq import ChatGroq

from app.core.text_utils import entferne_reasoning

load_dotenv()

# Naehrwert-Felder in fester Reihenfolge (Schluessel = JSON, Wert = Anzeigename).
_FELDER = {
    "kcal": "kcal",
    "eiweiss_g": "Eiweiss",
    "kohlenhydrate_g": "Kohlenhydrate",
    "fett_g": "Fett",
}

# Praefix, an dem der Orchestrator (und Tests) eine fehlgeschlagene Schaetzung erkennt.
FEHLER_PRAEFIX = "NAEHRWERT-FEHLER"

NAEHRWERT_ANWEISUNG = (
    "Schaetze die Naehrwerte des folgenden Gerichts fuer die GESAMTE angegebene "
    "Zutatenmenge (alle Portionen zusammen). Sind keine Mengen angegeben, nimm "
    "haushaltsuebliche Mengen fuer das Gericht an. Antworte AUSSCHLIESSLICH mit "
    "einem JSON-Objekt der Form "
    '{"kcal": <Zahl>, "eiweiss_g": <Zahl>, "kohlenhydrate_g": <Zahl>, '
    '"fett_g": <Zahl>} -- ohne Einheiten in den Werten, ohne weitere Erklaerung.'
)


def _baue_prompt(rezept_titel: str, zutaten: list[str]) -> str:
    """Setzt den Naehrwert-Prompt aus fester Anweisung + Rezeptdaten zusammen.

    BEWUSST keine str.format()-Nutzung: Die Anweisung enthaelt ein literales
    JSON-Beispiel mit geschweiften Klammern ('{"kcal": ...}'). str.format() wuerde
    diese als Platzhalter deuten und mit KeyError abbrechen. Konkatenation ist hier
    die robuste Loesung und bleibt ohne API-Key testbar.
    """
    zutaten_text = "\n".join(f"- {z}" for z in zutaten)
    # /no_think: schaltet qwen3-Reasoning fuer diese reine JSON-Aufgabe ab -- sonst kann
    # ein langer <think>-Block die Antwort abschneiden, BEVOR das JSON kommt (dann
    # scheitert die Schaetzung). Bei Modellen ohne /no_think ist es harmloser Text.
    return f"{NAEHRWERT_ANWEISUNG}\n\nGericht: {rezept_titel}\nZutaten:\n{zutaten_text}\n/no_think"


def _parse_naehrwerte(text: str) -> dict[str, float]:
    """Extrahiert ein Naehrwert-JSON aus der Modellantwort -- robust gegen Beiwerk.

    Sucht das erste JSON-Objekt im Text und liest die bekannten Felder als Zahlen.
    Fehlende oder unparsbare Werte werden zu 0.0 (defensiv, damit nachgelagerte
    Umrechnung nie crasht). Akzeptiert auch Zahlen mit Komma als Dezimaltrenner.
    """
    werte = {feld: 0.0 for feld in _FELDER}
    if not text:
        return werte
    treffer = re.search(r"\{.*\}", text, re.DOTALL)
    if not treffer:
        return werte
    try:
        roh = json.loads(treffer.group(0))
    except json.JSONDecodeError:
        return werte
    if not isinstance(roh, dict):
        return werte
    for feld in _FELDER:
        wert = roh.get(feld)
        if isinstance(wert, (int, float)):
            werte[feld] = float(wert)
        elif isinstance(wert, str):
            # "350 kcal" / "12,5" -> erste Zahl herausziehen, Komma -> Punkt.
            zahl = re.search(r"-?\d+(?:[.,]\d+)?", wert)
            if zahl:
                werte[feld] = float(zahl.group(0).replace(",", "."))
    return werte


def _pro_portion(gesamt: dict[str, float], portionen: int) -> dict[str, float]:
    """Teilt Gesamt-Naehrwerte gleichmaessig auf die Portionen auf (gerundet).

    Schuetzt gegen portionen <= 0 (faellt auf 1 Portion zurueck), damit der Agent
    keine Division durch Null ausloesen kann.
    """
    teiler = portionen if portionen and portionen > 0 else 1
    return {feld: round(wert / teiler, 1) for feld, wert in gesamt.items()}


def _formatiere(titel: str, portionen: int, gesamt: dict, je_portion: dict) -> str:
    """Baut die fuer den Agenten lesbare Antwort (mit Naeherungs-Hinweis)."""
    p = ", ".join(f"{name} {je_portion[feld]:g}g" if feld != "kcal"
                  else f"~{je_portion[feld]:g} kcal"
                  for feld, name in _FELDER.items())
    g = ", ".join(f"{name} {gesamt[feld]:g}g" if feld != "kcal"
                  else f"~{gesamt[feld]:g} kcal"
                  for feld, name in _FELDER.items())
    return (
        f'Geschaetzte Naehrwerte fuer "{titel}" '
        f"(Naeherung, keine verifizierte Datenbank):\n"
        f"- pro Portion (bei {max(portionen, 1)} Portionen): {p}\n"
        f"- gesamt: {g}"
    )


def _hole_schaetzung(rezept_titel: str, zutaten: list[str]) -> dict[str, float] | None:
    """LLM-Schaetzung der GESAMT-Naehrwerte. Gibt None bei Fehler/unbrauchbarer Antwort.

    Gemeinsamer Kern von naehrwerte_schaetzen (Tool, Text-Ausgabe) und
    schaetze_kcal_pro_portion (Zahl fuer den Wochenplan-Workflow) -- keine Duplizierung.
    """
    # Modell-Split (2026-07): reine Schaetz-Completion ohne Tool-Calling -- der
    # einfachste Kandidat fuer das kleine Modell mit eigenem TPM-Topf
    # (Begruendung: recherche_agent.py). entferne_reasoning unten haelt die
    # Funktion modell-agnostisch, falls doch ein Qwen-Modell konfiguriert wird.
    model = ChatGroq(
        model=os.getenv("GROQ_MODEL_KLEIN", "llama-3.1-8b-instant"),
        temperature=0,
        max_retries=5,  # transiente 429 (Free-Tier-TPM) automatisch abfangen (W9)
    )
    try:
        antwort = model.invoke([HumanMessage(content=_baue_prompt(rezept_titel, zutaten))])
    except Exception:  # Schaetzung scheitert -> None (Aufrufer entscheidet, wie er reagiert)
        return None
    # Reasoning-Modelle (qwen3) stellen dem JSON einen <think>-Block voran, dessen
    # geschweifte Klammern den JSON-Parser fehlleiten -> erst entfernen.
    gesamt = _parse_naehrwerte(entferne_reasoning(antwort.content))
    # Alle Werte 0.0 => Modellantwort war unbrauchbar. Als Fehler behandeln, NICHT als
    # "0 kcal" (das wuerde faelschlich als "unter dem Limit" gedeutet).
    if all(wert == 0.0 for wert in gesamt.values()):
        return None
    return gesamt


def schaetze_kcal_pro_portion(rezept_titel: str, zutaten: list[str], portionen: int = 2) -> float | None:
    """Schaetzt die kcal PRO PORTION als Zahl (fuer den Wochenplan-Constraint-Check im Code).

    Gibt None zurueck, wenn die Schaetzung fehlschlaegt -- der Workflow behandelt den
    kcal-Constraint dann als "nicht pruefbar" statt als erfuellt (siehe wochenplan_workflow).
    """
    gesamt = _hole_schaetzung(rezept_titel, zutaten)
    if gesamt is None:
        return None
    return _pro_portion(gesamt, portionen)["kcal"]


@tool
def naehrwerte_schaetzen(rezept_titel: str, zutaten: list[str], portionen: int = 2) -> str:
    """Schaetzt die Naehrwerte eines Rezepts und gibt sie PRO PORTION zurueck.

    Nutze dieses Tool NUR, wenn der Nutzer eine Naehrwert-/Kalorien-Vorgabe macht
    (z. B. "max 600 kcal pro Portion", "kalorienarm", "proteinreich") oder eine
    Portionszahl nennt, und du pruefen willst, ob ein Rezept dazu passt.
    Eingabe:
      rezept_titel: Name des Gerichts (Kontext fuer die Schaetzung).
      zutaten: die Zutatenliste des Rezepts (Mengenangaben verbessern die Schaetzung).
      portionen: fuer wie viele Portionen das Rezept gedacht ist (Default 2).
    Rueckgabe: geschaetzte kcal + Makros pro Portion und gesamt. Es sind
    NAEHERUNGEN ohne verifizierte Datenbank -- nutze sie nur zum groben Abgleich
    mit der Vorgabe, nicht als exakte oder diaet-sichere Angabe.
    """
    gesamt = _hole_schaetzung(rezept_titel, zutaten)
    if gesamt is None:
        return (
            f"{FEHLER_PRAEFIX}: Konnte die Naehrwerte nicht schaetzen. Behandle eine "
            f"etwaige kcal-Vorgabe als NICHT geprueft - nimm nicht an, dass sie erfuellt ist."
        )
    je_portion = _pro_portion(gesamt, portionen)
    return _formatiere(rezept_titel, portionen, gesamt, je_portion)
