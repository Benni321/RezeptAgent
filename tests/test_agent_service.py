"""Tests fuer die Eingabe-Zusammensetzung des Agent-Service (reine Funktion)."""

from app.core.agent_service import _baue_eingabe


def test_modus_einkaufsliste_wird_ergaenzt():
    text = _baue_eingabe("Ich habe Reis", "einkaufsliste", [])
    assert "Ich habe Reis" in text
    assert "Einkaufsliste" in text or "ergaenzt" in text


def test_modus_vorhanden_verbietet_fehlende():
    text = _baue_eingabe("Ich habe Reis", "vorhanden", [])
    assert "nur die vorhandenen Zutaten" in text


def test_filter_werden_angehaengt():
    text = _baue_eingabe("Pasta", "einkaufsliste", ["vegetarisch", "schnell"])
    assert "vegetarisch" in text and "schnell" in text
