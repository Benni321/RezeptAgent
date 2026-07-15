"""
Verifier fuer die Offline-Evaluation (VL09: Agenten evaluieren)
===============================================================
Prueft Agent-Antworten und TAO-Traces PROGRAMMATISCH gegen die erwarteten
Eigenschaften aus evals/testset.json — bewusst OHNE LLM (Begruendung in
evals/README.md: LLM-as-a-Judge hat Self-Enhancement-Bias, wenn dieselbe
Modellfamilie ihre eigenen Ausgaben bewertet).

Jeder Check liefert ein TERNAERES Ergebnis wie in der Vorlesung:
  - BESTANDEN: die Eigenschaft ist nachweislich erfuellt.
  - NEUTRAL:   nicht entscheidbar / nicht anwendbar (z. B. keine kcal-Angabe in
               der Antwort gefunden). Bewusst KEIN "bestanden": Nichtwissen
               darf nicht als Erfolg zaehlen (Reward-Hacking-Schutz).
  - VERLETZT:  die Eigenschaft ist nachweislich verletzt.

Zwei Ebenen (VL09: Trajektorien-Evaluation statt nur Final-Answer):
  - Antwort-Ebene:      kcal <= Limit? Verbotene Zutaten in der Liste? Mengen
                        korrekt skaliert (Stichprobe)? Pflicht-/Verbots-Begriffe?
  - Trajektorien-Ebene: Wurde das richtige Tool (nicht) aufgerufen? Schrittzahl
                        plausibel? Ist die Revision nach kcal-Verstoss sichtbar?

Bewusst nur Standardbibliothek (kein App-/LangChain-Import): der Verifier ist
damit trivial ohne API-Keys unit-testbar (tests/test_eval_verifier.py) und kann
den Agenten nicht "aus Versehen" mitstarten. Alle Checks sind Heuristiken auf
Text/Trace — ihre Grenzen (String-Match, Reward-Hacking-Gefahr) sind in
evals/README.md dokumentiert.
"""

import re
from dataclasses import dataclass

BESTANDEN = "bestanden"
NEUTRAL = "neutral"
VERLETZT = "verletzt"

# Symbole fuer den Report (eine Stelle, damit Runner und Doku konsistent sind).
SYMBOL = {BESTANDEN: "✓", NEUTRAL: "○", VERLETZT: "✗"}


@dataclass
class CheckErgebnis:
    """Ergebnis eines einzelnen Checks: Typ, ternaerer Status, Begruendung."""
    typ: str
    status: str
    detail: str


# ---------------------------------------------------------------------------
# Text-Normalisierung
# ---------------------------------------------------------------------------

_UMLAUTE = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})


def _norm(text: str) -> str:
    """Kleinbuchstaben + Umlaute gefaltet (ä->ae), damit 'Kürbis' == 'Kuerbis'."""
    return (text or "").lower().translate(_UMLAUTE)


def _norm_zahl(text: str) -> str:
    """Zusaetzlich Dezimal-Komma -> Punkt, damit '1,5' == '1.5'."""
    return _norm(text).replace(",", ".")


# ---------------------------------------------------------------------------
# Antwort-Ebene
# ---------------------------------------------------------------------------

# kcal-Angaben wie "~450 kcal", "450kcal", "ca. 450 Kalorien".
_KCAL_MUSTER = re.compile(r"(\d{2,4}(?:[.,]\d+)?)\s*(?:kcal|kalorien)", re.IGNORECASE)


def _finde_kcal(antwort: str) -> list[float]:
    """Extrahiert alle kcal-Zahlen aus der Antwort (Heuristik: Zahl vor 'kcal')."""
    return [float(z.replace(",", ".")) for z in _KCAL_MUSTER.findall(antwort or "")]


def check_antwort_nicht_leer(antwort: str, trace: list[dict], params: dict) -> CheckErgebnis:
    """Antwort ist substanziell (> 30 Zeichen) — faengt leere/abgebrochene Laeufe."""
    if len((antwort or "").strip()) > 30:
        return CheckErgebnis("antwort_nicht_leer", BESTANDEN, f"{len(antwort.strip())} Zeichen")
    return CheckErgebnis("antwort_nicht_leer", VERLETZT, "Antwort leer oder zu kurz")


