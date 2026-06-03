# Reflexion: Responsible AI (W14)

*RezeptAgent · Applied AI SS26*

Auch ein „harmloser" Rezept-Agent hat reale Risiken. Wir ordnen sie ein und nennen
konkrete Gegenmaßnahmen.

**1. Lebensmittel-/Gesundheitssicherheit (größtes Risiko).** Das LLM kann **Rezepte
halluzinieren** oder unsichere Angaben machen: falsche Garzeiten/-temperaturen (Geflügel,
Eier, Fisch → Salmonellen/Lebensmittelvergiftung), unsichere Konservierung oder giftige
Kombinationen (z. B. roh nicht essbare Zutaten). Unser Agent recherchiert zwar im Web
statt frei zu erfinden, aber Quellen können fehlerhaft sein. **Gegenmaßnahmen:** Rezepte
mit **Quellenangabe** ausgeben (Nachprüfbarkeit), ein deutlicher Hinweis, kritische
Garzeiten/Hygiene selbst zu prüfen, und keine medizinischen Aussagen.

**2. Allergene & Ernährungseinschränkungen.** Schlägt der Agent bei „nur vorhandene
Zutaten" oder über einen Filter etwas vor, das ein Allergen enthält (Nüsse, Gluten,
Laktose), kann das gefährlich sein. Aktuell verlässt sich das System auf Filter im Prompt,
ohne harte Garantie. **Gegenmaßnahme:** Allergie-Filter ernst nehmen (explizit prüfen statt
nur erwähnen) und im Zweifel warnen statt stillschweigend annehmen.

**3. Halluzination bei der Bildanalyse (VLM).** Die Zutatenerkennung kann Dinge falsch
oder gar nicht erkennen (VL5). Würde der Agent ungeprüft darauf aufbauen, entstünden
unpassende oder unsichere Vorschläge. **Gegenmaßnahme (umgesetzt):** Die erkannten Zutaten
werden dem Nutzer in der GUI **zur Bestätigung** angezeigt → **Human-in-the-Loop**.

**4. Bias.** Web-Quellen und Modell sind auf bestimmte (eher westliche/deutschsprachige)
Küchen ausgerichtet. Nutzer mit anderen kulinarischen Hintergründen bekommen evtl.
schlechtere Vorschläge. Ein Feedback-Loop ([W13](reflexion_continual.md)) kann das
**verstärken**. **Gegenmaßnahme:** Vielfalt bei der Wissensbasis-Kuratierung beachten,
Feedback-Lernen kontrollieren.

**5. Datenschutz.** Kühlschrank-Fotos sind persönliche Daten und gehen an ein **externes
VLM (Groq)**. Sie könnten ungewollt Personen, Adressen (Lieferscheine) o. Ä. enthalten.
**Gegenmaßnahmen:** transparent machen, dass das Bild an einen externen Dienst geht; Bilder
nicht dauerhaft speichern; für sensible Szenarien wäre ein **lokales VLM** vorzuziehen (VL5).

**6. Tool-/Prompt-Injection (VL3).** Da der Agent fremde Webinhalte verarbeitet, könnten
darin versteckte Anweisungen stehen (indirekte Prompt Injection). Das Risiko ist hier
gering, weil der Agent **keine gefährlichen Tools** hat (nur Suche + reine
Listen-Berechnung, keine Dateisystem-/Mail-Aktionen → kein Exfiltrationsweg, „Lethal
Trifecta" gebrochen). Dieses bewusst **minimale Tool-Set** ist unsere wichtigste
Schutzschicht.
