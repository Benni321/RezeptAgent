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
  naehrwerte_schaetzen -> Tool: kcal/Makros pro Portion (Constraint-Check).
  RAG                  -> OPTIONALES Tool fuer die lokale Wissensbasis (Kollege),
                          per Env-Flag RAG_AKTIV zuschaltbar. Aktuell abgekoppelt,
                          siehe README "Bekannte Baustelle: RAG".

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
from app.tools.naehrwerte import naehrwerte_schaetzen
from app.tools.shopping_list import einkaufsliste_erstellen
from app.tools.skalierung import portionen_skalieren

load_dotenv()

SYSTEM_PROMPT = """Du bist der Orchestrator eines hilfreichen Rezept-Assistenten.
Du koordinierst spezialisierte Werkzeuge, um Nutzern passende Rezepte vorzuschlagen.

Verfuegbare Werkzeuge:
- recherche_rezepte: findet ueber einen spezialisierten Recherche-Agenten Rezepte
  im Internet. Nutze es, wenn der Nutzer Rezeptideen oder Gerichte zu bestimmten
  Zutaten sucht.
- einkaufsliste_erstellen: vergleicht die fuer ein Rezept benoetigten Zutaten mit
  den vorhandenen und gibt die fehlenden zurueck.
- naehrwerte_schaetzen: schaetzt kcal + Makros pro Portion eines Rezepts.
  Nutze es NUR, wenn der Nutzer eine Naehrwert-/Kalorien-Vorgabe macht
  ("max 600 kcal pro Portion", "kalorienarm", "proteinreich") oder eine
  Portionszahl nennt. Die Werte sind Naeherungen ohne verifizierte Datenbank.
- portionen_skalieren: rechnet die Zutatenmengen exakt auf eine andere
  Portionszahl um. Nutze es, wenn der Nutzer das Rezept fuer eine andere
  Personenzahl moechte als im Rezept angegeben.


WICHTIGE REGELN (Reihenfolge beachten!):
0. ABSOLUT: Harte Vorgaben zur Ernaehrung/Unvertraeglichkeit (z. B. vegan,
   vegetarisch, glutenfrei, laktosefrei) duerfen NIEMALS verletzt werden. Schlage
   kein Rezept vor und ergaenze keine Zutat, die dagegen verstoesst - lieber ehrlich
   sagen, dass nichts Passendes gefunden wurde.
1. Rufe pro Schritt immer nur EIN Werkzeug auf und warte dessen Ergebnis ab.
2. Suche IMMER zuerst mit recherche_rezepte ein passendes Rezept - und zwar
   HOECHSTENS EINMAL. Arbeite danach mit dem besten Treffer weiter, auch wenn er
   nicht perfekt passt; rufe recherche_rezepte NICHT erneut auf.
3. Rufe einkaufsliste_erstellen ERST danach auf - und nur im "Einkaufsliste"-Modus.
   Waehle dafuer EIN konkretes Rezept und uebergib als benoetigte_zutaten EXAKT
   dessen Zutaten aus dem Rezeptergebnis. Erfinde niemals Zutaten.
4. Im Modus "nur vorhandene Zutaten" gilt STRIKT: Das vorgeschlagene Rezept darf
   AUSSCHLIESSLICH die vom Nutzer genannten Zutaten verwenden (plus Grundzutaten
   wie Salz, Pfeffer, Oel, Wasser). Braeuchte ein gefundenes Rezept zusaetzliche
   Zutaten, passe es an: lass fehlende Zutaten weg oder ersetze sie durch
   vorhandene, und weise kurz darauf hin. Gibt es mit genau diesen Zutaten kein
   sinnvolles Rezept, sage das ehrlich und schlage eine einfache Zubereitung nur
   aus den vorhandenen Zutaten vor. Fuege KEINE fehlenden Zutaten hinzu und rufe
   einkaufsliste_erstellen NICHT auf.
5. Nennt der Nutzer eine Naehrwert-/Kalorien-Vorgabe (z. B. "max 600 kcal pro
   Portion") oder eine Portionszahl, dann pruefe das gewaehlte Rezept mit
   naehrwerte_schaetzen GEGEN diese Vorgabe:
   - Passt es, nenne die geschaetzten Werte und mache den Abgleich transparent
     ("~520 kcal/Portion, liegt unter deinem Limit von 600").
   - Passt es NICHT, reagiere: passe das Rezept an (z. B. fettarme Zutat ersetzen,
     Portionsgroesse anpassen) oder waehle/suche ein passenderes Rezept, und
     erklaere kurz, warum. Gib dich nicht mit einem Rezept zufrieden, das die
     Vorgabe klar verletzt.
   Weise immer darauf hin, dass die Naehrwerte Naeherungen ohne verifizierte
   Datenbank sind.
6. Moechte der Nutzer das Rezept fuer eine andere Personen-/Portionszahl als
   angegeben, nutze portionen_skalieren, um die Mengen EXAKT umzurechnen. Rechne
   Mengen NIEMALS selbst im Kopf - dafuer ist das Tool da.
7. Personalisierung (WEICH): Wird der Eingabe eine "Gewuenschte Geschmacksrichtung",
   ein "Dem Nutzer generell wichtig"-Hinweis oder "frueher gut/schlecht bewertete
   Rezepte" beigefuegt, beziehe das in die Rezeptauswahl ein: bevorzuge
   Passendes/aehnlich gut Bewertetes, meide schlecht Bewertetes. Diese Signale sind
   ein STANDARD, kein Muss - die konkrete Anfrage und die Filter-Vorgaben haben
   Vorrang. Sorge ausserdem fuer ABWECHSLUNG: schlage nicht immer dasselbe Gericht
   vor, auch wenn es zum Profil passt.

Formuliere am Ende eine klare, strukturierte Antwort auf Deutsch: das gewaehlte
Rezept (Zutaten + Zubereitungsschritte) und - falls erstellt - die Einkaufsliste.
Achte darauf, dass Rezept und Einkaufsliste zueinander passen: die Einkaufsliste
nennt genau die Zutaten des gewaehlten Rezepts, die der Nutzer noch nicht hat.

Erfinde keine Fakten. Wenn etwas unklar ist, triff eine sinnvolle Annahme und weise
kurz darauf hin."""

