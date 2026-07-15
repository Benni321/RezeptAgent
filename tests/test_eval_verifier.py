"""Tests fuer die Eval-Verifier-Logik (evals/verifier.py) — rein offline, ohne Keys.

Der Verifier ist bewusst reine Stdlib-Logik auf Antwort-Text + TAO-Trace; hier
pruefen wir jede Check-Art inkl. der TERNAEREN Faelle (bestanden/neutral/verletzt),
denn genau die Neutral-Semantik ("Nichtwissen zaehlt nicht als Erfolg") ist der
Reward-Hacking-Schutz aus VL09.
"""

import json
from pathlib import Path

import pytest

from evals import verifier as v


def _aktion(name):
    return {"art": "aktion", "ziel": "Tool", "name": name, "args": {}}


def _beobachtung(name, inhalt):
    return {"art": "beobachtung", "quelle": "Tool", "name": name, "inhalt": inhalt}


# --- Antwort-Ebene -----------------------------------------------------------------

def test_kcal_limit_bestanden_wenn_alle_unter_limit():
    erg = v.check_kcal_limit("Gericht A hat ~450 kcal, Gericht B ca. 380 Kalorien.", [], {"limit": 500})
    assert erg.status == v.BESTANDEN


def test_kcal_limit_verletzt_bei_ueberschreitung():
    erg = v.check_kcal_limit("Leider hat das Gericht 650 kcal pro Portion.", [], {"limit": 500})
    assert erg.status == v.VERLETZT
    assert "650" in erg.detail


def test_kcal_limit_neutral_ohne_kcal_angabe():
    # Kein "bestanden": Der Agent koennte das Limit einfach verschweigen (Reward-Hacking).
    erg = v.check_kcal_limit("Hier ist ein leckeres Rezept ohne Zahlenangaben.", [], {"limit": 500})
    assert erg.status == v.NEUTRAL


def test_kcal_limit_versteht_dezimalkomma():
    erg = v.check_kcal_limit("Etwa 512,5 kcal pro Portion.", [], {"limit": 500})
    assert erg.status == v.VERLETZT


def test_kcal_summe_verletzt_wenn_einzelwert_ueber_budget():
    erg = v.check_kcal_summe_limit("Das Abendessen allein hat 1400 kcal.", [], {"limit": 1200})
    assert erg.status == v.VERLETZT


def test_kcal_summe_neutral_bei_moeglicher_doppelzaehlung():
    # 500+500+600=1600 > 1200, aber 600 koennte ein Gesamtwert sein -> nicht entscheidbar.
    erg = v.check_kcal_summe_limit("Fruehstueck 500 kcal, Mittag 500 kcal, gesamt 600 kcal.", [],
                                   {"limit": 1200})
    assert erg.status == v.NEUTRAL


def test_verbotene_zutat_in_listenzeile_verletzt():
    antwort = "Zutaten:\n- 200g Nudeln\n- 100g Salami\n- Basilikum"
    erg = v.check_verbotene_zutaten(antwort, [], {"zutaten": ["Salami"]})
    assert erg.status == v.VERLETZT
    assert "Salami" in erg.detail


def test_verbotene_zutat_nur_im_fliesstext_ist_ok():
    # Der Agent DARF den Konflikt ansprechen ("statt Salami ...") — geprueft werden nur Listenzeilen.
    antwort = "Du isst vegetarisch, daher ohne Salami.\nZutaten:\n- 200g Nudeln\n- Tomaten"
    erg = v.check_verbotene_zutaten(antwort, [], {"zutaten": ["Salami"]})
    assert erg.status == v.BESTANDEN


def test_verbotene_zutat_mit_vegan_praefix_zaehlt_nicht():
    antwort = "Zutaten:\n- 200ml vegane Sahne\n- 1 Zwiebel"
    erg = v.check_verbotene_zutaten(antwort, [], {"zutaten": ["Sahne"]})
    assert erg.status == v.BESTANDEN


