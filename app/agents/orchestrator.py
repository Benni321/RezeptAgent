"""
Orchestrator-Agent (Phase 1)
============================
Haupt-Agent des RezeptAgenten. Nutzt LangGraph's ReAct-Architektur,
um Nutzereingaben zu verstehen und passende Tools aufzurufen.

TAO-Zyklus:
  Thought   -> LLM entscheidet, welches Tool benoetigt wird
  Action    -> Tool wird aufgerufen (z. B. web_search)
  Observation -> Ergebnis des Tools fliesst zurueck ins LLM

Phase 1 Tools: web_search
Phase 2+ Tools: vision_tool, rag_retriever, filter_tool, shopping_list_tool
"""

import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langgraph.prebuilt import create_react_agent

from app.tools.web_search import get_web_search_tool

load_dotenv()

SYSTEM_PROMPT = """Du bist ein hilfreicher Rezept-Assistent. Deine Aufgabe ist es, Nutzern
bei der Rezeptsuche zu helfen und passende Gerichte vorzuschlagen.

Wenn ein Nutzer ein Rezept sucht oder nach Zutaten fragt, nutze das web_search-Tool,
um aktuelle und passende Rezepte im Internet zu finden.

Antworte immer auf Deutsch und strukturiere deine Antworten klar und uebersichtlich.
Gib bei Rezepten immer Zutaten und Zubereitungsschritte an."""


def create_orchestrator():
    """
    Erstellt und gibt den LangGraph ReAct Orchestrator-Agent zurueck.

    Der Agent arbeitet im ReAct-Muster:
    1. Thought: Analyse der Nutzeranfrage
    2. Action: Tool-Aufruf (z. B. web_search)
    3. Observation: Auswertung des Tool-Ergebnisses
    -> Wiederholung bis finale Antwort
    """
    model = ChatGroq(
        model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        temperature=0,
    )

    tools = [
        get_web_search_tool(max_results=5),
    ]

    agent = create_react_agent(
        model=model,
        tools=tools,
        prompt=SYSTEM_PROMPT,
    )

    return agent
