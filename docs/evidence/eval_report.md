# Eval-Report: Constraint-Treue des RezeptAgenten (VL09)

*Reale Laeufe gegen den echten Agenten (Groq `qwen/qwen3-32b` + Tavily), Stand 2026-07-15.*
*Erzeugt mit `python evals/run_eval.py`; Checks: `evals/verifier.py` (programmatisch,*
*ternaer, kein LLM-Judge — Begruendung in `evals/README.md`). Roh-Traces mit voller*
*Antwort und allen TAO-Schritten: `docs/evidence/eval_traces/<fall-id>.json`.*

## Gesamtquoten

- **Faelle:** 15 gelaufen, davon 10 ohne Verletzung
- **Checks:** 45 gesamt — ✓ 39 bestanden · ○ 0 neutral · ✗ 6 verletzt
- **Bestanden-Quote (ohne neutral):** 39/45 = 87%

Legende: ✓ bestanden · ○ neutral (nicht entscheidbar/anwendbar) · ✗ verletzt.
„Schwer“ = bewusst so gebaut, dass der Agent voraussichtlich scheitert
(Material fuer die ehrliche Reflexion, siehe Testset).

## Uebersicht

| Fall | Schwer? | ✓ | ○ | ✗ | Aktionen | Dauer | Gesamt |
|------|---------|---|---|---|----------|-------|--------|
| `einfach_tomate_mozzarella` | — | 4 | 0 | 0 | 1 | 19.3 s | ✓ |
| `kcal_limit_einzelrezept` | — | 3 | 0 | 0 | 3 | 150.3 s | ✓ |
| `portionen_skalierung` | — | 3 | 0 | 0 | 2 | 80.2 s | ✓ |
| `vegan_profil` | — | 3 | 0 | 0 | 1 | 69.3 s | ✓ |
| `glutenfrei_profil` | — | 2 | 0 | 0 | 2 | 91.1 s | ✓ |
| `konflikt_salami_vegetarisch` | — | 2 | 0 | 0 | 2 | 86.3 s | ✓ |
| `wochenplan_3_kcal` | — | 5 | 0 | 1 | 13 | 274.3 s | ✗ |
| `wochenplan_ohne_kcal` | — | 3 | 0 | 0 | 3 | 60.8 s | ✓ |
| `leere_suche_fallback` | — | 3 | 0 | 0 | 1 | 55.3 s | ✓ |
| `modus_vorhanden` | — | 2 | 0 | 0 | 1 | 52.3 s | ✓ |
| `memory_schlecht_bewertet` | — | 1 | 0 | 1 | 1 | 67.8 s | ✗ |
| `favoriten_rag` | — | 3 | 0 | 0 | 2 | 89.6 s | ✓ |
| `schwer_kombi_constraints` | ja | 3 | 0 | 1 | 11 | 246.1 s | ✗ |
| `schwer_skalierung_kette` | ja | 2 | 0 | 1 | 2 | 113.0 s | ✗ |
| `schwer_kcal_tagessumme` | ja | 0 | 0 | 2 | 3 | 227.4 s | ✗ |

## Ergebnisse im Detail

### `einfach_tomate_mozzarella`

Einfache Rezeptfrage - gerader Weg: genau EINE Recherche, dann Antwort (System-Prompt: 'hoechstens einmal recherchieren').

- **Eingabe:** „Was kann ich mit Tomaten und Mozzarella kochen?“ (Modus `einkaufsliste`)
- **Trajektorie:** recherche_rezepte 1×

| Check | Status | Detail |
|-------|--------|--------|
| `antwort_nicht_leer` | ✓ bestanden | 821 Zeichen |
| `tool_aufgerufen` | ✓ bestanden | recherche_rezepte: 1x aufgerufen |
| `tool_nicht_aufgerufen` | ✓ bestanden | naehrwerte_schaetzen: nicht aufgerufen |
| `schrittzahl` | ✓ bestanden | 1 Aktionen (Korridor 1-8) |

> **Antwort (Auszug):** Ich schlage das **Tomaten-Mozzarella-Salat**-Rezept vor – ein klassisches, frisches Gericht: **Zutaten** (für 2 Portionen): - 400g Cherrytomaten - 200g Mozzarella (in Scheiben) - 50g Basilikumblätter - 2 EL Olivenöl - 1 EL Balsamico-Essig - Salz, Pfeffer **Zubereitung**: 1. Tomaten und Mozzarella in dünne Scheiben schn …

