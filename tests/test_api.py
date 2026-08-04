"""Integrationstests fuer die FastAPI-Endpunkte (Agent wird gemockt -> kein Netz)."""

import io

from fastapi.testclient import TestClient
from PIL import Image

import app.api.main as api
from app.api.main import app
from app.core import praeferenzen

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


def test_chat_mit_bild_wird_synchron_gelesen(monkeypatch):
    # Regressionstest: /chat ist eine SYNCHRONE Route (kein async def), damit ein
    # lang laufender Wochenplan-Request nicht den Event-Loop blockiert und andere
    # Anfragen (/health, GUI-Sidebar) einfriert. Das Bild wird deshalb ueber
    # bild.file.read() statt "await bild.read()" gelesen -- dieser Test stellt
    # sicher, dass dieser Pfad ein echtes Bild weiterhin korrekt verarbeitet.
    empfangene_bytes = {}

    def fake_run(**kwargs):
        empfangene_bytes["laenge"] = len(kwargs.get("image_bytes") or b"")
        return {"antwort": "Test-Rezept", "trace": [], "erkannte_zutaten": ["Ei"]}

    monkeypatch.setattr(api, "run_rezept_agent", fake_run)

    bild_bytes = io.BytesIO()
    Image.new("RGB", (2, 2), color="white").save(bild_bytes, format="JPEG")

    antwort = client.post(
        "/chat",
        data={"nachricht": "Was kann ich damit kochen?", "modus": "einkaufsliste"},
        files={"bild": ("foto.jpg", bild_bytes.getvalue(), "image/jpeg")},
    )
    assert antwort.status_code == 200
    assert antwort.json()["erkannte_zutaten"] == ["Ei"]
    assert empfangene_bytes["laenge"] > 0


def test_profil_setzen_und_lesen(monkeypatch, tmp_path):
    # Store auf isolierten tmp-Pfad umbiegen, damit echte Daten nicht beruehrt werden.
    monkeypatch.setattr(praeferenzen, "_DEFAULT_PFAD", str(tmp_path / "p.json"))
    gesetzt = client.post(
        "/praeferenzen",
        data={"ernaehrung": "vegan, glutenfrei", "geschmack": "scharf, mediterran", "wichtig": "gesund"},
    )
    assert gesetzt.status_code == 200
    gelesen = client.get("/praeferenzen").json()
    assert gelesen["ernaehrung"] == ["glutenfrei", "vegan"]
    assert gelesen["geschmack"] == ["mediterran", "scharf"]
    assert gelesen["wichtig"] == ["gesund"]
    assert gelesen["onboarding_done"] is True


def test_bewertung_speichern(monkeypatch, tmp_path):
    monkeypatch.setattr(praeferenzen, "_DEFAULT_PFAD", str(tmp_path / "p.json"))
    antwort = client.post("/bewertung", data={"rezept": "Lasagne", "sterne": 5})
    assert antwort.status_code == 200
    assert antwort.json()["bewertungen"]["Lasagne"] == 5


def test_bewertung_leerer_name_wird_abgelehnt(monkeypatch, tmp_path):
    monkeypatch.setattr(praeferenzen, "_DEFAULT_PFAD", str(tmp_path / "p.json"))
    antwort = client.post("/bewertung", data={"rezept": "   ", "sterne": 3})
    assert antwort.status_code == 422


def test_gute_bewertung_landet_im_kochbuch(monkeypatch, tmp_path):
    # >= 4 Sterne + Antworttext mit Zutatenliste -> Rezept wandert in die
    # RAG-Wissensbasis (W3/W13: Kochbuch lernt aus Bewertungen). Die Zubereitung
    # wird mitgespeichert, damit die GUI das Rezept ohne Agenten-Lauf anzeigen kann.
    monkeypatch.setattr(praeferenzen, "_DEFAULT_PFAD", str(tmp_path / "p.json"))
    monkeypatch.setenv("KOCHBUCH_DIR", str(tmp_path / "rezepte"))
    antwort = client.post("/bewertung", data={
        "rezept": "Shakshuka", "sterne": 5,
        "antwort_text": "Zutaten:\n- 4 Eier\n- 1 Paprika\nZubereitung:\n1. anbraten\n2. Eier hineinsetzen",
    })
    assert antwort.status_code == 200
    assert antwort.json()["im_kochbuch"] is True
    from app.tools import kochbuch
    rezepte = kochbuch.lade_alle()
    assert [r["titel"] for r in rezepte] == ["Shakshuka"]
    assert rezepte[0]["zubereitung"] == ["anbraten", "Eier hineinsetzen"]


