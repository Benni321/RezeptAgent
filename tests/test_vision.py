"""Tests fuer das Parsen der VLM-Antwort (ohne echten Modellaufruf)."""

from app.tools.vision import _parse_zutaten


def test_parse_sauberes_json_array():
    assert _parse_zutaten('["Eier", "Milch", "Tomaten"]') == ["Eier", "Milch", "Tomaten"]


def test_parse_json_mit_beiwerk():
    text = 'Klar! Ich erkenne: ["Apfel", "Karotte"] auf dem Bild.'
    assert _parse_zutaten(text) == ["Apfel", "Karotte"]


def test_parse_fallback_kommaliste():
    # Kein JSON -> zeilen-/kommagetrennter Fallback, Aufzaehlungszeichen entfernt.
    assert _parse_zutaten("- Eier\n- Milch\n- Butter") == ["Eier", "Milch", "Butter"]


def test_parse_leer():
    assert _parse_zutaten("[]") == []
    assert _parse_zutaten("") == []
