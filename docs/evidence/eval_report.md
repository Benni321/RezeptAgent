# Eval-Report: Constraint-Treue des RezeptAgenten (VL09)

*Reale Laeufe gegen den echten Agenten (Groq `qwen/qwen3.6-27b` + Tavily), Stand 2026-08-03.*
*Erzeugt mit `python evals/run_eval.py`; Checks: `evals/verifier.py` (programmatisch,*
*ternaer, kein LLM-Judge — Begruendung in `evals/README.md`). Roh-Traces mit voller*
*Antwort und allen TAO-Schritten: `docs/evidence/eval_traces/<fall-id>.json`.*

## Gesamtquoten

- **Faelle:** 15 gelaufen, davon 10 ohne Verletzung
- **Checks:** 45 gesamt — ✓ 35 bestanden · ○ 4 neutral · ✗ 6 verletzt
- **Bestanden-Quote (ohne neutral):** 35/41 = 85%

Legende: ✓ bestanden · ○ neutral (nicht entscheidbar/anwendbar) · ✗ verletzt.
„Schwer“ = bewusst so gebaut, dass der Agent voraussichtlich scheitert
(Material fuer die ehrliche Reflexion, siehe Testset).

## Uebersicht

| Fall | Schwer? | ✓ | ○ | ✗ | Aktionen | Dauer | Gesamt |
|------|---------|---|---|---|----------|-------|--------|
| `einfach_tomate_mozzarella` | — | 4 | 0 | 0 | 1 | 24.7 s | ✓ |
| `kcal_limit_einzelrezept` | — | 3 | 0 | 0 | 4 | 177.4 s | ✓ |
| `portionen_skalierung` | — | 3 | 0 | 0 | 1 | 31.2 s | ✓ |
| `vegan_profil` | — | 3 | 0 | 0 | 1 | 57.3 s | ✓ |
| `glutenfrei_profil` | — | 2 | 0 | 0 | 1 | 55.3 s | ✓ |
| `konflikt_salami_vegetarisch` | — | 2 | 0 | 0 | 1 | 37.8 s | ✓ |
| `wochenplan_3_kcal` | — | 2 | 2 | 2 | 4 | 188.1 s | ✗ |
| `wochenplan_ohne_kcal` | — | 3 | 0 | 0 | 3 | 65.6 s | ✓ |
| `leere_suche_fallback` | — | 2 | 0 | 1 | 2 | 113.6 s | ✗ |
| `modus_vorhanden` | — | 2 | 0 | 0 | 0 | 1.7 s | ✓ |
| `memory_schlecht_bewertet` | — | 1 | 0 | 1 | 1 | 108.3 s | ✗ |
| `favoriten_rag` | — | 3 | 0 | 0 | 2 | 60.8 s | ✓ |
| `schwer_kombi_constraints` | ja | 1 | 2 | 1 | 5 | 286.8 s | ✗ |
| `schwer_skalierung_kette` | ja | 3 | 0 | 0 | 4 | 158.9 s | ✓ |
| `schwer_kcal_tagessumme` | ja | 1 | 0 | 1 | 6 | 187.7 s | ✗ |

## Ergebnisse im Detail

### `einfach_tomate_mozzarella`

Einfache Rezeptfrage - gerader Weg: genau EINE Recherche, dann Antwort (System-Prompt: 'hoechstens einmal recherchieren').

- **Eingabe:** „Was kann ich mit Tomaten und Mozzarella kochen?“ (Modus `einkaufsliste`)
- **Trajektorie:** recherche_rezepte 1×

| Check | Status | Detail |
|-------|--------|--------|
| `antwort_nicht_leer` | ✓ bestanden | 1580 Zeichen |
| `tool_aufgerufen` | ✓ bestanden | recherche_rezepte: 1x aufgerufen |
| `tool_nicht_aufgerufen` | ✓ bestanden | naehrwerte_schaetzen: nicht aufgerufen |
| `schrittzahl` | ✓ bestanden | 1 Aktionen (Korridor 1-8) |

