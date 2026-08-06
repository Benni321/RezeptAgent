"""
Seite: Rezept finden (Hauptseite)
=================================
Ruft das FastAPI-Backend auf (`POST /chat`) und macht sichtbar, WAS man eingeben
kann und WAS der Agent daraus macht (Rezept, Einkaufsliste, sichtbarer TAO-Trace).

Personalisierung (Memory):
  - Onboarding-Fragerunde beim ersten Start -> dauerhaftes Profil (Geschmacks-
    Tendenz + was dem Nutzer wichtig ist). Bestimmt die STANDARD-Vorschlaege.
  - Pro Rezept ist die Geschmacksrichtung erneut waehlbar (vorbelegt aus dem
    Profil) -> Tagesform schlaegt Standard, ohne das Profil zu aendern.
  - Sterne-Bewertung nach dem Rezept -> gelerntes Signal fuer kuenftige Vorschlaege.
Die Ergebnis-Anzeige liegt in st.session_state, damit sie ueber Reruns (z. B. beim
Bewerten) erhalten bleibt.
"""

import requests
import streamlit as st

from seiten._gemeinsam import (
    API_URL, ERNAEHRUNG_OPTIONEN, GESCHMACK_OPTIONEN, WICHTIG_OPTIONEN, zeige_gericht,
)

st.page_link("seiten/start.py", label="Zur Startseite", icon="🏠")

st.title("🍳 RezeptAgent")
st.caption("Sag, was du hast – der Agent recherchiert ein Rezept und sagt dir, was dir fehlt.")


def _lade_profil():
    """Holt das gespeicherte Profil; gibt (profil, backend_ok) zurueck."""
    try:
        antwort = requests.get(f"{API_URL}/praeferenzen", timeout=5)
        if antwort.status_code != 200:
            raise requests.RequestException(f"Status {antwort.status_code}")
        return antwort.json(), True
    except requests.RequestException:
        return {"geschmack": [], "wichtig": [], "onboarding_done": False}, False


profil, backend_ok = _lade_profil()

# --- Seitenleiste: Status ---------------------------------------------------
with st.sidebar:
    st.subheader("Status")
    if backend_ok:
        st.success("Backend erreichbar")
    else:
        st.error("Backend nicht erreichbar. Läuft die API?")
        st.code("uvicorn app.api.main:app --reload --reload-dir app", language="bash")
    st.caption(f"API: {API_URL}")