def test_kochbuch_liste_gelernte_vor_seeds(monkeypatch, tmp_path):
    # GET /kochbuch macht die Wissensbasis fuer die GUI sichtbar: gelernte
    # Rezepte (das eigentliche "eigene" Kochbuch) vor den mitgelieferten Seeds.
    monkeypatch.setenv("KOCHBUCH_DIR", str(tmp_path / "rezepte"))
    from app.tools import kochbuch
    kochbuch.speichere_rezept("Shakshuka", ["4 Eier"], quelle="seed")
    kochbuch.speichere_rezept("Lasagne", ["Nudeln", "Tomaten"], sterne=5, kcal=650)
    antwort = client.get("/kochbuch")
    assert antwort.status_code == 200
    assert [r["titel"] for r in antwort.json()] == ["Lasagne", "Shakshuka"]


def test_kochbuch_manuelles_rezept_hinzufuegen(monkeypatch, tmp_path):
    monkeypatch.setenv("KOCHBUCH_DIR", str(tmp_path / "rezepte"))
    antwort = client.post("/kochbuch", json={
        "titel": "Omas Kartoffelsalat",
        "zutaten": ["1kg Kartoffeln", "2 Gurken", "Mayonnaise"],
        "zubereitung": ["Kartoffeln kochen", "Alles vermischen"],
    })
    assert antwort.status_code == 200
    from app.tools import kochbuch
    gespeichert = kochbuch.lade_alle()
    assert len(gespeichert) == 1
    assert gespeichert[0]["titel"] == "Omas Kartoffelsalat"
    assert gespeichert[0]["zubereitung"] == ["Kartoffeln kochen", "Alles vermischen"]
    assert gespeichert[0]["quelle"] == "manuell"


def test_kochbuch_ohne_zutaten_wird_abgelehnt(monkeypatch, tmp_path):
    monkeypatch.setenv("KOCHBUCH_DIR", str(tmp_path / "rezepte"))
    antwort = client.post("/kochbuch", json={"titel": "Leer", "zutaten": []})
    assert antwort.status_code == 422


def test_kochbuch_rezept_loeschen(monkeypatch, tmp_path):
    monkeypatch.setenv("KOCHBUCH_DIR", str(tmp_path / "rezepte"))
    client.post("/kochbuch", json={"titel": "Testgericht", "zutaten": ["Reis"]})
    antwort = client.delete("/kochbuch", params={"titel": "Testgericht"})
    assert antwort.status_code == 200
    from app.tools import kochbuch
    assert kochbuch.lade_alle() == []


def test_kochbuch_seed_nicht_loeschbar(monkeypatch, tmp_path):
    monkeypatch.setenv("KOCHBUCH_DIR", str(tmp_path / "rezepte"))
    from app.tools import kochbuch
    kochbuch.speichere_rezept("Shakshuka", ["Eier"], quelle="seed")
    antwort = client.delete("/kochbuch", params={"titel": "Shakshuka"})
    assert antwort.status_code == 404
    assert len(kochbuch.lade_alle()) == 1


def test_wochenplan_aus_kochbuch(monkeypatch, tmp_path):
    monkeypatch.setenv("KOCHBUCH_DIR", str(tmp_path / "rezepte"))
    from app.tools import kochbuch
    kochbuch.speichere_rezept("Linsen-Dal", ["Linsen", "Zwiebel"], sterne=5)
    kochbuch.speichere_rezept("Ofengemüse", ["Zucchini", "Zwiebel"], sterne=4)

    antwort = client.post("/wochenplan/aus-kochbuch", json={
        "rezept_titel": ["Linsen-Dal", "Ofengemüse"],
        "vorhandene_zutaten": ["Zwiebel"],
    })
    assert antwort.status_code == 200
    daten = antwort.json()
    assert [g["titel"] for g in daten["gerichte"]] == ["Linsen-Dal", "Ofengemüse"]
    assert "Zwiebel" not in daten["antwort"]  # vorhanden -> nicht auf der Einkaufsliste
    assert "Linsen" in daten["antwort"] and "Zucchini" in daten["antwort"]
    assert daten["nicht_gefunden"] == []


def test_wochenplan_aus_kochbuch_uebernimmt_zubereitung(monkeypatch, tmp_path):
    monkeypatch.setenv("KOCHBUCH_DIR", str(tmp_path / "rezepte"))
    from app.tools import kochbuch
    kochbuch.speichere_rezept("Linsen-Dal", ["Linsen"], sterne=5,
                              zubereitung=["Linsen kochen", "Wuerzen"])

    antwort = client.post("/wochenplan/aus-kochbuch", json={"rezept_titel": ["Linsen-Dal"]})
    assert antwort.status_code == 200
    assert antwort.json()["gerichte"][0]["zubereitung"] == ["Linsen kochen", "Wuerzen"]


def test_wochenplan_aus_kochbuch_mit_unbekanntem_titel(monkeypatch, tmp_path):
    monkeypatch.setenv("KOCHBUCH_DIR", str(tmp_path / "rezepte"))
    from app.tools import kochbuch
    kochbuch.speichere_rezept("Linsen-Dal", ["Linsen"], sterne=5)

    antwort = client.post("/wochenplan/aus-kochbuch", json={
        "rezept_titel": ["Linsen-Dal", "Erfundenes Gericht"],
    })
    assert antwort.status_code == 200
    assert antwort.json()["nicht_gefunden"] == ["Erfundenes Gericht"]


