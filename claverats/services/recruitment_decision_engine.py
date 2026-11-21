"""Aide a la decision explicable : Retenir / Entretien / Reserve / Ecarter, avec justification."""


def decide(report, trust=None, thresholds=(75, 55, 35)):
    s = report.get("score", 0)
    why = []
    st = report.get("stats", {})
    why.append("Score de compatibilite %d%%." % s)
    if st.get("job_skills_count"):
        why.append("%d/%d competences requises couvertes." % (st.get("matched_count", 0), st["job_skills_count"]))
    if report.get("missing_skills"):
        why.append("Manques : " + ", ".join(report["missing_skills"][:4]) + ".")
    verdict = "Retenir" if s >= thresholds[0] else "Entretien" if s >= thresholds[1] else "Reserve" if s >= thresholds[2] else "Ecarter"
    if trust is not None and trust < 50 and verdict in ("Retenir", "Entretien"):
        verdict = "Verifier le document"
        why.append("Confiance documentaire faible (%d/100)." % trust)
    return {"verdict": verdict, "confidence": min(99, 50 + abs(s - 50)), "why": why}
