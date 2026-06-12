"""
Recherche-Sub-Agent (Phase 2a)
==============================
Spezialisierter Sub-Agent fuer die Rezept-Recherche im Web.

Warum ein EIGENER Agent (statt nur web_search direkt im Orchestrator)?
  Eine Websuche liefert viele, teils unstrukturierte Treffer ("Rauschen").
  Dieser Sub-Agent verarbeitet sie in seinem EIGENEN Kontext (ggf. mehrere
  Suchen, Auswertung) und gibt dem Orchestrator nur eine kompakte, strukturierte
  Rezeptliste zurueck. Das haelt den Orchestrator-Kontext schlank
  -> Kontext-Isolation (VL4 "Multi-Agent-Systeme").

Aus Sicht des Orchestrators ist dieser Sub-Agent ein TOOL mit einem
Anfrage-Parameter (VL4: "Sub-Agent = Function Call"). Die innere TAO-Schleife
des Sub-Agenten ist nach aussen nicht sichtbar -- der Orchestrator sieht nur
das Ergebnis. Genau das ist die in W1 geforderte Rollenaufteilung
(Orchestrator + Subagent).
"""

import os

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langchain_groq import ChatGroq
from langgraph.prebuilt import create_react_agent

from app.tools.web_search import get_web_search_tool

load_dotenv()

RECHERCHE_PROMPT = """Du bist ein spezialisierter Rezept-Rechercheur.
Deine einzige Aufgabe: zu einer Anfrage passende Rezepte im Internet finden.

Vorgehen:
- Nutze das web_search-Tool, um nach konkreten Rezepten zu suchen.
- Suche bei Bedarf mehrfach mit unterschiedlichen Suchbegriffen.
- Bewerte die Treffer und waehle die passendsten 1-3 Rezepte aus.

Gib das Ergebnis KOMPAKT und STRUKTURIERT zurueck, je Rezept:
- Titel
- Hauptzutaten
- Kurze Zubereitung (Stichpunkte)
- Quelle (URL), falls vorhanden

Erfinde keine Rezepte. Wenn die Suche nichts Brauchbares liefert, sage das klar."""


def create_recherche_agent():
    """Erstellt den Recherche-Sub-Agenten (ReAct mit eigenem web_search-Tool)."""
    model = ChatGroq(
        model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        temperature=0,
    )
    return create_react_agent(
        model=model,
        tools=[get_web_search_tool(max_results=5)],
        prompt=RECHERCHE_PROMPT,
    )


@tool
def recherche_rezepte(anfrage: str) -> str:
    """Sucht ueber einen spezialisierten Recherche-Agenten Rezepte im Internet.

    Nutze dieses Tool, wenn der Nutzer neue Rezeptideen braucht oder ein
    Gericht/Zutaten genannt hat, zu denen du Rezepte aus dem Web brauchst.
    Eingabe: eine natuerlichsprachige Anfrage, z. B.
    'Rezepte mit Haehnchen, Zitrone und Knoblauch'.
    Rueckgabe: eine kompakte, strukturierte Liste passender Rezepte.
    """
    agent = create_recherche_agent()
    result = agent.invoke({"messages": [HumanMessage(content=anfrage)]})
    # Die letzte AIMessage ist die finale, zusammengefasste Antwort des Sub-Agenten.
    # Nur diese fliesst zum Orchestrator zurueck (Kontext-Isolation). Wir begrenzen
    # die Laenge, damit der Orchestrator-Kontext nicht ueber das Token-Limit waechst.
    zusammenfassung = result["messages"][-1].content
    max_zeichen = 3000
    if len(zusammenfassung) > max_zeichen:
        zusammenfassung = zusammenfassung[:max_zeichen] + "\n[... gekuerzt ...]"
    return zusammenfassung
