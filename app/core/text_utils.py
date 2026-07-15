"""Kleine Text-Helfer, die mehrere Ausfuehrungspfade teilen."""

import re

# Reasoning-Modelle (z. B. qwen3) geben ihren Denkprozess in <think>...</think>
# aus. Das gehoert NICHT in die Nutzerantwort -> vor der Ausgabe entfernen.
_THINK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def entferne_reasoning(text: str) -> str:
    """Entfernt <think>...</think>-Bloecke und trimmt die Antwort.

    Robust auch gegen einen abgeschnittenen, nicht geschlossenen <think>-Block
    (dann wird ab dem Tag alles entfernt).
    """
    if not text:
        return ""
    bereinigt = _THINK.sub("", text)
    # Fallback: geoeffneter, aber nie geschlossener <think>-Block.
    offen = bereinigt.lower().find("<think>")
    if offen != -1:
        bereinigt = bereinigt[:offen]
    return bereinigt.strip()