> **Antwort (Auszug):** ## Cremiger Nudelauflauf mit Tomaten und Mozzarella Das klingt nach einem leckeren, sättigenden Gericht! Hier ist das Rezept für den **Cremigen Nudelauflauf mit Tomaten und Mozzarella**. **Zutaten (für 2 Personen):** * 200g Nudeln (z. B. Penne oder Fusilli) * 250g Kirschtomaten * 125g Mozzarella (in Würfel geschnitten) …

### `kcal_limit_einzelrezept`

Harter Constraint: kcal-Vorgabe beim Einzelrezept. Der Agent MUSS naehrwerte_schaetzen aufrufen (nicht selbst schaetzen), genannte kcal muessen <= Limit sein.

- **Eingabe:** „Schlag mir ein Abendessen mit maximal 500 kcal pro Portion vor.“ (Modus `einkaufsliste`)
- **Trajektorie:** recherche_rezepte 2×, naehrwerte_schaetzen 1×, einkaufsliste_erstellen 1×

| Check | Status | Detail |
|-------|--------|--------|
| `antwort_nicht_leer` | ✓ bestanden | 1431 Zeichen |
| `tool_aufgerufen` | ✓ bestanden | naehrwerte_schaetzen: 1x aufgerufen |
| `kcal_limit` | ✓ bestanden | alle 2 kcal-Angaben <= 500 |

> **Antwort (Auszug):** ## Mediterrane Hähnchen-Gemüse-Pfanne Hier ist ein leckeres, kalorienarmes Abendessen, das gut unter deinem Limit von 500 kcal liegt. **Geschätzte Nährwerte pro Portion:** ~343 kcal (Eiweiß: 31g, Kohlenhydrate: 12g, Fett: 21g). *Hinweis: Dies sind Näherungswerte ohne verifizierte Datenbank.* ### Zutaten (für 2 Portione …

### `portionen_skalierung`

Harter Constraint: Personenzahl. Skalierung MUSS ueber portionen_skalieren laufen (kein Kopfrechnen); Stichprobe: 400g*3=1200, 2*3=6, 300g*3=900, 1/2 TL*3=1,5. Keine Recherche noetig (situationsabhaengige Tool-Wahl).

- **Eingabe:** „Ich habe ein Rezept fuer 2 Personen: 400g Reis, 2 Zwiebeln, 300g Gemuese, 1/2 TL Salz. Rechne mir die Mengen fuer 6 Personen um.“ (Modus `einkaufsliste`)
- **Trajektorie:** portionen_skalieren 1×

| Check | Status | Detail |
|-------|--------|--------|
| `tool_aufgerufen` | ✓ bestanden | portionen_skalieren: 1x aufgerufen |
| `tool_nicht_aufgerufen` | ✓ bestanden | recherche_rezepte: nicht aufgerufen |
| `erwaehnt_alle` | ✓ bestanden | alle 4 Begriffe enthalten |

> **Antwort (Auszug):** ## Reis mit Gemüse (für 6 Personen) Hier sind die umgerechneten Zutatenmengen für 6 Personen: - 1200g Reis - 6 Zwiebeln - 900g Gemüse - 1,5 TL Salz Da du im Modus "Fehlende Zutaten dürfen ergänzt und als Einkaufsliste ausgegeben werden" bist, benötige ich noch eine Information, um die Einkaufsliste zu erstellen: **Welc …

### `vegan_profil`

Harter Constraint aus dem Profil: vegan. In der Zutaten-/Einkaufsliste duerfen keine tierischen Produkte stehen (vegane Varianten wie 'vegane Sahne' sind erlaubt).

- **Eingabe:** „Schlag mir ein cremiges Pasta-Gericht zum Abendessen vor.“ (Modus `einkaufsliste`)
- **Profil-Fixture:** `{"ernaehrung": ["vegan"], "geschmack": [], "wichtig": [], "bewertungen": {}}`
- **Trajektorie:** recherche_rezepte 1×

