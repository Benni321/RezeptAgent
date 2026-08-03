"""
Seite: Mein Profil
==================
Dauerhaftes Geschmacksprofil (Memory) ansehen und bearbeiten: harte
Ernaehrungs-Vorgaben, Geschmacks-Tendenz, Prioritaeten -- plus die bisherigen
Sterne-Bewertungen (gelerntes Signal). Schreiben laeuft wie ueberall ueber den
deterministischen API-Pfad (POST /praeferenzen), nie ueber den Agenten.
"""

import requests
import streamlit as st

from seiten._gemeinsam import (
    API_URL, ERNAEHRUNG_OPTIONEN, GESCHMACK_OPTIONEN, WICHTIG_OPTIONEN,
)

st.page_link("seiten/start.py", label="Zur Startseite", icon="🏠")

st.title("👤 Mein Profil")
st.caption("Dauerhafte Vorgaben und Vorlieben – der Agent berücksichtigt sie bei jeder Anfrage.")

try:
    _antwort = requests.get(f"{API_URL}/praeferenzen", timeout=5)
    if _antwort.status_code != 200:
        raise requests.RequestException(f"Status {_antwort.status_code}")
    profil = _antwort.json()
except requests.RequestException:
    st.error("Backend nicht erreichbar. Läuft die API?")
    st.code("uvicorn app.api.main:app --reload --reload-dir app", language="bash")
    st.stop()

# Erfolgsmeldung des letzten Speicherns (ueberlebt den Rerun nach dem Submit).
if st.session_state.pop("profil_gespeichert", False):
    st.success("Profil gespeichert – gilt ab der nächsten Anfrage.")

with st.form("profil_bearbeiten"):
    # accept_new_options: eigene Tags einfach eintippen (z. B. "Allergie gegen
    # Fisch"). Tags sind freie Strings -- der Agent bekommt sie woertlich als
    # Vorgabe-Text (siehe agent_service._baue_eingabe).
    e = st.multiselect(
        "Ernährung / Unverträglichkeiten (hart – gilt bei jeder Anfrage)",
        sorted(set(ERNAEHRUNG_OPTIONEN) | set(profil.get("ernaehrung", []))),
        default=profil.get("ernaehrung", []),
        accept_new_options=True,
        help="Eigene Einträge (z. B. 'Allergie gegen Erdbeeren') eintippen und mit Enter bestätigen.",
    )
    g = st.multiselect(
        "Geschmacks-Tendenz (weich – Standard, pro Rezept änderbar)",
        sorted(set(GESCHMACK_OPTIONEN) | set(profil.get("geschmack", []))),
        default=profil.get("geschmack", []),
        accept_new_options=True,
        help="Eigene Richtungen einfach eintippen und mit Enter bestätigen.",
    )
    w = st.multiselect(
        "Was dir bei Gerichten wichtig ist",
        sorted(set(WICHTIG_OPTIONEN) | set(profil.get("wichtig", []))),
        default=profil.get("wichtig", []),
        accept_new_options=True,
        help="Eigene Prioritäten einfach eintippen und mit Enter bestätigen.",
    )
    speichern = st.form_submit_button("Profil speichern", type="primary")

if speichern:
    try:
        requests.post(
            f"{API_URL}/praeferenzen",
            data={"ernaehrung": ",".join(e), "geschmack": ",".join(g), "wichtig": ",".join(w)},
            timeout=5,
        )
        st.session_state["profil_gespeichert"] = True
        st.rerun()
    except requests.RequestException:
        st.error("Konnte das Profil nicht speichern.")

# --- Bewertungen: das gelernte Signal, nur lesend --------------------------------
bewertungen = profil.get("bewertungen", {})
if bewertungen:
    st.divider()
    st.subheader("Meine Bewertungen")
    st.caption("Ab 4 Sternen landet das Rezept zusätzlich im Kochbuch; schlecht Bewertetes meidet der Agent.")
    for titel, sterne in sorted(bewertungen.items(), key=lambda x: (-x[1], x[0])):
        st.markdown(f"{'⭐' * int(sterne)}&nbsp;&nbsp;{titel}")