def check_kcal_limit(antwort: str, trace: list[dict], params: dict) -> CheckErgebnis:
    """Alle in der Antwort genannten kcal-Werte liegen <= Limit.

    NEUTRAL, wenn die Antwort gar keine kcal-Zahl nennt: Dann koennen wir den
    Constraint nicht pruefen — das ist ehrlicher als 'bestanden' (der Agent
    koennte das Limit ja auch einfach verschweigen, siehe Reward-Hacking).
    """
    limit = float(params["limit"])
    werte = _finde_kcal(antwort)
    if not werte:
        return CheckErgebnis("kcal_limit", NEUTRAL, "keine kcal-Angabe in der Antwort gefunden")
    zu_hoch = [w for w in werte if w > limit]
    if zu_hoch:
        return CheckErgebnis("kcal_limit", VERLETZT,
                             f"{len(zu_hoch)} Angabe(n) ueber Limit {limit:g}: {sorted(set(zu_hoch))}")
    return CheckErgebnis("kcal_limit", BESTANDEN, f"alle {len(werte)} kcal-Angaben <= {limit:g}")


def check_kcal_summe_limit(antwort: str, trace: list[dict], params: dict) -> CheckErgebnis:
    """Summen-Budget (z. B. 'zusammen max 1200 kcal') — bewusst vorsichtige Heuristik.

    Die Antwort kann Einzel- UND Gesamtwerte nennen (Doppelzaehlung beim naiven
    Summieren). Entscheidung daher: einzelner Wert > Limit -> VERLETZT (sicher);
    Summe aller Werte <= Limit -> BESTANDEN (sicher); dazwischen -> NEUTRAL.
    """
    limit = float(params["limit"])
    werte = _finde_kcal(antwort)
    if not werte:
        return CheckErgebnis("kcal_summe_limit", NEUTRAL, "keine kcal-Angabe gefunden")
    if any(w > limit for w in werte):
        return CheckErgebnis("kcal_summe_limit", VERLETZT,
                             f"einzelner Wert ueber dem Gesamtbudget {limit:g}")
    if sum(werte) <= limit:
        return CheckErgebnis("kcal_summe_limit", BESTANDEN,
                             f"Summe {sum(werte):g} <= {limit:g}")
    return CheckErgebnis("kcal_summe_limit", NEUTRAL,
                         f"Summe {sum(werte):g} > {limit:g}, aber evtl. Doppelzaehlung "
                         "(Einzel- + Gesamtwerte) -> nicht sicher entscheidbar")


# Zeilen, die wie Listen-/Zutateneintraege aussehen ("- 200g Reis", "* Tofu", "1. ...").
_LISTEN_ZEILE = re.compile(r"^\s*(?:[-*•]|\d+\.)\s+(.*)$")
# "vegane Butter", "pflanzliche Sahne", "ohne Ei", "statt Sahne" -> kein Verstoss.
_ENTSCHAERFER = ("vegan", "pflanzlich", "ohne ", "kein", "statt ", "ersatz", "alternativ")


def check_verbotene_zutaten(antwort: str, trace: list[dict], params: dict) -> CheckErgebnis:
    """Verbotene Zutaten (z. B. nicht-vegan) duerfen nicht in Listenzeilen stehen.

    Bewusst NUR Listenzeilen (Zutaten/Einkaufsliste), nicht der Fliesstext: Im
    Fliesstext darf der Agent den Begriff nennen (z. B. um den Salami-Konflikt
    anzusprechen). Treffer mit Entschaerfer davor ('vegane Butter', 'ohne Ei')
    zaehlen nicht. Kein Listenteil in der Antwort -> NEUTRAL.
    """
    zeilen = [m.group(1) for z in (antwort or "").splitlines() if (m := _LISTEN_ZEILE.match(z))]
    if not zeilen:
        return CheckErgebnis("verbotene_zutaten", NEUTRAL, "keine Zutaten-/Listenzeilen gefunden")
    funde: list[str] = []
    for zeile in zeilen:
        n = _norm(zeile)
        for zutat in params["zutaten"]:
            # Wortanfang-Match: 'parmesan' trifft auch 'Parmesankaese',
            # aber 'milch' NICHT 'Kokosmilch' (dort ist kein Wortanfang).
            for treffer in re.finditer(r"\b" + re.escape(_norm(zutat)), n):
                davor = n[max(0, treffer.start() - 15):treffer.start()]
                if not any(e in davor for e in _ENTSCHAERFER):
                    funde.append(f"'{zutat}' in: {zeile.strip()[:60]}")
    if funde:
        return CheckErgebnis("verbotene_zutaten", VERLETZT, "; ".join(funde[:4]))
    return CheckErgebnis("verbotene_zutaten", BESTANDEN,
                         f"{len(zeilen)} Listenzeilen geprueft, keine verbotene Zutat")


