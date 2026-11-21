"""Profil de talent synthetique : seniorite, domaine, forces, stabilite, indice de coherence."""
from .job_knowledge_base import role_for
from . import experience_analyzer as ea


def profile(report):
    cv = report.get("cv_details", {}) or {}
    skills = report.get("matched_skills", []) + report.get("bonus_skills", [])
    years = float(cv.get("exp_years", 0) or 0)
    seniority = "Senior" if years >= 8 else "Confirme" if years >= 4 else "Junior" if years >= 1 else "Debutant"
    analysis = cv.get("experience_analysis") or ea.analyze(cv.get("structured_experiences", []))
    roles = role_for(skills)[:3]
    cats = report.get("category_breakdown", []) or []
    if isinstance(cats, dict):
        cats = [{"category": k, "percent": 0} for k in cats]
    strengths = [(c.get("category"), c.get("percent", 0)) for c in sorted(cats, key=lambda c: -c.get("percent", 0))[:3]]
    ratio = len(set(skills)) / max(1, years + 1)
    return {"seniority": seniority, "years": years, "likely_roles": [{"role": r, "fit": round(s * 100)} for r, s in roles],
            "strengths": [k for k, _ in strengths], "stability": analysis.get("stability"), "consistency": analysis.get("consistency"),
            "skill_density": round(ratio, 1), "talent_index": min(100, round(0.5 * report.get("score", 0) + 0.3 * (analysis.get("consistency") or 50) + 2 * min(10, len(skills)) * 0.5))}
