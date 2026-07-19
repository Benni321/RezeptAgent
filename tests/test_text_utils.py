"""Tests fuer die Text-Helfer: Reasoning-Bereinigung + Rezept-Titel-Extraktion."""

from app.core.text_utils import entferne_reasoning, extrahiere_rezept_titel


def test_entfernt_think_block():
    assert entferne_reasoning("<think>ueberlege kurz</think>Hallo") == "Hallo"


def test_entfernt_mehrzeiligen_think_block():
    text = "<think>\nlange\nueberlegung\n</think>\nDie eigentliche Antwort."
    assert entferne_reasoning(text) == "Die eigentliche Antwort."


def test_offener_think_block_wird_abgeschnitten():
    assert entferne_reasoning("Antwort<think>abgeschnitten ohne Ende") == "Antwort"


def test_ohne_think_unveraendert():
    assert entferne_reasoning("Ganz normale Antwort") == "Ganz normale Antwort"


def test_leer():
    assert entferne_reasoning("") == ""


# --- extrahiere_rezept_titel -----------------------------------------------------
# Die Faelle entsprechen realen Antwort-Formaten aus docs/evidence/eval_traces/.

def test_titel_aus_ueberschrift():
    antwort = "## Zitronenhaehnchen mit Knoblauch\n**Zutaten:** ..."
    assert extrahiere_rezept_titel(antwort) == "Zitronenhaehnchen mit Knoblauch"


def test_titel_aus_fett_mit_label():
    antwort = "**Vorgeschlagenes Rezept: Gebackener Lachs mit Spargel**\n**Kalorien:** ~480 kcal"
    assert extrahiere_rezept_titel(antwort) == "Gebackener Lachs mit Spargel"


def test_titel_aus_fett_in_prosa():
    antwort = "Ich schlage das **Tomaten-Mozzarella-Salat**-Rezept vor – ein klassisches Gericht."
    assert extrahiere_rezept_titel(antwort) == "Tomaten-Mozzarella-Salat"


def test_titel_aus_klartext_label():
    assert extrahiere_rezept_titel("Rezept: Shakshuka\nZutaten: Eier, Tomaten") == "Shakshuka"


def test_abschnitts_labels_sind_kein_titel():
    antwort = "**Zutaten (fuer 2 Portionen):**\n- 400g Tomaten\n**Zubereitung:** schneiden"
    assert extrahiere_rezept_titel(antwort) is None


def test_fehlertext_ohne_titel_gibt_none():
    # Genau der Fall, der frueher als Rezeptname in der GUI landete.
    antwort = ("Da die Rezeptrecherche fehlgeschlagen ist, schlage ich ein "
               "einfaches Rezept vor, das den Vorgaben entspricht.")
    assert extrahiere_rezept_titel(antwort) is None


def test_fallback_rezept_nach_fehlertext_wird_gefunden():
    # Fallback auf eigenes Wissen: der Titel steht NACH dem Erklaersatz.
    antwort = ("Da die Websuche leer war, schlage ich aus eigenem Wissen vor:\n"
               "## Spaghetti Aglio e Olio\n**Zutaten:** Spaghetti, Knoblauch, Oel")
    assert extrahiere_rezept_titel(antwort) == "Spaghetti Aglio e Olio"


def test_titel_leer_gibt_none():
    assert extrahiere_rezept_titel("") is None