### `kcal_limit_einzelrezept`

Harter Constraint: kcal-Vorgabe beim Einzelrezept. Der Agent MUSS naehrwerte_schaetzen aufrufen (nicht selbst schaetzen), genannte kcal muessen <= Limit sein.

- **Eingabe:** „Schlag mir ein Abendessen mit maximal 500 kcal pro Portion vor.“ (Modus `einkaufsliste`)
- **Trajektorie:** recherche_rezepte 1×, naehrwerte_schaetzen 1×, portionen_skalieren 1×

| Check | Status | Detail |
|-------|--------|--------|
| `antwort_nicht_leer` | ✓ bestanden | 768 Zeichen |
| `tool_aufgerufen` | ✓ bestanden | naehrwerte_schaetzen: 1x aufgerufen |
| `kcal_limit` | ✓ bestanden | alle 3 kcal-Angaben <= 500 |

> **Antwort (Auszug):** **Vorgeschlagenes Rezept: Gebackener Lachs mit Spargel** **Kalorien:** ~480 kcal/Portion (unter deinem Limit von 500 kcal) **Zutaten (für 1 Portion):** - 150g Lachsfilet - 100g Spargel - 1 Zitrone (Saft) - 1 Knoblauchzehe - 1 EL Olivenöl - Salz, Pfeffer **Zubereitung:** 1. Lachsfilet mit Zitronensaft und zerdrücktem Kn …

### `portionen_skalierung`

Harter Constraint: Personenzahl. Skalierung MUSS ueber portionen_skalieren laufen (kein Kopfrechnen); Stichprobe: 400g*3=1200, 2*3=6, 300g*3=900, 1/2 TL*3=1,5. Keine Recherche noetig (situationsabhaengige Tool-Wahl).

- **Eingabe:** „Ich habe ein Rezept fuer 2 Personen: 400g Reis, 2 Zwiebeln, 300g Gemuese, 1/2 TL Salz. Rechne mir die Mengen fuer 6 Personen um.“ (Modus `einkaufsliste`)
- **Trajektorie:** portionen_skalieren 1×, einkaufsliste_erstellen 1×

| Check | Status | Detail |
|-------|--------|--------|
| `tool_aufgerufen` | ✓ bestanden | portionen_skalieren: 1x aufgerufen |
| `tool_nicht_aufgerufen` | ✓ bestanden | recherche_rezepte: nicht aufgerufen |
| `erwaehnt_alle` | ✓ bestanden | alle 4 Begriffe enthalten |

> **Antwort (Auszug):** **Rezept fuer 6 Personen:** - **1200g Reis** - **6 Zwiebeln** - **900g Gemuese** - **1,5 TL Salz** **Einkaufsliste (alle Zutaten fehlen):** - 1200g Reis - 6 Zwiebeln - 900g Gemuese - 1,5 TL Salz *Hinweis: Die Mengen wurden exakt fuer 6 Portionen umgerechnet. Fuer eine Naehrwert-Pruefung oder Anpassung an Kalorien-/Erna …

### `vegan_profil`

Harter Constraint aus dem Profil: vegan. In der Zutaten-/Einkaufsliste duerfen keine tierischen Produkte stehen (vegane Varianten wie 'vegane Sahne' sind erlaubt).

- **Eingabe:** „Schlag mir ein cremiges Pasta-Gericht zum Abendessen vor.“ (Modus `einkaufsliste`)
- **Profil-Fixture:** `{"ernaehrung": ["vegan"], "geschmack": [], "wichtig": [], "bewertungen": {}}`
- **Trajektorie:** recherche_rezepte 1×

| Check | Status | Detail |
|-------|--------|--------|
| `antwort_nicht_leer` | ✓ bestanden | 773 Zeichen |
| `verbotene_zutaten` | ✓ bestanden | 19 Listenzeilen geprueft, keine verbotene Zutat |
| `tool_aufgerufen` | ✓ bestanden | recherche_rezepte: 1x aufgerufen |

> **Antwort (Auszug):** **Rezept: Creamy Vegan One-Pot Pasta** **Zutaten**: - 100g Cashews - 200ml Gemüsebrühe - 1 EL Tomatenpaste - 1 Zwiebel - 2 Knoblauchzehen - 200g Penne-Nudeln - 1 geräucherte Paprika - Salz, Pfeffer, Olivenöl **Zubereitung**: 1. Cashews mit Brühe und Tomatenpaste pürieren. 2. Zwiebel und Knoblauch in Olivenöl anbraten,  …

