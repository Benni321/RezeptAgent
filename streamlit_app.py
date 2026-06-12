"""
Streamlit-GUI (Phase 3)
=======================
Grafische Oberflaeche des RezeptAgenten. Sie ruft das FastAPI-Backend auf
(`POST /chat`) und macht sichtbar, WAS man eingeben kann und WAS der Agent daraus
macht (Rezept, Einkaufsliste, sichtbarer TAO-Trace).

Personalisierung (Memory):
  - Onboarding-Fragerunde beim ersten Start -> dauerhaftes Profil (Geschmacks-
    Tendenz + was dem Nutzer wichtig ist). Bestimmt die STANDARD-Vorschlaege.
  - Pro Rezept ist die Geschmacksrichtung erneut waehlbar (vorbelegt aus dem
    Profil) -> Tagesform schlaegt Standard, ohne das Profil zu aendern.
  - Sterne-Bewertung nach dem Rezept -> gelerntes Signal fuer kuenftige Vorschlaege.
Die Ergebnis-Anzeige liegt in st.session_state, damit sie ueber Reruns (z. B. beim
Bewerten) erhalten bleibt.

Start (Backend muss laufen):
    uvicorn app.api.main:app --reload --reload-dir app   # Terminal 1
    streamlit run streamlit_app.py                       # Terminal 2
"""

import os

import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000")

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

st.set_page_config(page_title="RezeptAgent", page_icon="🍳", layout="centered")
st.title("🍳 RezeptAgent")
st.caption("Sag, was du hast – der Agent recherchiert ein Rezept und sagt dir, was dir fehlt.")


def _ableiten_titel(antwort: str) -> str:
    """Erste sinnvolle Zeile der Antwort als Rezept-Titel (fuer die Bewertung)."""
    for zeile in antwort.splitlines():
        z = zeile.strip().lstrip("#*-•0123456789. ").strip()
        if z:
            return z[:80]
    return "Rezept"


def _lade_profil():
    """Holt das gespeicherte Profil; gibt (profil, backend_ok) zurueck."""
    try:
        return requests.get(f"{API_URL}/praeferenzen", timeout=5).json(), True
    except requests.RequestException:
        return {"geschmack": [], "wichtig": [], "onboarding_done": False}, False


profil, backend_ok = _lade_profil()

# --- Seitenleiste: Status + Profil ----------------------------------------------
with st.sidebar:
    st.subheader("Status")
    if backend_ok:
        st.success("Backend erreichbar")
    else:
        st.error("Backend nicht erreichbar. Läuft die API?")
        st.code("uvicorn app.api.main:app --reload --reload-dir app", language="bash")
    st.caption(f"API: {API_URL}")

    if backend_ok and profil.get("onboarding_done"):
        st.divider()
        st.subheader("Dein Profil")
        st.caption("Ernährung: " + (", ".join(profil.get("ernaehrung", [])) or "–"))
        st.caption("Geschmack: " + (", ".join(profil.get("geschmack", [])) or "–"))
        st.caption("Wichtig: " + (", ".join(profil.get("wichtig", [])) or "–"))
        if st.button("Profil bearbeiten"):
            st.session_state["onboarding_offen"] = True
            st.rerun()

# --- Onboarding-Fragerunde (beim ersten Start oder auf Wunsch) -------------------
# Blockiert die Hauptansicht, bis das Profil einmal gesetzt ist (Personalisierungs-Basis).
braucht_onboarding = backend_ok and (
    not profil.get("onboarding_done") or st.session_state.get("onboarding_offen")
)
if braucht_onboarding:
    st.subheader("👋 Kurze Fragerunde – damit ich dich kenne")
    st.caption("Einmalig. Bestimmt deine Standard-Vorschläge; pro Rezept kannst du jederzeit abweichen.")
    with st.form("onboarding"):
        e = st.multiselect(
            "Isst du eingeschränkt? (Ernährung / Unverträglichkeiten)",
            sorted(set(ERNAEHRUNG_OPTIONEN) | set(profil.get("ernaehrung", []))),
            default=profil.get("ernaehrung", []),
            help="Gilt dauerhaft für jedes Rezept und wird strikt eingehalten.",
        )
        g = st.multiselect(
            "Worauf stehst du geschmacklich generell?",
            sorted(set(GESCHMACK_OPTIONEN) | set(profil.get("geschmack", []))),
            default=profil.get("geschmack", []),
        )
        w = st.multiselect(
            "Was ist dir bei Gerichten wichtig?",
            sorted(set(WICHTIG_OPTIONEN) | set(profil.get("wichtig", []))),
            default=profil.get("wichtig", []),
        )
        gespeichert = st.form_submit_button("Speichern & loslegen", type="primary")
    if gespeichert:
        try:
            requests.post(
                f"{API_URL}/praeferenzen",
                data={"ernaehrung": ",".join(e), "geschmack": ",".join(g), "wichtig": ",".join(w)},
                timeout=5,
            )
            st.session_state["onboarding_offen"] = False
            st.rerun()
        except requests.RequestException:
            st.error("Konnte das Profil nicht speichern.")
    st.stop()

