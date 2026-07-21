"""Tests fuer den code-orchestrierten Wochenplan-Workflow (gemockt, ohne Keys).

Belegt, dass der WORKFLOW die plan->pruefe->revidiere-Schritt-Reihenfolge
deterministisch garantiert -- unabhaengig davon, ob ein Modell einen Prompt befolgt.
Die LLM-gestuetzten Teilschritte (Erkennung, Rezept-Extraktion, Formulierung) sind
gemockt; die deterministische Orchestrierung ist der Testgegenstand.
"""

import pytest

from app.core import wochenplan_workflow as wf


class _FakeTool:
    """Ersatz fuer ein @tool-Objekt mit fester invoke-Rueckgabe."""
    def __init__(self, rueckgabe):
        self.rueckgabe = rueckgabe

    def invoke(self, _):
        return self.rueckgabe


class _SpyTool:
    """Wie _FakeTool, zeichnet aber jede Eingabe auf (fuer Query-Vergleiche)."""
    def __init__(self, rueckgabe):
        self.rueckgabe = rueckgabe
        self.aufrufe: list[dict] = []

    def invoke(self, eingabe):
        self.aufrufe.append(eingabe)
        return self.rueckgabe


class _FakeResp:
    def __init__(self, content):
        self.content = content


class _FakeModel:
    def __init__(self, content):
        self._content = content

    def invoke(self, _):
        return _FakeResp(self._content)


class _KaputtesModel:
    """Simuliert einen fehlschlagenden Modellaufruf (z. B. Rate-Limit-Exception)."""
    def invoke(self, _):
        raise RuntimeError("simulierter Modellfehler")


# --- _json_aus_text: robust gegen haeufige Modell-Marotten ------------------------

def test_json_aus_text_mit_markdown_codefence():
    text = '```json\n{"titel": "Curry", "zutaten": ["Reis"]}\n```'
    assert wf._json_aus_text(text) == {"titel": "Curry", "zutaten": ["Reis"]}


def test_json_aus_text_mit_trailing_komma():
    text = '{"titel": "Curry", "zutaten": ["Reis", "Kokosmilch",]}'
    assert wf._json_aus_text(text) == {"titel": "Curry", "zutaten": ["Reis", "Kokosmilch"]}


def test_json_aus_text_ohne_json_gibt_none():
    assert wf._json_aus_text("Tut mir leid, ich habe kein passendes Rezept gefunden.") is None


# --- erkenne_wochenplan -----------------------------------------------------------

def test_erkenne_wochenplan_ohne_hinweis_gibt_none():
    # Kein Wochenplan-Hinweis im Text -> None, ganz ohne LLM-Call.
    assert wf.erkenne_wochenplan("Was kann ich mit Tomaten und Mozzarella kochen?") is None


def test_erkenne_wochenplan_extrahiert_parameter(monkeypatch):
    monkeypatch.setattr(wf, "_modell",
                        lambda temperature=0: _FakeModel('{"wochenplan": true, "anzahl_gerichte": 3, "kcal_limit": 500, "portionen": 2}'))
    params = wf.erkenne_wochenplan("Plane mir 3 Abendessen fuer die Woche")
    assert params == {"anzahl_gerichte": 3, "kcal_limit": 500.0, "portionen": 2}


def test_erkenne_wochenplan_einzelrezept_trotz_stichwort(monkeypatch):
    # "Woche" kommt vor, aber das LLM erkennt: nur ein Gericht -> None.
    monkeypatch.setattr(wf, "_modell",
                        lambda temperature=0: _FakeModel('{"wochenplan": false, "anzahl_gerichte": 1}'))
    assert wf.erkenne_wochenplan("Ein schnelles Rezept fuer diese Woche") is None


def test_erkenne_wochenplan_bei_modellfehler_gibt_none(monkeypatch):
    # Ein Modellfehler (z. B. Rate-Limit) darf die Anfrage nicht abbrechen -- sie
    # laeuft dann einfach als normales Einzelrezept weiter (W9-Geist).
    monkeypatch.setattr(wf, "_modell", lambda temperature=0: _KaputtesModel())
    assert wf.erkenne_wochenplan("Plane mir 3 Abendessen fuer die Woche") is None


# --- plane_woche: garantierte Schritt-Reihenfolge ---------------------------------