### `glutenfrei_profil`

Harter Constraint aus dem Profil: glutenfrei - bei einer Nudel-Anfrage. Der Agent muss das Thema adressieren und darf keine Gluten-Quellen listen.

- **Eingabe:** „Ich moechte heute etwas mit Nudeln kochen.“ (Modus `einkaufsliste`)
- **Profil-Fixture:** `{"ernaehrung": ["glutenfrei"], "geschmack": [], "wichtig": [], "bewertungen": {}}`
- **Trajektorie:** recherche_rezepte 1×, einkaufsliste_erstellen 1×

| Check | Status | Detail |
|-------|--------|--------|
| `erwaehnt_eines` | ✓ bestanden | gefunden: ['glutenfrei'] |
| `verbotene_zutaten` | ✓ bestanden | 16 Listenzeilen geprueft, keine verbotene Zutat |

> **Antwort (Auszug):** **Glutenfreie Spaghetti mit Hackfleischsauce** **Zutaten (für 2 Portionen):** - 200g glutenfreie Nudeln - 300g Hackfleisch (z. B. Rind) - 1 Zwiebel - 2 Knoblauchzehen - 2 EL Tomatenmark - 200ml Wasser oder Brühe - Salz, Pfeffer, italienische Kräuter **Zubereitung:** 1. Nudeln nach Packungsanweisung kochen, abspülen. 2. …

### `konflikt_salami_vegetarisch`

Randfall: Tageswunsch (Salami) widerspricht der harten Profil-Vorgabe (vegetarisch). Der Agent muss den Konflikt ansprechen; Salami darf nicht in der Zutatenliste landen.

- **Eingabe:** „Ich haette heute richtig Lust auf Pizza mit Salami.“ (Modus `einkaufsliste`)
- **Profil-Fixture:** `{"ernaehrung": ["vegetarisch"], "geschmack": [], "wichtig": [], "bewertungen": {}}`
- **Trajektorie:** recherche_rezepte 1×, einkaufsliste_erstellen 1×

| Check | Status | Detail |
|-------|--------|--------|
| `erwaehnt_eines` | ✓ bestanden | gefunden: ['vegetarisch'] |
| `verbotene_zutaten` | ✓ bestanden | 18 Listenzeilen geprueft, keine verbotene Zutat |

> **Antwort (Auszug):** Hier ist ein passendes vegetarisches Pizza-Rezept für Sie: **Vegetarische Pizza mit Tomatensauce & Gemüse** **Zutaten (für 2 Portionen):** - 1 Pizza-Teig (ca. 300g) - 200g Tomatensauce - 100g Mozzarella (gewiegen) - 1/2 Paprika (rot/gelb) - 100g Champignons - 50g Oliven (schwarz/rot) - Salz & Pfeffer nach Geschmack **Z …

### `wochenplan_3_kcal`

Planungsfall: 3 Gerichte, kcal-Limit, vegetarisches Profil. Trajektorie muss die plan->pruefe->revidiere-Schleife zeigen: je Gericht Recherche + Naehrwert-Check, genau ein deterministischer Abschluss.

- **Eingabe:** „Plane mir 3 unterschiedliche Abendessen fuer die Woche, maximal 500 kcal pro Portion, fuer 2 Personen.“ (Modus `einkaufsliste`)
- **Profil-Fixture:** `{"ernaehrung": ["vegetarisch"], "geschmack": [], "wichtig": [], "bewertungen": {}}`
- **Trajektorie:** recherche_rezepte 6×, naehrwerte_schaetzen 6×, wochenplan_zusammenstellen 1×

| Check | Status | Detail |
|-------|--------|--------|
| `tool_aufgerufen` | ✓ bestanden | recherche_rezepte: 6x aufgerufen |
| `tool_aufgerufen` | ✓ bestanden | naehrwerte_schaetzen: 6x aufgerufen |
| `tool_aufgerufen` | ✓ bestanden | wochenplan_zusammenstellen: 1x aufgerufen |
| `revision_geprueft` | ✓ bestanden | 3x ueber Limit, jeweils Revision sichtbar |
| `kcal_limit` | ✗ verletzt | 3 Angabe(n) ueber Limit 500: [600.0] |
| `schrittzahl` | ✓ bestanden | 13 Aktionen (Korridor 7-40) |