| Check | Status | Detail |
|-------|--------|--------|
| `antwort_nicht_leer` | ✓ bestanden | 2123 Zeichen |
| `verbotene_zutaten` | ✓ bestanden | 27 Listenzeilen geprueft, keine verbotene Zutat |
| `tool_aufgerufen` | ✓ bestanden | recherche_rezepte: 1x aufgerufen |

> **Antwort (Auszug):** ## Cremige Gemüsepasta mit Cashew-Sauce Hier ist ein leckeres, cremiges und veganes Pasta-Rezept für dich. Die Sauce basiert auf Cashewkernen und Hafermilch, was eine herrlich sämige Konsistenz ergibt, ohne tierische Produkte zu verwenden. **Zutaten (für 2 Personen):** * 200 g Nudeln (z. B. Penne oder Fusilli) * 100 g  …

### `glutenfrei_profil`

Harter Constraint aus dem Profil: glutenfrei - bei einer Nudel-Anfrage. Der Agent muss das Thema adressieren und darf keine Gluten-Quellen listen.

- **Eingabe:** „Ich moechte heute etwas mit Nudeln kochen.“ (Modus `einkaufsliste`)
- **Profil-Fixture:** `{"ernaehrung": ["glutenfrei"], "geschmack": [], "wichtig": [], "bewertungen": {}}`
- **Trajektorie:** recherche_rezepte 1×

| Check | Status | Detail |
|-------|--------|--------|
| `erwaehnt_eines` | ✓ bestanden | gefunden: ['glutenfrei'] |
| `verbotene_zutaten` | ✓ bestanden | 12 Listenzeilen geprueft, keine verbotene Zutat |

> **Antwort (Auszug):** ## Glutenfreie Nudeln (Klassisch mit Xanthan) Hier ist ein einfaches und bewährtes Rezept für selbstgemachte glutenfreie Nudeln. Da du den Modus "Einkaufsliste" gewählt hast, erstelle ich dir im nächsten Schritt eine Liste der fehlenden Zutaten. **Zutaten (für 2 Personen):** * 200 g glutenfreie Mehlmischung (z. B. aus  …

### `konflikt_salami_vegetarisch`

Randfall: Tageswunsch (Salami) widerspricht der harten Profil-Vorgabe (vegetarisch). Der Agent muss den Konflikt ansprechen; Salami darf nicht in der Zutatenliste landen.

- **Eingabe:** „Ich haette heute richtig Lust auf Pizza mit Salami.“ (Modus `einkaufsliste`)
- **Profil-Fixture:** `{"ernaehrung": ["vegetarisch"], "geschmack": [], "wichtig": [], "bewertungen": {}}`
- **Trajektorie:** einkaufsliste_erstellen 1×

| Check | Status | Detail |
|-------|--------|--------|
| `erwaehnt_eines` | ✓ bestanden | gefunden: ['vegetarisch'] |
| `verbotene_zutaten` | ✓ bestanden | 6 Listenzeilen geprueft, keine verbotene Zutat |