def test_plane_woche_haelt_schrittfolge_ein(monkeypatch):
    monkeypatch.setattr(wf, "recherche_rezepte", _FakeTool("irgendein Rezept-Text"))
    rezepte = iter([
        {"titel": "Linsen-Dal", "zutaten": ["Linsen", "Zwiebel"]},
        {"titel": "Ofengemuese", "zutaten": ["Zucchini", "Paprika"]},
    ])
    monkeypatch.setattr(wf, "_extrahiere_rezept", lambda text, vermeide, model: next(rezepte))
    monkeypatch.setattr(wf, "schaetze_kcal_pro_portion", lambda t, z, p: 400.0)  # unter Limit
    monkeypatch.setattr(wf, "_formuliere_antwort", lambda g, p, n, m: "Fertiger Wochenplan")
    monkeypatch.setattr(wf, "_modell", lambda temperature=0: _FakeModel(""))

    erg = wf.plane_woche("Plane 2 Gerichte", {"anzahl_gerichte": 2, "kcal_limit": 500.0, "portionen": 2},
                         harte_vorgaben=["vegetarisch"])

    namen = [s["name"] for s in erg["trace"] if s["art"] == "aktion"]
    assert namen.count("recherche_rezepte") == 2       # eine Recherche je Gericht
    assert namen.count("naehrwerte_schaetzen") == 2    # Constraint-Check je Gericht
    assert "wochenplan_zusammenstellen" in namen       # deterministischer Abschluss
    assert erg["antwort"] == "Fertiger Wochenplan"


def test_plane_woche_revidiert_bei_kcal_ueberschreitung(monkeypatch):
    monkeypatch.setattr(wf, "recherche_rezepte", _FakeTool("Rezept-Text"))
    monkeypatch.setattr(wf, "_extrahiere_rezept", lambda text, vermeide, model: {"titel": "X", "zutaten": ["a"]})
    kcals = iter([700.0, 400.0])  # Erstversuch ueber Limit, Ersatz drunter
    monkeypatch.setattr(wf, "schaetze_kcal_pro_portion", lambda t, z, p: next(kcals))
    monkeypatch.setattr(wf, "_formuliere_antwort", lambda g, p, n, m: "Plan")
    monkeypatch.setattr(wf, "_modell", lambda temperature=0: _FakeModel(""))

    erg = wf.plane_woche("Plane 1 Gericht unter 500 kcal", {"anzahl_gerichte": 1, "kcal_limit": 500.0, "portionen": 2},
                         harte_vorgaben=[])

    namen = [s["name"] for s in erg["trace"] if s["art"] == "aktion"]
    # Revision sichtbar: zwei Recherchen (Original + kalorienaermerer Ersatz) fuer EIN Gericht.
    assert namen.count("recherche_rezepte") == 2
    # Und im Trace steht der Revisions-Grund (ueber Limit).
    assert any("UEBER Limit" in (s.get("inhalt") or "") for s in erg["trace"])


def test_extrahiere_rezept_bei_modellfehler_gibt_none():
    # Wie bei erkenne_wochenplan: ein Modellfehler darf nur DIESES Gericht kosten,
    # nicht die ganze Wochenplan-Anfrage crashen lassen.
    assert wf._extrahiere_rezept("irgendein Rechercheergebnis", [], _KaputtesModel()) is None


def test_extrahiere_rezept_uebernimmt_zubereitung_falls_vorhanden():
    # Der Recherche-Sub-Agent liefert laut eigenem Prompt "Kurze Zubereitung
    # (Stichpunkte)" -- die soll mit ins Gericht wandern, nicht verworfen werden.
    modell = _FakeModel(
        '{"titel": "Linsen-Dal", "zutaten": ["Linsen", "Zwiebel"], '
        '"zubereitung": ["Zwiebel anbraten", "Linsen zugeben"]}'
    )
    rezept = wf._extrahiere_rezept("irgendein Rechercheergebnis", [], modell)
    assert rezept["zubereitung"] == ["Zwiebel anbraten", "Linsen zugeben"]


def test_extrahiere_rezept_ohne_zubereitung_gibt_leere_liste():
    # Nennt die Recherche keine Zubereitung, gibt es keinen Absturz -- nur ein
    # leeres Array (Feld ist "falls vorhanden", kein Pflichtfeld).
    modell = _FakeModel('{"titel": "Linsen-Dal", "zutaten": ["Linsen"]}')
    rezept = wf._extrahiere_rezept("irgendein Rechercheergebnis", [], modell)
    assert rezept["zubereitung"] == []


