"""Fiche candidat 360° et comparaison (espace RH). Lecture seule : aucune décision automatique."""


def _pct(m, x):
    return round(100 * m / (m + x)) if (m + x) else 0


def sheet(c, rank_total=None):
    m, x = c.get("matched_skills") or [], c.get("missing_skills") or []
    exps = c.get("structured_experiences") or []
    strengths, watch = [], []
    if _pct(len(m), len(x)) >= 70:
        strengths.append(f"Couvre {_pct(len(m), len(x))} % des compétences exigées")
    if (c.get("exp_years") or 0) >= 5:
        strengths.append(f"{c.get('exp_years')} ans d'expérience")
    if (c.get("doc_trust") or {}).get("level") == "Fiable":
        strengths.append("Document jugé fiable")
    if x:
        watch.append("Compétences non retrouvées : " + ", ".join(x[:6]) + (f" (+{len(x) - 6})" if len(x) > 6 else ""))
    if c.get("chrono_gaps"):
        watch.append("Interruptions de parcours à clarifier en entretien")
    if c.get("readability") in ("partial", "unreadable"):
        watch.append("CV partiellement lisible : vérifier le document original")
    if (c.get("score_confidence") or {}).get("level") in ("faible", "insuffisante"):
        watch.append("Score peu fiable (peu d'exigences exploitables dans l'offre)")
    return {
        "name": c.get("name"), "score": c.get("score"), "rank": c.get("rank"), "of": rank_total, "rank_reason": c.get("rank_reason", ""),
        "profession": c.get("main_profession"), "seniority": c.get("seniority"), "location": c.get("location"),
        "contact": {"emails": c.get("emails") or ([c["email"]] if c.get("email") else []), "phones": c.get("phones") or ([c["phone"]] if c.get("phone") else [])},
        "coverage_pct": _pct(len(m), len(x)), "matched": m, "missing": x, "bonus": c.get("bonus_skills") or [],
        "score_explanation": c.get("score_explanation") or [], "score_confidence": c.get("score_confidence"),
        "experiences": [{"company": e.get("company") or e.get("employer"), "role": e.get("role"), "period": e.get("period"), "duration_months": e.get("duration_months")} for e in exps],
        "strengths": strengths, "watch": watch, "status": c.get("hr_status"), "note": c.get("hr_note", ""),
        "disclaimer": "Aide à la décision : la décision finale revient toujours à un humain.",
    }


def compare(a, b):
    sa, sb = set(a.get("matched_skills") or []), set(b.get("matched_skills") or [])
    return {
        "a": {"name": a.get("name"), "score": a.get("score"), "exp": a.get("exp_years"), "coverage_pct": _pct(len(sa), len(a.get("missing_skills") or []))},
        "b": {"name": b.get("name"), "score": b.get("score"), "exp": b.get("exp_years"), "coverage_pct": _pct(len(sb), len(b.get("missing_skills") or []))},
        "common": sorted(sa & sb), "only_a": sorted(sa - sb), "only_b": sorted(sb - sa),
        "verdict": ("Scores identiques : départagez sur l'expérience et les compétences propres à chacun." if a.get("score") == b.get("score")
                    else f"{a.get('name') if (a.get('score') or 0) > (b.get('score') or 0) else b.get('name')} a le meilleur score ({max(a.get('score') or 0, b.get('score') or 0)} %)."),
    }
