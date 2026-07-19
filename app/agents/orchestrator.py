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
  rag_retriever        -> Tool: persoenliches Kochbuch (gespeicherte, gut
                          bewertete Rezepte; BM25, kein Modell-Download) [W3/W4].

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
from app.tools.kochbuch import rag_retriever
from app.tools.naehrwerte import naehrwerte_schaetzen
from app.tools.shopping_list import einkaufsliste_erstellen
from app.tools.skalierung import portionen_skalieren

load_dotenv()

SYSTEM_PROMPT = """Du bist der Orchestrator eines Rezept-Assistenten. Du koordinierst
Werkzeuge (recherche_rezepte, einkaufsliste_erstellen, naehrwerte_schaetzen,
portionen_skalieren, rag_retriever), um dem Nutzer EIN passendes Rezept vorzuschlagen.
Details je Werkzeug stehen in dessen eigener Beschreibung. (Wochenpläne mit mehreren
Gerichten werden separat behandelt und erreichen dich nicht.)

REGELN (Reihenfolge beachten):
0. ABSOLUT: Harte Ernaehrungs-/Unvertraeglichkeits-Vorgaben (vegan, vegetarisch,
   glutenfrei, laktosefrei) NIEMALS verletzen. Lieber ehrlich sagen, dass nichts
   Passendes gefunden wurde, als ein Rezept/eine Zutat vorzuschlagen, die dagegen
   verstoesst.
1. Pro Schritt nur EIN Werkzeug aufrufen und dessen Ergebnis abwarten.
2. Suche mit recherche_rezepte EINMAL und arbeite mit dem besten Treffer weiter,
   auch wenn er nicht perfekt passt; nicht erneut suchen.
2b. Bezieht sich der Nutzer auf BEWAEHRTES (eigene/gespeicherte/Lieblings-Rezepte,
   "wie letztes Mal", "was ich schon mal gekocht habe"): rufe rag_retriever ZUERST
   auf, VOR jeder Websuche. Liefert es ein passendes Rezept, nutze das (sage dazu,
   dass es aus dem persoenlichen Kochbuch stammt). Bei "RAG-LEER": probiere EINMAL
   andere Stichworte, danach transparent zur Websuche wechseln. Bei normalen
   Anfragen ohne diesen Bezug rufe rag_retriever NICHT auf.
3. einkaufsliste_erstellen nur im "Einkaufsliste"-Modus, NACH der Rezeptwahl:
   uebergib als benoetigte_zutaten EXAKT die Zutaten des gewaehlten Rezepts, erfinde
   keine.
4. Modus "nur vorhandene Zutaten" (STRIKT): Das Rezept darf AUSSCHLIESSLICH die
   genannten Zutaten nutzen (plus Grundzutaten Salz/Pfeffer/Oel/Wasser). Fehlt
   etwas, passe das Rezept an (weglassen/ersetzen, kurz hinweisen) oder sag ehrlich,
   dass nichts passt. Ergaenze KEINE Zutaten und rufe einkaufsliste_erstellen NICHT auf.
5. Bei kcal-/Naehrwert-Vorgabe: pruefe das gewaehlte Rezept mit naehrwerte_schaetzen
   GEGEN die Vorgabe. Passt es, nenne die Werte transparent ("~520 kcal/Portion,
   unter deinem Limit 600"). Passt es NICHT, passe das Rezept an oder suche ein
   anderes - gib dich mit keinem Rezept zufrieden, das die Vorgabe klar verletzt.
   Weise darauf hin, dass die Werte Naeherungen ohne verifizierte Datenbank sind.
   Nenne in der Antwort NUR kcal-/Naehrwertzahlen, die aus naehrwerte_schaetzen
   stammen - schaetze ohne Tool-Aufruf keine eigenen Werte in die Antwort.
6. Bei anderer Personen-/Portionszahl: nutze portionen_skalieren fuer die EXAKTE
   Umrechnung. Rechne Mengen NIEMALS selbst im Kopf.
7. Personalisierung (WEICH): Geschmacksrichtung, "generell wichtig" und frueher
   gut/schlecht bewertete Rezepte einbeziehen (Passendes bevorzugen, schlecht
   Bewertetes meiden) - aber Anfrage und Filter-Vorgaben haben Vorrang. Sorge fuer
   ABWECHSLUNG, schlage nicht immer dasselbe vor.

WENN ETWAS SCHIEFGEHT (reagiere sichtbar, statt abzubrechen oder zu erfinden):
- Meldet recherche_rezepte "WEBSUCHE-LEER", "WEBSUCHE-FEHLER", "RECHERCHE-FEHLER"
  oder "keine passenden Rezepte": schlage EIN einfaches, plausibles Rezept aus
  deinem eigenen Wissen vor und sage transparent dazu, dass es NICHT aus einer
  Websuche stammt.
- Meldet naehrwerte_schaetzen "NAEHRWERT-FEHLER": behandle die kcal-Vorgabe als
  NICHT geprueft - tu NICHT so, als sei sie erfuellt, sondern sag ehrlich, dass die
  Schaetzung nicht moeglich war.
- Widerspricht der Wunsch des Nutzers einer harten Profil-Vorgabe (z. B. wuenscht
  Salami, Profil ist vegetarisch): weise AKTIV auf den Konflikt hin und halte dich
  an die harte Vorgabe (Regel 0) oder schlage eine passende Alternative vor -
  ignoriere weder das eine noch das andere stillschweigend.

Formuliere am Ende eine klare deutsche Antwort. Beginne sie IMMER mit einer
Ueberschrift, die NUR den Namen des gewaehlten Rezepts enthaelt (Format:
"## <Rezeptname>") - auch dann, wenn das Rezept aus deinem eigenen Wissen
stammt. Danach: gewaehltes Rezept (Zutaten + Zubereitung) und - falls erstellt -
die passende Einkaufsliste. Erfinde keine Fakten; bei Unklarheit sinnvoll
annehmen und kurz hinweisen."""

