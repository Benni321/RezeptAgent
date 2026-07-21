"""
FastAPI-Backend (Phase 3)   [W6 Prediction Service, W11 Monitoring-Endpoint]
============================================================================
Stellt den RezeptAgenten als HTTP-Service bereit. Echter Konsument ist die
Streamlit-GUI (streamlit_app.py) -- dadurch ist die API fachlich begruendet,
nicht aufgesetzt.

Endpunkte:
  GET  /health  -> Betriebsbereitschaft (W11)
  POST /chat    -> Anfrage (Text + optional Foto) an den Agenten (W6)

Eingaben werden validiert, bevor der Agent startet, und Fehler werden graceful
in saubere HTTP-Antworten uebersetzt (W9).

Start (lokal):  uvicorn app.api.main:app --reload
"""

import io

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError
from pydantic import ValidationError

from app.api.schemas import (
    ChatAnfrage, ChatAntwort, ERLAUBTE_BILDTYPEN, KochbuchRezeptSpeichern,
    WochenplanAusKochbuch, WochenplanSpeichern,
)
from app.core.agent_service import run_rezept_agent
from app.core.logging_config import get_logger, log_ereignis
from app.core import praeferenzen, wochenplaene
from app.tools import kochbuch
from app.tools.wochenplan import wochenplan_zusammenstellen

logger = get_logger("rezeptagent.api")

app = FastAPI(
    title="RezeptAgent API",
    version="0.3.0",
    description="HTTP-Schnittstelle zum RezeptAgenten (Multi-Agent, Vision, TAO).",
)


@app.get("/health")
def health() -> dict:
    """Liveness-/Readiness-Check fuer Monitoring und Container-Healthcheck."""
    return {"status": "ok", "service": "rezeptagent"}


@app.post("/chat", response_model=ChatAntwort)
def chat(
    nachricht: str = Form(...),
    modus: str = Form("einkaufsliste"),
    filter: str = Form(""),
    anmerkungen: str = Form(""),
    geschmack_heute: str = Form(""),
    bild: UploadFile | None = File(None),
) -> ChatAntwort:
    """Nimmt eine Nutzeranfrage (Text + optional Foto) entgegen und ruft den Agenten.

    Bewusst SYNCHRON (kein async def): FastAPI fuehrt eine synchrone Route in
    einem Threadpool aus, statt im einzigen Event-Loop-Thread. Ein Wochenplan
    kann mehrere Minuten dauern (mehrere sequenzielle LLM-/Websuche-Aufrufe je
    Gericht) -- als `async def` haette dieser einzelne lang laufende Request den
    Event-Loop blockiert und JEDE andere Anfrage (auch /health, /kochbuch,
    /praeferenzen der GUI-Sidebar) waere fuer die Dauer des Laufs eingefroren.
    """
    # 1) Text-Eingaben validieren (W9) -- Pydantic prueft Laenge/Modus/Filter.
    filter_liste = [f.strip() for f in filter.split(",") if f.strip()]
    geschmack_liste = [g.strip() for g in geschmack_heute.split(",") if g.strip()]
    try:
        anfrage = ChatAnfrage(
            nachricht=nachricht,
            modus=modus,
            filter=filter_liste,
            anmerkungen=anmerkungen,
            geschmack_heute=geschmack_liste,
        )
    except ValidationError as exc:
        log_ereignis(logger, "validierung_fehlgeschlagen", anzahl_fehler=len(exc.errors()))
        raise HTTPException(status_code=422, detail=exc.errors())

    # 2) Optionales Bild validieren (Typ + Lesbarkeit).
    image_bytes = None
    image_mime = "image/jpeg"
    if bild is not None:
        if bild.content_type not in ERLAUBTE_BILDTYPEN:
            raise HTTPException(
                status_code=415,
                detail=f"Nicht unterstuetzter Bildtyp: {bild.content_type}. Erlaubt: {sorted(ERLAUBTE_BILDTYPEN)}",
            )
        image_bytes = bild.file.read()  # synchrone Route -> synchrones Lesen (kein await)
        try:
            Image.open(io.BytesIO(image_bytes)).verify()
        except (UnidentifiedImageError, OSError):
            raise HTTPException(status_code=422, detail="Die hochgeladene Datei ist kein lesbares Bild.")
        image_mime = bild.content_type

    # 3) Agent ausfuehren -- Laufzeitfehler graceful abfangen (W9).
    try:
        ergebnis = run_rezept_agent(
            nachricht=anfrage.nachricht,
            modus=anfrage.modus,
            filter_=anfrage.filter,
            anmerkungen=anfrage.anmerkungen,
            geschmack_heute=anfrage.geschmack_heute,
            image_bytes=image_bytes,
            image_mime=image_mime,
        )
    except Exception as exc:  # bewusst breit: nach aussen eine saubere Meldung
        log_ereignis(logger, "agent_fehler", fehler=type(exc).__name__)
        raise HTTPException(
            status_code=502,
            detail="Der Agent konnte die Anfrage gerade nicht verarbeiten. Bitte spaeter erneut versuchen.",
        )

    return ChatAntwort(**ergebnis)