# --- Eingabe-Bereich: macht sichtbar, was man tun kann --------------------------
with st.form("anfrage"):
    nachricht = st.text_area(
        "Was möchtest du kochen? Welche Zutaten hast du?",
        placeholder="z. B. Ich habe Hähnchen, Reis und Zwiebeln und möchte etwas Schnelles.",
        height=100,
    )

    modus_label = st.radio(
        "Modus",
        ["Einkaufsliste ergänzen", "Nur vorhandene Zutaten"],
        help="Steuert, ob der Agent fehlende Zutaten vorschlagen darf.",
        horizontal=True,
    )

    geschmack_heute = st.multiselect(
        "Geschmacksrichtung (für dieses Rezept)",
        sorted(set(GESCHMACK_OPTIONEN) | set(profil.get("geschmack", []))),
        default=profil.get("geschmack", []),
        help="Vorbelegt aus deinem Profil – für dieses Rezept frei änderbar (z. B. heute mal süß).",
    )

    anmerkungen = st.text_input(
        "Sonstige Wünsche (optional)",
        placeholder="z. B. wenig Fleisch, keine Pilze, extra knusprig",
        help="Freitext für Sonderwünsche, die in keine Liste passen – gilt nur für diese Anfrage.",
    )

    foto = st.file_uploader(
        "Kühlschrank-Foto (optional)",
        type=["jpg", "jpeg", "png", "webp"],
        help="Lade ein Foto hoch – der Agent erkennt die Zutaten automatisch.",
    )

    absenden = st.form_submit_button("Rezept finden", type="primary")

# --- Verarbeitung: Anfrage absenden, Ergebnis in session_state ablegen ----------
if absenden:
    if not nachricht.strip() and foto is None:
        st.warning("Bitte gib etwas ein oder lade ein Foto hoch.")
        st.stop()

    modus = "einkaufsliste" if modus_label.startswith("Einkaufsliste") else "vorhanden"
    daten = {
        "nachricht": nachricht.strip() or "Schlag mir ein Rezept aus den Zutaten auf dem Foto vor.",
        "modus": modus,
        "anmerkungen": anmerkungen.strip(),
        "geschmack_heute": ",".join(geschmack_heute),
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
    # In session_state ablegen, damit die Anzeige beim Bewerten (Rerun) erhalten bleibt.
    st.session_state["ergebnis"] = ergebnis
    st.session_state["titel"] = _ableiten_titel(ergebnis.get("antwort", ""))

# --- Anzeige: lebt aus session_state, ueberlebt Reruns --------------------------
if "ergebnis" in st.session_state:
    ergebnis = st.session_state["ergebnis"]

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

    # Bewertung (Memory): fliesst ins Bewertungsprofil ein.
    st.divider()
    st.subheader("Wie gut war dieses Rezept?")
    rezept_name = st.text_input("Rezept", value=st.session_state.get("titel", "Rezept"))
    sterne = st.slider("Bewertung (Sterne)", 1, 5, 4)
    if st.button("Bewertung speichern"):
        try:
            antwort_b = requests.post(
                f"{API_URL}/bewertung",
                data={"rezept": rezept_name, "sterne": sterne},
                timeout=5,
            )
            if antwort_b.status_code == 200:
                st.success(f"Danke! '{rezept_name}' mit {sterne} Sternen gespeichert – fließt künftig in Vorschläge ein.")
            else:
                st.error(f"Konnte die Bewertung nicht speichern ({antwort_b.status_code}).")
        except requests.RequestException:
            st.error("Backend nicht erreichbar – Bewertung nicht gespeichert.")
