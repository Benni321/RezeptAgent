"""
Seite: Mein Kochbuch
====================
Eigene Ansicht fuer die gelernte Wissensbasis (W3/W13): alle Lieblingsrezepte
(4+-Sterne-Bewertungen), manuell hinzugefuegte Rezepte und die mitgelieferten
Seed-Rezepte. Die Anzeige kommt DIREKT aus den gespeicherten Daten (GET
/kochbuch) -- ohne Agenten-Lauf, ohne Tokens. Nur eine fehlende Zubereitung
(aeltere Eintraege/Seeds) holt auf ausdruecklichen Klick der Agent nach; die
Antwort wird pro Rezept in st.session_state zwischengespeichert, damit sie
nicht erneut kostet.
"""

import requests
import streamlit as st

from seiten._gemeinsam import API_URL

st.page_link("seiten/start.py", label="Zur Startseite", icon="🏠")

st.title("📖 Mein Kochbuch")
st.caption("Deine Lieblingsrezepte (ab 4 Sternen automatisch gespeichert) und die mitgelieferten Starter-Rezepte.")

with st.expander("➕ Eigenes Rezept hinzufügen", expanded=False):
    with st.form("eigenes_rezept"):
        titel_neu = st.text_input("Titel")
        zutaten_neu = st.text_area(
            "Zutaten (eine pro Zeile)", height=100,
            placeholder="4 Eier\n400g Tomaten\n1 Paprika",
        )
        zubereitung_neu = st.text_area(
            "Zubereitung (ein Schritt pro Zeile, optional)", height=120,
            placeholder="Zwiebel anbraten\nEier hineingeben",
        )
        speichern_neu = st.form_submit_button("Rezept speichern", type="primary")
    if speichern_neu:
        zutaten_liste = [z.strip() for z in zutaten_neu.splitlines() if z.strip()]
        zubereitung_liste = [s.strip() for s in zubereitung_neu.splitlines() if s.strip()]
        if not titel_neu.strip() or not zutaten_liste:
            st.warning("Bitte mindestens Titel und eine Zutat angeben.")
        else:
            try:
                antwort_neu = requests.post(
                    f"{API_URL}/kochbuch",
                    json={"titel": titel_neu.strip(), "zutaten": zutaten_liste,
                          "zubereitung": zubereitung_liste},
                    timeout=5,
                )
                if antwort_neu.status_code == 200:
                    st.success(f"„{titel_neu.strip()}“ gespeichert!")
                    st.rerun()
                else:
                    st.error(f"Konnte nicht gespeichert werden ({antwort_neu.status_code}).")
            except requests.RequestException:
                st.error("Backend nicht erreichbar.")

try:
    _antwort = requests.get(f"{API_URL}/kochbuch", timeout=5)
    # Status pruefen, BEVOR der JSON-Body als Rezeptliste behandelt wird -- bei
    # einem Serverfehler liefert FastAPI ein Dict wie {"detail": "..."} zurueck;
    # ohne diese Pruefung wuerde die Iteration darueber nur die String-Keys des
    # Dicts liefern und beim ersten rezept["titel"] mit "string indices must be
    # integers" abstuerzen.
    rezepte = _antwort.json() if _antwort.status_code == 200 else []
    backend_ok = _antwort.status_code == 200
except requests.RequestException:
    rezepte, backend_ok = [], False

if not backend_ok:
    st.error("Backend nicht erreichbar. Läuft die API?")
    st.code("uvicorn app.api.main:app --reload --reload-dir app", language="bash")
    st.stop()

if not rezepte:
    st.info("Noch keine Rezepte gespeichert. Bewerte auf der Seite „Rezept finden“ "
            "ein Rezept mit 4 oder 5 Sternen – dann erscheint es hier.")
    st.stop()

st.caption(f"{len(rezepte)} Rezepte im Kochbuch")

# Vom Agenten nachgeholte Zubereitungen (pro Rezepttitel), ueberlebt Reruns.
agent_cache = st.session_state.setdefault("kochbuch_agent_cache", {})

for i, rezept in enumerate(rezepte):
    # Titel bleibt REIN der Rezeptname (Expander-Kopfzeile); die Bewertung steht
    # als eigene Zeile ganz oben im aufgeklappten Inhalt, nicht im Titel selbst.
    with st.expander(rezept["titel"], expanded=False):
        extras = []
        if rezept.get("sterne"):
            extras.append(f"{'⭐' * int(rezept['sterne'])} ({int(rezept['sterne'])} Sterne)")
        if rezept.get("kcal_pro_portion"):
            extras.append(f"~{rezept['kcal_pro_portion']:g} kcal/Portion")
        if extras:
            st.caption(" · ".join(extras))

        st.markdown("**Zutaten**")
        st.markdown("\n".join(f"- {z}" for z in rezept.get("zutaten", [])))

        if rezept.get("zubereitung"):
            st.markdown("**Zubereitung**")
            st.markdown("\n".join(f"{n}. {s}" for n, s in enumerate(rezept["zubereitung"], 1)))
        elif rezept["titel"] in agent_cache:
            # Bereits einmal vom Agenten geholt -> aus dem Cache, kostet nichts mehr.
            st.markdown(agent_cache[rezept["titel"]])
        else:
            st.caption("Für dieses Rezept ist keine Zubereitung gespeichert. "
                       "Neu gespeicherte Rezepte sichern die Zubereitung automatisch mit.")
            if st.button("🤖 Zubereitung vom Agenten holen", key=f"kb_agent_{i}"):
                daten = {
                    "nachricht": (
                        f"Zeig mir mein gespeichertes Rezept '{rezept['titel']}' aus meinem "
                        "Kochbuch — vollständig mit Zutaten und Zubereitung. Ergänze eine "
                        "passende Zubereitung, falls sie nicht gespeichert ist. Ich brauche "
                        "KEINE Einkaufsliste; stelle keine Rückfragen, sondern antworte direkt."
                    ),
                    "modus": "einkaufsliste",
                }
                with st.spinner("Der Agent ergänzt die Zubereitung …"):
                    try:
                        antwort = requests.post(f"{API_URL}/chat", data=daten, timeout=300)
                    except requests.RequestException:
                        antwort = None
                if antwort is not None and antwort.status_code == 200:
                    agent_cache[rezept["titel"]] = antwort.json().get("antwort", "")
                    st.rerun()
                elif antwort is not None:
                    st.error(f"Fehler ({antwort.status_code}) beim Abruf.")
                else:
                    st.error("Backend nicht erreichbar oder Zeitüberschreitung.")

        # Loeschen NUR fuer gelernte/manuelle Eintraege -- Seeds sind mitgeliefertes,
        # git-getracktes Material und bewusst nicht ueber die GUI entfernbar.
        if rezept.get("quelle") != "seed":
            st.divider()
            if st.button("🗑️ Aus dem Kochbuch löschen", key=f"kb_loeschen_{i}"):
                try:
                    loesch_antwort = requests.delete(
                        f"{API_URL}/kochbuch", params={"titel": rezept["titel"]}, timeout=5,
                    )
                except requests.RequestException:
                    loesch_antwort = None
                if loesch_antwort is not None and loesch_antwort.status_code == 200:
                    st.rerun()
                elif loesch_antwort is not None:
                    st.error(f"Konnte nicht gelöscht werden ({loesch_antwort.status_code}).")
                else:
                    st.error("Backend nicht erreichbar.")