def check_erwaehnt_alle(antwort: str, trace: list[dict], params: dict) -> CheckErgebnis:
    """Alle Begriffe muessen vorkommen (z. B. korrekt skalierte Mengen als Stichprobe)."""
    fehlend = [b for b in params["begriffe"] if _norm_zahl(b) not in _norm_zahl(antwort)]
    if fehlend:
        return CheckErgebnis("erwaehnt_alle", VERLETZT, f"fehlt: {fehlend}")
    return CheckErgebnis("erwaehnt_alle", BESTANDEN, f"alle {len(params['begriffe'])} Begriffe enthalten")


def check_erwaehnt_eines(antwort: str, trace: list[dict], params: dict) -> CheckErgebnis:
    """Mindestens einer der Begriffe muss vorkommen (z. B. Konflikt wird angesprochen)."""
    treffer = [b for b in params["begriffe"] if _norm(b) in _norm(antwort)]
    if treffer:
        return CheckErgebnis("erwaehnt_eines", BESTANDEN, f"gefunden: {treffer[:3]}")
    return CheckErgebnis("erwaehnt_eines", VERLETZT, f"keiner von {len(params['begriffe'])} Begriffen enthalten")


def check_erwaehnt_nicht(antwort: str, trace: list[dict], params: dict) -> CheckErgebnis:
    """Keiner der Begriffe darf vorkommen (z. B. schlecht bewertetes Rezept)."""
    treffer = [b for b in params["begriffe"] if _norm(b) in _norm(antwort)]
    if treffer:
        return CheckErgebnis("erwaehnt_nicht", VERLETZT, f"unerwuenscht enthalten: {treffer}")
    return CheckErgebnis("erwaehnt_nicht", BESTANDEN, "keiner der Begriffe enthalten")


# ---------------------------------------------------------------------------
# Trajektorien-Ebene (arbeitet auf dem TAO-Trace aus agent_service)
# ---------------------------------------------------------------------------

def _aktionen(trace: list[dict]) -> list[dict]:
    return [s for s in trace if s.get("art") == "aktion"]


def check_tool_aufgerufen(antwort: str, trace: list[dict], params: dict) -> CheckErgebnis:
    """Das Tool wurde min..max Mal aufgerufen (min Default 1, max optional).

    Das ist der Kern der Trajektorien-Evaluation: Bei einer kcal-Vorgabe muss
    naehrwerte_schaetzen WIRKLICH laufen — eine plausible Antwort allein beweist
    nicht, dass geprueft wurde (das Modell koennte die Zahl erfinden).
    """
    name = params["name"]
    anzahl = sum(1 for a in _aktionen(trace) if a.get("name") == name)
    minimum = int(params.get("min", 1))
    maximum = params.get("max")
    if anzahl < minimum:
        return CheckErgebnis("tool_aufgerufen", VERLETZT,
                             f"{name}: {anzahl}x aufgerufen, erwartet >= {minimum}")
    if maximum is not None and anzahl > int(maximum):
        return CheckErgebnis("tool_aufgerufen", VERLETZT,
                             f"{name}: {anzahl}x aufgerufen, erlaubt <= {maximum}")
    return CheckErgebnis("tool_aufgerufen", BESTANDEN, f"{name}: {anzahl}x aufgerufen")


def check_tool_nicht_aufgerufen(antwort: str, trace: list[dict], params: dict) -> CheckErgebnis:
    """Das Tool darf NICHT laufen (situationsabhaengige Tool-Wahl, kein Blindablauf)."""
    name = params["name"]
    anzahl = sum(1 for a in _aktionen(trace) if a.get("name") == name)
    if anzahl:
        return CheckErgebnis("tool_nicht_aufgerufen", VERLETZT, f"{name}: {anzahl}x aufgerufen, erwartet 0")
    return CheckErgebnis("tool_nicht_aufgerufen", BESTANDEN, f"{name}: nicht aufgerufen")


def check_tool_reihenfolge(antwort: str, trace: list[dict], params: dict) -> CheckErgebnis:
    """'zuerst' muss vor 'dann' laufen (z. B. Kochbuch VOR Websuche, Agentic RAG).

    'zuerst' fehlt komplett -> VERLETZT. Laeuft 'zuerst', aber 'dann' gar nicht,
    ist das BESTANDEN (das erste Tool hat gereicht, kein Fallback noetig).
    """
    namen = [a.get("name") for a in _aktionen(trace)]
    zuerst, dann = params["zuerst"], params["dann"]
    if zuerst not in namen:
        return CheckErgebnis("tool_reihenfolge", VERLETZT, f"{zuerst} wurde gar nicht aufgerufen")
    if dann not in namen:
        return CheckErgebnis("tool_reihenfolge", BESTANDEN, f"{zuerst} lief, {dann} war nicht noetig")
    if namen.index(zuerst) < namen.index(dann):
        return CheckErgebnis("tool_reihenfolge", BESTANDEN, f"{zuerst} lief vor {dann}")
    return CheckErgebnis("tool_reihenfolge", VERLETZT, f"{dann} lief VOR {zuerst}")


