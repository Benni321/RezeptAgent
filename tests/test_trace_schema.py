"""Tests fuer das Trace/Span-Schema (W5 -> VL09-Niveau) — gemockt, ohne Keys.

Belegt die zwei Kernzusagen der Observability-Schicht:
  1. Alle Log-Eintraege eines Runs tragen automatisch dieselbe trace_id
     (ContextVar, kein Durchreichen noetig) — und ausserhalb eines Runs keine.
  2. Ein kompletter Agent-Run wird (wenn AGENT_TRACE_DIR gesetzt ist) als EINE
     zusammenhaengende, maschinenlesbare JSON-Datei persistiert, deren Schritte
     Span-Felder (dauer_ms, status) tragen — die gemeinsame Quelle fuer
     Eval-Runner und Evidence-Erzeugung.
"""

import io
import json
import logging

from app.core import agent_service as svc
from app.core import logging_config as lc


def test_log_ereignis_traegt_trace_id_nur_im_run():
    logger = lc.get_logger("rezeptagent.test")
    puffer = io.StringIO()
    handler = logging.StreamHandler(puffer)
    handler.setFormatter(lc._JsonFormatter())
    logging.getLogger("rezeptagent").addHandler(handler)
    try:
        trace_id = lc.starte_trace()
        lc.log_ereignis(logger, "im_run", foo=1)
        lc.log_span(logger, "tool", "naehrwerte_schaetzen", dauer_ms=42, status="ok")
        lc.beende_trace()
        lc.log_ereignis(logger, "ausserhalb")
    finally:
        logging.getLogger("rezeptagent").removeHandler(handler)

    zeilen = [json.loads(z) for z in puffer.getvalue().splitlines()]
    assert zeilen[0]["trace_id"] == trace_id           # automatisch angehaengt
    assert zeilen[0]["foo"] == 1
    # Span-Eintrag: gleiche trace_id + Span-Pflichtfelder (VL09-Schema).
    assert zeilen[1]["ereignis"] == "span"
    assert zeilen[1]["trace_id"] == trace_id
    assert zeilen[1]["span_typ"] == "tool"
    assert zeilen[1]["dauer_ms"] == 42
    assert zeilen[1]["status"] == "ok"
    assert "trace_id" not in zeilen[2]                 # nach beende_trace: keine


def test_run_persistiert_zusammenhaengenden_trace(monkeypatch, tmp_path):
    monkeypatch.setenv("AGENT_TRACE_DIR", str(tmp_path / "runs"))
    monkeypatch.setattr(svc.praeferenzen, "_DEFAULT_PFAD", str(tmp_path / "p.json"))

    # Minimaler agentischer Lauf: Tool-Entscheidung -> (Fehler-)Observation -> Antwort.
    class AIMessage:
        def __init__(self, content="", tool_calls=None):
            self.content, self.tool_calls = content, tool_calls or []

    class ToolMessage:
        def __init__(self, name, content, tool_call_id):
            self.name, self.content, self.tool_call_id = name, content, tool_call_id

    class FakeOrchestrator:
        def stream(self, *a, **k):
            return iter([
                {"agent": {"messages": [AIMessage(tool_calls=[
                    {"name": "recherche_rezepte", "args": {"anfrage": "x"}, "id": "c1"}])]}},
                {"tools": {"messages": [ToolMessage("recherche_rezepte", "WEBSUCHE-LEER: nichts", "c1")]}},
                {"agent": {"messages": [AIMessage(content="Fertige Antwort")]}},
            ])

    monkeypatch.setattr(svc, "create_orchestrator", lambda: FakeOrchestrator())

    ergebnis = svc.run_rezept_agent(nachricht="Was kann ich kochen?")

    # Rueckgabe traegt die trace_id, Datei <trace_id>.json existiert.
    trace_id = ergebnis["trace_id"]
    assert trace_id
    datei = tmp_path / "runs" / f"{trace_id}.json"
    assert datei.exists()

    daten = json.loads(datei.read_text(encoding="utf-8"))
    # Schema: ein zusammenhaengender Run mit Metadaten + allen Schritten.
    assert daten["trace_id"] == trace_id
    for feld in ("zeit_start", "dauer_ms", "eingabe", "modus", "antwort", "schritte"):
        assert feld in daten, f"Trace-Schema unvollstaendig: {feld} fehlt"
    assert daten["antwort"] == "Fertige Antwort"
    assert [s["art"] for s in daten["schritte"]] == ["aktion", "beobachtung"]
    # Span-Felder an der Observation: Dauer gemessen, Fehler-Praefix -> status "fehler".
    beobachtung = daten["schritte"][1]
    assert isinstance(beobachtung["dauer_ms"], int)
    assert beobachtung["status"] == "fehler"
