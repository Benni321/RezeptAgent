"""Tests fuer das Parsen der VLM-Antwort (ohne echten Modellaufruf)."""

from app.core.text_utils import entferne_reasoning
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


def test_parse_mit_think_block():
    # Regression (Modellwechsel 2026-07 auf qwen/qwen3.6-27b): Qwen stellt einen
    # <think>-Block voran. Ohne entferne_reasoning zerlegte der Zeilen-Fallback
    # den Denktext in Dutzende Pseudo-"Zutaten" (real beobachtet: 95 statt 6).
    # erkenne_zutaten_aus_bild wendet deshalb erst entferne_reasoning an.
    text = (
        "<think>\nIch sehe einen Kuehlschrank.\n- oberste Ablage: ein Glas\n"
        "- Tuer: Flaschen\n</think>\n[\"Eier\", \"Milch\", \"Tofu\"]"
    )
    assert _parse_zutaten(entferne_reasoning(text)) == ["Eier", "Milch", "Tofu"]
