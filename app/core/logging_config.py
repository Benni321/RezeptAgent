"""
Strukturiertes Logging / Tracing (W5, Begriffsniveau VL09: Trace/Span)
======================================================================
Eine einfache, abhaengigkeitsfreie Observability-Schicht: jeder Log-Eintrag ist
eine JSON-Zeile auf stdout (gut maschinen-auswertbar und in Containern/CI lesbar).

Trace/Span-Modell (bewusst an die OpenTelemetry-GenAI-Idee aus VL09 angelehnt,
ohne deren Infrastruktur):
- TRACE = ein kompletter Agent-Run. `starte_trace()` erzeugt eine trace_id, die
  ueber eine ContextVar automatisch an ALLE log_ereignis-Eintraege des Runs
  gehaengt wird — so lassen sich die Zeilen eines Laufs maschinell zusammensetzen.
- SPAN  = ein Teilschritt des Runs (LLM-Thought, Tool-Call, Sub-Agent-Delegation,
  finale Antwort) als eigener Log-Eintrag mit span_typ, name, dauer_ms, status.
- Optional wird der komplette Trace eines Runs als EINE JSON-Datei persistiert
  (Env AGENT_TRACE_DIR) — gemeinsame Quelle fuer Eval-Runner und Evidence.

Warum eigenes JSON-Logging statt Langfuse/OTel (ehrliche Grenze, docs/PROJEKTDOKU.md):
- Fuer EIN lokales Projekt ohne Betriebsteam reichen strukturierte stdout-/
  Datei-Logs voellig; eine Tracing-Plattform waere der Production-Schritt.
- Observability ist nicht nur Debugging, sondern auch eine Sicherheitsmassnahme
  (VL3: ungewoehnliche Tool-Aufruf-Muster im Audit erkennen).

Nutzung:
    from app.core.logging_config import get_logger, log_ereignis
    logger = get_logger("rezeptagent.api")
    log_ereignis(logger, "anfrage_empfangen", modus="einkaufsliste", hat_bild=False)
"""

import json
import logging
import os
import sys
import uuid
from contextvars import ContextVar
from pathlib import Path
from typing import Optional

_BASIS_NAME = "rezeptagent"
_konfiguriert = False

# Trace-Kontext des aktuellen Runs. ContextVar statt globaler Variable, damit
# parallele Requests (FastAPI) sich die trace_id nicht gegenseitig ueberschreiben.
_trace_id_var: ContextVar[Optional[str]] = ContextVar("rezeptagent_trace_id", default=None)


class _JsonFormatter(logging.Formatter):
    """Formatiert jeden Log-Eintrag als kompakte JSON-Zeile."""

    def format(self, record: logging.LogRecord) -> str:
        eintrag = {
            "zeit": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "komponente": record.name,
            "ereignis": record.getMessage(),
        }
        # Zusatzfelder, die ueber log_ereignis(...) mitgegeben wurden.
        for schluessel, wert in getattr(record, "felder", {}).items():
            eintrag[schluessel] = wert
        return json.dumps(eintrag, ensure_ascii=False)


def get_logger(name: str = _BASIS_NAME) -> logging.Logger:
    """Gibt einen konfigurierten Logger zurueck (JSON-Ausgabe auf stdout)."""
    global _konfiguriert
    if not _konfiguriert:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(_JsonFormatter())
        basis = logging.getLogger(_BASIS_NAME)
        basis.handlers.clear()
        basis.addHandler(handler)
        basis.setLevel(logging.INFO)
        basis.propagate = False
        _konfiguriert = True
    return logging.getLogger(name if name.startswith(_BASIS_NAME) else f"{_BASIS_NAME}.{name}")


def log_ereignis(logger: logging.Logger, ereignis: str, **felder) -> None:
    """Loggt ein benanntes Ereignis mit beliebigen strukturierten Zusatzfeldern.

    Laeuft gerade ein Trace (starte_trace), wird dessen trace_id automatisch
    angehaengt — kein Aufrufer muss sie durchreichen.
    """
    trace_id = _trace_id_var.get()
    if trace_id and "trace_id" not in felder:
        felder = {"trace_id": trace_id, **felder}
    logger.info(ereignis, extra={"felder": felder})


# ---------------------------------------------------------------------------
# Trace/Span (VL09)
# ---------------------------------------------------------------------------

def starte_trace() -> str:
    """Beginnt einen neuen Agent-Run-Trace und gibt seine trace_id zurueck."""
    trace_id = uuid.uuid4().hex[:12]
    _trace_id_var.set(trace_id)
    return trace_id


def aktuelle_trace_id() -> Optional[str]:
    """Gibt die trace_id des laufenden Runs zurueck (None ausserhalb eines Runs)."""
    return _trace_id_var.get()


def beende_trace() -> None:
    """Beendet den aktuellen Trace-Kontext (nachfolgende Logs ohne trace_id)."""
    _trace_id_var.set(None)


def log_span(logger: logging.Logger, span_typ: str, name: str,
             dauer_ms: Optional[int] = None, status: str = "ok", **felder) -> None:
    """Loggt einen Teilschritt des Runs als Span-artigen Eintrag (VL09).

    span_typ: "run" | "llm_thought" | "llm" | "tool" | "subagent" | "antwort".
    status:   "ok" | "fehler" (Fehler = Tool meldet Fehler-Observation o. ae.).
    """
    log_ereignis(logger, "span", span_typ=span_typ, name=name,
                 dauer_ms=dauer_ms, status=status, **felder)


def persistiere_trace(trace_daten: dict) -> Optional[Path]:
    """Schreibt den kompletten Trace eines Runs als EINE JSON-Datei (optional).

    Aktiv nur, wenn die Env-Variable AGENT_TRACE_DIR gesetzt ist (bewusst zur
    Laufzeit gelesen, damit Runner/Tests sie pro Lauf setzen koennen). Dateiname
    ist die trace_id -> Eval-Runner und Evidence-Erzeugung lesen dieselbe Quelle.
    Gibt den Pfad zurueck oder None, wenn die Persistenz aus ist.
    """
    ziel_dir = os.getenv("AGENT_TRACE_DIR", "").strip()
    if not ziel_dir:
        return None
    pfad = Path(ziel_dir) / f"{trace_daten.get('trace_id', 'ohne_id')}.json"
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(json.dumps(trace_daten, ensure_ascii=False, indent=2), encoding="utf-8")
    return pfad
