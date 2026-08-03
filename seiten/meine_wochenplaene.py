"""
Seite: Meine Wochenpläne
========================
Zwei Wege zu einem gespeicherten Wochenplan:
  1. Auf "Rezept finden" den Agenten nach mehreren Gerichten fragen und das
     Ergebnis dort speichern (agentisch, mit Websuche).
  2. HIER direkt aus dem eigenen Kochbuch zusammenstellen (deterministisch,
     POST /wochenplan/aus-kochbuch): Tage waehlen, Gerichte aus den eigenen
     Lieblingsrezepten auswaehlen, vorhandene Zutaten angeben -- die
     Einkaufsliste aggregiert dasselbe Tool wie der agentische Workflow
     (wochenplan_zusammenstellen), nur ohne Agenten-/LLM-Aufruf noetig.

Anzeige gespeicherter Plaene kommt DIREKT aus den gespeicherten Daten (GET
/wochenplan) -- ohne Agenten-Lauf, ohne Tokens. Loeschen ist moeglich (DELETE
/wochenplan/{id}), da ein Wochenplan anders als das Kochbuch keine
Wissensbasis ist, sondern reine Nutzerablage.
"""

import requests
import streamlit as st

from seiten._gemeinsam import API_URL, zeige_gericht

st.page_link("seiten/start.py", label="Zur Startseite", icon="🏠")

st.title("📅 Meine Wochenpläne")
st.caption("Gespeicherte Wochenpläne mit Gerichten und gemeinsamer Einkaufsliste.")

try:
    _antwort = requests.get(f"{API_URL}/kochbuch", timeout=5)
    # Status pruefen, BEVOR der JSON-Body als Rezeptliste behandelt wird (gleicher
    # Grund wie in mein_kochbuch.py): ein Fehler-Body ist ein Dict, kein Liste.
    kochbuch_rezepte = _antwort.json() if _antwort.status_code == 200 else []
    backend_ok = _antwort.status_code == 200
except requests.RequestException:
    kochbuch_rezepte, backend_ok = [], False

if not backend_ok:
    st.error("Backend nicht erreichbar. Läuft die API?")
    st.code("uvicorn app.api.main:app --reload --reload-dir app", language="bash")
    st.stop()

# --- Wochenplan aus dem eigenen Kochbuch zusammenstellen (deterministisch) -------
with st.expander("➕ Wochenplan aus meinem Kochbuch erstellen", expanded=False):
    if not kochbuch_rezepte:
        st.caption("Dein Kochbuch ist noch leer – speichere zuerst ein paar "
                   "Lieblingsrezepte (Seite „Mein Kochbuch“).")
    else:
        # AUSSERHALB des Forms: Aendern dieser Zahl loest sofort einen Rerun aus,
        # damit die max_selections-Grenze der Gerichte-Auswahl unten sofort passt.
        tage = st.number_input("Für wie viele Tage?", min_value=1, max_value=7, value=3)

        with st.form("wochenplan_aus_kochbuch"):
            titel_optionen = sorted(r["titel"] for r in kochbuch_rezepte)
            ausgewaehlt = st.multiselect(
                f"Wähle bis zu {tage} Gerichte aus deinem Kochbuch",
                titel_optionen,
                max_selections=int(tage),
            )
            zutaten_text = st.text_area(
                "Welche Zutaten hast du schon zuhause? (eine pro Zeile, optional)",
                placeholder="Reis\nZwiebeln\nOlivenöl",
                height=100,
            )
            erstellen = st.form_submit_button("Wochenplan erstellen", type="primary")

        if erstellen:
            if not ausgewaehlt:
                st.warning("Bitte mindestens ein Gericht auswählen.")
            else:
                vorhandene = [z.strip() for z in zutaten_text.splitlines() if z.strip()]
                try:
                    antwort = requests.post(
                        f"{API_URL}/wochenplan/aus-kochbuch",
                        json={"rezept_titel": ausgewaehlt, "vorhandene_zutaten": vorhandene},
                        timeout=10,
                    )
                except requests.RequestException:
                    antwort = None
                if antwort is not None and antwort.status_code == 200:
                    st.session_state["kb_plan_ergebnis"] = antwort.json()
                    st.rerun()
                elif antwort is not None:
                    st.error(f"Konnte nicht erstellt werden ({antwort.status_code}): {antwort.text[:300]}")
                else:
                    st.error("Backend nicht erreichbar.")

    # Vorschau + Speichern-Button fuer das zuletzt erstellte Ergebnis.
    if "kb_plan_ergebnis" in st.session_state:
        ergebnis = st.session_state["kb_plan_ergebnis"]
        st.divider()
        if ergebnis.get("nicht_gefunden"):
            st.warning("Nicht gefunden (übersprungen): " + ", ".join(ergebnis["nicht_gefunden"]))
        for i, gericht in enumerate(ergebnis["gerichte"]):
            zeige_gericht(gericht, key=f"kb_vorschau_{i}")
        st.markdown("**Vollständige Antwort (inkl. Einkaufsliste)**")
        st.markdown(ergebnis["antwort"])

        plan_titel = st.text_input("Name für diesen Wochenplan", key="kb_plan_titel_eingabe")
        if st.button("💾 Wochenplan speichern", type="primary", key="kb_plan_speichern"):
            try:
                speicher_antwort = requests.post(
                    f"{API_URL}/wochenplan",
                    json={
                        "titel": plan_titel.strip(),
                        "nachricht": "Manuell aus dem Kochbuch zusammengestellt.",
                        "antwort": ergebnis["antwort"],
                        "gerichte": ergebnis["gerichte"],
                    },
                    timeout=5,
                )
                if speicher_antwort.status_code == 200:
                    st.success(f"Gespeichert als „{speicher_antwort.json()['titel']}“ 📅")
                    del st.session_state["kb_plan_ergebnis"]
                    st.rerun()
                else:
                    st.error(f"Konnte nicht gespeichert werden ({speicher_antwort.status_code}).")
            except requests.RequestException:
                st.error("Backend nicht erreichbar – Wochenplan nicht gespeichert.")

