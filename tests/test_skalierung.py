"""Tests fuer die deterministische Portions-Skalierung."""

from app.tools.skalierung import _skaliere_menge, _zahl_format, portionen_skalieren


def test_zahl_format_ganz_und_komma():
    assert _zahl_format(2.0) == "2"
    assert _zahl_format(1.5) == "1,5"
    assert _zahl_format(0.75) == "0,75"


def test_skaliere_gramm_und_anzahl():
    assert _skaliere_menge("400g Reis", 2) == "800g Reis"
    assert _skaliere_menge("2 Zwiebeln", 2) == "4 Zwiebeln"


def test_skaliere_dezimal_mit_komma():
    assert _skaliere_menge("1,5 EL Olivenoel", 2) == "3 EL Olivenoel"


def test_skaliere_bruch():
    assert _skaliere_menge("1/2 TL Salz", 3) == "1,5 TL Salz"


def test_zutat_ohne_menge_bleibt_unveraendert():
    # "Salz nach Bedarf" hat keine fuehrende Zahl -> darf nicht hochskaliert werden.
    assert _skaliere_menge("Salz nach Bedarf", 4) == "Salz nach Bedarf"


def test_tool_halbieren_und_kopfzeile():
    ergebnis = portionen_skalieren.invoke(
        {"zutaten": ["400g Reis", "2 Zwiebeln"], "von_portionen": 4, "auf_portionen": 2}
    )
    assert "200g Reis" in ergebnis
    assert "1 Zwiebeln" in ergebnis
    assert "Faktor 0,5" in ergebnis


def test_tool_schuetzt_gegen_null_portionen():
    # von_portionen <= 0 darf keine Division durch Null ausloesen (faellt auf 1).
    ergebnis = portionen_skalieren.invoke(
        {"zutaten": ["100g Mehl"], "von_portionen": 0, "auf_portionen": 3}
    )
    assert "300g Mehl" in ergebnis
