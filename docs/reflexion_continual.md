# Konzept: Continual Learning (W13)

*RezeptAgent · Applied AI SS26*

**Continual Learning** heißt: das System mit neuen Daten laufend verbessern, ohne es
komplett neu zu bauen. Für den Rezept-Agenten ist der naheliegendste und günstigste Hebel
**nicht** das Nachtrainieren des LLMs, sondern das **Wachsen und Verbessern der
Wissensbasis** plus **Nutzer-Feedback**.

**1. Feedback erheben.** In der GUI würden wir pro Rezeptvorschlag ein einfaches Signal
einbauen: 👍/👎 und optional „gekocht / nicht gekocht". Zusätzlich ist implizites Feedback
nutzbar: Hat der Nutzer die Anfrage danach umformuliert (Vorschlag unpassend)? Hat er die
Einkaufsliste genutzt? Diese Signale landen mit der Anfrage in den **strukturierten Logs
(W5)**.

**2. Aus Feedback lernen — über die Wissensbasis (RAG).** Positiv bewertete, real
gekochte Rezepte werden in die lokale **RAG-Wissensbasis (W3/W4)** aufgenommen und
periodisch neu indexiert. So wird der Agent schrittweise besser bei den Gerichten, die
*unsere* Nutzer tatsächlich mögen — ein Lernschritt **ohne Modelltraining**, dafür
nachvollziehbar und sofort wirksam. Schlecht bewertete Quellen/Rezepte kann man abwerten
oder ausschließen.

**3. Personalisierung.** Wiederkehrende Präferenzen (z. B. „immer vegetarisch", „keine
Pilze") ließen sich als Nutzerprofil speichern und automatisch als Filter vorbelegen.

**4. Schwereres Geschütz — Fine-Tuning.** Theoretisch könnte man aus gesammelten
(Anfrage → guter Antwort)-Paaren das Antwortmodell feintunen. Das ist für ein
Studienprojekt unverhältnismäßig: teuer, datenschutzkritisch und mit Risiko des
**katastrophalen Vergessens** (das Modell verlernt Allgemeinkönnen). Für unseren Use-Case
liefert der RAG-/Feedback-Weg den größten Nutzen pro Aufwand.

**Risiken & Gütekontrolle.** Lernen aus Feedback kann **Bias verstärken** (ein
Feedback-Loop, der immer dieselben populären Gerichte hochspült) und Datenqualität
verschlechtern, wenn man unkuratiert alles aufnimmt. Gegenmittel: nur kuratiertes,
plausibilisiertes Feedback in die Wissensbasis übernehmen und Änderungen gegen das feste
Eval-Set aus [W12](reflexion_drift.md) prüfen, bevor sie produktiv gehen.
