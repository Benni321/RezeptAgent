# Reflexion: Continual Learning (W13)

*RezeptAgent · Applied AI SS26*

**Continual Learning** heißt für uns nicht Nachtrainieren des LLMs, sondern:
Das System wird mit jeder Nutzung besser, ohne dass jemand Code anfasst. Dieser
Loop ist bei uns **implementiert, nicht nur konzipiert** — und genau deshalb
können wir auch konkret sagen, wo er brüchig ist.

**1. Was heute wirklich passiert (der implementierte Loop).** Der Nutzer
bewertet einen Vorschlag mit Sternen (`POST /bewertung`,
[api/main.py](../app/api/main.py)). Daraus entstehen zwei Lernsignale:
(a) Die Bewertung landet im Profil (`data/praeferenzen.json`) und wird bei jeder
künftigen Anfrage als Kontext injiziert — gut Bewertetes wird bevorzugt, schlecht
Bewertetes gemieden (nachgewiesen im Eval-Fall `memory_schlecht_bewertet`: eine
1-Stern-Kürbissuppe → im Lauf 2026-07-14 schlug der Agent Süßkartoffelsuppe vor
und schrieb „enthält keine Kürbisse"; im aktuellen Lauf 2026-08-03 eine cremige
Tomatensuppe mit dem Hinweis, „dass du Kürbissuppe eher meidest" — der Effekt
ist stabil, die konkrete Alternative wechselt mit Modell und Websuche). (b) Ab **4 Sternen** wird das Rezept zusätzlich als
JSON in die Kochbuch-Wissensbasis (`data/rezepte/`) übernommen, die
`rag_retriever` per BM25 durchsucht ([kochbuch.py](../app/tools/kochbuch.py)) —
der Eval-Fall `favoriten_rag` misst, dass der Agent bei Bezug auf Bewährtes
**zuerst** dort sucht statt im Web. Das ist Continual Learning ohne
Modelltraining: nachvollziehbar (jedes gelernte Rezept ist eine lesbare Datei),
sofort wirksam, rückbaubar (Datei löschen).

**2. Der VL09-Kreislauf: Online-Signale werden Offline-Testfälle.** Die
Vorlesung beschreibt Evaluation als Kreislauf — Beobachtungen aus dem Betrieb
werden zu Regressionstests. Wir haben das in beide Richtungen angefangen: Die
persistierten Run-Traces (`AGENT_TRACE_DIR`) sind dasselbe Format, das der
Eval-Runner schreibt, und die drei „schweren" Testfälle sind aus echten
beobachteten Schwächen destilliert (Tools-im-Kopf-Rechnen, Mehrfach-Constraints).
Der konsequente nächste Schritt wäre, **jeden real fehlgeschlagenen Lauf als
neuen Eval-Fall einzufrieren** — z. B. gehört `schwer_skalierung_kette`
(Agent skalierte Mengen selbst statt `portionen_skalieren` aufzurufen, Check
verletzt: „0x aufgerufen, erwartet >= 1",
[eval_report.md](evidence/eval_report.md)) genau in diese Kategorie: erst
beobachtet, dann als dauerhafter Regressionsfall fixiert.

**3. Ehrliche Risiken — an unseren eigenen Daten sichtbar.**
- **Overfitting auf winzige Signalmengen.** Eine einzige 1-Stern-Bewertung
  löschte im Eval die gesamte Zutat Kürbis aus dem Vorschlagsraum. Bei einem
  Nutzer mit 3 Bewertungen ist jedes Signal ein Vorschlaghammer; es gibt keine
  Gewichtung nach Anzahl oder Alter der Bewertungen.
- **Cold-Start.** Ein frisches Kochbuch wäre leer und `rag_retriever` meldete
  nur `RAG-LEER`; wir mildern das mit gekennzeichneten Seed-Rezepten — die aber
  *unsere* Auswahl widerspiegeln, nicht die des Nutzers (Bias-Anfangswert,
  siehe [W14](reflexion_responsible_ai.md)).
- **Der Schlüssel ist eine Heuristik.** Bewertung und Kochbuch-Eintrag hängen am
  **Rezept-Titel**, der per Listenzeilen-Heuristik aus der Antwort extrahiert
  wird (`rezept_aus_antwort`). Formuliert das Modell den Titel um, lernen wir
  unter zwei Namen oder gar nicht — wir haben bewusst „lieber kein Eintrag als
  ein falscher" gewählt, was Lernsignale kostet.
- **Vergessen ist möglich, aber manuell.** Seit dem GUI-Ausbau kann der Nutzer
  gelernte und selbst angelegte Rezepte wieder löschen (`DELETE /kochbuch`,
  Löschen-Button im Kochbuch) — die Basis wächst also nicht mehr zwangsläufig
  monoton. Was weiterhin fehlt, ist *automatisches* Vergessen: kein Abklingen
  alter Bewertungen, kein „zuletzt gekocht"-Zeitstempel. Kuration ist damit eine
  bewusste Handlung des Nutzers, keine Eigenschaft des Systems
  ([W12](reflexion_drift.md)).

**4. Was wir bewusst nicht tun: Fine-Tuning.** Aus (Anfrage → gute Antwort)-
Paaren ließe sich das Modell feintunen. Für diesen Use-Case ist das
unverhältnismäßig: teuer, datenschutzkritisch, mit Risiko des katastrophalen
Vergessens — und es würde das Beste an unserem Ansatz zerstören: dass jeder
Lernschritt eine inspizierbare Datei ist statt eines Gewichts-Deltas. Der
RAG-/Feedback-Weg liefert hier den größten Nutzen pro Aufwand.

**Gütekontrolle vor Übernahme:** In die Basis kommt nichts ohne menschliche
Entscheidung — aber auf zwei verschiedenen Wegen: **automatisch gelernt** wird
nur kuratiert (≥ 4 Sterne), **manuell angelegte** Rezepte (`POST /kochbuch`)
umgehen diese Schwelle bewusst, weil der Nutzer die Kuratierung dort selbst
vorgenommen hat — die Sternehürde ist eine Qualitätsprüfung für *Agenten*-
Vorschläge, nicht für eigene Eingaben. Beide Wege sind deterministische
API-Pfade; das LLM kann die Basis in keinem Fall selbst beschreiben (VL03).
Der Preis der manuellen Tür, ehrlich: Was der Nutzer einträgt, wird inhaltlich
nicht geprüft — eine unvollständige Zutatenliste landet unverändert im
Retrieval-Korpus. Änderungen am System lassen sich gegen das feste Eval-Set
prüfen, bevor sie „produktiv" gehen. Was fehlt (Production-Schritt): stabile Rezept-IDs
statt Titel, bewertungsgewichtetes Ranking im Retriever und ein periodischer
Eval-Lauf als Gate für Wissensbasis-Änderungen.
