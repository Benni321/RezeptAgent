"""
Strukturiertes Logging / Tracing (W5)
=====================================
Eine einfache, abhaengigkeitsfreie Observability-Schicht: jeder Log-Eintrag ist
eine JSON-Zeile auf stdout (gut maschinen-auswertbar und in Containern/CI lesbar).

Warum eigenes JSON-Logging statt nur print():
- Tool-Aufrufe, Fehler und Anfragen werden einheitlich und durchsuchbar erfasst.
- Observability ist nicht nur Debugging, sondern auch eine Sicherheitsmassnahme
  (VL3: ungewoehnliche Tool-Aufruf-Muster erkennen).

Nutzung:
    from app.core.logging_config import get_logger, log_ereignis
    logger = get_logger("rezeptagent.api")
    log_ereignis(logger, "anfrage_empfangen", modus="einkaufsliste", hat_bild=False)
"""

import json
import logging
import sys

_BASIS_NAME = "rezeptagent"
_konfiguriert = False


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
    """Loggt ein benanntes Ereignis mit beliebigen strukturierten Zusatzfeldern."""
    logger.info(ereignis, extra={"felder": felder})
