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
        description="Harte Vorgaben fuer DIESE Anfrage (Diaet/Tempo): 'vegetarisch', 'schnell', 'glutenfrei'.",
    )
    anmerkungen: str = Field(
        default="",
        max_length=500,
        description="Freitext-Sonderwuensche, die in keine Liste passen, z. B. 'wenig Fleisch', 'keine Pilze'.",
    )
    geschmack_heute: list[str] = Field(
        default_factory=list,
        max_length=10,
        description="Geschmacksrichtung NUR fuer diese Anfrage (Default aus dem Profil), z. B. 'suesslich'.",
    )


class TraceSchritt(BaseModel):
    """Ein einzelner TAO-Schritt (Aktion oder Beobachtung) fuer die Anzeige."""

    art: str  # "aktion" oder "beobachtung"
    name: Optional[str] = None
    ziel: Optional[str] = None     # bei Aktion: "Tool" / "Sub-Agent"
    quelle: Optional[str] = None   # bei Beobachtung: "Tool" / "Sub-Agent"
    args: Optional[dict] = None
    inhalt: Optional[str] = None
    dauer_ms: Optional[int] = None  # Span-Dauer des Schritts (W5/VL09)
    status: Optional[str] = None    # "ok" / "fehler" (Fehler-Observation)


class ChatAntwort(BaseModel):
    """Antwort der API: finale Antwort + sichtbarer TAO-Trace (P2)."""

    antwort: str
    trace: list[TraceSchritt] = Field(default_factory=list)
    erkannte_zutaten: Optional[list[str]] = None
    trace_id: Optional[str] = None  # verknuepft die Antwort mit den JSON-Logs (W5)
    rezept_titel: Optional[str] = None  # extrahierter Rezeptname fuer Bewertung/Kochbuch (None = kein belastbarer Titel)
    gerichte: Optional[list[dict]] = None  # NUR bei Wochenplan-Antworten gesetzt (je {"titel", "zutaten"})


class WochenplanSpeichern(BaseModel):
    """Eingabe zum Sichern eines fertig geplanten Wochenplans (POST /wochenplan)."""

    titel: str = Field(default="", max_length=100)
    nachricht: str = Field(default="", max_length=2000)
    antwort: str = Field(..., min_length=1)
    gerichte: list[dict] = Field(..., min_length=1)


class KochbuchRezeptSpeichern(BaseModel):
    """Eingabe fuer ein manuell hinzugefuegtes Kochbuch-Rezept (POST /kochbuch)."""

    titel: str = Field(..., min_length=1, max_length=100)
    zutaten: list[str] = Field(..., min_length=1, max_length=50)
    zubereitung: list[str] = Field(default_factory=list, max_length=30)
    sterne: Optional[int] = Field(default=None, ge=1, le=5)


class WochenplanAusKochbuch(BaseModel):
    """Eingabe zum deterministischen Zusammenstellen eines Wochenplans aus
    bereits gespeicherten Kochbuch-Rezepten (POST /wochenplan/aus-kochbuch)."""

    rezept_titel: list[str] = Field(..., min_length=1, max_length=7)
    vorhandene_zutaten: list[str] = Field(default_factory=list, max_length=50)