# --- Praeferenzen (Memory: Geschmack + Bewertungen) -----------------------------
# Schreiben ist eine deterministische Aktion (kein Agenten-Reasoning), daher hier
# als schlanke Endpunkte statt als Tool -- siehe app/core/praeferenzen.py.

@app.get("/praeferenzen")
def praeferenzen_lesen() -> dict:
    """Gibt das gespeicherte Geschmacksprofil + die Bewertungen zurueck (fuer die GUI)."""
    return praeferenzen.lade()


@app.get("/kochbuch")
def kochbuch_lesen() -> list[dict]:
    """Listet alle Kochbuch-Rezepte fuer die GUI-Ansicht (deterministisches Lesen).

    Macht die RAG-Wissensbasis (W3) fuer den Nutzer direkt sichtbar, statt nur
    indirekt ueber den Agenten (rag_retriever). Sortierung: gelernte Rezepte
    zuerst (das eigentliche 'eigene' Kochbuch), beste Bewertung oben; die
    mitgelieferten Seeds danach.
    """
    rezepte = kochbuch.lade_alle()
    rezepte.sort(key=lambda r: (r.get("quelle") == "seed", -(r.get("sterne") or 0), r.get("titel", "")))
    return rezepte


@app.post("/kochbuch")
def kochbuch_rezept_hinzufuegen(anfrage: KochbuchRezeptSpeichern) -> dict:
    """Speichert ein manuell eingegebenes Rezept im Kochbuch (kein Agenten-Lauf,
    keine Bewertung noetig -- der Nutzer traegt Titel/Zutaten/Zubereitung selbst ein)."""
    kochbuch.speichere_rezept(
        anfrage.titel, anfrage.zutaten, sterne=anfrage.sterne,
        quelle="manuell", zubereitung=anfrage.zubereitung,
    )
    log_ereignis(logger, "kochbuch_manuell_gespeichert", anzahl_zutaten=len(anfrage.zutaten))
    return {"titel": anfrage.titel, "zutaten": anfrage.zutaten, "zubereitung": anfrage.zubereitung}


@app.delete("/kochbuch")
def kochbuch_rezept_loeschen(titel: str) -> dict:
    """Loescht ein gelerntes/manuelles Kochbuch-Rezept per Titel (Seeds nicht loeschbar)."""
    if not kochbuch.loesche(titel):
        raise HTTPException(
            status_code=404,
            detail="Rezept nicht gefunden oder ist ein mitgeliefertes Seed-Rezept (nicht löschbar).",
        )
    return {"geloescht": True}


@app.post("/praeferenzen")
def profil_setzen(
    ernaehrung: str = Form(""),
    geschmack: str = Form(""),
    wichtig: str = Form(""),
) -> dict:
    """Setzt das dauerhafte Profil (Ernaehrung + Geschmacks-Tendenz + Prioritaeten).

    Alle Felder sind kommagetrennte Tag-Listen. Markiert das Onboarding als erledigt.
    """
    ernaehrung_tags = [t.strip() for t in ernaehrung.split(",") if t.strip()]
    geschmack_tags = [t.strip() for t in geschmack.split(",") if t.strip()]
    wichtig_tags = [t.strip() for t in wichtig.split(",") if t.strip()]
    daten = praeferenzen.setze_profil(geschmack_tags, wichtig_tags, ernaehrung_tags)
    log_ereignis(
        logger,
        "profil_gesetzt",
        anzahl_ernaehrung=len(daten["ernaehrung"]),
        anzahl_geschmack=len(daten["geschmack"]),
        anzahl_wichtig=len(daten["wichtig"]),
    )
    return daten


