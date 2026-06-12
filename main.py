"""
RezeptAgent — Einstiegspunkt (Phase 1)
=======================================
Startet den Orchestrator-Agent im interaktiven Modus.
Gibt den TAO-Zyklus (Thought, Action, Observation) sichtbar im Terminal aus.

Starten:
    python main.py

Voraussetzungen:
    - .env mit OPENAI_API_KEY und TAVILY_API_KEY
    - pip install -r requirements.txt
"""

from langchain_core.messages import HumanMessage

from app.agents.orchestrator import create_orchestrator

# Tools, hinter denen ein eigener Sub-Agent steckt (fuer eine klare Trace-Beschriftung).
SUB_AGENTEN = {"recherche_rezepte"}


def print_tao_trace(chunk: dict) -> None:
    """
    Gibt den TAO-Zyklus strukturiert im Terminal aus.

    LangGraph liefert pro Schritt ein Dict mit dem Node-Namen als Key:
    - 'agent'  -> Thought-Schritt (LLM-Entscheidung / Tool-Aufruf)
    - 'tools'  -> Observation-Schritt (Tool-/Sub-Agent-Ergebnis)
    """
    for node_name, node_output in chunk.items():
        messages = node_output.get("messages", [])
        for msg in messages:
            msg_type = type(msg).__name__

            if msg_type == "AIMessage":
                # Thought + Action: LLM hat entschieden, etwas aufzurufen.
                if msg.tool_calls:
                    for tc in msg.tool_calls:
                        ziel = "Sub-Agent" if tc["name"] in SUB_AGENTEN else "Tool"
                        print(f"\n[THOUGHT] Ich brauche {ziel}: {tc['name']}")
                        print(f"[ACTION]  Aufruf mit: {tc['args']}")
                # Finale Antwort (nur, wenn wirklich Text vorhanden ist).
                elif msg.content and msg.content.strip():
                    print(f"\n[ANSWER]  {msg.content}")

            elif msg_type == "ToolMessage":
                # Observation: Ergebnis eines Tools oder Sub-Agenten.
                quelle = "Sub-Agent" if msg.name in SUB_AGENTEN else "Tool"
                preview = msg.content[:300] + "..." if len(msg.content) > 300 else msg.content
                print(f"[OBSERVATION] {quelle} '{msg.name}' antwortete:\n  {preview}")


def run_agent(user_input: str) -> None:
    print("\n" + "=" * 60)
    print(f"ANFRAGE: {user_input}")
    print("=" * 60)

    agent = create_orchestrator()
    inputs = {"messages": [HumanMessage(content=user_input)]}

    for chunk in agent.stream(inputs, stream_mode="updates"):
        print_tao_trace(chunk)

    print("\n" + "=" * 60 + "\n")


def main():
    print("RezeptAgent gestartet. Tippe 'exit' zum Beenden.\n")

    while True:
        user_input = input("Du: ").strip()
        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit", "q"):
            print("Auf Wiedersehen!")
            break
        run_agent(user_input)


if __name__ == "__main__":
    main()
