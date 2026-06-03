"""Integrationstests fuer die FastAPI-Endpunkte (Agent wird gemockt -> kein Netz)."""

from fastapi.testclient import TestClient

import app.api.main as api
from app.api.main import app

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