> **Antwort (Auszug):** 1. **Zucchini-Nudeln mit Tomatensoße**: Zucchini, Tomatensoße, Olivenöl, Knoblauch, Petersilie (~600 kcal/Portion). 2. **Jackfruit-Gemüsepfanne**: Jackfruit, Reisnudeln, Brokkoli, Bohnen, Pilze, Curry (~600 kcal/Portion). 3. **Borschtsch vegetarisch**: Rote Bete, Kartoffeln, Karotten, Zwiebel, Knoblauch, Gemüsebrühe, E …

### `wochenplan_ohne_kcal`

Planungsfall ohne kcal-Vorgabe: situationsabhaengiger Pfad - der Naehrwert-Check darf NICHT laufen (kein Constraint -> kein Check), Abwechslung ueber zwei Recherchen.

- **Eingabe:** „Plane mir 2 Abendessen fuer die Woche, eins mit Fisch und eins nur mit Gemuese.“ (Modus `einkaufsliste`)
- **Trajektorie:** recherche_rezepte 2×, wochenplan_zusammenstellen 1×

| Check | Status | Detail |
|-------|--------|--------|
| `tool_aufgerufen` | ✓ bestanden | recherche_rezepte: 2x aufgerufen |
| `tool_nicht_aufgerufen` | ✓ bestanden | naehrwerte_schaetzen: nicht aufgerufen |
| `tool_aufgerufen` | ✓ bestanden | wochenplan_zusammenstellen: 1x aufgerufen |

> **Antwort (Auszug):** 1. Gebratener Lachs mit Dill-Sauce (ca. 500 kcal) - Lachsfilet, Dill, Butter, Kartoffeln, Zitrone Gesamt-Einkaufsliste: - Lachsfilet - Dill - Butter - Kartoffeln - Zitrone

### `leere_suche_fallback`

Fehlerfall: Suche nach Fantasie-Zutaten laeuft ins Leere. Erwartet: Agent erkennt den Fehlschlag und faellt TRANSPARENT auf eigenes Wissen zurueck oder sagt ehrlich, dass nichts gefunden wurde - statt Treffer zu erfinden.

- **Eingabe:** „Was kann ich mit Quargelbrumsel und Fizzelkraut kochen?“ (Modus `einkaufsliste`)
- **Trajektorie:** recherche_rezepte 1×

| Check | Status | Detail |
|-------|--------|--------|
| `antwort_nicht_leer` | ✓ bestanden | 960 Zeichen |
| `tool_aufgerufen` | ✓ bestanden | recherche_rezepte: 1x aufgerufen |
| `erwaehnt_eines` | ✓ bestanden | gefunden: ['keine passenden'] |

> **Antwort (Auszug):** Da keine passenden Rezepte für Quargelbrumsel und Fizzelkraut gefunden wurden, schlage ich ein selbst zusammengestelltes Gericht vor, basierend auf ähnlichen Zutaten: **Quargelbrumsel-Fizzelkraut-Eintopf** *(Eigene Kreation)* **Zutaten** (für 2 Portionen): - 200g Quargelbrumsel (oder Quark als Ersatz) - 300g Fizzelkrau …

### `modus_vorhanden`

Randfall Modus 'vorhanden': nur vorhandene Zutaten verwenden - die Einkaufslisten-Maschinerie darf nicht anspringen (situationsabhaengige Tool-Wahl).

- **Eingabe:** „Ich habe nur Eier, Tomaten, Zwiebeln und Brot da. Was kann ich damit kochen?“ (Modus `vorhanden`)
- **Trajektorie:** recherche_rezepte 1×

| Check | Status | Detail |
|-------|--------|--------|
| `antwort_nicht_leer` | ✓ bestanden | 760 Zeichen |
| `tool_nicht_aufgerufen` | ✓ bestanden | einkaufsliste_erstellen: nicht aufgerufen |

> **Antwort (Auszug):** Ich schlage das Rezept **Tomaten-Ei-Brot mit Zwiebeln** vor, das sich mit deinen vorhandenen Zutaten (plus Grundzutaten wie Olivenöl) zubereiten lässt: **Zutaten**: - 2–3 Eier - 1–2 Tomaten (gewürfelt) - 1 Zwiebel (gehackt) - 2–3 Scheiben Brot (in Würfel gehackt) - 1 EL Olivenöl - Salz, Pfeffer **Zubereitung**: 1. Eier …

