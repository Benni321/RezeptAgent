# Reflexion: Responsible AI (W14)

*RezeptAgent · Applied AI SS26*

Auch ein „harmloser" Rezept-Agent hat reale Risiken. Wir benennen sie konkret an
unserem System — inklusive der Stellen, an denen unsere Gegenmaßnahmen nur
teilweise genügen.

**1. Allergene & Unverträglichkeiten: harte Constraints auf weicher Grundlage
(größtes Risiko).** Unser Design nimmt Ernährungsvorgaben ernst: vegan/
glutenfrei/laktosefrei sind **harte Profil-Vorgaben**, Prompt-Regel 0 lautet
„NIEMALS verletzen" ([orchestrator.py](../app/agents/orchestrator.py)), und die
Eval-Fälle `vegan_profil`, `glutenfrei_profil` und `konflikt_salami_vegetarisch`
bestehen ([eval_report.md](evidence/eval_report.md)). **Aber:** Die Durchsetzung
basiert auf LLM-Wissen und String-Heuristiken, nicht auf einer verifizierten
Zutaten-Datenbank. Konkretes Schadensszenario: Ein Nutzer mit Zöliakie und
Glutenfrei-Profil bekommt eine asiatische Gemüsepfanne vorgeschlagen — mit
**Sojasauce**, die verstecktes Gluten enthält. Weder die Prompt-Regel (das
Modell muss das *wissen*) noch unser Eval-Verifier (Wortlisten-Match auf
Listenzeilen; „Sojasauce" steht in keiner Verbotsliste des Falls) würde das
zuverlässig fangen. Unsere Antwort darauf — Näherungs-Disclaimer, keine
medizinische Zusage — genügt nur teilweise: Ein Disclaimer schützt den
Anbieter, nicht den Allergiker, der ihm vertraut. *Production-Schritt:*
Zutaten-Abgleich gegen eine gepflegte Allergen-Datenbank als **deterministischer
Check nach der Rezeptwahl** (dasselbe Muster wie unser kcal-Check im
Wochenplan-Workflow: prüfen im Code, nicht im Prompt).

**2. Gesundheitsbezogene Zahlen aus einer LLM-Schätzung.** `naehrwerte_schaetzen`
liefert Näherungen ohne Datenbank. Der Eval zeigt die Fehlbarkeit mit Zahlen
(Lauf 2026-07-15, `qwen3-32b`): Im Fall `schwer_kombi_constraints` blieb trotz
Revision ein Gericht bei **~617 kcal statt der geforderten ≤ 400**; im Fall
`schwer_kcal_tagessumme` wurde ein Tages-Summen-Budget (1200 kcal für drei
Mahlzeiten) als Pro-Portion-Limit fehlinterpretiert und `naehrwerte_schaetzen`
lief gar nicht (0× statt ≥ 3×). Der Re-Run nach dem erzwungenen Modellwechsel
(2026-08-02, `qwen3.6-27b`) verschob das Bild, ohne es zu verbessern: Dieselbe
Kombi-Anfrage lieferte eine Antwort ganz **ohne** kcal-Zahlen (Checks nur noch
„neutral" — das in [evals/README](../evals/README.md) beschriebene
Reward-Hacking-Schlupfloch, real eingetreten), und die Summen-Anfrage wurde gar
nicht erst als Mehr-Mahlzeiten-Plan erkannt. **Nachtrag 2026-08-03:** Nach
Beispielen in der Wochenplan-Erkennung greift die Summen-Anfrage wieder — der
Plan wird erkannt und die Tagessumme (512 kcal) bleibt unter dem Budget von
1200. Das Reward-Hacking-Schlupfloch bei `schwer_kombi_constraints` besteht
dagegen weiter. Die Lehre bleibt: Was *genau* bricht, wandert mit dem Modell;
dass etwas bricht, ist der Normalfall. Für Komfort-Nutzer ist das ein
Schönheitsfehler; für jemanden,
der aus medizinischen Gründen zählt (Diabetes, Adipositas-Therapie), wäre
dieselbe Ausgabe schädlich. Wir kennzeichnen die Werte konsequent als
Schätzungen — aber wir wissen aus dem eigenen Eval, dass Nutzer im Grenzfall
falsche Zahlen mit korrektem Disclaimer bekommen.

**3. Halluzination bei der Bildanalyse (VLM) — nur teilweise mitigiert.** Die
Zutatenerkennung kann falsch liegen. Umgesetzt ist **Transparenz**: Die
erkannten Zutaten stehen sichtbar über der Antwort („Aus dem Foto erkannt: …",
[seiten/rezept_finden.py](../seiten/rezept_finden.py)), sodass eine
Fehlerkennung erkennbar ist und die Anfrage korrigiert wiederholt werden kann;
ein Vision-Fehler degradiert zu „ohne Foto-Zutaten weiterarbeiten" statt falsche
Zutaten still zu übernehmen ([agent_service.py](../app/core/agent_service.py)).
**Selbstkritisch:** Das ist *kein* Human-in-the-Loop im Sinne der Vorlesung — die
Anzeige erfolgt **nach** dem Lauf, nicht als Freigabe davor. Für Rezeptvorschläge
(keine destruktive Aktion, kein Geld, keine Daten nach außen außer dem Foto
selbst) halten wir das für vertretbar; bei einem System, das auf Basis der
erkannten Zutaten *bestellen* würde, wäre es fahrlässig. Der Ausbauschritt steht
in [PROJEKTDOKU § 5](PROJEKTDOKU.md#5-grenzen-des-systems): zweistufiger Flow mit
editierbarer Bestätigung.

**4. Küchen-Bias — auch in unserem eigenen Testset.** Websuche und Modell sind
auf westliche/deutschsprachige Küche ausgerichtet; wer anders kocht, bekommt
schlechtere Treffer. Selbstkritisch: **Unser Eval-Testset reproduziert diesen
Bias** — die 15 Fälle fragen Käsespätzle-, Pizza-, Suppen- und Pasta-Welten ab;
kein einziger Fall prüft, ob der Agent z. B. für westafrikanische oder
südasiatische Anfragen gleichwertig funktioniert. Das Eval-Instrument *könnte*
Bias messen (gleiche Constraints, andere Küche, Quoten vergleichen), tut es
heute nicht. Dazu kommt der Verstärkungs-Loop aus [W13](reflexion_continual.md):
Das Kochbuch lernt aus dem, was vorgeschlagen und gut bewertet wurde — was der
Bias-Ausgangspunkt vorschlägt, wird das Memory bevorzugen. Die Seed-Rezepte
(unsere Auswahl) setzen diesen Anfangswert.

**5. Datenschutz beim Foto-Upload.** Kühlschrank-Fotos gehen an ein **externes
VLM (Groq)** und können Unbeabsichtigtes enthalten (Personen im Hintergrund,
Adressen auf Lieferscheinen). Wir speichern Bilder nicht dauerhaft und
verarbeiten sie nur im Request; seit 2026-07-16 weist die GUI direkt beim
Upload-Feld auf den externen Versand hin
([seiten/rezept_finden.py](../seiten/rezept_finden.py)) — zuvor stand das nur in
der Doku (die damalige Lücke haben wir geschlossen, weil ein Hinweis, den niemand
vor dem Upload sieht, keine Transparenz ist).
Verbleibende Grenze: Der Versand selbst bleibt; für sensible Kontexte wäre ein
lokales VLM der richtige Schritt — im Kostenlos-Stack dieses Projekts war es
keine Option.

**6. Indirect Prompt Injection über Web-Inhalte.** Der Recherche-Sub-Agent
liest fremde Webseiten — das vollständige Threat-Model (Lethal-Trifecta-Analyse,
Untrusted-Delimiter, Excessive-Agency-Deckel, Injection-Test) steht in
[sicherheit.md](sicherheit.md) und wird hier bewusst nicht dupliziert. Kern für
Responsible AI: Die belastbare Schutzschicht ist das **minimale Tool-Set**
(kein Exfiltrations-/Ausführungskanal), nicht das Vertrauen darauf, dass das
Modell injizierte Anweisungen ignoriert — Letzteres bleibt eine Mitigation ohne
Garantie.

**Fazit (selbstkritisch):** Unsere wirksamsten Maßnahmen sind durchweg die
strukturellen (Human-in-the-Loop, deterministische Checks, minimale Rechte) —
überall dort, wo wir stattdessen auf Prompt-Regeln oder Disclaimer setzen
(versteckte Allergene, Nährwert-Genauigkeit, GUI-Transparenz beim Foto), ist der
Schutz nachweislich lückenhaft. Genau diese Stellen stehen deshalb in
[PROJEKTDOKU § Grenzen](PROJEKTDOKU.md#5-grenzen-des-systems) als
Production-Schritte.
