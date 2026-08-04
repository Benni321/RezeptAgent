"""Kleine Text-Helfer, die mehrere Ausfuehrungspfade teilen."""

import json
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
    diese Heuristik zusaetzlich Label-Zeilen ("Rezept: X") und Fett-Spans.
    PRIORITAET: Erst werden ALLE gescannten Zeilen auf eine Markdown-Ueberschrift
    geprueft, dann erst Fett-Spans/Labels — sonst gewinnt ein fett gesetztes
    Wort aus einem Fallback-Vorspann ("... schlage ich **ausschliesslich** ...")
    gegen die spaeter folgende echte Ueberschrift (realer GUI-Lauf 2026-08-02).
    None statt Raten: Die GUI zeigt dann einen neutralen Platzhalter — frueher
    wurde die erste Prosa-Zeile uebernommen, was bei Fehlerfaellen Saetze wie
    "Da die Rezeptrecherche fehlgeschlagen ist, ..." als Rezeptnamen vorschlug.
    """
    if not antwort:
        return None
    zeilen = [z.strip() for z in antwort.splitlines() if z.strip()][:_MAX_TITEL_ZEILEN]
    # 1) Markdown-Ueberschrift hat Vorrang: "## Zitronenhaehnchen mit Knoblauch"
    for zeile in zeilen:
        if zeile.startswith("#"):
            titel = _als_titel(zeile)
            if titel:
                return titel
    # 2) Fallback ohne Ueberschrift: Fett-Spans und Klartext-Labels.
    for zeile in zeilen:
        if zeile.startswith("#"):
            continue
        # Fett-Span, auch mitten in Prosa: "Ich schlage das **X**-Rezept vor"
        for span in _FETT_SPAN.findall(zeile):
            titel = _als_titel(span)
            if titel:
                return titel
        # Klartext-Label am Zeilenanfang: "Rezept: Shakshuka"
        if _TITEL_LABEL.match(zeile):
            titel = _als_titel(zeile)
            if titel:
                return titel
    return None


# --- JSON aus einer Modellantwort holen -------------------------------------------

def json_objekt_aus_text(text: str) -> dict | None:
    r"""Extrahiert das ERSTE vollstaendige JSON-Objekt aus einer Modellantwort.

    Warum nicht einfach `re.search(r"\{.*\}", text, re.DOTALL)`? Weil dieser
    Ausdruck GIERIG ist: Er matcht vom ersten `{` bis zur LETZTEN `}` im ganzen
    Text. Modelle haengen an ihr JSON aber gern eine Erklaerung an ("Berechnung:
    ...{...}"), und dann ist der Match kein gueltiges JSON mehr -> die Schaetzung
    scheitert, obwohl das Modell sauber geantwortet hat. Real beobachtet bei der
    Naehrwert-Schaetzung (alle Werte 0.0 -> "NAEHRWERT-FEHLER" trotz korrekter
    Modellantwort).

    Deshalb: Klammern zaehlen und beim ersten balancierten Objekt aufhoeren.
    Robust zusaetzlich gegen Markdown-Codefences und ueberzaehlige Kommas vor der
    schliessenden Klammer. Gibt None zurueck, wenn nichts Brauchbares drinsteht.
    """
    if not text:
        return None
    bereinigt = entferne_reasoning(text)
    bereinigt = re.sub(r"```(?:json)?\s*|\s*```", "", bereinigt)

    start = bereinigt.find("{")
    while start != -1:
        tiefe, in_string, escaped = 0, False, False
        for i in range(start, len(bereinigt)):
            zeichen = bereinigt[i]
            if escaped:
                escaped = False
                continue
            if zeichen == "\\":
                escaped = True
            elif zeichen == '"':
                in_string = not in_string
            elif not in_string:
                if zeichen == "{":
                    tiefe += 1
                elif zeichen == "}":
                    tiefe -= 1
                    if tiefe == 0:
                        roh = bereinigt[start:i + 1]
                        roh = re.sub(r",(\s*[}\]])", r"\1", roh)  # trailing commas
                        try:
                            wert = json.loads(roh)
                        except json.JSONDecodeError:
                            break  # dieses Objekt ist kaputt -> naechstes probieren
                        return wert if isinstance(wert, dict) else None
        start = bereinigt.find("{", start + 1)
    return None
