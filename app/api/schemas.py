"""
Pydantic-Schemas + Eingabe-Validierung (W9)
===========================================
Definiert die Datenvertraege der API und validiert Nutzereingaben, BEVOR der
Agent gestartet wird. Fehlerhafte/unerwartete Eingaben werden so frueh und
graceful abgefangen (W9), statt erst tief im Agenten Fehler zu erzeugen.
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field

# Erlaubte Modi und Bild-MIME-Typen zentral definiert.
Modus = Literal["vorhanden", "einkaufsliste"]
ERLAUBTE_BILDTYPEN = {"image/jpeg", "image/png", "image/webp"}


class ChatAnfrage(BaseModel):
    """Validierte Chat-Anfrage an den RezeptAgenten."""

    nachricht: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Wunsch/Zutaten des Nutzers, z. B. 'Ich habe Haehnchen und Reis'.",
    )
    modus: Modus = Field(
        default="einkaufsliste",
        description="'vorhanden' = nur vorhandene Zutaten; 'einkaufsliste' = fehlende ergaenzen.",
    )
    filter: list[str] = Field(
        default_factory=list,
        max_length=10,
        description="Optionale Vorgaben wie 'vegetarisch', 'schnell', 'glutenfrei'.",
    )


class TraceSchritt(BaseModel):
    """Ein einzelner TAO-Schritt (Aktion oder Beobachtung) fuer die Anzeige."""

    art: str  # "aktion" oder "beobachtung"
    name: Optional[str] = None
    ziel: Optional[str] = None     # bei Aktion: "Tool" / "Sub-Agent"
    quelle: Optional[str] = None   # bei Beobachtung: "Tool" / "Sub-Agent"
    args: Optional[dict] = None
    inhalt: Optional[str] = None


class ChatAntwort(BaseModel):
    """Antwort der API: finale Antwort + sichtbarer TAO-Trace (P2)."""

    antwort: str
    trace: list[TraceSchritt] = Field(default_factory=list)
    erkannte_zutaten: Optional[list[str]] = None
