"""Recommandation de metiers adaptes au profil (regles locales)."""
from .job_knowledge_base import ROLES, role_for


def recommend(report, top=4):
    sk = report.get("matched_skills", []) + report.get("bonus_skills", [])
    out = []
    for role, sc in role_for(sk)[:top]:
        d = ROLES[role]
        have = {s.lower() for s in sk}
        out.append({"role": role, "fit": round(sc * 100), "missing_core": [k for k in d["core"] if k not in have],
                    "next_roles": d["next"], "salary_ref": d["salary"]})
    return out
