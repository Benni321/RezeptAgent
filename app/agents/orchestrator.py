"""
Orchestrator-Agent (Phase 2a/2c)
================================
Haupt-Agent ("Manager") des RezeptAgenten. Koordiniert spezialisierte
Sub-Agenten und Tools im TAO-Zyklus (LangGraph ReAct).

Rollenaufteilung (Multi-Agent, W1):
  Orchestrator         -> versteht die Nutzeranfrage, entscheidet den Modus
                          ("nur vorhandene Zutaten" vs. "Einkaufsliste ergaenzen"),
                          delegiert Teilaufgaben, formuliert die finale Antwort.
  recherche_rezepte    -> Sub-Agent fuer die Web-Rezeptrecherche (eigener Kontext).
  einkaufsliste_...    -> Tool: ermittelt fehlende Zutaten.
  RAG                  -> Tool fuer die lokale Rezept-Wissensbasis (Kollege).

Bild-Eingaben (W2) werden NICHT hier verarbeitet, sondern vorgelagert im
Vision-Modul (app/tools/vision.py): Foto -> Zutatenliste -> als Text an den
Orchestrator. So bleibt der Orchestrator rein text-/tool-basiert und der Nutzer
kann die erkannten Zutaten vorher bestaetigen (Human-in-the-Loop, VL5).

TAO-Zyklus:
  Thought     -> Orchestrator entscheidet, welches Tool / welcher Sub-Agent.
  Action      -> Aufruf (z. B. recherche_rezepte).
  Observation -> Ergebnis fliesst zurueck -> naechster Thought.
"""

import os

from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langgraph.prebuilt import create_react_agent

from app.agents.recherche_agent import recherche_rezepte
from app.tools.shopping_list import einkaufsliste_erstellen

from app.rag.retriever import rag_retriever

load_dotenv()

SYSTEM_PROMPT = """Du bist der Orchestrator eines hilfreichen Rezept-Assistenten.
Du koordinierst spezialisierte Werkzeuge, um Nutzern passende Rezepte vorzuschlagen.

Verfuegbare Werkzeuge:
- recherche_rezepte: findet ueber einen spezialisierten Recherche-Agenten Rezepte
  im Internet. Nutze es, wenn der Nutzer Rezeptideen oder Gerichte zu bestimmten
  Zutaten sucht.
- einkaufsliste_erstellen: vergleicht die fuer ein Rezept benoetigten Zutaten mit
  den vorhandenen und gibt die fehlenden zurueck.
- rag_retriever: durchsucht die persoenliche, gespeicherte Rezeptsammlung des Nutzers.
  Nutze es, wenn der Nutzer nach eigenen oder gespeicherten Rezepten fragt,
  Zutaten nennt die er zu Hause hat, oder wenn du pruefen willst ob ein passendes
  Rezept bereits in der Sammlung existiert, bevor du im Internet suchst.


WICHTIGE REGELN (Reihenfolge beachten!):
1. Rufe pro Schritt immer nur EIN Werkzeug auf und warte dessen Ergebnis ab.
2. Suche IMMER zuerst mit recherche_rezepte ein passendes Rezept - und zwar
   HOECHSTENS EINMAL. Arbeite danach mit dem besten Treffer weiter, auch wenn er
   nicht perfekt passt; rufe recherche_rezepte NICHT erneut auf.
3. Wenn der Nutzer nach seinen Lieblingsrezepten oder seiner persoenlichen Sammlung
   fragt, rufe IMMER zuerst rag_retriever auf. Passen die gefundenen Rezepte nicht
   zu den genannten Zutaten oder liefert rag_retriever kein sinnvolles Ergebnis,
   suche danach mit recherche_rezepte im Internet weiter.
4. Rufe einkaufsliste_erstellen ERST danach auf - und nur im "Einkaufsliste"-Modus.
   Waehle dafuer EIN konkretes Rezept und uebergib als benoetigte_zutaten EXAKT
   dessen Zutaten aus dem Rezeptergebnis. Erfinde niemals Zutaten.
5. Im Modus "nur vorhandene Zutaten" gilt STRIKT: Das vorgeschlagene Rezept darf
   AUSSCHLIESSLICH die vom Nutzer genannten Zutaten verwenden (plus Grundzutaten
   wie Salz, Pfeffer, Oel, Wasser). Braeuchte ein gefundenes Rezept zusaetzliche
   Zutaten, passe es an: lass fehlende Zutaten weg oder ersetze sie durch
   vorhandene, und weise kurz darauf hin. Gibt es mit genau diesen Zutaten kein
   sinnvolles Rezept, sage das ehrlich und schlage eine einfache Zubereitung nur
   aus den vorhandenen Zutaten vor. Fuege KEINE fehlenden Zutaten hinzu und rufe
   einkaufsliste_erstellen NICHT auf.

Formuliere am Ende eine klare, strukturierte Antwort auf Deutsch: das gewaehlte
Rezept (Zutaten + Zubereitungsschritte) und - falls erstellt - die Einkaufsliste.
Achte darauf, dass Rezept und Einkaufsliste zueinander passen: die Einkaufsliste
nennt genau die Zutaten des gewaehlten Rezepts, die der Nutzer noch nicht hat.

Erfinde keine Fakten. Wenn etwas unklar ist, triff eine sinnvolle Annahme und weise
kurz darauf hin."""


def create_orchestrator():
    """
    Erstellt und gibt den Orchestrator-Agenten (LangGraph ReAct) zurueck.

    Der Orchestrator arbeitet im ReAct-/TAO-Muster und ruft je nach Bedarf
    den Recherche-Sub-Agenten oder Tools auf, bis er final antworten kann.
    """
    model = ChatGroq(
        model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        temperature=0,
    )

    tools = [
        recherche_rezepte,        # Sub-Agent: Web-Rezeptrecherche      [W1]
        einkaufsliste_erstellen,  # Tool: fehlende Zutaten ermitteln
        rag_retriever             # lokale Wissensbasis                 [W3/W4]
    ]

    agent = create_react_agent(
        model=model,
        tools=tools,
        prompt=SYSTEM_PROMPT,
    )

    return agent
