"""
Seite: Start (Startseite)
=========================
Kurze Begruessung + Ueberblick, was der Agent kann, mit direkten Links zu den
anderen Seiten. Rein informativ, kein Agenten-/API-Aufruf noetig.
"""

import streamlit as st

st.title("🍳 RezeptAgent")
st.caption("von Benni und Jonathan")

st.markdown(
    "Willkommen! Der RezeptAgent hilft dir, aus dem zu kochen, was du gerade hast "
    "— oder plant dir gleich mehrere Tage im Voraus. Er merkt sich, was dir "
    "schmeckt, und wird mit jeder Bewertung ein bisschen besser."
)

st.subheader("Was kannst du tun?")

st.markdown(
    "- 🍳 **Finde ein leckeres Rezept:** sag, was für Zutaten du hast oder "
    "worauf du Lust hast — der Agent recherchiert und schlägt dir ein Rezept vor.\n"
    "- ⭐ **Rezept klingt super lecker?** Speichere es als Lieblingsrezept mit "
    "Bewertung ab.\n"
    "- 📖 **Auf deine Lieblingsrezepte zugreifen:** frag gezielt nach deinem "
    "Lieblingsrezept, und der Agent holt es aus deinem persönlichen Kochbuch "
    "und sagt dir, was du noch dafür brauchst.\n"
    "- 🔍 **Kochbuch erstellen:** speichere deine Lieblingsrezepte ab und "
    "erstelle so dein eigenes Kochbuch.\n"
    "- 📅 **Essensplan:** sag dem Agenten, für wie viele Tage und mit welchen "
    "Vorgaben (z. B. Personenzahl) du einen brauchst, und er stellt dir einen "
    "kompletten Plan inklusive Einkaufsliste zusammen.\n"
    "- 🔥 **Kalorien tracken?** Sag dem Agenten Bescheid und gib deine "
    "kcal-Limits an."
)

st.divider()

links = st.columns(3)
with links[0]:
    st.page_link("seiten/rezept_finden.py", label="Rezept finden", icon="🍳")
with links[1]:
    st.page_link("seiten/mein_kochbuch.py", label="Mein Kochbuch", icon="📖")
with links[2]:
    st.page_link("seiten/meine_wochenplaene.py", label="Meine Wochenpläne", icon="📅")