st.divider()

try:
    _plaene_antwort = requests.get(f"{API_URL}/wochenplan", timeout=5)
    plaene = _plaene_antwort.json() if _plaene_antwort.status_code == 200 else []
except requests.RequestException:
    plaene = []

if not plaene:
    st.info("Noch keine Wochenpläne gespeichert. Nutze oben „➕ Wochenplan aus "
            "meinem Kochbuch erstellen“ oder frag den Agenten auf der Seite "
            "„Rezept finden“ nach mehreren Gerichten (z. B. „Plane mir 3 "
            "Abendessen für diese Woche“) und speichere das Ergebnis dort.")
    st.stop()

st.caption(f"{len(plaene)} gespeicherte Wochenpläne")

for plan in plaene:
    erstellt = plan.get("erstellt_am", "")[:16].replace("T", " ")
    anzahl_gerichte = plan.get("anzahl_gerichte", 0)
    angefragt = plan.get("anzahl_angefragt")
    luecken_hinweis = f" ⚠️ (von {angefragt} gewünscht)" if angefragt and anzahl_gerichte < angefragt else ""
    with st.expander(f"{plan['titel']}  ·  {anzahl_gerichte} Gerichte{luecken_hinweis}  ·  {erstellt}"):
        if luecken_hinweis:
            st.warning(f"Nur {anzahl_gerichte} von {angefragt} gewünschten Gerichten wurden geplant "
                       "(vermutlich Groq-Free-Tier-Budget beim Erstellen knapp geworden).")
        for i, gericht in enumerate(plan.get("gerichte", [])):
            zeige_gericht(gericht, key=f"wp_{plan['id']}_{i}")
        st.divider()
        st.markdown("**Vollständige Antwort (inkl. Einkaufsliste)**")
        st.markdown(plan.get("antwort", ""))

        if st.button("🗑️ Löschen", key=f"wp_loeschen_{plan['id']}"):
            try:
                antwort = requests.delete(f"{API_URL}/wochenplan/{plan['id']}", timeout=5)
            except requests.RequestException:
                antwort = None
            if antwort is not None and antwort.status_code == 200:
                st.rerun()
            elif antwort is not None:
                st.error(f"Konnte nicht gelöscht werden ({antwort.status_code}).")
            else:
                st.error("Backend nicht erreichbar.")
