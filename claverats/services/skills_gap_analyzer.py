"""Analyse des ecarts de competences et plan d'apprentissage local."""
from .skill_relationship_engine import transferability
from .job_knowledge_base import TRAINING_HINTS


def analyze(report):
    have = report.get("matched_skills", []) + report.get("bonus_skills", [])
    miss = report.get("missing_skills", [])
    tr = transferability(have, miss)
    plan = []
    for t in tr[:8]:
        plan.append({"skill": t["skill"], "effort": "faible" if t["closeness"] >= 70 else "moyen" if t["closeness"] >= 35 else "eleve",
                     "closeness": t["closeness"], "via": t["via"],
                     "hint": TRAINING_HINTS.get(t["skill"].lower(), "Cours en ligne + mini-projet pratique.")})
    total = len(report.get("matched_skills", [])) + len(miss)
    return {"coverage": round(100 * len(report.get("matched_skills", [])) / total) if total else 100,
            "gaps": plan, "quick_wins": [p["skill"] for p in plan if p["effort"] == "faible"][:5]}
