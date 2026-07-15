"""Tests fuer den code-orchestrierten Wochenplan-Workflow (gemockt, ohne Keys).

Belegt, dass der WORKFLOW die plan->pruefe->revidiere-Schritt-Reihenfolge
deterministisch garantiert -- unabhaengig davon, ob ein Modell einen Prompt befolgt.
Die LLM-gestuetzten Teilschritte (Erkennung, Rezept-Extraktion, Formulierung) sind
gemockt; die deterministische Orchestrierung ist der Testgegenstand.
"""

from app.core import wochenplan_workflow as wf


class _FakeTool:
    """Ersatz fuer ein @tool-Objekt mit fester invoke-Rueckgabe."""
    def __init__(self, rueckgabe):
        self.rueckgabe = rueckgabe

    def invoke(self, _):
        return self.rueckgabe


class _FakeResp:
    def __init__(self, content):
        self.content = content


class _FakeModel:
    def __init__(self, content):
        self._content = content

    def invoke(self, _):
        return _FakeResp(self._content)


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


def test_plane_woche_ohne_treffer_bricht_nicht_ab(monkeypatch):
    monkeypatch.setattr(wf, "recherche_rezepte", _FakeTool("WEBSUCHE-LEER: nichts"))
    monkeypatch.setattr(wf, "_extrahiere_rezept", lambda text, vermeide, model: None)
    monkeypatch.setattr(wf, "_formuliere_antwort", lambda g, p, n, m: "sollte nicht aufgerufen werden")
    monkeypatch.setattr(wf, "_modell", lambda temperature=0: _FakeModel(""))

    erg = wf.plane_woche("Plane 2 Gerichte", {"anzahl_gerichte": 2, "kcal_limit": None, "portionen": 2},
                         harte_vorgaben=[])
    # Kein Gericht gefunden -> ehrliche Meldung statt Crash oder Halluzination.
    assert "keine passenden rezepte" in erg["antwort"].lower()