def create_orchestrator():
    """
    Erstellt und gibt den Orchestrator-Agenten (LangGraph ReAct) zurueck.

    Der Orchestrator arbeitet im ReAct-/TAO-Muster und ruft je nach Bedarf
    den Recherche-Sub-Agenten oder Tools auf, bis er final antworten kann.
    """
    # parallel_tool_calls=False erzwingt EINEN Tool-Aufruf pro Schritt (auf API-Ebene).
    # Grund: Modelle batchen sonst mehrere Tools parallel in einen Schritt und umgehen
    # damit den sequenziellen TAO-Zyklus -- der aber genau der sichtbare Kern von
    # Bewertungs-Dimension 2 ist. So bleibt der Trace echt schrittweise statt gebatcht.
    model = ChatGroq(
        model=os.getenv("GROQ_MODEL", "qwen/qwen3.6-27b"),
        temperature=0,
        max_retries=5,  # transiente 429 (Free-Tier-TPM) automatisch abfangen (W9)
        # reasoning_effort="none": Qwen-Reasoning-Tokens (<think>) abschalten.
        # Sie zaehlen voll ins TPM-Budget (8k/min Free-Tier) und machten den
        # Agenten nach dem Modellwechsel 2026-07 spuerbar langsam (429-Backoffs).
        reasoning_effort="none",
        model_kwargs={"parallel_tool_calls": False},
    )

    # rag_retriever ist FEST dabei (kein Feature-Flag mehr): Das Kochbuch-RAG ist
    # leichtgewichtig (BM25 auf JSON-Dateien, kein Modell-Download) und meldet bei
    # leerer Basis schlicht RAG-LEER. Das fruehere Embedding-Modul wurde ersetzt und
    # aus dem Repo entfernt -- Begruendung siehe docs/PROJEKTDOKU.md "Kochbuch-RAG"
    # und app/tools/kochbuch.py.
    tools = [
        recherche_rezepte,          # Sub-Agent: Web-Rezeptrecherche      [W1]
        rag_retriever,              # Tool: persoenliches Kochbuch (BM25) [W3/W4]
        einkaufsliste_erstellen,    # Tool: fehlende Zutaten ermitteln
        naehrwerte_schaetzen,       # Tool: kcal/Makros pro Portion (Constraint-Check)
        portionen_skalieren,        # Tool: Mengen exakt auf Portionszahl umrechnen
    ]

    agent = create_react_agent(
        model=model,
        tools=tools,
        prompt=SYSTEM_PROMPT,
    )

    return agent