def test_verbotene_zutat_wortanfang_trifft_kompositum_aber_nicht_kokosmilch():
    antwort = "Zutaten:\n- 50g Parmesankaese\n- 200ml Kokosmilch"
    assert v.check_verbotene_zutaten(antwort, [], {"zutaten": ["Parmesan"]}).status == v.VERLETZT
    # "milch" steht in "Kokosmilch" nicht am Wortanfang -> vegane Kokosmilch ist kein Verstoss.
    assert v.check_verbotene_zutaten("- 200ml Kokosmilch", [], {"zutaten": ["Milch"]}).status == v.BESTANDEN
    assert v.check_verbotene_zutaten("- 200ml Milch", [], {"zutaten": ["Milch"]}).status == v.VERLETZT


def test_verbotene_zutaten_neutral_ohne_listenzeilen():
    erg = v.check_verbotene_zutaten("Nur Fliesstext ohne jede Liste.", [], {"zutaten": ["Sahne"]})
    assert erg.status == v.NEUTRAL


def test_erwaehnt_alle_normalisiert_komma_und_umlaute():
    antwort = "Skaliert: 1200g Reis, 6 Zwiebeln, 900g Gemüse und 1.5 TL Salz."
    erg = v.check_erwaehnt_alle(antwort, [], {"begriffe": ["1200", "6 Zwiebeln", "900", "1,5", "Gemuese"]})
    assert erg.status == v.BESTANDEN


def test_erwaehnt_alle_verletzt_bei_fehlendem_begriff():
    erg = v.check_erwaehnt_alle("Nur 1200g Reis.", [], {"begriffe": ["1200", "6 Zwiebeln"]})
    assert erg.status == v.VERLETZT
    assert "6 Zwiebeln" in erg.detail


def test_erwaehnt_eines_und_erwaehnt_nicht():
    assert v.check_erwaehnt_eines("Da du vegetarisch isst, ...", [], {"begriffe": ["vegetarisch"]}).status == v.BESTANDEN
    assert v.check_erwaehnt_eines("Hier dein Rezept.", [], {"begriffe": ["vegetarisch"]}).status == v.VERLETZT
    # Umlaut-Faltung: Testset schreibt "Kuerbis", Antwort "Kürbis".
    assert v.check_erwaehnt_nicht("Ich empfehle Kürbissuppe!", [], {"begriffe": ["Kuerbissuppe"]}).status == v.VERLETZT
    assert v.check_erwaehnt_nicht("Ich empfehle Linsensuppe!", [], {"begriffe": ["Kuerbissuppe"]}).status == v.BESTANDEN


# --- Trajektorien-Ebene -------------------------------------------------------------

def test_tool_aufgerufen_min_und_max():
    trace = [_aktion("recherche_rezepte"), _beobachtung("recherche_rezepte", "..."),
             _aktion("recherche_rezepte")]
    assert v.check_tool_aufgerufen("", trace, {"name": "recherche_rezepte", "min": 2}).status == v.BESTANDEN
    # System-Prompt erlaubt HOECHSTENS eine Recherche -> max wird geprueft.
    assert v.check_tool_aufgerufen("", trace, {"name": "recherche_rezepte", "min": 1, "max": 1}).status == v.VERLETZT
    assert v.check_tool_aufgerufen("", trace, {"name": "naehrwerte_schaetzen"}).status == v.VERLETZT


def test_tool_nicht_aufgerufen():
    trace = [_aktion("recherche_rezepte")]
    assert v.check_tool_nicht_aufgerufen("", trace, {"name": "naehrwerte_schaetzen"}).status == v.BESTANDEN
    assert v.check_tool_nicht_aufgerufen("", trace, {"name": "recherche_rezepte"}).status == v.VERLETZT


def test_tool_reihenfolge_kochbuch_vor_websuche():
    params = {"zuerst": "rag_retriever", "dann": "recherche_rezepte"}
    # Kochbuch zuerst, dann Websuche -> ok; Kochbuch reicht allein -> auch ok.
    assert v.check_tool_reihenfolge("", [_aktion("rag_retriever"), _aktion("recherche_rezepte")], params).status == v.BESTANDEN
    assert v.check_tool_reihenfolge("", [_aktion("rag_retriever")], params).status == v.BESTANDEN
    # Websuche zuerst oder Kochbuch nie -> verletzt.
    assert v.check_tool_reihenfolge("", [_aktion("recherche_rezepte"), _aktion("rag_retriever")], params).status == v.VERLETZT
    assert v.check_tool_reihenfolge("", [_aktion("recherche_rezepte")], params).status == v.VERLETZT


