"""Integrationstests fuer die FastAPI-Endpunkte (Agent wird gemockt -> kein Netz)."""

from fastapi.testclient import TestClient

import app.api.main as api
from app.api.main import app
from app.core import praeferenzen

client = TestClient(app)


def test_health_ok():
    antwort = client.get("/health")
    assert antwort.status_code == 200
    assert antwort.json()["status"] == "ok"


def test_chat_leere_nachricht_wird_abgelehnt():
    # Leere Nachricht verletzt min_length -> Validierung greift (W9), kein Agentlauf.
    antwort = client.post("/chat", data={"nachricht": "", "modus": "einkaufsliste"})
    assert antwort.status_code == 422


def test_chat_ungueltiger_modus_wird_abgelehnt():
    antwort = client.post("/chat", data={"nachricht": "Reis", "modus": "quatsch"})
    assert antwort.status_code == 422


def test_chat_erfolg_mit_gemocktem_agent(monkeypatch):
    def fake_run(**kwargs):
        return {"antwort": "Test-Rezept", "trace": [], "erkannte_zutaten": None}

    monkeypatch.setattr(api, "run_rezept_agent", fake_run)
    antwort = client.post("/chat", data={"nachricht": "Ich habe Reis", "modus": "einkaufsliste"})
    assert antwort.status_code == 200
    assert antwort.json()["antwort"] == "Test-Rezept"


def test_profil_setzen_und_lesen(monkeypatch, tmp_path):
    # Store auf isolierten tmp-Pfad umbiegen, damit echte Daten nicht beruehrt werden.
    monkeypatch.setattr(praeferenzen, "_DEFAULT_PFAD", str(tmp_path / "p.json"))
    gesetzt = client.post(
        "/praeferenzen",
        data={"ernaehrung": "vegan, glutenfrei", "geschmack": "scharf, mediterran", "wichtig": "gesund"},
    )
    assert gesetzt.status_code == 200
    gelesen = client.get("/praeferenzen").json()
    assert gelesen["ernaehrung"] == ["glutenfrei", "vegan"]
    assert gelesen["geschmack"] == ["mediterran", "scharf"]
    assert gelesen["wichtig"] == ["gesund"]
    assert gelesen["onboarding_done"] is True


def test_bewertung_speichern(monkeypatch, tmp_path):
    monkeypatch.setattr(praeferenzen, "_DEFAULT_PFAD", str(tmp_path / "p.json"))
    antwort = client.post("/bewertung", data={"rezept": "Lasagne", "sterne": 5})
    assert antwort.status_code == 200
    assert antwort.json()["bewertungen"]["Lasagne"] == 5


def test_bewertung_leerer_name_wird_abgelehnt(monkeypatch, tmp_path):
    monkeypatch.setattr(praeferenzen, "_DEFAULT_PFAD", str(tmp_path / "p.json"))
    antwort = client.post("/bewertung", data={"rezept": "   ", "sterne": 3})
    assert antwort.status_code == 422