### `memory_schlecht_bewertet`

Memory-Fall: Kuerbissuppe wurde mit 1 Stern bewertet ('eher meiden'). Bei einer Suppen-Anfrage darf der Agent nicht ausgerechnet Kuerbissuppe vorschlagen.

- **Eingabe:** „Schlag mir eine Suppe fuer heute Abend vor.“ (Modus `einkaufsliste`)
- **Profil-Fixture:** `{"ernaehrung": [], "geschmack": [], "wichtig": ["schnell"], "bewertungen": {"Kuerbissuppe": 1}}`
- **Trajektorie:** recherche_rezepte 1×

| Check | Status | Detail |
|-------|--------|--------|
| `antwort_nicht_leer` | ✓ bestanden | 780 Zeichen |
| `erwaehnt_nicht` | ✗ verletzt | unerwuenscht enthalten: ['Kuerbis'] |

> **Antwort (Auszug):** **Rezeptvorschlag: Süßkartoffelsuppe mit Blumenkohl** **Zutaten**: - 2–3 Süßkartoffeln - 1 Blumenkohl - 1 Zwiebel - 2 Knoblauchzehen - 2 EL Olivenöl - 1 Liter Brühe (Würzmittel oder Gemüsebrühe) - Salz, Pfeffer, eventuell Currypulver **Zubereitung**: 1. Zwiebel und Knoblauch in Olivenöl anbraten. 2. Süßkartoffeln und B …

### `favoriten_rag`

Agentic RAG (W3/W4): Bezug auf Bewaehrtes ('meine gespeicherten Lieblingsrezepte') -> der Agent muss ZUERST im persoenlichen Kochbuch suchen (rag_retriever), nicht im Web, und den Treffer verwenden.

- **Eingabe:** „Koch mir heute Abend eines meiner gespeicherten Lieblingsrezepte nach - am liebsten das Curry.“ (Modus `einkaufsliste`)
- **Kochbuch-Fixture:** Gemuese-Curry mit Kokosmilch, Linsen-Dal
- **Trajektorie:** rag_retriever 1×, einkaufsliste_erstellen 1×

| Check | Status | Detail |
|-------|--------|--------|
| `tool_aufgerufen` | ✓ bestanden | rag_retriever: 1x aufgerufen |
| `tool_reihenfolge` | ✓ bestanden | rag_retriever lief, recherche_rezepte war nicht noetig |
| `erwaehnt_eines` | ✓ bestanden | gefunden: ['Curry'] |

> **Antwort (Auszug):** Hier ist dein gespeichertes Lieblingsrezept und die dazugehörige Einkaufsliste: **Rezept: Gemüse-Curry mit Kokosmilch** (5 Sterne, ~540 kcal/Portion) 1. 2 Süßkartoffeln schälen und in Würfel schneiden 2. 400ml Kokosmilch mit 2 EL roter Currypaste vermengen 3. Süßkartoffeln in der Curry-Kokos-Mischung 15-20 Minuten köch …

### `schwer_kombi_constraints` — *bewusst schwerer Fall*

SCHWERER FALL: 4 Gerichte, vegan UND glutenfrei UND max 400 kcal, 3 Personen, abwechslungsreich. Viele gleichzeitige Constraints - hier erwarten wir Verletzungen (z.B. kcal trotz Revision ueber Limit oder tierische Zutat aus schlecht gefilterter Recherche).

*Warum schwer:* Die Recherche liefert selten Rezepte, die vegan+glutenfrei+kalorienarm zugleich sind; der Workflow revidiert nur EINMAL pro Gericht. Wir erwarten, dass mindestens ein Constraint reisst.

- **Eingabe:** „Plane mir 4 abwechslungsreiche Abendessen fuer die Woche, maximal 400 kcal pro Portion, fuer 3 Personen.“ (Modus `einkaufsliste`)
- **Profil-Fixture:** `{"ernaehrung": ["vegan", "glutenfrei"], "geschmack": [], "wichtig": [], "bewertungen": {}}`
- **Trajektorie:** recherche_rezepte 5×, naehrwerte_schaetzen 5×, wochenplan_zusammenstellen 1×

