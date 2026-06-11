"""
Streamlit-GUI (Phase 3)
=======================
Grafische Oberflaeche des RezeptAgenten. Sie ruft das FastAPI-Backend auf
(`POST /chat`) und macht fuer den Nutzer klar sichtbar, WAS er eingeben kann
(Text, Foto, Modus, Filter) und WAS der Agent daraus macht (Rezept, Einkaufsliste,
sichtbarer TAO-Trace).

Diese strukturierte Eingabe liefert dem Agenten gleichzeitig eindeutige Daten
(zahlt auf W9 ein) -- der Nutzer muss nicht "frei" formulieren.

Start (Backend muss laufen):
    uvicorn app.api.main:app --reload      # Terminal 1
    streamlit run streamlit_app.py         # Terminal 2
"""

import os

import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000")

st.set_page_config(page_title="RezeptAgent", page_icon="🍳", layout="centered")
st.title("🍳 RezeptAgent")
st.caption("Sag, was du hast – der Agent recherchiert ein Rezept und sagt dir, was dir fehlt.")

# --- Seitenleiste: Backend-Status (nutzt /health) -------------------------------
with st.sidebar:
    st.subheader("Status")
    try:
        gesund = requests.get(f"{API_URL}/health", timeout=3).json()
        st.success(f"Backend erreichbar ({gesund.get('service', '?')})")
    except requests.RequestException:
        st.error("Backend nicht erreichbar. Läuft die API?")
        st.code("uvicorn app.api.main:app --reload", language="bash")
    st.caption(f"API: {API_URL}")

# --- Eingabe-Bereich: macht sichtbar, was man tun kann --------------------------
with st.form("anfrage"):
    nachricht = st.text_area(
        "Was möchtest du kochen? Welche Zutaten hast du?",
        placeholder="z. B. Ich habe Hähnchen, Reis und Zwiebeln und möchte etwas Schnelles.",
        height=100,
    )

    spalte_links, spalte_rechts = st.columns(2)
    with spalte_links:
        modus_label = st.radio(
            "Modus",
            ["Einkaufsliste ergänzen", "Nur vorhandene Zutaten"],
            help="Steuert, ob der Agent fehlende Zutaten vorschlagen darf.",
        )
    with spalte_rechts:
        filter_auswahl = st.multiselect(
            "Filter (optional)",
            ["vegetarisch", "vegan", "schnell (unter 30 min)", "glutenfrei", "laktosefrei", "kalorienarm"],
            help="Vorgaben, die der Agent berücksichtigt.",
        )

    foto = st.file_uploader(
        "Kühlschrank-Foto (optional)",
        type=["jpg", "jpeg", "png", "webp"],
        help="Lade ein Foto hoch – der Agent erkennt die Zutaten automatisch.",
    )

    absenden = st.form_submit_button("Rezept finden", type="primary")

# --- Verarbeitung ---------------------------------------------------------------
if absenden:
    if not nachricht.strip() and foto is None:
        st.warning("Bitte gib etwas ein oder lade ein Foto hoch.")
        st.stop()

    modus = "einkaufsliste" if modus_label.startswith("Einkaufsliste") else "vorhanden"
    daten = {
        "nachricht": nachricht.strip() or "Schlag mir ein Rezept aus den Zutaten auf dem Foto vor.",
        "modus": modus,
        "filter": ",".join(filter_auswahl),
    }
    dateien = {"bild": (foto.name, foto.getvalue(), foto.type)} if foto is not None else None

    with st.spinner("Der Agent denkt nach (Recherche, ggf. Bildanalyse) …"):
        try:
            antwort = requests.post(f"{API_URL}/chat", data=daten, files=dateien, timeout=120)
        except requests.RequestException:
            st.error("Backend nicht erreichbar. Bitte starte die API und versuche es erneut.")
            st.stop()

    if antwort.status_code != 200:
        st.error(f"Fehler ({antwort.status_code}): {antwort.text[:400]}")
        st.stop()

    ergebnis = antwort.json()

    # Erkannte Zutaten zur Bestätigung anzeigen (Human-in-the-Loop, VL5).
    if ergebnis.get("erkannte_zutaten"):
        st.info("Aus dem Foto erkannt: " + ", ".join(ergebnis["erkannte_zutaten"]))

    st.markdown(ergebnis.get("antwort", "_(keine Antwort)_"))

    # Sichtbarer TAO-Trace (P2): wie der Agent zur Antwort kam.
    with st.expander("🔎 Wie der Agent gearbeitet hat (TAO-Zyklus)"):
        for schritt in ergebnis.get("trace", []):
            if schritt["art"] == "aktion":
                st.markdown(f"**[Thought→Action]** {schritt.get('ziel')} `{schritt.get('name')}`")
                if schritt.get("args"):
                    st.code(str(schritt["args"]), language="json")
            else:
                inhalt = (schritt.get("inhalt") or "")[:600]
                st.markdown(f"**[Observation]** {schritt.get('quelle')} `{schritt.get('name')}`")
                st.text(inhalt)
