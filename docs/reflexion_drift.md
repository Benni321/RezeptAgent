# Reflexion: Data / Concept Drift (W12)

*RezeptAgent · Applied AI SS26*

**Drift** heißt: Die Daten- oder Bedeutungswelt verändert sich nach dem Aufsetzen
des Systems, und die Qualität sinkt unbemerkt. Für unser System sind drei Arten
konkret — jeweils mit der Frage, **woran wir es messbar merken würden**, denn ein
Drift, den keine Metrik anzeigt, ist in Production der gefährlichste.

**1. Saisonale Rezept-Drift: unsere Stärke ist zugleich unsere Instabilität.**
Der Agent recherchiert live über Tavily statt aus eingefrorenem Modellwissen —
gegen veraltete Rezepttrends ist er damit robust. Der Preis: **Das
Systemverhalten hängt an einer Datenquelle, die sich ohne Code-Änderung
verschiebt.** Der Referenz-Trace (b) vom 2026-07-15 fand für „max. 500 kcal,
vegetarisch" ein Kürbis-Spinat-Curry mit ~325 kcal
([referenz_traces.md](evidence/referenz_traces.md)); dieselbe Anfrage im Dezember
trifft auf Saisonrezepte-Seiten mit Aufläufen und Eintöpfen — tendenziell
kalorienreicher, also mehr Revisionen und mehr „trotz Revision über Limit"-Fälle.
**Woran wir es merken:** Der Eval-Report ist reproduzierbar erzeugbar
(`python evals/run_eval.py`, aktuell **35/41 wertbare Checks = 85 %**, Stand
2026-08-03, [eval_report.md](evidence/eval_report.md)). Kippen bei einem Wiederholungslauf
mit identischem Testset **und unverändertem Modell** die `kcal_limit`- und
`revision_geprueft`-Checks, hat sich die Quellenwelt verschoben, nicht unser
Code (dass auch ein Modellwechsel Checks kippt, zeigt der Re-Run in Punkt 2 —
die beiden Ursachen muss man beim Lesen der Quote auseinanderhalten). Genau dafür müsste die Eval
periodisch laufen (heute: manuell) — das ist die ehrliche Lücke: Wir *können*
Drift messen, aber nichts *stößt* die Messung an.

