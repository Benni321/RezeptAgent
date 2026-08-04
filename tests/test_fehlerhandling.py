"""Tests fuer graceful Fehlerhandling (Dim 2 / W9) -- alles gemockt, ohne Keys/Netz.

Belegt: Fehler in Tools/Sub-Agent/Vision brechen den Lauf NICHT ab, sondern werden
zu einer klaren Observation bzw. graceful abgefangen -- die Grundlage dafuer, dass
der Orchestrator situationsabhaengig reagieren kann (statt eines festen Ablaufs).
"""

from app.agents import recherche_agent as ra
from app.core import agent_service as svc
from app.tools import naehrwerte as nw
from app.tools import web_search as ws


# --- Websuche: leer und fehlgeschlagen werden zur Observation, nicht zum Crash ---

def test_web_search_leer_gibt_klare_meldung(monkeypatch):
    class FakeTavily:
        def invoke(self, query):
            return []
    monkeypatch.setattr(ws, "TavilySearchResults", lambda **k: FakeTavily())
    ergebnis = ws.web_search.invoke({"query": "voellig ausgedachtes Gericht xyz"})
    assert ergebnis.startswith(ws.LEER_PRAEFIX)


def test_web_search_exception_gibt_fehlermeldung(monkeypatch):
    class FakeTavily:
        def invoke(self, query):
            raise RuntimeError("Tavily nicht erreichbar")
    monkeypatch.setattr(ws, "TavilySearchResults", lambda **k: FakeTavily())
    ergebnis = ws.web_search.invoke({"query": "Pasta"})
    assert ergebnis.startswith(ws.FEHLER_PRAEFIX)


# --- Recherche-Sub-Agent: interner Fehler wird zur Observation ------------------

def test_recherche_sub_agent_fehler_wird_observation(monkeypatch):
    class FakeAgent:
        def invoke(self, _):
            raise RuntimeError("Sub-Agent abgestuerzt")
    monkeypatch.setattr(ra, "create_recherche_agent", lambda: FakeAgent())
    ergebnis = ra.recherche_rezepte.invoke({"anfrage": "Rezept mit Reis"})
    assert ergebnis.startswith("RECHERCHE-FEHLER")


# --- Naehrwerte: Fehler UND unbrauchbare Schaetzung -> klares Fehlersignal -------
# (Wichtig: eine 0-kcal-Ausgabe wuerde der Orchestrator faelschlich als
#  "unter dem Limit" deuten -- daher explizit als Fehler kennzeichnen.)

def test_naehrwerte_exception_gibt_fehlersignal(monkeypatch):
    class FakeModel:
        def invoke(self, _):
            raise RuntimeError("LLM nicht erreichbar")
    monkeypatch.setattr(nw, "ChatGroq", lambda **k: FakeModel())
    ergebnis = nw.naehrwerte_schaetzen.invoke({"rezept_titel": "Chili", "zutaten": ["Bohnen"]})
    assert ergebnis.startswith(nw.FEHLER_PRAEFIX)


def test_naehrwerte_unparsebar_gibt_fehlersignal_statt_null(monkeypatch):
    class FakeResp:
        content = "Tut mir leid, dazu habe ich keine Angaben."
    class FakeModel:
        def invoke(self, _):
            return FakeResp()
    monkeypatch.setattr(nw, "ChatGroq", lambda **k: FakeModel())
    ergebnis = nw.naehrwerte_schaetzen.invoke({"rezept_titel": "Chili", "zutaten": ["Bohnen"]})
    assert ergebnis.startswith(nw.FEHLER_PRAEFIX)
    assert "0 kcal" not in ergebnis  # darf NICHT wie "erfuellt" aussehen


# --- Vision: Bildanalyse-Fehler bricht die Anfrage nicht ab (graceful) ----------

def test_vision_fehler_wird_graceful_abgefangen(monkeypatch, tmp_path):
    # Profil-Store auf leeren tmp-Pfad, damit der Test deterministisch ist.
    monkeypatch.setattr(svc.praeferenzen, "_DEFAULT_PFAD", str(tmp_path / "p.json"))

    def wirft(*a, **k):
        raise RuntimeError("VLM-Timeout")
    monkeypatch.setattr(svc, "erkenne_zutaten_aus_bild", wirft)

    class FakeOrchestrator:
        def stream(self, *a, **k):
            return iter([])  # keine Schritte -> leere Antwort, aber kein Crash
    monkeypatch.setattr(svc, "create_orchestrator", lambda: FakeOrchestrator())

    ergebnis = svc.run_rezept_agent(nachricht="Was kann ich kochen?", image_bytes=b"kaputt")
    assert ergebnis["erkannte_zutaten"] == []  # graceful: kein Absturz, leere Liste


def test_vision_llm_fehler_gibt_leere_liste_statt_exception(monkeypatch):
    # erkenne_zutaten_aus_bild faengt den LLM-Aufruf selbst ab (nicht erst der
    # agent_service). Wichtig fuer Direktaufrufe, z. B. aus den Evidence-Skripten:
    # dort gibt es keinen umgebenden try/except.
    from app.tools import vision

    class KaputtesModell:
        def invoke(self, *_a, **_k):
            raise RuntimeError("Groq nicht erreichbar")

    monkeypatch.setattr(vision, "ChatGroq", lambda **_kw: KaputtesModell())
    assert vision.erkenne_zutaten_aus_bild(b"egal", "image/jpeg") == []


# --- Trace-Lebenszyklus: keine trace_id-Leaks nach einer Exception ---------------

def test_trace_wird_auch_bei_exception_beendet(monkeypatch, tmp_path):
    # Ohne try/finally bliebe die trace_id in der ContextVar stehen und haftete an
    # den Logs des NAECHSTEN Requests im selben Thread -- die Observability (W5)
    # waere ausgerechnet im Fehlerfall unbrauchbar.
    from app.core import logging_config

    monkeypatch.setattr(svc.praeferenzen, "_DEFAULT_PFAD", str(tmp_path / "p.json"))

    class ExplodierenderOrchestrator:
        def stream(self, *a, **k):
            raise RuntimeError("Modell nicht erreichbar")

    monkeypatch.setattr(svc, "create_orchestrator", lambda: ExplodierenderOrchestrator())

    try:
        svc.run_rezept_agent(nachricht="Was kann ich kochen?")
    except RuntimeError:
        pass  # Fehler wird bewusst nach aussen gereicht (API macht daraus 502)

    assert logging_config.aktuelle_trace_id() is None
