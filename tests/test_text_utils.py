"""Tests fuer die Reasoning-Bereinigung (Reasoning-Modelle wie qwen geben <think> aus)."""

from app.core.text_utils import entferne_reasoning


def test_entfernt_think_block():
    assert entferne_reasoning("<think>ueberlege kurz</think>Hallo") == "Hallo"


def test_entfernt_mehrzeiligen_think_block():
    text = "<think>\nlange\nueberlegung\n</think>\nDie eigentliche Antwort."
    assert entferne_reasoning(text) == "Die eigentliche Antwort."


def test_offener_think_block_wird_abgeschnitten():
    assert entferne_reasoning("Antwort<think>abgeschnitten ohne Ende") == "Antwort"


def test_ohne_think_unveraendert():
    assert entferne_reasoning("Ganz normale Antwort") == "Ganz normale Antwort"


def test_leer():
    assert entferne_reasoning("") == ""