def test_formuliere_antwort_faellt_bei_modellfehler_auf_rohtext_zurueck():
    # Die Gerichte + Einkaufsliste sind zu diesem Zeitpunkt bereits deterministisch
    # fertig (wochenplan_zusammenstellen) -- ein Fehler NUR bei der sprachlichen
    # Formulierung darf sie nicht wegwerfen.
    gerichte = [{"titel": "Linsen-Dal", "zutaten": ["Linsen", "Zwiebel"]}]
    text = wf._formuliere_antwort(gerichte, "Einkaufsliste: Linsen, Zwiebel",
                                  ["Linsen-Dal: ~400 kcal/Portion"], _KaputtesModel())
    assert "Linsen-Dal" in text
    assert "Einkaufsliste: Linsen, Zwiebel" in text
    assert "400 kcal" in text


def test_plane_woche_variiert_suche_nach_fehlgeschlagener_extraktion(monkeypatch):
    # Bug-Regression: Schlaegt die Extraktion fehl OHNE dass schon ein Gericht
    # feststeht, blieb die Suchanfrage fuer den naechsten Versuch bisher IDENTISCH
    # (die Variation haengt nur an bereits erfolgreichen "gerichte") -- das fuehrte
    # dazu, dass bei wiederholten Extraktions-Fehlern derselbe (erfolglose) Versuch
    # einfach nochmal gestellt wurde, statt der Recherche eine echte neue Chance zu geben.
    spy = _SpyTool("Rechercheergebnis-Text")
    monkeypatch.setattr(wf, "recherche_rezepte", spy)
    ergebnisse = iter([None, {"titel": "X", "zutaten": ["a"]}])  # 1. Versuch scheitert, 2. gelingt
    monkeypatch.setattr(wf, "_extrahiere_rezept", lambda text, vermeide, model: next(ergebnisse))
    monkeypatch.setattr(wf, "_formuliere_antwort", lambda g, p, n, m: "Plan")
    monkeypatch.setattr(wf, "_modell", lambda temperature=0: _FakeModel(""))

    wf.plane_woche("Plane 2 Gerichte", {"anzahl_gerichte": 2, "kcal_limit": None, "portionen": 2},
                   harte_vorgaben=[])

    anfragen = [a["anfrage"] for a in spy.aufrufe]
    assert len(anfragen) == 2
    assert anfragen[0] != anfragen[1]
    assert "Versuch" in anfragen[1]


def test_plane_woche_meldet_wenn_weniger_gerichte_als_gewuenscht(monkeypatch):
    # Transparenz statt stiller Kuerzung: 2 gewuenscht, nur 1 gefunden -> die
    # Antwort-Formulierung muss einen klaren Hinweis darauf bekommen.
    monkeypatch.setattr(wf, "recherche_rezepte", _FakeTool("Text"))
    ergebnisse = iter([None, {"titel": "X", "zutaten": ["a"]}])
    monkeypatch.setattr(wf, "_extrahiere_rezept", lambda text, vermeide, model: next(ergebnisse))
    erfasst = {}

    def fake_formuliere(g, p, notizen, m):
        erfasst["notizen"] = notizen
        return "Plan"

    monkeypatch.setattr(wf, "_formuliere_antwort", fake_formuliere)
    monkeypatch.setattr(wf, "_modell", lambda temperature=0: _FakeModel(""))

    erg = wf.plane_woche("Plane 2 Gerichte", {"anzahl_gerichte": 2, "kcal_limit": None, "portionen": 2},
                         harte_vorgaben=[])

    assert len(erg["gerichte"]) == 1
    assert any("Nur 1 von 2" in n for n in erfasst["notizen"])


def test_plane_woche_ohne_treffer_bricht_nicht_ab(monkeypatch):
    monkeypatch.setattr(wf, "recherche_rezepte", _FakeTool("WEBSUCHE-LEER: nichts"))
    monkeypatch.setattr(wf, "_extrahiere_rezept", lambda text, vermeide, model: None)
    monkeypatch.setattr(wf, "_formuliere_antwort", lambda g, p, n, m: "sollte nicht aufgerufen werden")
    monkeypatch.setattr(wf, "_modell", lambda temperature=0: _FakeModel(""))

    erg = wf.plane_woche("Plane 2 Gerichte", {"anzahl_gerichte": 2, "kcal_limit": None, "portionen": 2},
                         harte_vorgaben=[])
    # Kein Gericht gefunden -> ehrliche Meldung statt Crash oder Halluzination.
    assert "keine passenden rezepte" in erg["antwort"].lower()
