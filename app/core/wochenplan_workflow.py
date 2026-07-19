"""
Wochenplan-Workflow (code-orchestriert)
=======================================
Plant mehrere Gerichte mit garantierter plan->pruefe->revidiere-Schleife.

Warum ein Workflow statt eines voll-agentischen Prompts (bewusste Architektur-
entscheidung, siehe docs/PROJEKTDOKU.md "Wochenplan-Workflow"):
Der Wochenplan wurde zuerst rein agentisch gebaut (der Orchestrator koordiniert
alle Schritte per Prompt). In der Praxis befolgte KEIN getestetes Modell die
Mehrschritt-Reihenfolge zuverlaessig: Modelle uebersprangen den Naehrwert-Check
oder recherchierten obsessiv, ohne zum Abschluss zu kommen. Deshalb steuert hier
der CODE die Schritt-Reihenfolge deterministisch (pro Gericht: 1 Recherche ->
Naehrwert-Check -> ggf. 1 Revision -> Abschluss), waehrend das LLM die INHALTLICHEN
Entscheidungen trifft (welches Rezept aus den Treffern, passt der kcal-Constraint,
finale Formulierung). Das ist das Muster "Workflow fuer die Struktur, Agent fuer
den Inhalt" -- zuverlaessig UND weiterhin modellgestuetzt. Der Einzelrezept-Modus
bleibt voll agentisch (Orchestrator).

Die plan->pruefe->revidiere-Schleife ist damit GARANTIERT sichtbar im Trace
(Bewertungs-Dimension 2), unabhaengig von der Prompt-Befolgung des Modells.
"""

import json
import os
import re
import time

from langchain_core.messages import HumanMessage
from langchain_groq import ChatGroq

from app.agents.recherche_agent import recherche_rezepte
from app.core.logging_config import get_logger, log_span
from app.core.text_utils import entferne_reasoning
from app.tools.naehrwerte import schaetze_kcal_pro_portion
from app.tools.wochenplan import wochenplan_zusammenstellen

logger = get_logger("rezeptagent.workflow")


def _dauer_ms(start: float) -> int:
    return int((time.monotonic() - start) * 1000)


def _recherche_mit_trace(anfrage: str, trace: list[dict], args_label: dict) -> str:
    """Fuehrt eine Recherche aus und haelt sie einheitlich als Trace-Schritte
    (Aktion + Beobachtung mit dauer_ms/status) und als Span fest (W5/VL09)."""
    t0 = time.monotonic()
    text = recherche_rezepte.invoke({"anfrage": anfrage})
    dauer = _dauer_ms(t0)
    status = "fehler" if (text or "").startswith(("WEBSUCHE", "RECHERCHE-FEHLER")) else "ok"
    trace.append({"art": "aktion", "ziel": "Sub-Agent", "name": "recherche_rezepte",
                  "args": args_label})
    trace.append({"art": "beobachtung", "quelle": "Sub-Agent", "name": "recherche_rezepte",
                  "inhalt": text, "dauer_ms": dauer, "status": status})
    log_span(logger, "subagent", "recherche_rezepte", dauer_ms=dauer, status=status)
    return text


def _kcal_mit_span(titel: str, zutaten: list[str], portionen: int) -> tuple[float | None, int]:
    """kcal-Schaetzung mit Zeitmessung; gibt (kcal, dauer_ms) zurueck."""
    t0 = time.monotonic()
    kcal = schaetze_kcal_pro_portion(titel, zutaten, portionen)
    dauer = _dauer_ms(t0)
    log_span(logger, "tool", "naehrwerte_schaetzen", dauer_ms=dauer,
             status="ok" if kcal is not None else "fehler")
    return kcal, dauer

# Hinweise, dass es um MEHRERE Gerichte geht. Nur dann laeuft ueberhaupt der
# (LLM-gestuetzte) Parameter-Check -- normale Einzelrezept-Anfragen bleiben
# unberuehrt und kosten keinen Extra-Call.
_WOCHENPLAN_HINWEISE = re.compile(
    r"\b(wochenplan|woche|wochen|\d+\s*(gerichte|abendessen|essen|tage|mahlzeiten|mittagessen)"
    r"|mehrere\s+gerichte|meal\s*prep)\b",
    re.IGNORECASE,
)


