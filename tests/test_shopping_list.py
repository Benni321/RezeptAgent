"""Tests fuer das Einkaufslisten-Tool (deterministische Logik)."""

from app.tools.shopping_list import einkaufsliste_erstellen


def _liste(benoetigt, vorhanden):
    return einkaufsliste_erstellen.invoke(
        {"benoetigte_zutaten": benoetigt, "vorhandene_zutaten": vorhanden}
    )


def test_fehlende_zutaten_werden_erkannt():
    ergebnis = _liste(["Reis", "Curry", "Kokosmilch"], ["Reis"])
    assert "Curry" in ergebnis
    assert "Kokosmilch" in ergebnis
    assert "Reis" not in ergebnis  # vorhanden -> nicht in der Liste


def test_nichts_fehlt():
    ergebnis = _liste(["Nudeln", "Tomaten"], ["Nudeln", "Tomaten", "Basilikum"])
    assert "fehlt nichts" in ergebnis.lower()


def test_mengen_und_einheiten_werden_ignoriert():
    # "400g Reis" muss als vorhanden gelten, wenn der Nutzer "Reis" hat.
    ergebnis = _liste(["400g Reis", "2 EL Olivenoel"], ["Reis", "Olivenoel"])
    assert "fehlt nichts" in ergebnis.lower()


def test_plural_und_umlaut_matchen():
    # "Zwiebeln" (Plural) <-> "1 rote Zwiebel"; "Haehnchen" <-> "Hähnchenbrustfilet".
    ergebnis = _liste(["1 rote Zwiebel", "Hähnchenbrustfilet"], ["Zwiebeln", "haehnchen"])
    assert "fehlt nichts" in ergebnis.lower()
