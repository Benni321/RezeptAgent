"""Tests fuer das Kochbuch-RAG (W3/W4) — reine Logik, ohne Keys/Netz/Modell.

Genau das ist der Punkt der Design-Entscheidung "BM25 statt Embedding-Modell":
Wissensbasis UND Retrieval sind deterministische, offline testbare Logik.
"""

import json

from app.tools import kochbuch as kb


def _mit_kochbuch(monkeypatch, tmp_path, rezepte):
    """Setzt ein isoliertes Kochbuch-Verzeichnis mit den gegebenen Rezepten auf."""
    monkeypatch.setenv("KOCHBUCH_DIR", str(tmp_path))
    for r in rezepte:
        kb.speichere_rezept(r["titel"], r["zutaten"],
                            sterne=r.get("sterne"), kcal=r.get("kcal"),
                            quelle=r.get("quelle", "bewertung"))


# --- Wissensbasis: speichern + laden ------------------------------------------------

def test_speichern_und_laden_roundtrip(monkeypatch, tmp_path):
    _mit_kochbuch(monkeypatch, tmp_path, [
        {"titel": "Linsen-Dal", "zutaten": ["250g rote Linsen", "1 Zwiebel"], "sterne": 5, "kcal": 420},
    ])
    rezepte = kb.lade_alle()
    assert len(rezepte) == 1
    assert rezepte[0]["titel"] == "Linsen-Dal"
    assert rezepte[0]["sterne"] == 5
    assert rezepte[0]["kcal_pro_portion"] == 420
    # Gelernte Rezepte tragen das Praefix 'gelernt_' (Seeds vs. Gelerntes bleibt sichtbar).
    assert (tmp_path / "gelernt_linsen-dal.json").exists()


def test_gleicher_titel_ueberschreibt_statt_duplikat(monkeypatch, tmp_path):
    _mit_kochbuch(monkeypatch, tmp_path, [
        {"titel": "Shakshuka", "zutaten": ["4 Eier"], "sterne": 4},
        {"titel": "Shakshuka", "zutaten": ["4 Eier", "1 Paprika"], "sterne": 5},
    ])
    rezepte = kb.lade_alle()
    assert len(rezepte) == 1
    assert rezepte[0]["sterne"] == 5


def test_lade_alle_ueberspringt_kaputte_dateien(monkeypatch, tmp_path):
    monkeypatch.setenv("KOCHBUCH_DIR", str(tmp_path))
    (tmp_path / "kaputt.json").write_text("{ kein json", encoding="utf-8")
    (tmp_path / "ohne_zutaten.json").write_text(json.dumps({"titel": "X"}), encoding="utf-8")
    kb.speichere_rezept("Gutes Rezept", ["Reis"])
    assert [r["titel"] for r in kb.lade_alle()] == ["Gutes Rezept"]


def test_leeres_oder_fehlendes_verzeichnis(monkeypatch, tmp_path):
    monkeypatch.setenv("KOCHBUCH_DIR", str(tmp_path / "gibt_es_nicht"))
    assert kb.lade_alle() == []
    assert kb.suche("Curry") == []


# --- Retrieval: BM25 ----------------------------------------------------------------

def test_suche_rankt_relevantes_rezept_zuerst(monkeypatch, tmp_path):
    _mit_kochbuch(monkeypatch, tmp_path, [
        {"titel": "Gemuese-Curry mit Kokosmilch", "zutaten": ["Currypaste", "Kokosmilch", "Reis"]},
        {"titel": "Spaghetti Aglio e Olio", "zutaten": ["Spaghetti", "Knoblauch", "Olivenoel"]},
        {"titel": "Linsen-Dal", "zutaten": ["rote Linsen", "Kurkuma"]},
    ])
    treffer = kb.suche("scharfes Curry mit Reis")
    assert treffer[0]["titel"] == "Gemuese-Curry mit Kokosmilch"
    # Irrelevantes (Score 0) taucht gar nicht auf.
    assert all(t["titel"] != "Spaghetti Aglio e Olio" for t in treffer)


def test_suche_faltet_umlaute_und_trifft_komposita(monkeypatch, tmp_path):
    _mit_kochbuch(monkeypatch, tmp_path, [
        {"titel": "Hähnchenbrust mit Ofengemüse", "zutaten": ["2 Hähnchenbrustfilets", "Zucchini"]},
    ])
    # Query ohne Umlaut + kuerzeres Wort als im Titel (Teilwort-Match ab 5 Zeichen).
    assert kb.suche("Haehnchen")[0]["titel"].startswith("Hähnchenbrust")


def test_suche_ohne_treffer_gibt_leere_liste(monkeypatch, tmp_path):
    _mit_kochbuch(monkeypatch, tmp_path, [
        {"titel": "Linsen-Dal", "zutaten": ["rote Linsen"]},
    ])
    assert kb.suche("Sushi mit Lachs") == []


# --- Tool-Vertrag: rag_retriever ----------------------------------------------------

def test_tool_leeres_kochbuch_meldet_rag_leer(monkeypatch, tmp_path):
    monkeypatch.setenv("KOCHBUCH_DIR", str(tmp_path))
    ergebnis = kb.rag_retriever.invoke({"anfrage": "Curry"})
    assert ergebnis.startswith(kb.LEER_PRAEFIX)
    assert "Websuche" in ergebnis  # klare Handlungsanweisung fuer den Orchestrator


def test_tool_kein_treffer_meldet_rag_leer(monkeypatch, tmp_path):
    _mit_kochbuch(monkeypatch, tmp_path, [{"titel": "Linsen-Dal", "zutaten": ["Linsen"]}])
    ergebnis = kb.rag_retriever.invoke({"anfrage": "Sushi"})
    assert ergebnis.startswith(kb.LEER_PRAEFIX)


def test_tool_treffer_enthaelt_titel_und_herkunft(monkeypatch, tmp_path):
    _mit_kochbuch(monkeypatch, tmp_path, [
        {"titel": "Gemuese-Curry", "zutaten": ["Currypaste", "Reis"], "sterne": 5},
    ])
    ergebnis = kb.rag_retriever.invoke({"anfrage": "Curry"})
    assert "Gemuese-Curry" in ergebnis
    assert "5 Sterne" in ergebnis
    assert "vom Nutzer gelernt" in ergebnis  # Herkunft transparent (Seed vs. gelernt)


# --- Schreibpfad: Zutaten-Extraktion aus der Agent-Antwort ---------------------------

def test_rezept_aus_antwort_extrahiert_zutaten_vor_zubereitung():
    antwort = (
        "**Rezept: Shakshuka**\n\n**Zutaten:**\n- 4 Eier\n- 400g Tomaten\n- 1 Paprika\n\n"
        "**Zubereitung:**\n1. Zwiebel anbraten\n2. Eier hineingeben\n\n~380 kcal pro Portion"
    )
    extrakt = kb.rezept_aus_antwort("Shakshuka", antwort)
    assert extrakt["zutaten"] == ["4 Eier", "400g Tomaten", "1 Paprika"]
    # Zubereitungsschritte landen NICHT als Zutaten; kcal wird mitgenommen.
    assert extrakt["kcal"] == 380


def test_rezept_aus_antwort_ohne_listenzeilen_gibt_none():
    # Lieber KEIN Kochbuch-Eintrag als ein falscher (ehrliche Grenze der Heuristik).
    assert kb.rezept_aus_antwort("Rezept", "Nur Fliesstext ohne jede Liste.") is None
    assert kb.rezept_aus_antwort("", "- 4 Eier") is None