def _modell(temperature: float = 0) -> ChatGroq:
    return ChatGroq(
        model=os.getenv("GROQ_MODEL", "qwen/qwen3.6-27b"),
        temperature=temperature,
        max_retries=5,
        reasoning_effort="none",  # Reasoning-Tokens sparen (TPM-Budget, s. orchestrator.py)
    )


def _json_aus_text(text: str) -> dict | None:
    """Zieht das erste JSON-Objekt aus einer Modellantwort (robust gegen Beiwerk).

    Entfernt zuerst <think>-Bloecke (qwen3): deren geschweifte Klammern wuerden den
    Parser sonst auf das falsche Objekt fuehren.
    """
    treffer = re.search(r"\{.*\}", entferne_reasoning(text or ""), re.DOTALL)
    if not treffer:
        return None
    try:
        wert = json.loads(treffer.group(0))
        return wert if isinstance(wert, dict) else None
    except json.JSONDecodeError:
        return None


def erkenne_wochenplan(nachricht: str, model: ChatGroq | None = None) -> dict | None:
    """Erkennt eine Wochenplan-Anfrage und extrahiert die Parameter -- sonst None.

    Rueckgabe bei Wochenplan: {"anzahl_gerichte": int, "kcal_limit": float|None,
    "portionen": int|None}. Bei einer normalen Einzelrezept-Anfrage: None.
    Ohne Wochenplan-Hinweis im Text wird gar kein LLM-Call gemacht (Effizienz).
    """
    if not _WOCHENPLAN_HINWEISE.search(nachricht or ""):
        return None
    model = model or _modell()
    prompt = (
        "Analysiere die folgende Kochanfrage. Geht es um MEHRERE Gerichte / einen "
        "Wochen- oder Mehr-Tages-Plan? Antworte AUSSCHLIESSLICH mit JSON:\n"
        '{"wochenplan": true/false, "anzahl_gerichte": <ganze Zahl>, '
        '"kcal_limit": <Zahl pro Portion oder null>, "portionen": <Zahl oder null>}\n'
        "Setze wochenplan=false, wenn nur EIN Gericht gewuenscht ist.\n\n"
        f"Anfrage: {nachricht}"
    )
    daten = _json_aus_text(model.invoke([HumanMessage(content=prompt)]).content)
    if not daten or not daten.get("wochenplan"):
        return None
    try:
        anzahl = int(daten.get("anzahl_gerichte") or 0)
    except (TypeError, ValueError):
        anzahl = 0
    if anzahl < 2:
        return None
    anzahl = min(anzahl, 7)  # Deckel: kein Runaway (Kosten/Zeit)

    def _zahl(x):
        try:
            return float(x)
        except (TypeError, ValueError):
            return None

    return {
        "anzahl_gerichte": anzahl,
        "kcal_limit": _zahl(daten.get("kcal_limit")),
        "portionen": int(_zahl(daten.get("portionen")) or 2),
    }


def _extrahiere_rezept(recherche_text: str, vermeide_titel: list[str], model: ChatGroq) -> dict | None:
    """Extrahiert EIN konkretes Rezept (Titel + Zutaten) aus der Recherche-Antwort.

    Waehlt bewusst ein Gericht, das sich von den bereits geplanten unterscheidet
    (Abwechslung). Gibt None zurueck, wenn nichts Brauchbares extrahierbar ist.
    """
    if not recherche_text or recherche_text.startswith(("WEBSUCHE", "RECHERCHE-FEHLER")):
        return None
    hinweis = ""
    if vermeide_titel:
        hinweis = (
            "\nWaehle ein Gericht, das sich klar von diesen bereits geplanten "
            f"unterscheidet (andere Hauptzutat): {', '.join(vermeide_titel)}."
        )
    prompt = (
        "Waehle aus den folgenden Rezept-Suchergebnissen EIN konkretes Rezept und gib "
        "es als JSON zurueck:\n"
        '{"titel": "<Name>", "zutaten": ["<Zutat 1>", "<Zutat 2>", ...]}\n'
        "Nur echte, im Text genannte Rezepte; erfinde nichts. Antworte NUR mit dem JSON."
        f"{hinweis}\n\nSuchergebnisse:\n{recherche_text}"
    )
    daten = _json_aus_text(model.invoke([HumanMessage(content=prompt)]).content)
    if not daten or not daten.get("titel") or not isinstance(daten.get("zutaten"), list):
        return None
    return {"titel": str(daten["titel"]).strip(), "zutaten": [str(z).strip() for z in daten["zutaten"] if str(z).strip()]}