| Check | Status | Detail |
|-------|--------|--------|
| `tool_aufgerufen` | ✓ bestanden | recherche_rezepte: 5x aufgerufen |
| `tool_aufgerufen` | ✓ bestanden | naehrwerte_schaetzen: 5x aufgerufen |
| `kcal_limit` | ✗ verletzt | 1 Angabe(n) ueber Limit 400: [617.0] |
| `verbotene_zutaten` | ✓ bestanden | 21 Listenzeilen geprueft, keine verbotene Zutat |

> **Antwort (Auszug):** 1. **Black Bean, Tofu & Avocado Rice Bowl**: Schwarze Bohnen, Tofu, Reis, Avocado, Spinat (~617 kcal/Portion). 2. **Spinach & Sweet Potato Curry**: Süßkartoffeln, Spinat, Kokosmilch, Kurkuma (~400 kcal/Portion). 3. **Zucchini Noodles with Pesto**: Zucchini, Pinienkerne, Petersilie, Olivenöl, Zitrone (~400 kcal/Portion) …

### `schwer_skalierung_kette` — *bewusst schwerer Fall*

SCHWERER FALL: Zwei-Tool-Kette in EINER Anfrage - Rezept finden, kcal-Limit pruefen UND exakt auf 5 Personen skalieren. Erfahrungsgemaess laesst der Agent einen der beiden Constraint-Schritte aus.

*Warum schwer:* Der Agent muss naehrwerte_schaetzen UND portionen_skalieren in einem Lauf kombinieren; Modelle neigen dazu, die Skalierung 'im Kopf' zu machen oder ganz wegzulassen.

- **Eingabe:** „Such mir ein Curry-Rezept mit maximal 450 kcal pro Portion und rechne die Zutatenmengen exakt fuer 5 Personen um.“ (Modus `einkaufsliste`)
- **Trajektorie:** recherche_rezepte 1×, naehrwerte_schaetzen 1×

| Check | Status | Detail |
|-------|--------|--------|
| `tool_aufgerufen` | ✓ bestanden | naehrwerte_schaetzen: 1x aufgerufen |
| `tool_aufgerufen` | ✗ verletzt | portionen_skalieren: 0x aufgerufen, erwartet >= 1 |
| `kcal_limit` | ✓ bestanden | alle 2 kcal-Angaben <= 450 |

> **Antwort (Auszug):** Das Rezept **Kichererbsen-Curry** wurde angepasst, um die kcal-Vorgabe (~450 kcal/Portion) zu erfüllen. Hier die Details: --- ### **Rezept: Kichererbsen-Curry (für 5 Personen)** **Zutaten (angepasst):** - 1000g Kichererbsen - 5 Tomaten - 2,5 Zwiebeln - 2,5 EL Currypulver - 100ml Kokosmilch (ursprünglich 200ml reduziert …

### `schwer_kcal_tagessumme` — *bewusst schwerer Fall*

SCHWERER FALL: Tages-SUMMEN-Constraint (3 Mahlzeiten zusammen max 1200 kcal) statt Pro-Portion-Limit. Der Workflow kennt nur Pro-Portion-Limits - die Summen-Semantik wird voraussichtlich falsch behandelt.

*Warum schwer:* erkenne_wochenplan extrahiert 'kcal_limit pro Portion'; ein Summen-Budget ueber mehrere Mahlzeiten kann es nicht ausdruecken. Erwartung: das Limit wird als 1200/Portion fehlinterpretiert oder ignoriert.

- **Eingabe:** „Plane mir 3 Mahlzeiten fuer einen Tag (Fruehstueck, Mittag, Abend), die zusammen hoechstens 1200 kcal pro Person haben. Fuer 2 Personen.“ (Modus `einkaufsliste`)
- **Trajektorie:** recherche_rezepte 3×

| Check | Status | Detail |
|-------|--------|--------|
| `tool_aufgerufen` | ✗ verletzt | naehrwerte_schaetzen: 0x aufgerufen, erwartet >= 3 |
| `kcal_summe_limit` | ✗ verletzt | einzelner Wert ueber dem Gesamtbudget 1200 |

> **Antwort (Auszug):** **Vorgeschlagene Mahlzeiten für 2 Personen (max. 1200 kcal gesamt):** --- ### **1. Frühstück: Chia-Pancakes** **Zutaten**: - 100g Chia-Samen - 200ml Milch (Hafer- oder Soja-Milch für Laktose-Allergiker) - 2 Eier - 100g Mehl (glutenfrei, falls erforderlich) - 1 TL Backpulver - 1 EL Honig - 1 Prise Salz **Zubereitung**:  …

