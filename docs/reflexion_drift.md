# Reflexion: Data / Concept Drift (W12)

*RezeptAgent · Applied AI SS26*

**Drift** bedeutet, dass sich die Daten- oder Bedeutungswelt nach dem Aufsetzen des
Systems verändert und die Qualität dadurch unbemerkt sinkt. Für unseren Rezept-Agenten
sind drei Arten relevant.

**1. Concept Drift bei Nutzerwünschen (saisonal & Trends).** Was Nutzer kochen wollen,
schwankt: im Sommer Salate und Grillgerichte, im Winter Eintöpfe; dazu Ernährungstrends
(z. B. „high protein", „meal prep"). Die Bedeutung einer Anfrage wie „etwas Leichtes"
verschiebt sich also über die Zeit. Unser Agent ist hier relativ robust, weil er **live im
Web recherchiert** (Tavily) statt aus eingefrorenem Modellwissen zu antworten — die
Websuche liefert aktuelle Treffer. Anfälliger wäre die geplante **RAG-Wissensbasis**: eine
einmal kuratierte Rezeptsammlung veraltet und deckt neue Trends nicht ab.

**2. Data Drift in den Quellen.** Rezept-Webseiten ändern Layout, Paywalls oder
verschwinden; die Tavily-Ergebnisse verschieben sich dadurch. Auch das **Eingabe-Bild**
driftet: andere Kühlschrank-Fotos, Verpackungen oder Beleuchtung als bei unseren Tests
können die Zutatenerkennung verschlechtern (Data Drift im Vision-Input).

**3. Modell-/Verhaltens-Drift.** Wir nutzen gehostete Groq-Modelle. Wird ein Modell
ausgetauscht oder ein Endpoint deprecatet (wie bei den alten Llama-Vision-Modellen),
ändert sich das Verhalten schlagartig — ohne dass wir Code anfassen.

**Woran wir Drift merken würden.** Ohne Gegenmaßnahmen schleichend, aber Indikatoren wären:
- steigende Rate an Anfragen ohne brauchbares Rezept bzw. häufiges Umformulieren durch Nutzer,
- mehr „nichts erkannt"-Fälle oder offensichtliche Fehlerkennungen bei der Bildanalyse,
- negative Nutzer-Rückmeldungen (sobald wir Feedback erheben, siehe [W13](reflexion_continual.md)),
- gehäufte leere/fehlerhafte Tool-Ergebnisse in den **strukturierten Logs (W5)**.

**Wie man gegensteuern würde.** Strukturiertes Logging der Tool-Ausgaben als Frühwarnung;
ein kleines, regelmäßig laufendes Eval-Set fester Beispiel-Anfragen (Regression der
Antwortqualität); Versionspinning der Modelle und bewusste, getestete Updates; und —
sobald RAG existiert — eine Aktualisierungsstrategie für die Wissensbasis (saisonale
Nachpflege).
