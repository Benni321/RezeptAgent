"""
Streamlit-GUI (Phase 3) — Einstiegspunkt
========================================
Grafische Oberflaeche des RezeptAgenten, aufgeteilt in mehrere Seiten
(st.navigation, Navigation erscheint oben in der Seitenleiste):

  - seiten/start.py          -> Startseite: kurze Begruessung + Ueberblick, was
                                der Agent kann, mit Links zu den anderen Seiten.
  - seiten/rezept_finden.py  -> Anfrage an den Agenten (POST /chat),
                                Erstlauf-Onboarding, TAO-Trace, Bewertung.
  - seiten/mein_kochbuch.py  -> eigene Seite fuer die gelernte Wissensbasis (W3):
                                alle Lieblingsrezepte, direkt aus den gespeicherten
                                Daten angezeigt (ohne Agenten-Lauf).
  - seiten/meine_wochenplaene.py -> eigene Seite fuer gespeicherte Wochenplaene:
                                auf "Rezept finden" per Button gesichert, hier
                                aus den gespeicherten Daten angezeigt (loeschbar).
  - seiten/mein_profil.py    -> eigene Seite fuer das dauerhafte Profil (Memory):
                                ansehen, bearbeiten, plus bisherige Bewertungen.
Gemeinsame Konstanten (API_URL, Options-Listen): seiten/_gemeinsam.py.

Start (Backend muss laufen):
    uvicorn app.api.main:app --reload --reload-dir app   # Terminal 1
    streamlit run streamlit_app.py                       # Terminal 2
"""

import streamlit as st

st.set_page_config(page_title="RezeptAgent", page_icon="🍳", layout="centered")

# Auswahl-Tags (Multiselect-Chips) in ruhigem, neutralem Grau-Blau statt
# Streamlit-Rot; gilt fuer alle Seiten.
st.markdown(
    """
    <style>
    span[data-baseweb="tag"] {
        background-color: #E2E8F0 !important;
        color: #334155 !important;
    }
    span[data-baseweb="tag"] svg { fill: #334155 !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

pg = st.navigation([
    st.Page("seiten/start.py", title="Start", icon="🏠", default=True),
    st.Page("seiten/rezept_finden.py", title="Rezept finden", icon="🍳"),
    st.Page("seiten/mein_kochbuch.py", title="Mein Kochbuch", icon="📖"),
    st.Page("seiten/meine_wochenplaene.py", title="Meine Wochenpläne", icon="📅"),
    st.Page("seiten/mein_profil.py", title="Mein Profil", icon="👤"),
])
pg.run()
