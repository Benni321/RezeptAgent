# Referenz-Traces: vier Eingaben, vier Trajektorien (P2 + Dim 2)

*Reale Läufe gegen den echten Agenten (Groq + Tavily) am 2026-07-15,
erzeugt mit `python scripts/erzeuge_referenz_traces.py` (reproduzierbar). Die
Eingaben und ihre Erwartungen sind in [referenz_eingaben.md](referenz_eingaben.md)
begründet; hier stehen die tatsächlichen Traces. Roh-Format (maschinenlesbar,
mit `trace_id`, `dauer_ms`, `status` je Schritt): `traces/referenz_<a-d>.json`.*

## (a) Einfache Rezeptfrage → gerade Recherche-Trajektorie

- **Eingabe:** „Was kann ich mit Hähnchen, Zitrone und Knoblauch kochen?“
- **Profil:** leer
- **Erwartung:** eine Recherche → Antwort; kein Nährwert-Check, keine Skalierung
- **Tatsächliche Trajektorie:** recherche_rezepte — 1 TAO-Zyklen
- **Roh-Trace:** [traces/referenz_a.json](traces/referenz_a.json) (trace_id `4d3a9b046537`)


**TAO-Zyklus 1 — [Thought → Action]** Sub-Agent `recherche_rezepte`
    args: {'anfrage': 'Rezepte mit Hähnchen, Zitrone und Knoblauch'}
