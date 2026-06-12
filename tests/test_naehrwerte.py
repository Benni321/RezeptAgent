"""Tests fuer die deterministische Naehrwert-Logik (ohne echten Modellaufruf)."""

from app.tools.naehrwerte import _formatiere, _parse_naehrwerte, _pro_portion


def test_parse_sauberes_json():
    werte = _parse_naehrwerte('{"kcal": 800, "eiweiss_g": 40, "kohlenhydrate_g": 90, "fett_g": 25}')
    assert werte == {"kcal": 800.0, "eiweiss_g": 40.0, "kohlenhydrate_g": 90.0, "fett_g": 25.0}


def test_parse_json_mit_beiwerk_und_komma():
    # Modell antwortet mit Text drumherum und Komma-Dezimaltrenner / Einheit im String.
    text = 'Hier die Schaetzung: {"kcal": "750 kcal", "eiweiss_g": "12,5", "kohlenhydrate_g": 60, "fett_g": 30} -- ungefaehr.'
    werte = _parse_naehrwerte(text)
    assert werte["kcal"] == 750.0
    assert werte["eiweiss_g"] == 12.5


def test_parse_defensiv_bei_muell():
    # Kein JSON / fehlende Felder -> 0.0 statt Crash.
    assert _parse_naehrwerte("keine ahnung") == {
        "kcal": 0.0, "eiweiss_g": 0.0, "kohlenhydrate_g": 0.0, "fett_g": 0.0,
    }
    assert _parse_naehrwerte('{"kcal": 400}')["fett_g"] == 0.0


def test_pro_portion_teilt_und_rundet():
    gesamt = {"kcal": 800.0, "eiweiss_g": 41.0, "kohlenhydrate_g": 90.0, "fett_g": 25.0}
    assert _pro_portion(gesamt, 4) == {
        "kcal": 200.0, "eiweiss_g": 10.2, "kohlenhydrate_g": 22.5, "fett_g": 6.2,
    }


def test_pro_portion_schuetzt_gegen_null():
    # portionen <= 0 darf keine Division durch Null ausloesen -> faellt auf 1 zurueck.
    gesamt = {"kcal": 500.0, "eiweiss_g": 20.0, "kohlenhydrate_g": 50.0, "fett_g": 10.0}
    assert _pro_portion(gesamt, 0) == gesamt
    assert _pro_portion(gesamt, -3) == gesamt


def test_formatierung_nennt_naeherung_und_portionen():
    gesamt = {"kcal": 800.0, "eiweiss_g": 40.0, "kohlenhydrate_g": 90.0, "fett_g": 25.0}
    text = _formatiere("Chili", 4, gesamt, _pro_portion(gesamt, 4))
    assert "Naeherung" in text
    assert "bei 4 Portionen" in text
    assert "200 kcal" in text  # 800 / 4 pro Portion