**2. Modell-Drift: bei uns keine Theorie, sondern dreimal passiert.** Erst
erzeugte `llama-3.3-70b` auf Groq ein defektes Tool-Call-Format
(`tool_use_failed` — jede Recherche scheiterte), dann wurden die alten
Llama-Vision-Modelle deprecatet — und im Juli 2026 zog Groq auch das danach
genutzte `qwen/qwen3-32b` samt `llama-4-scout` (Vision) zurück. Der dritte
erzwungene Wechsel (auf `qwen/qwen3.6-27b` als EIN multimodales Modell für Text
und Vision, das damit zwei zuvor getrennte Modell-Slots ersetzte) traf exakt das
hier vorhergesagte Muster: Eval-Report und Evidence waren auf das zurückgezogene
Modell geeicht und mussten gegen das unveränderte Testset neu gefahren werden.
Der Re-Run bezifferte den Effekt: **87 % → 80 %**, und das *Fehlerbild* verschob
sich — der alte Regel-6-Verstoß (Skalierung „im Kopf") verschwand, dafür ließ
das neue Modell in `leere_suche_fallback` die Websuche ganz aus, die
LLM-gestützte Wochenplan-Erkennung verfehlte 2 von 3 Plan-Eingaben, und der
Recherche-Sub-Agent lief mehrfach in seinen Schritt-Deckel (`recursion_limit=6`
→ „Sorry, need more steps"). Ein Modellwechsel verschiebt also nicht nur
Qualität, sondern *wo* es bricht. **Nachtrag 2026-08-03 — Drift gemessen,
mitigiert, neu gemessen:** Gezielte Anpassungen an den Nachfolger
(`recursion_limit` 6→10, Beispiele in der Wochenplan-Erkennung,
Recherche-Pflicht auch bei Fantasie-Zutaten) hoben die Quote von 80 % auf
**85 %** zurück; die Wochenplan-Erkennung greift wieder. Restgrenze, ehrlich:
Bei überspezifizierten Mehrfach-Constraint-Anfragen (kcal + Ernährung +
Abwechslung in einem Suchauftrag) erschöpft der Sub-Agent weiterhin seine
Schritte; eine dagegen ergänzte Such-Deckelung im Sub-Agent-Prompt ist
eingebaut, ihre Wirkung konnte am selben Tag wegen des Tages-Token-Limits
nicht mehr gemessen werden (Re-Run der drei betroffenen Fälle ausstehend).
Die unbequeme Annahme dahinter: Unser
System ist über `GROQ_MODEL` scheinbar modellagnostisch, tatsächlich aber auf
**ein Modellverhalten kalibriert** — der `<think>`-Filter in
[text_utils.py](../app/core/text_utils.py) existiert nur wegen qwen3, die
Schrittzahl-Korridore im Verifier (`schrittzahl`, Korridor 1–8 bzw. 7–40) sind
an qwen3-Trajektorien geeicht, und `gpt-oss-120b` recherchierte im Test 7× statt
2×. Ein stiller Modelltausch beim Anbieter würde also nicht nur Antworten ändern,
sondern unsere Messinstrumente teilweise entwerten. **Woran wir es merken:**
Häufung von `status="fehler"`-Spans in den JSON-Logs (W5), gerissene
`schrittzahl`-Checks im Eval, `tool_aufgerufen`-Verletzungen (Tool-Calling-Format
kaputt). *Production-Schritt:* Modellversion pinnen, Updates bewusst gegen das
Eval-Set fahren — im Groq-Free-Tier ist Pinning aber nur begrenzt möglich; diese
Abhängigkeit haben wir uns mit dem Kostenlos-Stack eingekauft.

**2b. Der Modell-Split: eine Abwägung, die Drift-Risiko *erhöht*.** Nach dem
dritten Wechsel haben wir Recherche-Sub-Agent und Nährwert-Schätzung auf ein
kleines Zweitmodell gelegt (`GROQ_MODEL_KLEIN`, `llama-3.1-8b-instant`), weil
Groqs Rate-Limits pro Modell gelten und der Wochenplan sonst regelmäßig in
429-Backoffs lief. Ehrlich betrachtet ist das ein **Zielkonflikt gegen genau
diese Reflexion**: Wir haben Verfügbarkeit gekauft und dafür die
Deprecation-Fläche verdoppelt — statt einer Modellabhängigkeit haben wir jetzt
zwei, jede mit eigenem Verhalten, auf das Prompts und Verifier-Korridore
kalibriert sind. Die Entscheidung fiel bewusst so, weil ein Abbruch mitten im
Wochenplan den Nutzer sofort trifft, während eine Deprecation angekündigt wird
und einmalig Arbeit kostet. **Woran wir es merken:** Der Eval-Report nennt bisher
nur `GROQ_MODEL` — würde das kleine Modell zurückgezogen, stünde im Report
weiterhin das große, und die Ursache wäre schwer zu sehen. Deshalb protokolliert
der Runner seit 2026-08-05 **beide** Modelle im Report-Kopf.

**3. Präferenz-Drift: das Memory lernt, aber es vergisst nie.** Bewertungen
liegen als `Rezept → Sterne` ohne Zeitstempel in `data/praeferenzen.json`; das
Kochbuch (`data/rezepte/`) wächst nur. Ändert sich der Geschmack (der Nutzer mag
2027 wieder Kürbis), steuert das Signal von 2026 weiter dagegen — der Eval-Fall
`memory_schlecht_bewertet` zeigt, wie stark eine einzige 1-Stern-Bewertung wirkt:
Der Agent mied daraufhin Kürbis vollständig. Concept Drift findet hier **im
Nutzer** statt, während unser gespeichertes Signal statisch bleibt. **Woran wir
es merken:** heute gar nicht automatisch — es gibt keine Metrik „Nutzer folgt den
Kochbuch-Vorschlägen seltener". Messbar wäre es über die Bewertungen selbst
(sinkende Sterne für RAG-basierte Vorschläge). *Production-Schritt:* Zeitstempel
+ Abklingfaktor auf Bewertungen, Kochbuch-Einträge mit „zuletzt gekocht".

**4. Data Drift im Vision-Input.** Unser realer Nachweis
([vision_nachweis.md](evidence/vision_nachweis.md)) basiert auf einem
aufgeräumten Kühlschrank-Foto bei guter Beleuchtung. Andere Kameras, volle
Fächer, Verpackungen statt roher Zutaten verschieben die Erkennungsqualität.
Abgefedert wird das nicht durch Modellvertrauen, sondern durch den
**Human-in-the-Loop**: Die erkannten Zutaten werden vor der Verwendung zur
Bestätigung angezeigt — Drift verschlechtert dann den Komfort, nicht die
Korrektheit. **Woran wir es merken:** `vision_fehler`-Ereignisse und sinkende
`anzahl` in `zutaten_aus_bild_erkannt`-Logs
([agent_service.py](../app/core/agent_service.py)).

**Fazit (selbstkritisch):** Unsere Drift-Erkennung existiert als Werkzeug
(reproduzierbare Eval, strukturierte Logs), aber nicht als Prozess — nichts
läuft periodisch, niemand schaut automatisch auf die Quoten. Für ein
Semesterprojekt ist das eine bewusste Grenze; in Production wäre ein
wöchentlicher Eval-Lauf mit Alarm auf Quoten-Abfall (z. B. < 80 %) die erste
Maßnahme, noch vor jeder Modell-Verbesserung.
