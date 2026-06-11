"""
Agent-Service (Phase 3)
=======================
Zentrale Ausfuehrungsschicht, die CLI, API und GUI gemeinsam nutzen. Sie:
  1. verarbeitet optional ein Foto (Vision -> Zutaten, W2),
  2. baut aus Nachricht + Modus + Filtern eine klare Eingabe fuer den Orchestrator,
  3. fuehrt den Orchestrator aus und sammelt den TAO-Trace strukturiert ein,
  4. loggt die wichtigsten Ereignisse strukturiert (W5).

Damit gibt es genau EINE Stelle, an der der Agent gestartet wird -> kein doppelter
Code zwischen API und GUI, leichter testbar.
"""

from typing import Optional

from langchain_core.messages import HumanMessage

from app.agents.orchestrator import create_orchestrator
from app.core.logging_config import get_logger, log_ereignis
from app.tools.vision import erkenne_zutaten_aus_bild

logger = get_logger("rezeptagent.service")

# Tools, hinter denen ein eigener Sub-Agent steckt (fuer die Trace-Beschriftung).
SUB_AGENTEN = {"recherche_rezepte"}


def _baue_eingabe(nachricht: str, modus: str, filter_: list[str]) -> str:
    """Setzt aus Nachricht, Modus und Filtern eine eindeutige Orchestrator-Eingabe zusammen."""
    teile = [nachricht.strip()]
    if modus == "vorhanden":
        teile.append(
            "Modus: nur die vorhandenen Zutaten verwenden (plus Grundzutaten wie Salz, "
            "Pfeffer, Oel, Wasser). Schlage KEIN Rezept mit zusaetzlichen, fehlenden "
            "Zutaten vor; passe Rezepte notfalls an oder sage ehrlich, wenn nichts passt."
        )
    elif modus == "einkaufsliste":
        teile.append("Modus: Fehlende Zutaten duerfen ergaenzt und als Einkaufsliste ausgegeben werden.")
    if filter_:
        teile.append("Beruecksichtige diese Vorgaben: " + ", ".join(filter_) + ".")
    return "\n".join(teile)


def run_rezept_agent(
    nachricht: str,
    modus: str = "einkaufsliste",
    filter_: Optional[list[str]] = None,
    image_bytes: Optional[bytes] = None,
    image_mime: str = "image/jpeg",
) -> dict:
    """Fuehrt den RezeptAgenten aus und gibt Antwort + TAO-Trace zurueck.

    Returns:
        dict mit:
          - "antwort": finale Antwort des Orchestrators (str)
          - "trace": Liste der TAO-Schritte (Aktionen + Beobachtungen)
          - "erkannte_zutaten": aus dem Foto erkannte Zutaten oder None
    """
    filter_ = filter_ or []
    erkannte_zutaten: Optional[list[str]] = None

    # 1) Optional: Foto -> Zutaten (W2).
    if image_bytes:
        erkannte_zutaten = erkenne_zutaten_aus_bild(image_bytes, image_mime)
        log_ereignis(logger, "zutaten_aus_bild_erkannt", anzahl=len(erkannte_zutaten))
        if erkannte_zutaten:
            nachricht = f"{nachricht}\nLaut Foto habe ich folgende Zutaten: {', '.join(erkannte_zutaten)}".strip()

    eingabe = _baue_eingabe(nachricht, modus, filter_)
    log_ereignis(logger, "anfrage_empfangen", modus=modus, hat_bild=bool(image_bytes), anzahl_filter=len(filter_))

    # 2) Orchestrator ausfuehren und TAO-Trace mitschneiden.
    agent = create_orchestrator()
    trace: list[dict] = []
    antwort = ""

    # recursion_limit als Sicherheitsnetz gegen Endlosschleifen (begrenzt die TAO-Schritte,
    # bevor der Kontext ueber das Token-Limit waechst).
    for chunk in agent.stream(
        {"messages": [HumanMessage(content=eingabe)]},
        stream_mode="updates",
        config={"recursion_limit": 10},
    ):
        for _node, node_output in chunk.items():
            for msg in node_output.get("messages", []):
                msg_type = type(msg).__name__
                if msg_type == "AIMessage":
                    if msg.tool_calls:
                        for tc in msg.tool_calls:
                            ziel = "Sub-Agent" if tc["name"] in SUB_AGENTEN else "Tool"
                            trace.append({"art": "aktion", "ziel": ziel, "name": tc["name"], "args": tc["args"]})
                            log_ereignis(logger, "tool_aufruf", ziel=ziel, name=tc["name"])
                    elif msg.content and msg.content.strip():
                        antwort = msg.content
                elif msg_type == "ToolMessage":
                    quelle = "Sub-Agent" if msg.name in SUB_AGENTEN else "Tool"
                    trace.append({"art": "beobachtung", "quelle": quelle, "name": msg.name, "inhalt": msg.content})

    log_ereignis(logger, "antwort_fertig", anzahl_schritte=len(trace))
    return {"antwort": antwort, "trace": trace, "erkannte_zutaten": erkannte_zutaten}