def test_schrittzahl_korridor():
    trace = [_aktion("a"), _beobachtung("a", "x"), _aktion("b")]
    assert v.check_schrittzahl("", trace, {"min": 1, "max": 8}).status == v.BESTANDEN
    assert v.check_schrittzahl("", trace, {"min": 4, "max": 8}).status == v.VERLETZT


def test_revision_geprueft_neutral_ohne_limit_verstoss():
    trace = [_aktion("naehrwerte_schaetzen"), _beobachtung("naehrwerte_schaetzen", "~400 kcal -> unter Limit 500")]
    assert v.check_revision_geprueft("", trace, {}).status == v.NEUTRAL


def test_revision_geprueft_bestanden_wenn_ersatzrecherche_folgt():
    trace = [
        _beobachtung("naehrwerte_schaetzen", "~700 kcal/Portion -> UEBER Limit 500, revidiere"),
        _aktion("recherche_rezepte"),
    ]
    assert v.check_revision_geprueft("", trace, {}).status == v.BESTANDEN


def test_revision_geprueft_verletzt_ohne_ersatzrecherche():
    trace = [_beobachtung("naehrwerte_schaetzen", "~700 kcal/Portion -> UEBER Limit 500, revidiere")]
    assert v.check_revision_geprueft("", trace, {}).status == v.VERLETZT


# --- Fall-Auswertung ---------------------------------------------------------------

def test_pruefe_fall_wertet_alle_checks_aus():
    fall = {"id": "t", "checks": [{"typ": "antwort_nicht_leer"},
                                  {"typ": "tool_aufgerufen", "name": "recherche_rezepte"}]}
    ergebnisse = v.pruefe_fall(fall, "Eine ausreichend lange Antwort fuer den Test hier.",
                               [_aktion("recherche_rezepte")])
    assert [e.status for e in ergebnisse] == [v.BESTANDEN, v.BESTANDEN]


def test_pruefe_fall_unbekannter_checktyp_wirft_fehler():
    # Bewusst hart: ein Tippfehler im Testset darf nicht still als "gruen" durchgehen.
    with pytest.raises(ValueError, match="tippfehler_check"):
        v.pruefe_fall({"id": "t", "checks": [{"typ": "tippfehler_check"}]}, "x", [])


def test_fall_status_aggregation():
    B, N, V = (v.CheckErgebnis("t", s, "") for s in (v.BESTANDEN, v.NEUTRAL, v.VERLETZT))
    assert v.fall_status([B, N]) == v.BESTANDEN
    assert v.fall_status([B, V]) == v.VERLETZT      # eine Verletzung kippt den Fall
    assert v.fall_status([N, N]) == v.NEUTRAL       # nur Neutrales ist kein Erfolg


def test_testset_ist_valide_und_alle_checktypen_bekannt():
    """Schema-Smoke-Test: jedes Testset-Feld, das der Runner/Verifier braucht, existiert,
    und jeder referenzierte Check-Typ ist implementiert (schuetzt vor Drift zwischen
    testset.json und verifier.py)."""
    pfad = Path(__file__).resolve().parent.parent / "evals" / "testset.json"
    testset = json.loads(pfad.read_text(encoding="utf-8"))
    faelle = testset["faelle"]
    assert 12 <= len(faelle) <= 15
    assert sum(1 for f in faelle if f.get("erwartet_schwer")) >= 2
    ids = [f["id"] for f in faelle]
    assert len(ids) == len(set(ids)), "Fall-IDs muessen eindeutig sein (Dateinamen der Traces)"
    for fall in faelle:
        assert fall["eingabe"]["nachricht"].strip()
        for check in fall["checks"]:
            assert check["typ"] in v.CHECKS, f"unbekannter Check-Typ in {fall['id']}: {check['typ']}"
