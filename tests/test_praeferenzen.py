"""Tests fuer den Praeferenz-Store (deterministisch, isolierter tmp-Pfad)."""

from app.core import praeferenzen


def _pfad(tmp_path):
    return str(tmp_path / "praeferenzen.json")


def test_leeres_profil_wenn_datei_fehlt(tmp_path):
    daten = praeferenzen.lade(_pfad(tmp_path))
    assert daten == {
        "ernaehrung": [], "geschmack": [], "wichtig": [], "bewertungen": {}, "onboarding_done": False,
    }
    assert praeferenzen.als_kontext_text(_pfad(tmp_path)) == ""


def test_setze_profil_normalisiert_und_markiert_onboarding(tmp_path):
    p = _pfad(tmp_path)
    praeferenzen.setze_profil(
        ["  scharf ", "mediterran", "", "scharf"], ["gesund", "schnell"], ["vegan"], pfad=p
    )
    daten = praeferenzen.lade(p)
    assert daten["ernaehrung"] == ["vegan"]
    assert daten["geschmack"] == ["mediterran", "scharf"]   # getrimmt, dedupliziert, sortiert
    assert daten["wichtig"] == ["gesund", "schnell"]
    assert daten["onboarding_done"] is True


def test_bewertung_wird_geklemmt(tmp_path):
    p = _pfad(tmp_path)
    praeferenzen.speichere_bewertung("Chili sin Carne", 9, pfad=p)   # > 5 -> 5
    praeferenzen.speichere_bewertung("Pilzrisotto", -2, pfad=p)      # < 1 -> 1
    daten = praeferenzen.lade(p)
    assert daten["bewertungen"] == {"Chili sin Carne": 5, "Pilzrisotto": 1}


def test_kontext_text_enthaelt_prioritaeten_und_bewertungssignale(tmp_path):
    # als_kontext_text spiegelt das DAUERHAFTE Signal (wichtig + Bewertungen),
    # NICHT die Geschmacks-Tendenz (die ist Pro-Rezept-Default, kein Kontext-Text).
    p = _pfad(tmp_path)
    praeferenzen.setze_profil(["mediterran"], ["gesund"], pfad=p)
    praeferenzen.speichere_bewertung("Lasagne", 5, pfad=p)
    praeferenzen.speichere_bewertung("Pilzpfanne", 1, pfad=p)
    text = praeferenzen.als_kontext_text(p)
    assert "gesund" in text and "wichtig" in text
    assert "Lasagne" in text and "bevorzugen" in text
    assert "Pilzpfanne" in text and "meiden" in text
    assert "mediterran" not in text   # Geschmack gehoert NICHT in den Kontext-Text


def test_kaputte_datei_faellt_auf_leer_zurueck(tmp_path):
    p = _pfad(tmp_path)
    (tmp_path / "praeferenzen.json").write_text("kein json {", encoding="utf-8")
    assert praeferenzen.lade(p)["geschmack"] == []