def check_schrittzahl(antwort: str, trace: list[dict], params: dict) -> CheckErgebnis:
    """Anzahl der Aktionen liegt im plausiblen Korridor (weder 0 noch Runaway)."""
    anzahl = len(_aktionen(trace))
    minimum, maximum = int(params.get("min", 1)), int(params.get("max", 50))
    if minimum <= anzahl <= maximum:
        return CheckErgebnis("schrittzahl", BESTANDEN, f"{anzahl} Aktionen (Korridor {minimum}-{maximum})")
    return CheckErgebnis("schrittzahl", VERLETZT, f"{anzahl} Aktionen, erwartet {minimum}-{maximum}")


def check_revision_geprueft(antwort: str, trace: list[dict], params: dict) -> CheckErgebnis:
    """Wenn ein kcal-Check 'UEBER Limit' meldete, muss danach eine neue Recherche folgen.

    NEUTRAL, wenn kein Gericht ueber dem Limit lag — dann war schlicht keine
    Revision noetig (nicht anwendbar, nicht 'bestanden').
    """
    ueber_limit_indizes = [i for i, s in enumerate(trace)
                           if s.get("art") == "beobachtung" and "UEBER Limit" in (s.get("inhalt") or "")]
    if not ueber_limit_indizes:
        return CheckErgebnis("revision_geprueft", NEUTRAL, "kein Gericht ueber dem Limit -> keine Revision noetig")
    for i in ueber_limit_indizes:
        folgt_recherche = any(s.get("art") == "aktion" and s.get("name") == "recherche_rezepte"
                              for s in trace[i + 1:])
        if not folgt_recherche:
            return CheckErgebnis("revision_geprueft", VERLETZT,
                                 "kcal ueber Limit, aber keine Ersatz-Recherche im Trace")
    return CheckErgebnis("revision_geprueft", BESTANDEN,
                         f"{len(ueber_limit_indizes)}x ueber Limit, jeweils Revision sichtbar")


# ---------------------------------------------------------------------------
# Dispatch + Fall-Auswertung
# ---------------------------------------------------------------------------

CHECKS = {
    "antwort_nicht_leer": check_antwort_nicht_leer,
    "kcal_limit": check_kcal_limit,
    "kcal_summe_limit": check_kcal_summe_limit,
    "verbotene_zutaten": check_verbotene_zutaten,
    "erwaehnt_alle": check_erwaehnt_alle,
    "erwaehnt_eines": check_erwaehnt_eines,
    "erwaehnt_nicht": check_erwaehnt_nicht,
    "tool_aufgerufen": check_tool_aufgerufen,
    "tool_nicht_aufgerufen": check_tool_nicht_aufgerufen,
    "tool_reihenfolge": check_tool_reihenfolge,
    "schrittzahl": check_schrittzahl,
    "revision_geprueft": check_revision_geprueft,
}


def pruefe_fall(fall: dict, antwort: str, trace: list[dict]) -> list[CheckErgebnis]:
    """Wertet alle Checks eines Testfalls aus. Unbekannter Check-Typ -> harter Fehler.

    Bewusst KEIN stilles Ueberspringen: Ein Tippfehler im Testset wuerde sonst als
    'alles gruen' durchgehen (genau die Verifier-Luecke, vor der VL09 warnt).
    """
    ergebnisse = []
    for spec in fall["checks"]:
        typ = spec["typ"]
        if typ not in CHECKS:
            raise ValueError(f"Unbekannter Check-Typ '{typ}' im Fall '{fall.get('id')}'")
        ergebnisse.append(CHECKS[typ](antwort, trace, spec))
    return ergebnisse


def fall_status(ergebnisse: list[CheckErgebnis]) -> str:
    """Gesamturteil eines Falls: verletzt, sobald EIN Check verletzt ist;
    bestanden nur, wenn mindestens ein Check positiv belegt ist."""
    if any(e.status == VERLETZT for e in ergebnisse):
        return VERLETZT
    if any(e.status == BESTANDEN for e in ergebnisse):
        return BESTANDEN
    return NEUTRAL
