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

import time
from datetime import datetime
from typing import Optional

from langchain_core.messages import HumanMessage

from app.agents.orchestrator import create_orchestrator
from app.core.logging_config import (
    beende_trace, get_logger, log_ereignis, log_span, persistiere_trace, starte_trace,
)
from app.core import praeferenzen
from app.core.text_utils import entferne_reasoning, extrahiere_rezept_titel
from app.core.wochenplan_workflow import erkenne_wochenplan, plane_woche
from app.tools.vision import erkenne_zutaten_aus_bild

logger = get_logger("rezeptagent.service")

# Tools, hinter denen ein eigener Sub-Agent steckt (fuer die Trace-Beschriftung).
SUB_AGENTEN = {"recherche_rezepte"}

# Fehler-Praefixe, an denen eine Tool-Observation als "fehler"-Span erkannt wird
# (die Tools werfen bewusst keine Exceptions, sondern melden Fehler als Text —
# siehe docs/PROJEKTDOKU.md "Fehler werden zur Entscheidung, nicht zum Absturz").
FEHLER_OBSERVATIONS = ("WEBSUCHE-LEER", "WEBSUCHE-FEHLER", "RECHERCHE-FEHLER", "NAEHRWERT-FEHLER")


def _dauer_ms(start: float) -> int:
    return int((time.monotonic() - start) * 1000)


def _schliesse_trace(trace_id: str, t_start: float, nachricht: str, modus: str,
                     ergebnis: dict) -> dict:
    """Gemeinsamer Run-Abschluss beider Pfade: Run-Span, optionale Persistenz
    (AGENT_TRACE_DIR), Trace-Kontext beenden. Gibt das Ergebnis (um trace_id
    ergaenzt) zurueck."""
    ergebnis["trace_id"] = trace_id
    dauer = _dauer_ms(t_start)
    log_span(logger, "run", "run_rezept_agent", dauer_ms=dauer,
             anzahl_schritte=len(ergebnis["trace"]))
    persistiere_trace({
        "trace_id": trace_id,
        "zeit_start": datetime.now().isoformat(timespec="seconds"),
        "dauer_ms": dauer,
        "eingabe": nachricht,
        "modus": modus,
        "antwort": ergebnis["antwort"],
        "schritte": ergebnis["trace"],
    })
    log_ereignis(logger, "antwort_fertig", anzahl_schritte=len(ergebnis["trace"]))
    beende_trace()
    return ergebnis


def _baue_eingabe(nachricht: str, modus: str, harte_vorgaben: list[str], anmerkungen: str = "") -> str:
    """Setzt aus Nachricht, Modus, harten Vorgaben und Freitext eine eindeutige Orchestrator-Eingabe zusammen.

    Bewusste Abgrenzung der Eingabekanaele (siehe docs/PROJEKTDOKU.md "Memory"):
      - harte_vorgaben = MUSS erfuellt sein: Ernaehrung/Unvertraeglichkeit (vegan,
        glutenfrei ...) aus dem Profil, plus evtl. uebergebene Vorgaben.
      - anmerkungen    = freie, einmalige Sonderwuensche -> beruecksichtigen.
      - (Geschmack = weiche Pro-Rezept-/Profil-Vorgabe, wird separat injiziert.)
    """
    teile = [nachricht.strip()]
    if modus == "vorhanden":
        teile.append(
            "Modus: nur die vorhandenen Zutaten verwenden (plus Grundzutaten wie Salz, "
            "Pfeffer, Oel, Wasser). Die Zutaten sind ein Vorrat zur Auswahl - das Rezept "
            "muss NICHT alle davon verwenden, uebrige bleiben uebrig. Schlage KEIN Rezept "
            "mit zusaetzlichen, fehlenden Zutaten vor; passe Rezepte notfalls an oder sage "
            "ehrlich, wenn nichts passt."
        )
    elif modus == "einkaufsliste":
        teile.append("Modus: Fehlende Zutaten duerfen ergaenzt und als Einkaufsliste ausgegeben werden.")
    if harte_vorgaben:
        teile.append(
            "Diese Vorgaben MUESSEN erfuellt sein (Ernaehrung/Unvertraeglichkeit): "
            + ", ".join(harte_vorgaben) + "."
        )
    if anmerkungen.strip():
        teile.append("Zusaetzliche Wuensche des Nutzers: " + anmerkungen.strip())
    return "\n".join(teile)


