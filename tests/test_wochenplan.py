"""Tests fuer die deterministische Wochenplan-Aggregation (ohne LLM/Keys).

Die plan->pruefe->revidiere-Schleife selbst ist LLM-Verhalten des Orchestrators
und wird per Evidence-Trace belegt (docs/evidence/), nicht hier. Diese Tests
sichern den deterministischen Kern ab: das Zusammenfuehren mehrerer Gerichte zu
einer korrekten, deduplizierten Gesamt-Einkaufsliste.
"""

from app.tools.wochenplan import (
    _aggregiere_einkaufsliste,
    _formatiere_wochenplan,
    wochenplan_zusammenstellen,
)

# Drei Gerichte, in denen sich "Zwiebel" ueber zwei Gerichte wiederholt.
GERICHTE = [
    {"titel": "Linsen-Dal", "zutaten": ["200g rote Linsen", "1 Zwiebel", "Currypulver"]},
    {"titel": "Gemuesepfanne", "zutaten": ["2 Zwiebeln", "Paprika", "Reis"]},
    {"titel": "Tomatensuppe", "zutaten": ["Tomaten", "Sahne"]},
]


def test_einkaufsliste_dedupliziert_ueber_gerichte():
    # "1 Zwiebel" und "2 Zwiebeln" teilen den Kernbegriff -> nur EINMAL auf der Liste.
    fehlend = _aggregiere_einkaufsliste(GERICHTE, vorhandene_zutaten=[])
    zwiebel_eintraege = [z for z in fehlend if "zwiebel" in z.lower()]
    assert len(zwiebel_eintraege) == 1


def test_vorhandene_zutaten_werden_abgezogen():
    # Reis + Tomaten sind da -> tauchen nicht in der Gesamt-Einkaufsliste auf.
    fehlend = _aggregiere_einkaufsliste(GERICHTE, vorhandene_zutaten=["Reis", "Tomaten"])
    tokens = " ".join(fehlend).lower()
    assert "reis" not in tokens
    assert "tomaten" not in tokens
    # Andere Zutaten fehlen weiterhin.
    assert any("linsen" in z.lower() for z in fehlend)


def test_alles_vorhanden_ergibt_leere_einkaufsliste():
    vorhanden = ["Linsen", "Zwiebeln", "Currypulver", "Paprika", "Reis", "Tomaten", "Sahne"]
    fehlend = _aggregiere_einkaufsliste(GERICHTE, vorhandene_zutaten=vorhanden)
    assert fehlend == []


def test_formatierung_nummeriert_gerichte_und_nennt_einkaufsliste():
    text = _formatiere_wochenplan(GERICHTE, fehlend=["Currypulver", "Sahne"])
    assert "1. Linsen-Dal" in text
    assert "3. Tomatensuppe" in text
    assert "Gesamt-Einkaufsliste" in text
    assert "- Currypulver" in text


def test_formatierung_ohne_fehlende_zutaten():
    text = _formatiere_wochenplan(GERICHTE, fehlend=[])
    assert "alles" in text.lower() and "vorhanden" in text.lower()


def test_gericht_ohne_titel_bekommt_platzhalter():
    text = _formatiere_wochenplan([{"zutaten": ["Ei"]}], fehlend=["Ei"])
    assert "Gericht 1" in text


def test_tool_invoke_end_to_end():
    # Ueber die @tool-Schnittstelle (wie der Agent es aufruft), ohne LLM.
    ergebnis = wochenplan_zusammenstellen.invoke(
        {"gerichte": GERICHTE, "vorhandene_zutaten": ["Reis"]}
    )
    assert "Wochenplan:" in ergebnis
    assert "Linsen-Dal" in ergebnis
    # Reis vorhanden -> nicht auf der Liste; Zwiebel genau einmal.
    assert ergebnis.lower().count("reis") == 0 or "reis" not in ergebnis.split("Einkaufsliste")[-1].lower()


def test_leere_gerichteliste_crasht_nicht():
    ergebnis = wochenplan_zusammenstellen.invoke({"gerichte": [], "vorhandene_zutaten": []})
    assert "Wochenplan" in ergebnis