def test_wochenplan_aus_kochbuch_ganz_unbekannt_gibt_422(monkeypatch, tmp_path):
    monkeypatch.setenv("KOCHBUCH_DIR", str(tmp_path / "rezepte"))
    antwort = client.post("/wochenplan/aus-kochbuch", json={"rezept_titel": ["Existiert nicht"]})
    assert antwort.status_code == 422


def test_wochenplan_speichern_und_lesen(monkeypatch, tmp_path):
    monkeypatch.setenv("WOCHENPLAENE_DIR", str(tmp_path))
    gespeichert = client.post("/wochenplan", json={
        "titel": "Meine Woche",
        "nachricht": "Plane mir 2 Abendessen",
        "antwort": "Hier ist dein Wochenplan ...",
        "gerichte": [{"titel": "Linsen-Dal", "zutaten": ["Linsen"]},
                     {"titel": "Ofengemuese", "zutaten": ["Zucchini"]}],
    })
    assert gespeichert.status_code == 200
    assert gespeichert.json()["anzahl_gerichte"] == 2

    liste = client.get("/wochenplan")
    assert liste.status_code == 200
    assert [p["titel"] for p in liste.json()] == ["Meine Woche"]


def test_wochenplan_speichern_mit_luecke_bei_angefragt(monkeypatch, tmp_path):
    # 4 gewuenscht, nur 3 im Plan -- die Luecke soll beim Speichern erhalten bleiben,
    # damit "Meine Wochenpläne" sie auch fuer laengst gespeicherte Plaene noch zeigt.
    monkeypatch.setenv("WOCHENPLAENE_DIR", str(tmp_path))
    gespeichert = client.post("/wochenplan", json={
        "antwort": "Hier ist dein Wochenplan ...",
        "gerichte": [{"titel": "X", "zutaten": ["a"]}] * 3,
        "anzahl_angefragt": 4,
    })
    assert gespeichert.status_code == 200
    daten = gespeichert.json()
    assert daten["anzahl_gerichte"] == 3
    assert daten["anzahl_angefragt"] == 4


def test_wochenplan_ohne_gerichte_wird_abgelehnt(monkeypatch, tmp_path):
    monkeypatch.setenv("WOCHENPLAENE_DIR", str(tmp_path))
    antwort = client.post("/wochenplan", json={"antwort": "Text", "gerichte": []})
    assert antwort.status_code == 422


def test_wochenplan_loeschen(monkeypatch, tmp_path):
    monkeypatch.setenv("WOCHENPLAENE_DIR", str(tmp_path))
    gespeichert = client.post("/wochenplan", json={
        "antwort": "Text", "gerichte": [{"titel": "X", "zutaten": ["a"]}],
    }).json()
    antwort = client.delete(f"/wochenplan/{gespeichert['id']}")
    assert antwort.status_code == 200
    assert client.get("/wochenplan").json() == []


def test_wochenplan_loeschen_unbekannt_gibt_404(monkeypatch, tmp_path):
    monkeypatch.setenv("WOCHENPLAENE_DIR", str(tmp_path))
    antwort = client.delete("/wochenplan/20260101-000000-nichts")
    assert antwort.status_code == 404


def test_schlechte_bewertung_landet_nicht_im_kochbuch(monkeypatch, tmp_path):
    monkeypatch.setattr(praeferenzen, "_DEFAULT_PFAD", str(tmp_path / "p.json"))
    monkeypatch.setenv("KOCHBUCH_DIR", str(tmp_path / "rezepte"))
    antwort = client.post("/bewertung", data={
        "rezept": "Fader Eintopf", "sterne": 2,
        "antwort_text": "Zutaten:\n- Kartoffeln",
    })
    assert antwort.status_code == 200
    assert antwort.json()["im_kochbuch"] is False
    from app.tools import kochbuch
    assert kochbuch.lade_alle() == []


def test_chat_zu_grosses_bild_wird_abgelehnt(monkeypatch):
    # W9: Groessenlimit VOR der Verarbeitung. Ohne das wandert ein beliebig
    # grosses Bild komplett in den RAM und base64-kodiert (+33 %) an das VLM.
    from app.api.schemas import MAX_BILD_BYTES

    def darf_nicht_laufen(**kwargs):
        raise AssertionError("Agent haette bei zu grossem Bild nicht starten duerfen")

    monkeypatch.setattr(api, "run_rezept_agent", darf_nicht_laufen)

    zu_gross = b"\xff\xd8\xff" + b"x" * (MAX_BILD_BYTES + 1)
    antwort = client.post(
        "/chat",
        data={"nachricht": "Was kann ich kochen?", "modus": "einkaufsliste"},
        files={"bild": ("riesig.jpg", zu_gross, "image/jpeg")},
    )
    assert antwort.status_code == 413
    assert "zu gross" in antwort.json()["detail"].lower()