**TAO-Zyklus 1 — [Observation]** (1554 ms, ok) Sub-Agent `recherche_rezepte`:
    1. **Hähnchen mit Zitrone und Knoblauch**  
       - **Hauptzutaten**: Hähnchen, Zitrone, Knoblauch, Olivenöl, Salz, Pfeffer  
       - **Zubereitung**: Hähnchen in Zitronensaft und Knoblauch marinieren. In Olivenöl anbraten, mit Zitronenscheiben und Knoblauchwürfeln weitergaren. Mit Salz und Pfeffer abschmecken.  
       - **Quelle**: [zitronen-haehnchen-rezept.de](https://www.zitronen-haehnchen-rezept.de)  
    
    2. **Zitronen-Hähnchen mit Knoblauch**  
       - **Hauptzutaten**: Hähnchenke

> **Finale Antwort (Auszug):** Ich schlage das Rezept **"Hähnchen mit Zitrone und Knoblauch"** vor: **Zutaten (für 2 Portionen):** - 4 Hähnchenfilets - 1 Zitrone (Saft + Schale) - 3 Knoblauchzehen (gewürfelt) - 2 EL Olivenöl - Salz, Pfeffer **Zubereitung:** 1. Hähnchen in Zitronensaft und Knoblauch marinieren (30 Min). 2. In Olivenöl anbraten, Zitronenschale und Knoblauchwürfel dazugeben. 3. Mit Salz und Pfeffer abschmecken, 15–20 Min. garen. **Einkaufsliste (falls Zutaten fehlen):** - Hähnchenfilets - Zitrone - Knoblauch - O …

## (b) Wochenplan mit kcal-Limit → Planungs-Schleife mit Revision (P2-Nachweis)

- **Eingabe:** „Plane mir 2 unterschiedliche Abendessen für diese Woche, max. 500 kcal pro Portion, für 2 Personen.“
- **Profil:** vegetarisch
- **Erwartung:** je Gericht Recherche → kcal-Check → ggf. Revision → Abschluss-Tool
- **Tatsächliche Trajektorie:** recherche_rezepte → naehrwerte_schaetzen → recherche_rezepte → naehrwerte_schaetzen → recherche_rezepte → naehrwerte_schaetzen → recherche_rezepte → naehrwerte_schaetzen → wochenplan_zusammenstellen — 9 TAO-Zyklen
- **Roh-Trace:** [traces/referenz_b.json](traces/referenz_b.json) (trace_id `ccfb59223863`)

**P2-Nachweis:** Dieser Trace enthält **9 vollständige TAO-Zyklen** (gefordert: ≥ 3), oben einzeln beschriftet. Transparenz: Dieser Lauf geht über den code-orchestrierten Wochenplan-Pfad (Struktur garantiert der Code, Inhalte entscheidet das LLM — PROJEKTDOKU § 2.4); einen voll agentischen Lauf mit ≥ 3 Zyklen zeigt [eval_traces/kcal_limit_einzelrezept.json](eval_traces/kcal_limit_einzelrezept.json).


**TAO-Zyklus 1 — [Thought → Action]** Sub-Agent `recherche_rezepte`
    args: {'anfrage': 'Plane mir 2 unterschiedliche Abendessen für diese Woche, max. 500 kcal pro Portion, für 2 Personen. vegetarisch'}
**TAO-Zyklus 1 — [Observation]** (27550 ms, ok) Sub-Agent `recherche_rezepte`:
    1. **Zucchini-Nudeln mit Tomatensoße**  
       - **Hauptzutaten**: Zucchini, Tomaten, Olivenöl, Knoblauch, Salz, Pfeffer  
       - **Zubereitung**:  
         - Zucchini in Nudelform hobeln.  
         - Tomatensoße aus Tomaten, Knoblauch und Gewürzen kochen.  
         - Zucchini-Nudeln kurz anbraten, mit Soße mischen.  
       - **Quelle**: [Edeka Rezepte](https://www.edeka.de/rezeptwelt/rezeptsammlungen/kochen/rezepte-unter-500-kcal)  
    
    2. **Couscoussalat mit Gemüse**  
       - **H

**TAO-Zyklus 2 — [Thought → Action]** Tool `naehrwerte_schaetzen`
    args: {'rezept_titel': 'Zucchini-Nudeln mit Tomatensoße', 'portionen': 2}
**TAO-Zyklus 2 — [Observation]** (5828 ms, ok) Tool `naehrwerte_schaetzen`:
    ~600 kcal/Portion -> UEBER Limit 500, revidiere

**TAO-Zyklus 3 — [Thought → Action]** Sub-Agent `recherche_rezepte`
    args: {'anfrage': 'Revision: kalorienarmer Ersatz'}
**TAO-Zyklus 3 — [Observation]** (9835 ms, ok) Sub-Agent `recherche_rezepte`:
    1. **Spaghetti mit Tomaten und Zucchini**  
       - **Hauptzutaten**: Spaghetti (50g), Zucchini (200g), Cherry-Tomaten (150g), Knoblauch, Olivenöl, Petersilie  
       - **Zubereitung**:  
         - Spaghetti kochen.  
         - Zucchini und Tomaten in Würfel schneiden, mit Knoblauch in Olivenöl anbraten.  
         - Mit Petersilie bestreuen, mit Spaghetti vermengen.  
       - **Quelle**: [vegetarisch-rezepte.de](https://www.vegetarisch-rezepte.de/spaghetti-tomaten-zucchini)  
       - **Ka

**TAO-Zyklus 4 — [Thought → Action]** Tool `naehrwerte_schaetzen`
    args: {'rezept_titel': 'Spaghetti mit Tomaten und Zucchini', 'portionen': 2}
**TAO-Zyklus 4 — [Observation]** (7568 ms, ok) Tool `naehrwerte_schaetzen`:
    Ersatz ~1400 kcal/Portion

**TAO-Zyklus 5 — [Thought → Action]** Sub-Agent `recherche_rezepte`
    args: {'anfrage': 'Plane mir 2 unterschiedliche Abendessen für diese Woche, max. 500 kcal pro Portion, für 2 Personen. vegetarisch (anderes Gericht als: Zucchini-Nudeln mit Tomatensoße)'}
**TAO-Zyklus 5 — [Observation]** (27360 ms, ok) Sub-Agent `recherche_rezepte`:
    1. **Vegetarischer Borschtsch**  
       **Hauptzutaten**: Rote Bete, Karotten, Zwiebeln, Kartoffeln, Sellerie, Petersilie, Zitronensäure  
       **Zubereitung**:  
       - Gemüse schälen und in Würfel schneiden.  
       - In Wasser mit Zwiebeln und Gewürzen 20–30 Minuten kochen.  
       - Mit Zitronensäure abschmecken.  
       **Quelle**: [eatsmarter.de](https://eatsmarter.de/rezepte/ernaehrung/vegetarisch/vegetarische-rezepte-unter-500-kcal)  
    
    2. **Zucchini-Paprika-Pfanne**  
   

**TAO-Zyklus 6 — [Thought → Action]** Tool `naehrwerte_schaetzen`
    args: {'rezept_titel': 'Vegetarischer Borschtsch', 'portionen': 2}
**TAO-Zyklus 6 — [Observation]** (4695 ms, ok) Tool `naehrwerte_schaetzen`:
    ~600 kcal/Portion -> UEBER Limit 500, revidiere

**TAO-Zyklus 7 — [Thought → Action]** Sub-Agent `recherche_rezepte`
    args: {'anfrage': 'Revision: kalorienarmer Ersatz'}
**TAO-Zyklus 7 — [Observation]** (9631 ms, ok) Sub-Agent `recherche_rezepte`:
    1. **Linsen-Salat mit Feta und Gurke**  
       - **Hauptzutaten**: 200g rote Linsen, 1 Gurke, 150g Feta, 100g Cherry-Tomaten, Olivenöl, Zitronensaft  
       - **Zubereitung**: Linsen kochen, abkühlen lassen. Gurke und Tomaten würfeln. Mit Feta, Olivenöl, Zitronensaft und Petersilie vermengen.  
       - **Quelle**: [lecker.de](https://www.lecker.de)  
    
    2. **Kürbis-Spinat-Curry mit Kokosmilch**  
       - **Hauptzutaten**: 300g Hokkaido-Kürbis, 100g frischer Spinat, 200ml Kokosmilch, 1 

**TAO-Zyklus 8 — [Thought → Action]** Tool `naehrwerte_schaetzen`
    args: {'rezept_titel': 'Kürbis-Spinat-Curry mit Kokosmilch', 'portionen': 2}
**TAO-Zyklus 8 — [Observation]** (8568 ms, ok) Tool `naehrwerte_schaetzen`:
    Ersatz ~325 kcal/Portion

**TAO-Zyklus 9 — [Thought → Action]** Tool `wochenplan_zusammenstellen`
    args: {'anzahl_gerichte': 2}
**TAO-Zyklus 9 — [Observation]** (0 ms, ok) Tool `wochenplan_zusammenstellen`:
    Wochenplan:
    1. Zucchini-Nudeln mit Tomatensoße
    2. Kürbis-Spinat-Curry mit Kokosmilch
    
    Gesamt-Einkaufsliste (fehlende Zutaten fuer alle Gerichte):
    - Zucchini
    - Tomaten
    - Olivenöl
    - Knoblauch
    - Salz
    - Pfeffer
    - 300g Hokkaido-Kürbis
    - 100g frischer Spinat
    - 200ml Kokosmilch
    - 1 Zwiebel
    - Currypulver
    - Kokosraspeln

> **Finale Antwort (Auszug):** 1. **Zucchini-Nudeln mit Tomatensoße** - Zucchini, Tomaten, Olivenöl, Knoblauch, Salz, Pfeffer - ~600 kcal/Portion (trotz Revision über Limit). 2. **Kürbis-Spinat-Curry mit Kokosmilch** - 300g Hokkaido-Kürbis, 100g frischer Spinat, 200ml Kokosmilch, 1 Zwiebel, Currypulver, Kokosraspeln - ~325 kcal/Portion (eingehalten). **Gesamt-Einkaufsliste (fehlende Zutaten für alle Gerichte):** - Zucchini - Tomaten - Olivenöl - Knoblauch - Salz - Pfeffer - 300g Hokkaido-Kürbis - 100g frischer Spinat - 200ml  …

## (c) Websuche läuft ins Leere → Fallback auf eigenes Wissen

- **Eingabe:** „Ich brauche ein Rezept für gebratene Mondsteine mit Einhornhaar.“
- **Profil:** leer
- **Erwartung:** Recherche scheitert erkennbar → transparent gekennzeichneter Fallback
- **Tatsächliche Trajektorie:** recherche_rezepte — 1 TAO-Zyklen
- **Roh-Trace:** [traces/referenz_c.json](traces/referenz_c.json) (trace_id `dfa481fd97b1`)


**TAO-Zyklus 1 — [Thought → Action]** Sub-Agent `recherche_rezepte`
    args: {'anfrage': 'gebratene Mondsteine mit Einhornhaar'}
**TAO-Zyklus 1 — [Observation]** (27209 ms, ok) Sub-Agent `recherche_rezepte`:
    Keine passenden Rezepte aus der Websuche gefunden. "Gebratene Mondsteine mit Einhornhaar" scheint keine existierende Rezeptbezeichnung zu sein – die Suchergebnisse enthielten nur allgemeine Informationen zu Einhornhaar (aus Harry Potter) und unabhängige Rezepte für Kuchen oder Dumplings.

> **Finale Antwort (Auszug):** Da "gebratene Mondsteine mit Einhornhaar" keine existierende Rezeptbezeichnung ist und die Websuche keine passenden Ergebnisse lieferte, schlage ich ein kreatives, magisches Rezept aus meinem Wissen vor (nicht aus einer Websuche): **Rezept: "Einhornhaar-Kekse mit Mondstein-Glasur"** *Zutaten:* - 200g Mehl - 100g Butter - 80g Zucker - 1 Ei - 1 Prise Salz - 1/2 TL Vanilleextrakt - Für die Glasur: 100g Puderzucker, 1-2 EL Milch, 1 Schuss Zitronensaft - "Einhornhaar": Edible Glitzer (optional) *Zube …

## (d) Konflikt Wunsch ↔ Profil → Agent thematisiert ihn

- **Eingabe:** „Ich hätte gerne ein Rezept mit Salami und Käse.“
- **Profil:** vegetarisch
- **Erwartung:** Konflikt wird angesprochen; harte Vorgabe (vegetarisch) gewinnt
- **Tatsächliche Trajektorie:** recherche_rezepte — 1 TAO-Zyklen
- **Roh-Trace:** [traces/referenz_d.json](traces/referenz_d.json) (trace_id `9c5f3e2b8bf5`)


**TAO-Zyklus 1 — [Thought → Action]** Sub-Agent `recherche_rezepte`
    args: {'anfrage': 'vegetarische Rezepte mit Käse (ohne Fleisch)'}
**TAO-Zyklus 1 — [Observation]** (11059 ms, ok) Sub-Agent `recherche_rezepte`:
    1. **Käsespätzle (Deutschland)**  
       - **Hauptzutaten**: Spätzleteig (Mehl, Eier, Milch), Käse (Emmental/Gouda), Butter  
       - **Zubereitung**: Spätzle formen und braten, mit geschmolzenem Käse übergießen, mit Butter servieren.  
       - **Quelle**: [Käsespätzle-Rezept](https://www.kochrezepte.at/rezept/kaesespaetzle)  
    
    2. **Spinat-Käse-Torte (Italienisch)**  
       - **Hauptzutaten**: Spinat, Mozzarella, Ricotta, Tomatensoße, Brötchenkruste  
       - **Zubereitung**: Spinat

> **Finale Antwort (Auszug):** Das Rezept "Käsespätzle" aus der Suche ist vegetarisch und passt zu deinen Vorgaben. Salami wurde bewusst ausgeschlossen, da sie nicht vegetarisch ist. Hier die Details: **Rezept: Käsespätzle** - **Zutaten**: - 200g Mehl - 2 Eier - 200ml Milch - 100g Emmental (geraspelt) - 2 EL Butter - Salz, Pfeffer - **Zubereitung**: 1. Spätzleteig aus Mehl, Eiern, Milch und Gewürzen kneten. 2. Kleine Teigstücke in kochendes Wasser geben, bis sie schwimmen. 3. In der Butter anbraten, mit Käse bestreuen und ser …

## Vergleich: gleiche Architektur, vier verschiedene Trajektorien (Dim 2)

Alle vier Läufe gehen durch **denselben** Agenten — der Weg unterscheidet sich
trotzdem sichtbar: (a) nimmt den geraden Weg (eine Recherche, Antwort), (b) fährt
die mehrstufige Planungs-Schleife mit kcal-Checks und Revision, (c) erkennt die
gescheiterte Suche und fällt transparent auf eigenes Wissen zurück, (d) ruft gar
keine Websuche blind auf, sondern thematisiert den Wunsch-Profil-Konflikt und
hält die harte Vorgabe ein. Tool-Wahl und Schrittzahl hängen an der Situation,
nicht an einem festen Ablauf — messbar auch in der Offline-Eval
([eval_report.md](eval_report.md)).
