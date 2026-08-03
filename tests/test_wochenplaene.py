"""Tests fuer die Wochenplan-Ablage (app/core/wochenplaene.py) -- reine Logik,
ohne Keys/Netz/Modell (gleiches Muster wie tests/test_kochbuch.py)."""

from app.core import wochenplaene as wp


def _isoliert(monkeypatch, tmp_path):
    monkeypatch.setenv("WOCHENPLAENE_DIR", str(tmp_path))


def test_speichern_und_laden_roundtrip(monkeypatch, tmp_path):
    _isoliert(monkeypatch, tmp_path)
    gespeichert = wp.speichere(
        "Plane mir 2 Abendessen", "Hier ist dein Wochenplan ...",
        [{"titel": "Linsen-Dal", "zutaten": ["Linsen", "Zwiebel"]},
         {"titel": "Ofengemuese", "zutaten": ["Zucchini"]}],
        titel="Meine Testwoche",
    )
    assert gespeichert["titel"] == "Meine Testwoche"
    assert gespeichert["anzahl_gerichte"] == 2

    geladen = wp.lade_alle()
    assert len(geladen) == 1
    assert geladen[0]["id"] == gespeichert["id"]
    assert geladen[0]["gerichte"][0]["titel"] == "Linsen-Dal"


def test_anzahl_angefragt_faellt_ohne_angabe_auf_len_gerichte_zurueck(monkeypatch, tmp_path):
    _isoliert(monkeypatch, tmp_path)
    gespeichert = wp.speichere("Anfrage", "Antwort",
                              [{"titel": "X", "zutaten": ["a"]}, {"titel": "Y", "zutaten": ["b"]}])
    assert gespeichert["anzahl_angefragt"] == 2


def test_anzahl_angefragt_wird_uebernommen_wenn_gegeben(monkeypatch, tmp_path):
    # Realer Fall: 4 gewuenscht, nur 3 tatsaechlich geplant (z. B. Groq-Budget
    # waehrend des Laufs knapp) -- die Luecke soll auch gespeichert sichtbar bleiben.
    _isoliert(monkeypatch, tmp_path)
    gespeichert = wp.speichere("Anfrage", "Antwort",
                              [{"titel": "X", "zutaten": ["a"]}] * 3, anzahl_angefragt=4)
    assert gespeichert["anzahl_gerichte"] == 3
    assert gespeichert["anzahl_angefragt"] == 4


def test_leerer_titel_bekommt_datums_default(monkeypatch, tmp_path):
    _isoliert(monkeypatch, tmp_path)
    gespeichert = wp.speichere("Anfrage", "Antwort", [{"titel": "X", "zutaten": ["a"]}])
    assert gespeichert["titel"].startswith("Wochenplan vom ")


def test_mehrere_plaene_ueberschreiben_sich_nicht(monkeypatch, tmp_path):
    # Anders als das Kochbuch (Titel = Schluessel) sollen zwei Wochenplaene mit
    # gleichem Titel NEBENEINANDER bestehen bleiben (Zeitstempel im Dateinamen).
    _isoliert(monkeypatch, tmp_path)
    wp.speichere("A", "Antwort 1", [{"titel": "X", "zutaten": ["a"]}], titel="Woche")
    wp.speichere("B", "Antwort 2", [{"titel": "Y", "zutaten": ["b"]}], titel="Woche")
    assert len(wp.lade_alle()) == 2


def test_lade_alle_sortiert_neueste_zuerst(monkeypatch, tmp_path):
    _isoliert(monkeypatch, tmp_path)
    erster = wp.speichere("A", "Antwort 1", [{"titel": "X", "zutaten": ["a"]}], titel="Erste")
    zweiter = wp.speichere("B", "Antwort 2", [{"titel": "Y", "zutaten": ["b"]}], titel="Zweite")
    geladen = wp.lade_alle()
    assert geladen[0]["id"] in (zweiter["id"], erster["id"])  # gleiche Sekunde moeglich
    assert {p["id"] for p in geladen} == {erster["id"], zweiter["id"]}


def test_lade_alle_ueberspringt_kaputte_dateien(monkeypatch, tmp_path):
    _isoliert(monkeypatch, tmp_path)
    (tmp_path / "kaputt.json").write_text("{ kein json", encoding="utf-8")
    wp.speichere("A", "Antwort", [{"titel": "X", "zutaten": ["a"]}])
    assert len(wp.lade_alle()) == 1


def test_lade_alle_ohne_verzeichnis_gibt_leere_liste(monkeypatch, tmp_path):
    monkeypatch.setenv("WOCHENPLAENE_DIR", str(tmp_path / "existiert-nicht"))
    assert wp.lade_alle() == []


def test_loeschen_entfernt_plan(monkeypatch, tmp_path):
    _isoliert(monkeypatch, tmp_path)
    gespeichert = wp.speichere("A", "Antwort", [{"titel": "X", "zutaten": ["a"]}])
    assert wp.loesche(gespeichert["id"]) is True
    assert wp.lade_alle() == []


def test_loeschen_unbekannte_id_gibt_false(monkeypatch, tmp_path):
    _isoliert(monkeypatch, tmp_path)
    assert wp.loesche("20260101-000000-nichts") is False


def test_loeschen_lehnt_pfad_traversal_ab(monkeypatch, tmp_path):
    # Excessive-Agency-Deckel (VL03): nur das erwartete ID-Format wird akzeptiert,
    # kein freier Dateiname/Pfad aus der API.
    _isoliert(monkeypatch, tmp_path)
    assert wp.loesche("../../etc/passwd") is False
    assert wp.loesche("some/path") is False