def _formuliere_antwort(gerichte: list[dict], plan_text: str, kcal_notizen: list[str], model: ChatGroq) -> str:
    """Formuliert die finale, nutzerfreundliche Wochenplan-Antwort."""
    gerichte_text = "\n".join(
        f"- {g['titel']}: {', '.join(g['zutaten'])}" for g in gerichte
    )
    notizen = "\n".join(kcal_notizen)
    prompt = (
        "Schreibe dem Nutzer seinen Wochenplan auf Deutsch. Beginne DIREKT mit dem Plan "
        "(KEINE Meta-Ueberschrift wie 'Klare Antwort' o. ae.). Nenne die Gerichte mit "
        "kurzen Zutaten, weise auf die geschaetzten Kalorien hin und haenge die "
        "Einkaufsliste an. Erfinde keine zusaetzlichen Gerichte.\n\n"
        f"Geplante Gerichte:\n{gerichte_text}\n\n"
        f"Kalorien-Hinweise (Naeherung ohne verifizierte DB):\n{notizen}\n\n"
        f"Plan + Einkaufsliste:\n{plan_text}"
    )
    return entferne_reasoning(model.invoke([HumanMessage(content=prompt)]).content)


def plane_woche(
    nachricht: str,
    params: dict,
    harte_vorgaben: list[str],
    vorhandene_zutaten: list[str] | None = None,
) -> dict:
    """Fuehrt den code-orchestrierten Wochenplan aus und gibt Antwort + TAO-Trace zurueck.

    Garantierte Schritt-Reihenfolge je Gericht: Recherche -> Rezept waehlen ->
    (bei kcal-Limit) Naehrwert-Check -> bei Verletzung EINE Revision. Zum Abschluss
    wochenplan_zusammenstellen. Jeder Schritt wird als Trace-Eintrag festgehalten.
    """
    model = _modell()
    anzahl = params["anzahl_gerichte"]
    kcal_limit = params.get("kcal_limit")
    portionen = params.get("portionen") or 2
    vorhandene_zutaten = vorhandene_zutaten or []

    zusatz = (" ".join(harte_vorgaben)).strip()
    trace: list[dict] = []
    gerichte: list[dict] = []
    kcal_notizen: list[str] = []

    for i in range(anzahl):
        such_anfrage = f"{nachricht} {zusatz}".strip()
        if gerichte:
            such_anfrage += f" (anderes Gericht als: {', '.join(g['titel'] for g in gerichte)})"

        recherche_text = _recherche_mit_trace(such_anfrage, trace, {"anfrage": such_anfrage})

        t_llm = time.monotonic()
        rezept = _extrahiere_rezept(recherche_text, [g["titel"] for g in gerichte], model)
        log_span(logger, "llm", "rezept_extraktion", dauer_ms=_dauer_ms(t_llm),
                 status="ok" if rezept else "fehler")
        if rezept is None:
            kcal_notizen.append(f"Gericht {i + 1}: kein passendes Rezept aus der Recherche gefunden.")
            continue

        # plan->PRUEFE: kcal-Constraint (falls vorgegeben) deterministisch checken.
        if kcal_limit:
            kcal, dauer = _kcal_mit_span(rezept["titel"], rezept["zutaten"], portionen)
            trace.append({"art": "aktion", "ziel": "Tool", "name": "naehrwerte_schaetzen",
                          "args": {"rezept_titel": rezept["titel"], "portionen": portionen}})
            if kcal is None:
                kcal_notizen.append(f"{rezept['titel']}: Kalorien nicht schaetzbar (Vorgabe nicht gepruefbar).")
                trace.append({"art": "beobachtung", "quelle": "Tool", "name": "naehrwerte_schaetzen",
                              "inhalt": "NAEHRWERT-FEHLER: nicht schaetzbar",
                              "dauer_ms": dauer, "status": "fehler"})
            elif kcal > kcal_limit:
                # REVIDIERE: genau EIN Ersatzversuch mit "leichter"-Hinweis.
                trace.append({"art": "beobachtung", "quelle": "Tool", "name": "naehrwerte_schaetzen",
                              "inhalt": f"~{round(kcal)} kcal/Portion -> UEBER Limit {round(kcal_limit)}, revidiere",
                              "dauer_ms": dauer, "status": "ok"})
                ersatz_text = _recherche_mit_trace(
                    f"{such_anfrage} besonders kalorienarm unter {round(kcal_limit)} kcal",
                    trace, {"anfrage": "Revision: kalorienarmer Ersatz"},
                )
                t_llm = time.monotonic()
                ersatz = _extrahiere_rezept(ersatz_text, [g["titel"] for g in gerichte], model)
                log_span(logger, "llm", "rezept_extraktion", dauer_ms=_dauer_ms(t_llm),
                         status="ok" if ersatz else "fehler")
                if ersatz:
                    ersatz_kcal, ersatz_dauer = _kcal_mit_span(ersatz["titel"], ersatz["zutaten"], portionen)
                    trace.append({"art": "aktion", "ziel": "Tool", "name": "naehrwerte_schaetzen",
                                  "args": {"rezept_titel": ersatz["titel"], "portionen": portionen}})
                    trace.append({"art": "beobachtung", "quelle": "Tool", "name": "naehrwerte_schaetzen",
                                  "inhalt": (f"Ersatz ~{round(ersatz_kcal)} kcal/Portion" if ersatz_kcal is not None
                                             else "Ersatz nicht schaetzbar"),
                                  "dauer_ms": ersatz_dauer,
                                  "status": "ok" if ersatz_kcal is not None else "fehler"})
                    # Nimm den Ersatz, wenn er schaetzbar und nicht schlechter ist.
                    if ersatz_kcal is not None and ersatz_kcal <= kcal:
                        rezept, kcal = ersatz, ersatz_kcal
                status = "eingehalten" if (kcal is not None and kcal <= kcal_limit) else "trotz Revision ueber Limit"
                kcal_notizen.append(f"{rezept['titel']}: ~{round(kcal)} kcal/Portion ({status}).")
            else:
                trace.append({"art": "beobachtung", "quelle": "Tool", "name": "naehrwerte_schaetzen",
                              "inhalt": f"~{round(kcal)} kcal/Portion -> unter Limit {round(kcal_limit)}",
                              "dauer_ms": dauer, "status": "ok"})
                kcal_notizen.append(f"{rezept['titel']}: ~{round(kcal)} kcal/Portion (unter Limit).")

        gerichte.append(rezept)

    # Abschluss: deterministische Aggregation zu einer Einkaufsliste.
    t0 = time.monotonic()
    plan_text = wochenplan_zusammenstellen.invoke(
        {"gerichte": gerichte, "vorhandene_zutaten": vorhandene_zutaten}
    )
    dauer = _dauer_ms(t0)
    trace.append({"art": "aktion", "ziel": "Tool", "name": "wochenplan_zusammenstellen",
                  "args": {"anzahl_gerichte": len(gerichte)}})
    trace.append({"art": "beobachtung", "quelle": "Tool", "name": "wochenplan_zusammenstellen",
                  "inhalt": plan_text, "dauer_ms": dauer, "status": "ok"})
    log_span(logger, "tool", "wochenplan_zusammenstellen", dauer_ms=dauer)

    if not gerichte:
        return {"antwort": "Ich konnte leider keine passenden Rezepte fuer den Wochenplan finden.",
                "trace": trace, "erkannte_zutaten": None}

    t_llm = time.monotonic()
    antwort = _formuliere_antwort(gerichte, plan_text, kcal_notizen, model)
    log_span(logger, "antwort", "antwort_formulierung", dauer_ms=_dauer_ms(t_llm))
    return {"antwort": antwort, "trace": trace, "erkannte_zutaten": None}