def run_rezept_agent(
    nachricht: str,
    modus: str = "einkaufsliste",
    filter_: Optional[list[str]] = None,
    anmerkungen: str = "",
    geschmack_heute: Optional[list[str]] = None,
    image_bytes: Optional[bytes] = None,
    image_mime: str = "image/jpeg",
) -> dict:
    """Fuehrt den RezeptAgenten aus und gibt Antwort + TAO-Trace zurueck.

    Duenner Wrapper um _fuehre_lauf_aus mit EINEM Zweck: sicherstellen, dass der
    Trace-Kontext auch dann beendet wird, wenn der Lauf mit einer Exception
    abbricht. Ohne dieses finally bliebe die trace_id in der ContextVar stehen
    und haftete an den Logs des naechsten Requests im selben Thread -- die
    Observability (W5) wuerde also ausgerechnet im Fehlerfall unbrauchbar, wo man
    sie am dringendsten braucht. beende_trace() ist idempotent, der zusaetzliche
    Aufruf im Erfolgsfall (via _schliesse_trace) schadet nicht.

    Returns:
        dict mit:
          - "antwort": finale Antwort des Orchestrators (str)
          - "trace": Liste der TAO-Schritte (Aktionen + Beobachtungen)
          - "erkannte_zutaten": aus dem Foto erkannte Zutaten oder None
          - "rezept_titel": extrahierter Rezeptname (None, wenn keiner erkennbar)
    """
    try:
        return _fuehre_lauf_aus(nachricht, modus, filter_, anmerkungen,
                                geschmack_heute, image_bytes, image_mime)
    finally:
        beende_trace()


