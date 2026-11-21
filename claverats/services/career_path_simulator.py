"""Simulation de trajectoire : quelles competences ajouter pour atteindre un metier cible, en combien de temps."""
from .job_knowledge_base import ROLES, role_for, TRAINING_HINTS


def simulate(skills, target_role=None, months_per_skill=1.5):
    have = {s.lower() for s in skills}
    if not target_role or target_role not in ROLES:
        target_role = role_for(skills)[0][0]
    d = ROLES[target_role]
    todo = [k for k in d["core"] + d["plus"] if k not in have]
    steps = []
    t = 0.0
    for k in todo:
        t += months_per_skill if k in d["core"] else months_per_skill * 0.7
        steps.append({"skill": k, "month": round(t, 1), "core": k in d["core"], "hint": TRAINING_HINTS.get(k, "")})
    return {"target": target_role, "steps": steps, "months_total": round(t, 1),
            "readiness_now": round(100 * (len(d["core"] + d["plus"]) - len(todo)) / len(d["core"] + d["plus"])),
            "then": d["next"]}