@app.post("/bewertung")
def bewertung_speichern(
    rezept: str = Form(...),
    sterne: int = Form(...),
    antwort_text: str = Form(""),
) -> dict:
    """Speichert eine Rezept-Bewertung (1..5 Sterne).

    Bei >= 4 Sternen wandert das Rezept zusaetzlich ins persoenliche Kochbuch
    (RAG-Wissensbasis, W3/W13): Die Zutaten werden heuristisch aus der
    mitgesendeten Agent-Antwort extrahiert (Listenzeilen vor der Zubereitung).
    Bewusst ein deterministischer API-Schritt, KEIN Agenten-Tool (VL03:
    Schreiben ist eine Aktion des Systems, nicht des LLM). Scheitert die
    Extraktion, wird nur die Bewertung gespeichert (kein falscher Eintrag).
    """
    if not rezept.strip():
        raise HTTPException(status_code=422, detail="Rezeptname darf nicht leer sein.")
    daten = praeferenzen.speichere_bewertung(rezept, sterne)
    log_ereignis(logger, "bewertung_gespeichert", sterne=max(1, min(5, sterne)))

    im_kochbuch = False
    if sterne >= 4 and antwort_text.strip():
        extrakt = kochbuch.rezept_aus_antwort(rezept, antwort_text)
        if extrakt:
            kochbuch.speichere_rezept(
                extrakt["titel"], extrakt["zutaten"],
                sterne=max(1, min(5, sterne)), kcal=extrakt["kcal"],
                zubereitung=extrakt.get("zubereitung"),
            )
            im_kochbuch = True
            log_ereignis(logger, "kochbuch_rezept_gespeichert",
                         anzahl_zutaten=len(extrakt["zutaten"]))
    return {**daten, "im_kochbuch": im_kochbuch}


# --- Gespeicherte Wochenplaene ---------------------------------------------------
# Ein Wochenplan ist eine Chat-Antwort des code-orchestrierten Workflows
# (app/core/wochenplan_workflow.py); ohne diese Ablage waere er nach dem
# Schliessen der GUI verloren. Speichern ist eine deterministische API-Aktion,
# kein Agenten-Tool (gleiche Begruendung wie beim Kochbuch-Schreibpfad, VL03).

@app.get("/wochenplan")
def wochenplaene_lesen() -> list[dict]:
    """Listet alle gespeicherten Wochenplaene fuer die GUI-Seite (neueste zuerst)."""
    return wochenplaene.lade_alle()


@app.post("/wochenplan")
def wochenplan_speichern(anfrage: WochenplanSpeichern) -> dict:
    """Sichert einen fertig geplanten Wochenplan dauerhaft."""
    return wochenplaene.speichere(anfrage.nachricht, anfrage.antwort, anfrage.gerichte, anfrage.titel)


@app.delete("/wochenplan/{plan_id}")
def wochenplan_loeschen(plan_id: str) -> dict:
    """Loescht einen gespeicherten Wochenplan per ID."""
    if not wochenplaene.loesche(plan_id):
        raise HTTPException(status_code=404, detail="Wochenplan nicht gefunden.")
    return {"geloescht": True}


@app.post("/wochenplan/aus-kochbuch")
def wochenplan_aus_kochbuch(anfrage: WochenplanAusKochbuch) -> dict:
    """Stellt einen Wochenplan DETERMINISTISCH aus bereits gespeicherten
    Kochbuch-Rezepten zusammen -- kein Agenten-/LLM-Aufruf noetig.

    Der Nutzer waehlt die Gerichte selbst aus seinem Kochbuch, statt sie vom
    Agenten recherchieren zu lassen; die Aggregation zu EINER Einkaufsliste ist
    reine Mengenlogik (wochenplan_zusammenstellen, dasselbe Tool, das auch der
    agentische Wochenplan-Workflow nutzt -- keine Duplikation, kostet 0 Tokens).
    """
    kochbuch_nach_titel = {r["titel"]: r for r in kochbuch.lade_alle()}
    gerichte = []
    nicht_gefunden = []
    for titel in anfrage.rezept_titel:
        rezept = kochbuch_nach_titel.get(titel)
        if rezept:
            # Zubereitung mit uebernehmen, falls im Kochbuch-Eintrag vorhanden
            # (z. B. bei neu gespeicherten/manuell hinzugefuegten Rezepten).
            gerichte.append({
                "titel": rezept["titel"],
                "zutaten": rezept.get("zutaten", []),
                "zubereitung": rezept.get("zubereitung") or [],
            })
        else:
            nicht_gefunden.append(titel)
    if not gerichte:
        raise HTTPException(
            status_code=422,
            detail="Keines der ausgewaehlten Rezepte wurde im Kochbuch gefunden.",
        )
    plan_text = wochenplan_zusammenstellen.invoke(
        {"gerichte": gerichte, "vorhandene_zutaten": anfrage.vorhandene_zutaten}
    )
    return {"gerichte": gerichte, "antwort": plan_text, "nicht_gefunden": nicht_gefunden}
