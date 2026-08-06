"""Tests fuer die Eingabe-Zusammensetzung des Agent-Service (reine Funktion)."""

from langchain_core.messages import AIMessage

from app.core import agent_service
from app.core.agent_service import _baue_eingabe, run_rezept_agent


def test_modus_einkaufsliste_wird_ergaenzt():
    text = _baue_eingabe("Ich habe Reis", "einkaufsliste", [])
    assert "Ich habe Reis" in text
    assert "Einkaufsliste" in text or "ergaenzt" in text


def test_modus_vorhanden_verbietet_fehlende():
    text = _baue_eingabe("Ich habe Reis", "vorhanden", [])
    assert "nur die vorhandenen Zutaten" in text


def test_filter_werden_angehaengt():
    text = _baue_eingabe("Pasta", "einkaufsliste", ["vegetarisch", "schnell"])
    assert "vegetarisch" in text and "schnell" in text


def test_harte_vorgaben_werden_als_muss_markiert():
    # Ernaehrungsform muss dem Agenten als MUSS-Vorgabe uebergeben werden -- die
    # deterministisch pruefbare Basis dafuer, dass sie nie verletzt wird (auch im
    # Wochenplan: das Durchsetzen selbst ist LLM-Verhalten, siehe Evidence-Trace).
    text = _baue_eingabe("Plane mir 3 Abendessen", "einkaufsliste", ["vegan"])
    assert "vegan" in text
    assert "MUESSEN erfuellt sein" in text or "MUSS" in text.upper()


# --- run_rezept_agent: rezept_titel-Verdrahtung ------------------------------------
# Der Orchestrator-Prompt fordert eine "## <Rezeptname>"-Ueberschrift; agent_service
# muss die finale Antwort durch extrahiere_rezept_titel schicken und das Ergebnis
# als eigenes Feld zurueckgeben (fuer Bewertung/Kochbuch in der GUI).

class _FakeAgent:
    """Ersatz fuer den LangGraph-Orchestrator: liefert eine feste Stream-Sequenz."""
    def __init__(self, antwort_text):
        self._antwort_text = antwort_text

    def stream(self, *_args, **_kwargs):
        # agent_service.py erkennt den Nachrichtentyp per type(msg).__name__ ==
        # "AIMessage" -- deshalb die echte LangChain-Klasse statt eines Fakes.
        yield {"agent": {"messages": [AIMessage(content=self._antwort_text)]}}


def test_run_rezept_agent_setzt_rezept_titel(monkeypatch, tmp_path):
    monkeypatch.setattr(agent_service, "create_orchestrator",
                        lambda: _FakeAgent("## Zitronenhaehnchen\n**Zutaten:** ..."))
    monkeypatch.setattr(agent_service.praeferenzen, "lade",
                        lambda: {"ernaehrung": [], "geschmack": [], "wichtig": [], "bewertungen": {}})
    monkeypatch.setattr(agent_service.praeferenzen, "als_kontext_text", lambda: "")
    monkeypatch.setenv("AGENT_TRACE_DIR", "")

    ergebnis = run_rezept_agent("Was kann ich mit Haehnchen kochen?")

    assert ergebnis["rezept_titel"] == "Zitronenhaehnchen"


def test_run_rezept_agent_ohne_belastbaren_titel_gibt_none(monkeypatch):
    monkeypatch.setattr(agent_service, "create_orchestrator",
                        lambda: _FakeAgent("Da die Rezeptrecherche fehlgeschlagen ist, ..."))
    monkeypatch.setattr(agent_service.praeferenzen, "lade",
                        lambda: {"ernaehrung": [], "geschmack": [], "wichtig": [], "bewertungen": {}})
    monkeypatch.setattr(agent_service.praeferenzen, "als_kontext_text", lambda: "")

    ergebnis = run_rezept_agent("Was kann ich mit Haehnchen kochen?")

    assert ergebnis["rezept_titel"] is None


def test_run_rezept_agent_bei_leerer_finaler_nachricht_gibt_fallback(monkeypatch):
    # Regression: Das Modell kann die ReAct-Schleife mit einer AIMessage OHNE
    # Tool-Call UND ohne Inhalt beenden (real unter Rate-Limit-Last beobachtet,
    # Docker-Test 2026-08-06). Ohne diesen Fallback blieb "antwort" stillschweigend
    # leer -- HTTP 200, aber keine sichtbare Antwort, kein geloggter Fehler.
    monkeypatch.setattr(agent_service, "create_orchestrator", lambda: _FakeAgent(""))
    monkeypatch.setattr(agent_service.praeferenzen, "lade",
                        lambda: {"ernaehrung": [], "geschmack": [], "wichtig": [], "bewertungen": {}})
    monkeypatch.setattr(agent_service.praeferenzen, "als_kontext_text", lambda: "")

    ergebnis = run_rezept_agent("Was kann ich mit Haehnchen kochen?")

    assert ergebnis["antwort"] == "Der Agent konnte keine Antwort formulieren (leere Modellantwort)."
    assert ergebnis["rezept_titel"] is None
