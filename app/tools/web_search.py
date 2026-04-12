"""
Tool: web_search
Sucht im Internet nach Rezepten und Kochanleitungen via Tavily API.
Wird vom Orchestrator-Agent als Tool aufgerufen (TAO: Action-Schritt).
"""

from langchain_community.tools.tavily_search import TavilySearchResults


def get_web_search_tool(max_results: int = 5) -> TavilySearchResults:
    """
    Gibt das Tavily-Web-Search-Tool zurueck.
    Der Agent ruft dieses Tool auf, wenn er Rezepte im Internet suchen soll.
    Benoetigt: TAVILY_API_KEY in .env
    """
    return TavilySearchResults(
        max_results=max_results,
        name="web_search",
        description=(
            "Sucht im Internet nach Rezepten, Zutaten und Kochanweisungen. "
            "Nutze dieses Tool, wenn der Nutzer ein Rezept anfraegt oder "
            "Informationen zu bestimmten Zutaten oder Gerichten benoetigt. "
            "Eingabe: eine Suchanfrage als Text, z. B. 'Spaghetti Carbonara Rezept'."
        ),
    )