> **Antwort (Auszug):** Hier ist deine Einkaufsliste für die vegetarische Pizza: **Einkaufsliste:** * 350 g Weizenmehl * 1 Päckchen Trockenhefe * Olivenöl (für Teig und Bestreichen) * 200 g passierte Tomaten * 200 g Mozzarella * Frische Basilikumblätter Guten Appetit! Wenn du doch lieber ein Rezept mit anderen vegetarischen Belägen (z. B. Pil …

### `wochenplan_3_kcal`

Planungsfall: 3 Gerichte, kcal-Limit, vegetarisches Profil. Trajektorie muss die plan->pruefe->revidiere-Schleife zeigen: je Gericht Recherche + Naehrwert-Check, genau ein deterministischer Abschluss.

- **Eingabe:** „Plane mir 3 unterschiedliche Abendessen fuer die Woche, maximal 500 kcal pro Portion, fuer 2 Personen.“ (Modus `einkaufsliste`)
- **Profil-Fixture:** `{"ernaehrung": ["vegetarisch"], "geschmack": [], "wichtig": [], "bewertungen": {}}`
- **Trajektorie:** recherche_rezepte 3×, wochenplan_zusammenstellen 1×

| Check | Status | Detail |
|-------|--------|--------|
| `tool_aufgerufen` | ✓ bestanden | recherche_rezepte: 3x aufgerufen |
| `tool_aufgerufen` | ✗ verletzt | naehrwerte_schaetzen: 0x aufgerufen, erwartet >= 3 |
| `tool_aufgerufen` | ✓ bestanden | wochenplan_zusammenstellen: 1x aufgerufen |
| `revision_geprueft` | ○ neutral | kein Gericht ueber dem Limit -> keine Revision noetig |
| `kcal_limit` | ○ neutral | keine kcal-Angabe in der Antwort gefunden |
| `schrittzahl` | ✗ verletzt | 4 Aktionen, erwartet 7-40 |

> **Antwort (Auszug):** Ich konnte leider keine passenden Rezepte fuer den Wochenplan finden.

### `wochenplan_ohne_kcal`

Planungsfall ohne kcal-Vorgabe: situationsabhaengiger Pfad - der Naehrwert-Check darf NICHT laufen (kein Constraint -> kein Check), Abwechslung ueber zwei Recherchen.

- **Eingabe:** „Plane mir 2 Abendessen fuer die Woche, eins mit Fisch und eins nur mit Gemuese.“ (Modus `einkaufsliste`)
- **Trajektorie:** recherche_rezepte 2×, wochenplan_zusammenstellen 1×

| Check | Status | Detail |
|-------|--------|--------|
| `tool_aufgerufen` | ✓ bestanden | recherche_rezepte: 2x aufgerufen |
| `tool_nicht_aufgerufen` | ✓ bestanden | naehrwerte_schaetzen: nicht aufgerufen |
| `tool_aufgerufen` | ✓ bestanden | wochenplan_zusammenstellen: 1x aufgerufen |

> **Antwort (Auszug):** Wochenplan: 1. Lachs-Sahne-Gratin aus dem Ofen Zutaten: Lachsfilets, Sahne, Zwiebeln, Petersilie, Salz, Pfeffer, Zitronensaft Hinweis: Geschätzte Kalorien (Näherung ohne verifizierte DB) 2. Meditaner Fisch mit Gemüse Zutaten: Weißes Fischfilet, Zwiebeln, Paprika, Zucchini, Weißwein, Gemüsebrühe, frisches Basilikum, Oli …

### `leere_suche_fallback`

Fehlerfall: Suche nach Fantasie-Zutaten laeuft ins Leere. Erwartet: Agent erkennt den Fehlschlag und faellt TRANSPARENT auf eigenes Wissen zurueck oder sagt ehrlich, dass nichts gefunden wurde - statt Treffer zu erfinden.

- **Eingabe:** „Was kann ich mit Quargelbrumsel und Fizzelkraut kochen?“ (Modus `einkaufsliste`)
- **Trajektorie:** recherche_rezepte 1×, einkaufsliste_erstellen 1×

| Check | Status | Detail |
|-------|--------|--------|
| `antwort_nicht_leer` | ✓ bestanden | 215 Zeichen |
| `tool_aufgerufen` | ✓ bestanden | recherche_rezepte: 1x aufgerufen |
| `erwaehnt_eines` | ✗ verletzt | keiner von 9 Begriffen enthalten |

> **Antwort (Auszug):** Hier ist deine Einkaufsliste für das **Quarkcreme mit Gurke und Dill**: - 250 g Magerquark - 1 kleine Gurke - 1 Bund frischer Dill - 100 ml Schmand oder saure Sahne - 1 Zwiebel - 1 TL Senf Viel Erfolg beim Kochen!

### `modus_vorhanden`

Randfall Modus 'vorhanden': nur vorhandene Zutaten verwenden - die Einkaufslisten-Maschinerie darf nicht anspringen (situationsabhaengige Tool-Wahl).

- **Eingabe:** „Ich habe nur Eier, Tomaten, Zwiebeln und Brot da. Was kann ich damit kochen?“ (Modus `vorhanden`)
- **Trajektorie:** —

| Check | Status | Detail |
|-------|--------|--------|
| `antwort_nicht_leer` | ✓ bestanden | 1955 Zeichen |
| `tool_nicht_aufgerufen` | ✓ bestanden | einkaufsliste_erstellen: nicht aufgerufen |

> **Antwort (Auszug):** ## Spanische Tortilla (Omelett mit Tomaten und Zwiebeln) Da du nur Eier, Tomaten, Zwiebeln und Brot hast, ist eine klassische **Spanische Tortilla** (oder ein einfaches Omelett) die beste Wahl. Das Brot kannst du dazu als Beilage servieren oder in kleine Würfel schneiden und mitbraten, um das Omelett zu binden und zu s …

### `memory_schlecht_bewertet`

Memory-Fall: Kuerbissuppe wurde mit 1 Stern bewertet ('eher meiden'). Bei einer Suppen-Anfrage darf der Agent nicht ausgerechnet Kuerbissuppe vorschlagen.

- **Eingabe:** „Schlag mir eine Suppe fuer heute Abend vor.“ (Modus `einkaufsliste`)
- **Profil-Fixture:** `{"ernaehrung": [], "geschmack": [], "wichtig": ["schnell"], "bewertungen": {"Kuerbissuppe": 1}}`
- **Trajektorie:** recherche_rezepte 1×

| Check | Status | Detail |
|-------|--------|--------|
| `antwort_nicht_leer` | ✓ bestanden | 1423 Zeichen |
| `erwaehnt_nicht` | ✗ verletzt | unerwuenscht enthalten: ['Kuerbissuppe', 'Kuerbis'] |

> **Antwort (Auszug):** ## Cremige Tomatensuppe Da dir bei Gerichten generell Schnelligkeit wichtig ist und du Kürbissuppe eher meidest, ist diese cremige Tomatensuppe eine hervorragende Wahl. Sie ist in etwa 20 Minuten zubereitet, schmeckt intensiv und ist ein klassischer Komfort-Klassiker. **Zutaten (für 2 Portionen):** * 1 Zwiebel * 2 Knob …

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

> **Antwort (Auszug):** ## Gemuese-Curry mit Kokosmilch Hier ist dein gespeichertes Lieblingsrezept aus dem persönlichen Kochbuch: **Zutaten:** - 2 Süßkartoffeln - 400 ml Kokosmilch - 2 EL rote Currypaste - 200 g Reis **Zubereitung:** 1. Die Süßkartoffeln schälen und in Würfel schneiden. 2. Den Reis nach Packungsanleitung garen. 3. In einem T …

### `schwer_kombi_constraints` — *bewusst schwerer Fall*

SCHWERER FALL: 4 Gerichte, vegan UND glutenfrei UND max 400 kcal, 3 Personen, abwechslungsreich. Viele gleichzeitige Constraints - hier erwarten wir Verletzungen (z.B. kcal trotz Revision ueber Limit oder tierische Zutat aus schlecht gefilterter Recherche).

*Warum schwer:* Die Recherche liefert selten Rezepte, die vegan+glutenfrei+kalorienarm zugleich sind; der Workflow revidiert nur EINMAL pro Gericht. Wir erwarten, dass mindestens ein Constraint reisst.

- **Eingabe:** „Plane mir 4 abwechslungsreiche Abendessen fuer die Woche, maximal 400 kcal pro Portion, fuer 3 Personen.“ (Modus `einkaufsliste`)
- **Profil-Fixture:** `{"ernaehrung": ["vegan", "glutenfrei"], "geschmack": [], "wichtig": [], "bewertungen": {}}`
- **Trajektorie:** recherche_rezepte 4×, wochenplan_zusammenstellen 1×

| Check | Status | Detail |
|-------|--------|--------|
| `tool_aufgerufen` | ✓ bestanden | recherche_rezepte: 4x aufgerufen |
| `tool_aufgerufen` | ✗ verletzt | naehrwerte_schaetzen: 0x aufgerufen, erwartet >= 4 |
| `kcal_limit` | ○ neutral | keine kcal-Angabe in der Antwort gefunden |
| `verbotene_zutaten` | ○ neutral | keine Zutaten-/Listenzeilen gefunden |

> **Antwort (Auszug):** Ich konnte leider keine passenden Rezepte fuer den Wochenplan finden.

### `schwer_skalierung_kette` — *bewusst schwerer Fall*

SCHWERER FALL: Zwei-Tool-Kette in EINER Anfrage - Rezept finden, kcal-Limit pruefen UND exakt auf 5 Personen skalieren. Erfahrungsgemaess laesst der Agent einen der beiden Constraint-Schritte aus.

*Warum schwer:* Der Agent muss naehrwerte_schaetzen UND portionen_skalieren in einem Lauf kombinieren; Modelle neigen dazu, die Skalierung 'im Kopf' zu machen oder ganz wegzulassen.

- **Eingabe:** „Such mir ein Curry-Rezept mit maximal 450 kcal pro Portion und rechne die Zutatenmengen exakt fuer 5 Personen um.“ (Modus `einkaufsliste`)
- **Trajektorie:** recherche_rezepte 1×, naehrwerte_schaetzen 2×, portionen_skalieren 1×

| Check | Status | Detail |
|-------|--------|--------|
| `tool_aufgerufen` | ✓ bestanden | naehrwerte_schaetzen: 2x aufgerufen |
| `tool_aufgerufen` | ✓ bestanden | portionen_skalieren: 1x aufgerufen |
| `kcal_limit` | ✓ bestanden | alle 2 kcal-Angaben <= 450 |

> **Antwort (Auszug):** ## Cremiges Low Carb Tomaten-Kokos-Curry mit Hähnchen (angepasst) Dieses Rezept liegt mit geschätzten **~392 kcal pro Portion** unter deinem Limit von 450 kcal. Die Werte sind Näherungen ohne verifizierte Datenbank. ### Zutaten für 5 Personen: - 1250g Hähnchenbrustfilet - 2,5 Zwiebeln - 5 Knoblauchzehen - 1000g passier …

### `schwer_kcal_tagessumme` — *bewusst schwerer Fall*

SCHWERER FALL: Tages-SUMMEN-Constraint (3 Mahlzeiten zusammen max 1200 kcal) statt Pro-Portion-Limit. Der Workflow kennt nur Pro-Portion-Limits - die Summen-Semantik wird voraussichtlich falsch behandelt.

*Warum schwer:* erkenne_wochenplan extrahiert 'kcal_limit pro Portion'; ein Summen-Budget ueber mehrere Mahlzeiten kann es nicht ausdruecken. Erwartung: das Limit wird als 1200/Portion fehlinterpretiert oder ignoriert.

- **Eingabe:** „Plane mir 3 Mahlzeiten fuer einen Tag (Fruehstueck, Mittag, Abend), die zusammen hoechstens 1200 kcal pro Person haben. Fuer 2 Personen.“ (Modus `einkaufsliste`)
- **Trajektorie:** recherche_rezepte 3×, naehrwerte_schaetzen 2×, wochenplan_zusammenstellen 1×

| Check | Status | Detail |
|-------|--------|--------|
| `tool_aufgerufen` | ✗ verletzt | naehrwerte_schaetzen: 2x aufgerufen, erwartet >= 3 |
| `kcal_summe_limit` | ✓ bestanden | Summe 512 <= 1200 |

> **Antwort (Auszug):** **Wochenplan** 1. **Beeren-Quinoa-Joghurt-Bowl** *Zutaten:* 200 g Magerquark oder Griechischer Joghurt (0–2 % Fett), 50 g Quinoa (gekocht) oder Haferflocken, 100 g Beeren (frisch oder tiefgekühlt, z. B. Himbeeren, Blaubeeren), 1 EL Chiasamen oder Leinsamen, Optional: etwas Zitrone oder Honig zum Süßen. *Kalorien:* ~172 …

