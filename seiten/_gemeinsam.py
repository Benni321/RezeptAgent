"""Gemeinsame Konstanten + UI-Helfer der GUI-Seiten (kein eigenes Seiten-Skript)."""

import os

import streamlit as st

# 127.0.0.1 statt localhost: Auf Windows loest "localhost" zuerst zu IPv6 (::1)
# auf, waehrend uvicorn nur auf IPv4 lauscht -- jeder Request zahlt dann ~2 s
# IPv6-Timeout, bevor er auf IPv4 zurueckfaellt (real gemessen: 2062 ms vs. 0 ms).
API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")

# Reine GESCHMACKSRICHTUNGEN/Kueche (nicht Diaet/Tempo -> das sind die Filter).
GESCHMACK_OPTIONEN = [
    "scharf", "mild", "mediterran", "italienisch", "asiatisch",
    "orientalisch", "deftig", "herzhaft", "süßlich",
]
# Was dem Nutzer bei Gerichten generell wichtig ist (dauerhafte Prioritaeten).
WICHTIG_OPTIONEN = [
    "gesund", "schnell", "günstig", "viel Gemüse",
    "wenig Fleisch", "proteinreich", "abwechslungsreich",
]
# Dauerhafte, HARTE Ernaehrungs-Eigenschaften/Unvertraeglichkeiten der Person.
ERNAEHRUNG_OPTIONEN = [
    "vegetarisch", "vegan", "pescetarisch",
    "glutenfrei", "laktosefrei", "ohne Schweinefleisch", "ohne Nüsse",
]


def zeige_gericht(gericht: dict, key: str) -> None:
    """Zeigt EIN Wochenplan-Gericht als eigenen, einzeln auf-/zuklappbaren
    Expander (Titel, Zutaten, Zubereitung falls vorhanden).

    Wiederverwendet auf allen Seiten, die Wochenplan-Gerichte anzeigen: die
    Vorschau vor dem Speichern (Rezept finden, Wochenplan aus Kochbuch) und die
    Liste bereits gespeicherter Plaene (Meine Wochenpläne). Verschachtelte
    Expander sind in dieser Streamlit-Version unproblematisch (empirisch
    getestet) -- diese Funktion wird deshalb auch INNERHALB eines aeusseren
    Plan-Expanders aufgerufen.
    """
    with st.expander(gericht.get("titel") or "Gericht", expanded=False, key=key):
        zutaten = gericht.get("zutaten") or []
        st.markdown("**Zutaten**")
        st.markdown("\n".join(f"- {z}" for z in zutaten) if zutaten else "_keine Zutaten hinterlegt_")
        if gericht.get("zubereitung"):
            st.markdown("**Zubereitung**")
            st.markdown("\n".join(f"{n}. {s}" for n, s in enumerate(gericht["zubereitung"], 1)))
