"""
RezeptAgent — CLI-Einstiegspunkt
================================
Startet den RezeptAgenten interaktiv ueber die ZENTRALE Service-Schicht
(app/core/agent_service.run_rezept_agent) — denselben Pfad, den auch API und
GUI nutzen. Damit gelten auch in der CLI: Wochenplan-Routing (mehrere Gerichte
-> code-orchestrierter Workflow), Memory-Injektion (Profil + Bewertungen) und
Observability (trace_id, Span-Logs, optionale Run-Persistenz).

Frueher rief die CLI den Orchestrator direkt auf und umging die Service-Schicht
(kein Wochenplan, kein Memory, keine trace_id) — das widersprach der
dokumentierten Architektur (docs/PROJEKTDOKU.md 2.1) und wurde behoben.

Der vollstaendige TAO-Zyklus (Thought, Action, Observation) wird nach dem Lauf
beschriftet im Terminal ausgegeben (P2).

Starten:
    python main.py

Voraussetzungen:
    - .env mit GROQ_API_KEY und TAVILY_API_KEY
    - pip install -r requirements.txt
"""

from app.core.agent_service import run_rezept_agent

# Observations in der Terminal-Ausgabe kuerzen (der volle Inhalt steht im
# persistierten Trace, wenn AGENT_TRACE_DIR gesetzt ist).
MAX_OBSERVATION_ZEICHEN = 300


def print_tao_trace(trace: list[dict]) -> None:
    """Gibt den gesammelten TAO-Trace beschriftet und nummeriert aus.

    Das Trace-Format ist das der Service-Schicht (art: aktion/beobachtung,
    ziel/quelle: Tool vs. Sub-Agent) — dieselben Schritte, die auch GUI,
    Eval-Runner und Evidence-Skripte sehen.
    """
    zyklus = 0
    for schritt in trace:
        if schritt.get("art") == "aktion":
            zyklus += 1
            print(f"\n[THOUGHT] Zyklus {zyklus}: Ich brauche {schritt['ziel']}: {schritt['name']}")
            print(f"[ACTION]  Aufruf mit: {schritt.get('args')}")
        elif schritt.get("art") == "beobachtung":
            inhalt = schritt.get("inhalt") or ""
            if len(inhalt) > MAX_OBSERVATION_ZEICHEN:
                inhalt = inhalt[:MAX_OBSERVATION_ZEICHEN] + "..."
            print(f"[OBSERVATION] {schritt['quelle']} '{schritt['name']}' antwortete:\n  {inhalt}")


def run_agent(user_input: str) -> None:
    print("\n" + "=" * 60)
    print(f"ANFRAGE: {user_input}")
    print("=" * 60)
    print("Agent arbeitet ... (der beschriftete TAO-Trace erscheint nach Abschluss)")

    # Technische Fehler (API-Limit, Netzwerk, fehlende Keys) graceful abfangen (W9):
    # eine klare Meldung statt eines Stacktrace, damit die CLI nutzbar bleibt.
    try:
        ergebnis = run_rezept_agent(user_input)
    except Exception as exc:
        print(f"\n[FEHLER] Anfrage konnte nicht verarbeitet werden ({type(exc).__name__}).")
        print("Moegliche Ursachen: API-Limit erreicht, Netzwerkproblem oder fehlende API-Keys.")
        return

    print_tao_trace(ergebnis["trace"])
    print(f"\n[ANSWER]  {ergebnis['antwort']}")
    print(f"\n(trace_id: {ergebnis['trace_id']})")
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
