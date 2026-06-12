"""
Vision-Modul: Zutatenerkennung aus einem Foto (Phase 2c)   [W2]
===============================================================
Verarbeitet eine NICHT-textuelle Modalitaet (Bild) als Eingabe: ein Foto vom
Kuehlschrank/Vorrat wird an ein Vision-Language-Model (Groq Llama-4, multimodal)
gegeben, das die sichtbaren Lebensmittel als Liste zurueckgibt.

Designentscheidung (sinnvoll statt aufgesetzt):
- Bewusst KEIN eigener Agent, sondern ein vorgelagerter Vision-Schritt. Die
  Bilderkennung ist ein abgeschlossener Einzelschritt ohne Mehrschritt-Loop
  -> ein VLM-Aufruf genuegt (VL5-Muster: Bild als task_images).
- Das Ergebnis (Zutatenliste) wird dem Nutzer in der GUI zur BESTAETIGUNG
  angezeigt, bevor der Orchestrator darauf aufbaut. Grund: VLMs halluzinieren
  auch bei Bildern (VL5) -> Human-in-the-Loop.

Modell ueber GROQ_VISION_MODEL konfigurierbar (Default: multimodales Llama-4).
"""

import base64
import json
import os
import re

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_groq import ChatGroq

load_dotenv()

VISION_PROMPT = (
    "Auf diesem Foto sind Lebensmittel/Zutaten zu sehen (z. B. ein Kuehlschrank "
    "oder Vorratsschrank). Erkenne die einzelnen Lebensmittel. Antworte AUSSCHLIESSLICH "
    "mit einem JSON-Array von Strings, z. B. [\"Eier\", \"Milch\", \"Tomaten\"]. "
    "Nenne nur Dinge, die du wirklich erkennst, ohne Mengenangaben. Wenn du nichts "
    "Essbares erkennst, antworte mit []."
)


def _to_data_url(image_bytes: bytes, mime_type: str = "image/jpeg") -> str:
    """Kodiert Bild-Bytes als data-URL fuer die multimodale Modell-Eingabe."""
    b64 = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{mime_type};base64,{b64}"


def _parse_zutaten(text: str) -> list[str]:
    """Extrahiert eine Zutatenliste aus der Modellantwort - robust gegen Beiwerk.

    Bevorzugt ein JSON-Array; faellt sonst auf zeilen-/kommagetrennte Begriffe
    zurueck. So bleibt die Funktion auch dann nutzbar, wenn das Modell nicht
    exakt JSON liefert.
    """
    if not text:
        return []
    # 1) Versuch: JSON-Array irgendwo im Text finden.
    treffer = re.search(r"\[.*\]", text, re.DOTALL)
    if treffer:
        try:
            werte = json.loads(treffer.group(0))
            if isinstance(werte, list):
                return [str(z).strip() for z in werte if str(z).strip()]
        except json.JSONDecodeError:
            pass
    # 2) Fallback: Zeilen/Kommas, Aufzaehlungszeichen entfernen.
    roh = re.split(r"[\n,]+", text)
    return [re.sub(r"^[\-\*\d\.\)\s]+", "", t).strip() for t in roh if t.strip()]


def erkenne_zutaten_aus_bild(image_bytes: bytes, mime_type: str = "image/jpeg") -> list[str]:
    """Erkennt Lebensmittel auf einem Foto und gibt sie als Liste zurueck.

    Args:
        image_bytes: die rohen Bilddaten.
        mime_type: z. B. "image/jpeg" oder "image/png".
    Returns:
        Liste erkannter Zutaten (kann leer sein, wenn nichts erkannt wurde).
    """
    model = ChatGroq(
        model=os.getenv("GROQ_VISION_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct"),
        temperature=0,
    )
    nachricht = HumanMessage(
        content=[
            {"type": "text", "text": VISION_PROMPT},
            {"type": "image_url", "image_url": {"url": _to_data_url(image_bytes, mime_type)}},
        ]
    )
    antwort = model.invoke([nachricht])
    return _parse_zutaten(antwort.content)
