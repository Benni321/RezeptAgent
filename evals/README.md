# Evaluation des RezeptAgenten (VL09: Agenten evaluieren)

Offline-Evaluation mit festem Testset: Wir belegen mit Zahlen, wie gut der Agent
Nutzer-Constraints einhält — und zeigen ehrlich, wo er scheitert.

## Bausteine

| Datei | Zweck |
|-------|-------|
| `testset.json` | 15 Fälle: harte Constraints (kcal, Personen, vegan/glutenfrei aus dem Profil), Planungsfälle (Wochenplan, Abwechslung), Fehler-/Randfälle (leere Suche, Wunsch↔Profil-Konflikt) und 3 **bewusst schwere Fälle**, an denen der Agent voraussichtlich scheitert (Material für die Reflexion). Erwartet werden **Eigenschaften** der Antwort/Trajektorie, nie exakter Text. |
| `verifier.py` | Programmatische Checks, **kein LLM**. Zwei Ebenen (VL09: Trajektorien-Evaluation statt nur Final-Answer): Antwort-Ebene (kcal ≤ Limit? verbotene Zutaten? Mengen-Stichprobe?) und Trajektorien-Ebene (wurde `naehrwerte_schaetzen` bei kcal-Vorgabe *wirklich* aufgerufen? `portionen_skalieren` statt Kopfrechnen? Schrittzahl plausibel? Revision nach Limit-Verstoß sichtbar?). Jeder Check ist **ternär**: bestanden / neutral (nicht entscheidbar) / verletzt. |
| `run_eval.py` | Führt das Testset gegen den **echten** Agenten aus (braucht `GROQ_API_KEY` + `TAVILY_API_KEY`, bewusst **nicht** Teil von pytest/CI). Schreibt `docs/evidence/eval_report.md` + Roh-Traces nach `docs/evidence/eval_traces/`. |
| `tests/test_eval_verifier.py` | Unit-Tests der Verifier-Logik — grün **ohne** API-Keys. |

## Nutzung

```bash
python evals/run_eval.py                # alle Fälle (Pause 20 s zwischen Fällen)
python evals/run_eval.py --nur id1,id2  # Teilmenge / Resume nach 429-Abbruch
```

Der Report wird aus allen vorhandenen Trace-JSONs neu gebaut — ein wegen des
Groq-Tages-Limits (TPD) abgebrochener Lauf lässt sich mit `--nur` fortsetzen,
ohne fertige Fälle erneut auszuführen.

## Warum ternär statt bestanden/durchgefallen?

Wie in VL09: Vieles ist aus Antwort/Trace **nicht entscheidbar** — nennt die
Antwort keine kcal-Zahl, können wir das Limit weder bestätigen noch widerlegen.
Das als „bestanden“ zu werten, wäre eine Einladung zum Reward-Hacking (siehe
unten); als „verletzt“ wäre es unfair. `neutral` hält die Unsicherheit ehrlich
fest und fließt nicht in die Bestanden-Quote ein.

## Ehrliche Grenzen der Verifier (wichtig!)

Unsere Checks sind **Heuristiken auf Strings und Traces**, keine semantische
Prüfung:

- **Zutaten-Stringmatch ist lückenhaft.** `verbotene_zutaten` prüft nur die
  Listenzeilen der Antwort gegen eine im Testset genannte Wortliste. „Parmesan“
  wird als nicht-vegan erkannt — *aber nur, wenn er in der Liste steht und im
  Lexikon des Falls vorkommt*. Ein Gericht, dessen Zubereitungstext Parmesan
  erwähnt, ohne ihn in die Zutatenliste zu schreiben, rutscht durch. Ebenso
  Synonyme/Komposita, die der Wortanfang-Match nicht trifft (z. B. „Grana
  Padano“ statt „Parmesan“).
- **False Positives kommen real vor (belegter Fall).** Im Lauf vom 2026-07-14
  hat der Agent im Fall `memory_schlecht_bewertet` genau richtig gehandelt —
  Kürbissuppe gemieden und transparent geschrieben „enthält keine Kürbisse“.
  Der `erwaehnt_nicht`-Check wertet die bloße Erwähnung trotzdem als Verstoß
  (siehe `docs/evidence/eval_traces/memory_schlecht_bewertet.json`). String-Match
  kann Erwähnung nicht von Empfehlung unterscheiden; genau dafür braucht es die
  menschliche Durchsicht der Traces. Wir lassen den Fall bewusst „rot“ stehen,
  statt den Check weichzuspülen — ein Verifier, den man nachträglich an die
  Agent-Ausgaben anpasst, misst nichts mehr.
- **kcal-Check liest nur, was dasteht.** Er extrahiert Zahlen vor „kcal“ aus der
  Antwort. Er kann nicht prüfen, ob die Zahl *stimmt* — sie kommt selbst aus
  einer LLM-Schätzung (`naehrwerte_schaetzen`, siehe README „Ehrliche Grenze“).
  Deshalb prüft die Trajektorien-Ebene zusätzlich, dass das Tool wirklich lief:
  eine plausible Zahl allein beweist keinen Check.
- **→ Reward-Hacking-Gefahr.** Ein Agent (oder ein Entwickler, der gegen diese
  Eval optimiert) könnte lernen, *zu formulieren, was der Verifier nicht sieht*:
  kcal-Angaben weglassen (→ neutral statt verletzt), verbotene Zutaten aus der
  Liste in den Fließtext verschieben, Listenformat vermeiden. Die Eval misst
  die Constraint-Treue also nur **so gut, wie ihre Heuristiken greifen** — sie
  ist ein Regressionssignal, kein Beweis. Gegenmaßnahmen: ternäre Wertung
  (Schweigen zählt nie als Erfolg), Trajektorien-Checks (Tool-Aufrufe lassen
  sich schwerer „wegformulieren“ als Text), und menschliche Stichprobe der
  Roh-Traces in `docs/evidence/eval_traces/`.

## Warum kein LLM-as-a-Judge als Haupt-Verifier?

Naheliegend wäre, ein LLM die Antworten bewerten zu lassen („ist das vegan?“).
Wir tun das bewusst **nicht** (VL09):

- **Self-Enhancement-Bias:** Unser Judge käme aus derselben (Groq-)Modellfamilie
  wie der Agent — Modelle bewerten Ausgaben, die ihren eigenen ähneln,
  systematisch zu gut. Die Eval würde den Agenten mit seinem eigenen Maßstab
  messen.
- **Zirkularität beim Kern-Constraint:** Die kcal-Zahl stammt schon aus einer
  LLM-Schätzung. Ein LLM-Judge, der eine LLM-Schätzung „verifiziert“, stapelt
  Unsicherheit auf Unsicherheit, statt sie zu reduzieren.
- **Reproduzierbarkeit:** Programmatische Checks liefern bei gleichem Input
  exakt dasselbe Urteil; ein Judge nicht — schlecht für Regressionvergleiche.

Zulässig wäre ein LLM-Judge höchstens als **ergänzende Zweitmeinung** mit
menschlicher Stichprobenprüfung (z. B. für weiche Eigenschaften wie
„Abwechslung“, die Heuristiken kaum fassen) — als Haupt-Verifier nicht.
