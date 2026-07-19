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


# --- Rezept-Titel aus einer Agent-Antwort ----------------------------------------
# Abschnitts-Labels, die in Antworten fett/als Ueberschrift stehen, aber kein
# Rezeptname sind ("**Zutaten (fuer 2 Portionen):**", "**Kalorien:** ...").
_KEIN_TITEL_PREFIX = re.compile(
    r"^(zutaten|zubereitung|einkaufsliste|kalorien|kcal|n(ae|ä)hrwerte?|"
    r"portionen|hinweis|tipp|quelle|bewertung|modus|wochenplan)\b",
    re.IGNORECASE,
)
# Label VOR dem eigentlichen Namen: "Vorgeschlagenes Rezept: Shakshuka".
_TITEL_LABEL = re.compile(
    r"^(vorgeschlagenes\s+rezept|rezeptvorschlag|rezept|gericht(\s*\d+)?)\s*:\s*",
    re.IGNORECASE,
)
_FETT_SPAN = re.compile(r"\*\*(.+?)\*\*")
_MAX_TITEL_ZEILEN = 15
_MAX_TITEL_LAENGE = 80


def _als_titel(text: str) -> str | None:
    """Bereinigt einen Kandidaten (Markdown, Labels) und verwirft Nicht-Titel."""
    kandidat = text.strip().strip("*_#").strip()
    kandidat = _TITEL_LABEL.sub("", kandidat)
    kandidat = kandidat.strip().rstrip(":").strip()
    if not kandidat or len(kandidat) > _MAX_TITEL_LAENGE:
        return None
    if _KEIN_TITEL_PREFIX.match(kandidat):
        return None
    return kandidat


def extrahiere_rezept_titel(antwort: str) -> str | None:
    """Extrahiert den Rezeptnamen aus einer Agent-Antwort — oder None.

    Der Orchestrator soll die Antwort per Prompt mit '## <Rezeptname>' beginnen;
    weil Prompt-Regeln weiches Modellverhalten bleiben (PROJEKTDOKU 5.8), prueft
    diese Heuristik in den ersten Zeilen zusaetzlich Label-Zeilen ("Rezept: X")
    und Fett-Spans. None statt Raten: Die GUI zeigt dann einen neutralen
    Platzhalter — frueher wurde die erste Prosa-Zeile uebernommen, was bei
    Fehlerfaellen Saetze wie "Da die Rezeptrecherche fehlgeschlagen ist, ..."
    als Rezeptnamen vorschlug.
    """
    if not antwort:
        return None
    zeilen = [z.strip() for z in antwort.splitlines() if z.strip()]
    for zeile in zeilen[:_MAX_TITEL_ZEILEN]:
        # 1) Markdown-Ueberschrift: "## Zitronenhaehnchen mit Knoblauch"
        if zeile.startswith("#"):
            titel = _als_titel(zeile)
            if titel:
                return titel
            continue
        # 2) Fett-Span, auch mitten in Prosa: "Ich schlage das **X**-Rezept vor"
        for span in _FETT_SPAN.findall(zeile):
            titel = _als_titel(span)
            if titel:
                return titel
        # 3) Klartext-Label am Zeilenanfang: "Rezept: Shakshuka"
        if _TITEL_LABEL.match(zeile):
            titel = _als_titel(zeile)
            if titel:
                return titel
    return None