# --- Onboarding-Fragerunde (beim ersten Start oder auf Wunsch) -------------------
# Blockiert die Hauptansicht, bis das Profil einmal gesetzt ist (Personalisierungs-Basis).
braucht_onboarding = backend_ok and (
    not profil.get("onboarding_done") or st.session_state.get("onboarding_offen")
)
if braucht_onboarding:
    st.subheader("👋 Kurze Fragerunde – damit ich dich kenne")
    st.caption("Einmalig. Bestimmt deine Standard-Vorschläge; pro Rezept kannst du jederzeit abweichen.")
    with st.form("onboarding"):
        # accept_new_options: eigene Tags einfach eintippen (z. B. "Allergie gegen
        # Fisch"). Tags sind freie Strings, keine feste Auswahl -- der Agent bekommt
        # sie woertlich als Vorgabe-Text (siehe agent_service._baue_eingabe).
        e = st.multiselect(
            "Isst du eingeschränkt? (Ernährung / Unverträglichkeiten)",
            sorted(set(ERNAEHRUNG_OPTIONEN) | set(profil.get("ernaehrung", []))),
            default=profil.get("ernaehrung", []),
            accept_new_options=True,
            help="Gilt dauerhaft für jedes Rezept und wird strikt eingehalten. "
                 "Eigene Einträge (z. B. 'Allergie gegen Erdbeeren') eintippen und mit Enter bestätigen.",
        )
        g = st.multiselect(
            "Worauf stehst du geschmacklich generell?",
            sorted(set(GESCHMACK_OPTIONEN) | set(profil.get("geschmack", []))),
            default=profil.get("geschmack", []),
            accept_new_options=True,
            help="Eigene Richtungen einfach eintippen und mit Enter bestätigen.",
        )
        w = st.multiselect(
            "Was ist dir bei Gerichten wichtig?",
            sorted(set(WICHTIG_OPTIONEN) | set(profil.get("wichtig", []))),
            default=profil.get("wichtig", []),
            accept_new_options=True,
            help="Eigene Prioritäten einfach eintippen und mit Enter bestätigen.",
        )
        gespeichert = st.form_submit_button("Speichern & loslegen", type="primary")
    if gespeichert:
        try:
            antwort_profil = requests.post(
                f"{API_URL}/praeferenzen",
                data={"ernaehrung": ",".join(e), "geschmack": ",".join(g), "wichtig": ",".join(w)},
                timeout=5,
            )
            # Status pruefen, bevor das Onboarding als erledigt gilt -- sonst
            # landet der Nutzer bei einem Serverfehler in einer stillen Schleife.
            if antwort_profil.status_code == 200:
                st.session_state["onboarding_offen"] = False
                st.rerun()
            else:
                st.error(f"Konnte das Profil nicht speichern ({antwort_profil.status_code}).")
        except requests.RequestException:
            st.error("Backend nicht erreichbar – Profil nicht gespeichert.")
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
        accept_new_options=True,
        max_selections=10,  # muss zu ChatAnfrage.geschmack_heute (schemas.py, max_length=10) passen
        help="Vorbelegt aus deinem Profil – für dieses Rezept frei änderbar (z. B. heute mal süß). "
             "Eigene Begriffe eintippen und mit Enter bestätigen. Maximal 10 Auswahlen.",
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
    # Transparenz (Responsible AI, W14): der Nutzer soll VOR dem Upload wissen,
    # dass das Bild das Geraet verlaesst — nicht erst in der Doku nachlesen.
    st.caption(
        "ℹ️ Das Foto wird zur Zutatenerkennung an ein externes Vision-Modell "
        "(Groq) gesendet und nicht dauerhaft gespeichert."
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

    # Grosszuegiger Timeout: ein Wochenplan mit mehreren Gerichten reiht pro Gericht
    # Recherche + ggf. Naehrwert-Revision aneinander (real beobachtet: 60-90 s je
    # Gericht auf dem Groq-Free-Tier) -- bei bis zu 7 Gerichten sind mehrere Minuten
    # Normalbetrieb, kein Haenger.
    with st.spinner("Der Agent denkt nach (Recherche, ggf. Bildanalyse) — bei einem "
                     "Wochenplan mit mehreren Gerichten kann das einige Minuten dauern …"):
        try:
            antwort = requests.post(f"{API_URL}/chat", data=daten, files=dateien, timeout=600)
        except requests.exceptions.Timeout:
            # KEIN "Backend nicht erreichbar" -- der Agent arbeitet vermutlich noch
            # (Groq-Free-Tier-Wartezeiten bei Ratenlimits), nur laenger als die
            # Geduldsgrenze dieses Requests.
            st.error("Die Anfrage dauert ungewöhnlich lange (über 10 Minuten) und wurde "
                     "abgebrochen. Der Agent läuft im Backend evtl. noch weiter (siehe "
                     "Server-Log). Versuch es mit weniger Gerichten oder ohne kcal-Vorgabe erneut.")
            st.stop()
        except requests.RequestException:
            st.error("Backend nicht erreichbar. Läuft die API?")
            st.code("uvicorn app.api.main:app --reload --reload-dir app", language="bash")
            st.stop()

    if antwort.status_code != 200:
        st.error(f"Fehler ({antwort.status_code}): {antwort.text[:400]}")
        st.stop()

    ergebnis = antwort.json()
    # In session_state ablegen, damit die Anzeige beim Bewerten (Rerun) erhalten bleibt.
    st.session_state["ergebnis"] = ergebnis
    # Rezeptname kommt als eigenes Feld vom Backend (extrahiere_rezept_titel);
    # neutraler Platzhalter statt der ersten Prosa-Zeile der Antwort, die bei
    # Fehlerfaellen Saetze wie "Da die Rezeptrecherche fehlgeschlagen ist, ..."
    # als Rezeptnamen vorschlug. Das Feld bleibt editierbar.
    st.session_state["titel"] = ergebnis.get("rezept_titel") or "Rezept"
    # Fuer den "Wochenplan speichern"-Block unten: die urspruengliche Anfrage
    # mitfuehren (steht nicht in ergebnis selbst).
    st.session_state["letzte_nachricht"] = daten["nachricht"]

# --- Anzeige: lebt aus session_state, ueberlebt Reruns --------------------------
if "ergebnis" in st.session_state:
    ergebnis = st.session_state["ergebnis"]

    # Erkannte Zutaten zur Bestätigung anzeigen (Human-in-the-Loop, VL5).
    if ergebnis.get("erkannte_zutaten"):
        st.info("Aus dem Foto erkannt: " + ", ".join(ergebnis["erkannte_zutaten"]))

    st.markdown(ergebnis.get("antwort", "_(keine Antwort)_"))

    # Sichtbarer TAO-Trace (P2): wie der Agent zur Antwort kam. Nur anzeigen, wenn
    # tatsaechlich Schritte da sind (z. B. bei einer direkten Antwort ohne
    # Tool-Aufruf waere der Expander sonst leer, aber trotzdem sichtbar).
    if ergebnis.get("trace"):
        with st.expander("🔎 Wie der Agent gearbeitet hat (TAO-Zyklus)"):
            for schritt in ergebnis["trace"]:
                if schritt["art"] == "aktion":
                    st.markdown(f"**[Thought→Action]** {schritt.get('ziel')} `{schritt.get('name')}`")
                    if schritt.get("args"):
                        st.code(str(schritt["args"]), language="json")
                else:
                    inhalt = (schritt.get("inhalt") or "")[:600]
                    st.markdown(f"**[Observation]** {schritt.get('quelle')} `{schritt.get('name')}`")
                    st.text(inhalt)

    if ergebnis.get("gerichte"):
        # Wochenplan-Antwort (mehrere Gerichte): Bewertung passt hier nicht (kein
        # einzelnes Rezept) -- stattdessen den ganzen Plan fuer die Seite
        # "Meine Wochenpläne" sichern (POST /wochenplan, deterministische Aktion).
        st.divider()

        # Klarer, NATIVER Warnhinweis statt darauf zu vertrauen, dass die
        # Formulierungs-KI eine Luecke zuverlaessig in ihrer Prosa erwaehnt (tut sie
        # nicht immer). Haeufigster Grund fuer eine Luecke: Groq-Free-Tier-Budget
        # wird waehrend eines langen Mehr-Gerichte-Laufs knapp (TPM/TPD).
        angefragt = ergebnis.get("anzahl_angefragt")
        geplant = len(ergebnis["gerichte"])
        if angefragt and geplant < angefragt:
            st.warning(
                f"⚠️ Nur {geplant} von {angefragt} gewünschten Gerichten konnten "
                "geplant werden – vermutlich wurde das Groq-Free-Tier-Budget "
                "während des Laufs knapp. Ein erneuter Versuch (ggf. mit weniger "
                "Gerichten) hilft oft."
            )

        st.markdown("**Gerichte im Detail** (Zutaten + Zubereitung, einzeln auf-/zuklappbar)")
        for i, gericht in enumerate(ergebnis["gerichte"]):
            zeige_gericht(gericht, key=f"chat_gericht_{i}")

        st.subheader("📅 Diesen Wochenplan speichern")
        st.caption("Damit du ihn auf der Seite „Meine Wochenpläne“ wiederfindest.")
        plan_titel = st.text_input(
            "Name für diesen Wochenplan",
            placeholder="z. B. Wochenplan KW 30",
            key="wochenplan_titel_eingabe",
        )
        if st.button("💾 Wochenplan speichern", type="primary"):
            try:
                antwort_wp = requests.post(
                    f"{API_URL}/wochenplan",
                    json={
                        "titel": plan_titel.strip(),
                        "nachricht": st.session_state.get("letzte_nachricht", ""),
                        "antwort": ergebnis.get("antwort", ""),
                        "gerichte": ergebnis["gerichte"],
                        "anzahl_angefragt": ergebnis.get("anzahl_angefragt"),
                    },
                    timeout=5,
                )
                if antwort_wp.status_code == 200:
                    st.success(f"Gespeichert als „{antwort_wp.json()['titel']}“ 📅")
                else:
                    st.error(f"Konnte den Wochenplan nicht speichern ({antwort_wp.status_code}).")
            except requests.RequestException:
                st.error("Backend nicht erreichbar – Wochenplan nicht gespeichert.")
    else:
        # Bewertung (Memory): fliesst ins Bewertungsprofil ein.
        st.divider()
        st.subheader("Wie gut war dieses Rezept?")
        rezept_name = st.text_input("Rezept", value=st.session_state.get("titel", "Rezept"))
        sterne = st.slider("Bewertung (Sterne)", 1, 5, 4)
        st.caption("Ab 4 Sternen wandert das Rezept in dein persönliches Kochbuch (Seite „Mein Kochbuch“) – der Agent kann es dann wiederfinden („koch mir eines meiner Lieblingsrezepte“).")
        if st.button("Rezept speichern"):
            try:
                antwort_b = requests.post(
                    f"{API_URL}/bewertung",
                    # antwort_text: daraus extrahiert das Backend Zutaten + Zubereitung fürs Kochbuch (>= 4 Sterne).
                    data={"rezept": rezept_name, "sterne": sterne,
                          "antwort_text": ergebnis.get("antwort", "")},
                    timeout=5,
                )
                if antwort_b.status_code == 200:
                    if antwort_b.json().get("im_kochbuch"):
                        st.success(f"Danke! '{rezept_name}' ({sterne} Sterne) gespeichert und ins Kochbuch übernommen 📖")
                    else:
                        st.success(f"Danke! '{rezept_name}' mit {sterne} Sternen gespeichert – fließt künftig in Vorschläge ein.")
                else:
                    st.error(f"Konnte die Bewertung nicht speichern ({antwort_b.status_code}).")
            except requests.RequestException:
                st.error("Backend nicht erreichbar – Bewertung nicht gespeichert.")
