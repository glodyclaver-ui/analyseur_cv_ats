"""Analyse des experiences : duree exacte, chevauchements, trous, stabilite."""
import re
from datetime import date

MONTHS = {"janvier": 1, "janv": 1, "fevrier": 2, "fevr": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6, "juillet": 7, "juil": 7,
          "aout": 8, "septembre": 9, "sept": 9, "octobre": 10, "oct": 10, "novembre": 11, "nov": 11, "decembre": 12, "dec": 12,
          "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6, "july": 7, "august": 8,
          "september": 9, "october": 10, "november": 11, "december": 12}
_PRESENT = ("present", "aujourd", "actuel", "en cours", "ce jour", "now", "current")


def _norm(s):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", (s or "").lower()) if unicodedata.category(c) != "Mn")


def parse_token(tok, ref, is_end=False):
    t = _norm(tok).strip(" .,")
    if any(p in t for p in _PRESENT):
        return ref
    m = re.search(r"(\d{1,2})[/.-](\d{4})", t)
    if m:
        return (int(m.group(2)), min(12, max(1, int(m.group(1)))))
    m = re.search(r"([a-z]{3,})\.?\s+(\d{4})", t)
    if m and m.group(1) in MONTHS:
        return (int(m.group(2)), MONTHS[m.group(1)])
    m = re.search(r"\b((?:19|20)\d{2})\b", t)
    if m:
        return (int(m.group(1)), 12 if is_end else 1)
    return None


def duration(period, ref=None):
    """period 'Mars 2020 - Juin 2022' -> {months, label}. ref = (annee, mois) de reference."""
    ref = ref or (date.today().year, date.today().month)
    parts = re.split(r"\s+[-–—]\s+|\s+(?:a|au|to|jusqu'a)\s+|\s*[–—]\s*", _norm(period).strip(), maxsplit=1)
    if len(parts) == 1:
        parts = re.split(r"\s*-\s*", _norm(period).strip(), maxsplit=1)
    if len(parts) < 2:
        return {"months": None, "label": "Duree non determinee"}
    a, b = parse_token(parts[0], ref), parse_token(parts[1], ref, True)
    if not a or not b:
        return {"months": None, "label": "Duree non determinee"}
    m = (b[0] - a[0]) * 12 + (b[1] - a[1]) + 1
    if m <= 0:
        return {"months": None, "label": "Dates incoherentes"}
    return {"months": m, "label": format_months(m), "start": a, "end": b}


def format_months(m):
    y, r = divmod(int(m), 12)
    s = []
    if y:
        s.append("%d an%s" % (y, "s" if y > 1 else ""))
    if r:
        s.append("%d mois" % r)
    return " ".join(s) or "moins d'un mois"


def analyze(exps, ref=None):
    """exps : liste de dict {company, role/title, period}. Retourne exps enrichies + indicateurs."""
    out, spans = [], []
    for e in exps or []:
        d = duration(e.get("period", "") or e.get("duration_raw", ""), ref)
        n = dict(e)
        n["duration_months"], n["duration_label"] = d["months"], d["label"]
        out.append(n)
        if d.get("start"):
            spans.append((d["start"], d["end"]))
    spans.sort()
    gaps, overlaps = 0, 0
    for (s1, e1), (s2, e2) in zip(spans, spans[1:]):
        diff = (s2[0] - e1[0]) * 12 + (s2[1] - e1[1])
        if diff > 6:
            gaps += 1
        elif diff < 0:
            overlaps += 1
    known = [x["duration_months"] for x in out if x["duration_months"]]
    avg = sum(known) / len(known) if known else 0
    stability = "Stable" if avg >= 24 else "Moyenne" if avg >= 12 else "Mobile" if known else "Inconnue"
    return {"experiences": out, "total_months": sum(known), "total_label": format_months(sum(known)) if known else "-",
            "avg_months": round(avg, 1), "stability": stability, "gaps": gaps, "overlaps": overlaps,
            "consistency": max(0, 100 - 15 * gaps - 10 * overlaps - (20 if not known else 0))}
