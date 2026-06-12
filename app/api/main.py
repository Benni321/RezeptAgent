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

from app.api.schemas import ChatAnfrage, ChatAntwort, ERLAUBTE_BILDTYPEN
from app.core.agent_service import run_rezept_agent
from app.core.logging_config import get_logger, log_ereignis
from app.core import praeferenzen

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
async def chat(
    nachricht: str = Form(...),
    modus: str = Form("einkaufsliste"),
    filter: str = Form(""),
    anmerkungen: str = Form(""),
    geschmack_heute: str = Form(""),
    bild: UploadFile | None = File(None),
) -> ChatAntwort:
    """Nimmt eine Nutzeranfrage (Text + optional Foto) entgegen und ruft den Agenten."""
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
        image_bytes = await bild.read()
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
def bewertung_speichern(rezept: str = Form(...), sterne: int = Form(...)) -> dict:
    """Speichert eine Rezept-Bewertung (1..5 Sterne)."""
    if not rezept.strip():
        raise HTTPException(status_code=422, detail="Rezeptname darf nicht leer sein.")
    daten = praeferenzen.speichere_bewertung(rezept, sterne)
    log_ereignis(logger, "bewertung_gespeichert", sterne=max(1, min(5, sterne)))
    return daten