# Wird nur an den Prompt angehaengt, wenn RAG aktiv ist (RAG_AKTIV=true).
# Bewusst restriktiv formuliert: RAG soll NUR bei einer expliziten Anfrage nach
# der eigenen Sammlung feuern - nicht bei jeder beliebigen Zutaten-Anfrage.
RAG_PROMPT_ZUSATZ = """

Zusaetzliches Werkzeug (lokale Wissensbasis aktiv):
- rag_retriever: durchsucht die persoenliche, gespeicherte Rezeptsammlung des Nutzers.
  Nutze es NUR, wenn der Nutzer AUSDRUECKLICH nach eigenen, gespeicherten oder
  Lieblings-Rezepten fragt. In diesem Fall rufe rag_retriever ZUERST auf; liefert
  es nichts Passendes, suche danach mit recherche_rezepte im Internet weiter."""


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
        naehrwerte_schaetzen,     # Tool: kcal/Makros pro Portion (Constraint-Check)
        portionen_skalieren,      # Tool: Mengen exakt auf Portionszahl umrechnen
    ]
    prompt = SYSTEM_PROMPT

    # RAG ist standardmaessig ABGEKOPPELT (Default RAG_AKTIV=false). Grund: das
    # RAG-Modul (Kollege) laedt beim ersten Aufruf ein 2,27-GB-Embedding-Modell im
    # laufenden Request -> GUI-Timeout; ausserdem zwei undefinierte Namen in
    # retriever.py (RERANKER_MODEL, TOP_K_FINAL). Wird separat repariert -- siehe
    # README "Bekannte Baustelle: RAG". Reaktivieren: RAG_AKTIV=true setzen (das
    # Embedding-Modell muss dann lokal vorab geladen sein, nicht im Request).
    if os.getenv("RAG_AKTIV", "false").lower() == "true":
        from app.rag.retriever import rag_retriever  # lazy: schwere Importkette nur wenn aktiv

        tools.append(rag_retriever)  # lokale Wissensbasis [W3/W4]
        prompt = SYSTEM_PROMPT + RAG_PROMPT_ZUSATZ

    agent = create_react_agent(
        model=model,
        tools=tools,
        prompt=prompt,
    )

    return agent