def _fuehre_lauf_aus(
    nachricht: str,
    modus: str,
    filter_: Optional[list[str]],
    anmerkungen: str,
    geschmack_heute: Optional[list[str]],
    image_bytes: Optional[bytes],
    image_mime: str,
) -> dict:
    """Die eigentliche Ausfuehrung (Vision -> Routing -> Agent/Workflow -> Trace)."""
    filter_ = filter_ or []
    erkannte_zutaten: Optional[list[str]] = None

    # Observability (W5/VL09): EIN Trace pro Run. Alle log_ereignis-Eintraege bis
    # zum Abschluss tragen automatisch diese trace_id (ContextVar).
    trace_id = starte_trace()
    t_start = time.monotonic()

    # 1) Optional: Foto -> Zutaten (W2). Ein Fehler in der Bildanalyse (z. B.
    #    VLM-Timeout) darf die Anfrage NICHT abbrechen: Wir loggen ihn und arbeiten
    #    ohne die Foto-Zutaten weiter (graceful degradation, W9).
    if image_bytes:
        try:
            erkannte_zutaten = erkenne_zutaten_aus_bild(image_bytes, image_mime)
        except Exception as exc:
            log_ereignis(logger, "vision_fehler", fehler=type(exc).__name__)
            erkannte_zutaten = []
        log_ereignis(logger, "zutaten_aus_bild_erkannt", anzahl=len(erkannte_zutaten))
        if erkannte_zutaten:
            nachricht = f"{nachricht}\nLaut Foto habe ich folgende Zutaten: {', '.join(erkannte_zutaten)}".strip()

    profil = praeferenzen.lade()

    # Harte Vorgaben = dauerhafte Ernaehrung/Unvertraeglichkeit aus dem Profil
    # (gilt bei JEDER Anfrage) plus evtl. uebergebene Vorgaben. MUSS erfuellt sein.
    harte_vorgaben = list(filter_) + profil.get("ernaehrung", [])

    # ROUTING: Wochenplan (MEHRERE Gerichte) -> code-orchestrierter Workflow mit
    # garantierter plan->pruefe->revidiere-Schleife. Einzelrezept -> agentischer
    # Orchestrator (unten). Grund fuer die Trennung siehe wochenplan_workflow.py.
    wp_params = erkenne_wochenplan(nachricht)
    if wp_params:
        log_ereignis(logger, "wochenplan_erkannt", anzahl_gerichte=wp_params["anzahl_gerichte"],
                     hat_kcal_limit=wp_params["kcal_limit"] is not None)
        ergebnis = plane_woche(
            nachricht, wp_params, harte_vorgaben,
            vorhandene_zutaten=erkannte_zutaten or [],
        )
        ergebnis["erkannte_zutaten"] = erkannte_zutaten
        # Ein Wochenplan hat keinen EINEN Rezeptnamen -> bewusst kein Titel
        # (die GUI zeigt dann einen neutralen Platzhalter im Bewertungsfeld).
        ergebnis["rezept_titel"] = None
        return _schliesse_trace(trace_id, t_start, nachricht, modus, ergebnis)

    eingabe = _baue_eingabe(nachricht, modus, harte_vorgaben, anmerkungen)

    # Personalisierung (siehe app/core/praeferenzen.py / docs/PROJEKTDOKU.md):
    #  - Geschmacksrichtung: pro Rezept gewaehlt, faellt sonst auf die dauerhafte
    #    Tendenz aus dem Profil zurueck (Standard). Bewusst als WEICHE Vorgabe.
    #  - dauerhaftes Signal (Prioritaeten + Bewertungen) wird als Kontext injiziert,
    #    nicht per Tool abgefragt.
    geschmack = geschmack_heute or profil["geschmack"]
    if geschmack:
        eingabe += (
            "\nGewuenschte Geschmacksrichtung (weiche Vorgabe, Standard aus Profil): "
            + ", ".join(geschmack) + "."
        )

    praeferenz_text = praeferenzen.als_kontext_text()
    if praeferenz_text:
        eingabe += f"\n{praeferenz_text}"

    log_ereignis(
        logger,
        "anfrage_empfangen",
        modus=modus,
        hat_bild=bool(image_bytes),
        anzahl_filter=len(filter_),
        hat_geschmack=bool(geschmack),
        hat_praeferenzen=bool(praeferenz_text),
    )

    # 2) Orchestrator ausfuehren und TAO-Trace mitschneiden. Jeder Teilschritt wird
    #    zusaetzlich als Span geloggt (VL09): LLM-Thought (Zeit seit dem letzten
    #    Stream-Ereignis = LLM-Latenz inkl. Netz), Tool-/Sub-Agent-Aufruf (Zeit von
    #    der Tool-Entscheidung bis zur Observation), finale Antwort.
    agent = create_orchestrator()
    trace: list[dict] = []
    antwort = ""
    t_letztes = time.monotonic()          # Zeitpunkt des letzten Stream-Ereignisses
    offene_tool_calls: dict[str, float] = {}  # tool_call_id -> Startzeit

    # recursion_limit als Sicherheitsnetz gegen Endlosschleifen. Hier laeuft nur der
    # EINZELREZEPT-Fall (Wochenplaene gehen ueber den code-orchestrierten Workflow, s. o.);
    # ein Einzelrezept braucht wenige Schritte (Recherche + ggf. Naehrwerte/Skalierung/
    # Einkaufsliste), 15 ist reichlich und deckelt Runaway.
    for chunk in agent.stream(
        {"messages": [HumanMessage(content=eingabe)]},
        stream_mode="updates",
        config={"recursion_limit": 15},
    ):
        for _node, node_output in chunk.items():
            for msg in node_output.get("messages", []):
                msg_type = type(msg).__name__
                if msg_type == "AIMessage":
                    if msg.tool_calls:
                        for tc in msg.tool_calls:
                            ziel = "Sub-Agent" if tc["name"] in SUB_AGENTEN else "Tool"
                            trace.append({"art": "aktion", "ziel": ziel, "name": tc["name"], "args": tc["args"]})
                            log_span(logger, "llm_thought", tc["name"], dauer_ms=_dauer_ms(t_letztes))
                            log_ereignis(logger, "tool_aufruf", ziel=ziel, name=tc["name"])
                            if tc.get("id"):
                                offene_tool_calls[tc["id"]] = time.monotonic()
                    elif msg.content and msg.content.strip():
                        antwort = entferne_reasoning(msg.content)
                        log_span(logger, "antwort", "finale_antwort", dauer_ms=_dauer_ms(t_letztes))
                    elif not antwort:
                        # Modell beendet die ReAct-Schleife (kein Tool-Call mehr), liefert
                        # dabei aber eine leere Nachricht -- real unter Last beobachtet
                        # (HTTP 200, aber keine sichtbare Antwort, kein geloggter Fehler).
                        # Gleiches Muster wie RECHERCHE-FEHLER/NAEHRWERT-FEHLER: der
                        # Fehlschlag wird sichtbar, statt still im Leeren zu verpuffen.
                        antwort = "Der Agent konnte keine Antwort formulieren (leere Modellantwort)."
                        log_span(logger, "antwort", "finale_antwort",
                                 dauer_ms=_dauer_ms(t_letztes), status="fehler")
                elif msg_type == "ToolMessage":
                    quelle = "Sub-Agent" if msg.name in SUB_AGENTEN else "Tool"
                    inhalt = msg.content or ""
                    t_call = offene_tool_calls.pop(getattr(msg, "tool_call_id", None), t_letztes)
                    dauer = _dauer_ms(t_call)
                    status = "fehler" if inhalt.startswith(FEHLER_OBSERVATIONS) else "ok"
                    trace.append({"art": "beobachtung", "quelle": quelle, "name": msg.name,
                                  "inhalt": inhalt, "dauer_ms": dauer, "status": status})
                    log_span(logger, "subagent" if msg.name in SUB_AGENTEN else "tool",
                             msg.name, dauer_ms=dauer, status=status)
                t_letztes = time.monotonic()

    # Rezeptname als eigenes, maschinenlesbares Feld (fuer Bewertung/Kochbuch in
    # der GUI): Prompt fordert '## <Rezeptname>' als erste Zeile (orchestrator.py),
    # die Heuristik faengt Abweichungen ab; None, wenn kein belastbarer Titel
    # gefunden wird (GUI zeigt dann einen neutralen Platzhalter).
    return _schliesse_trace(trace_id, t_start, nachricht, modus,
                            {"antwort": antwort, "trace": trace,
                             "erkannte_zutaten": erkannte_zutaten,
                             "rezept_titel": extrahiere_rezept_titel(antwort)})
