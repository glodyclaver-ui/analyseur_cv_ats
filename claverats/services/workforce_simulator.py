"""Simulation d'embauche : combien de postes couvrir avec un budget, en combinant les meilleurs profils."""


def simulate(reports, required, budget=None, per_hire_cost=1200, seats=3):
    req = set(required)
    chosen, covered = [], set()
    pool = list(enumerate(reports))
    for _ in range(seats):
        best, bg = None, -1
        for i, r in pool:
            if i in chosen:
                continue
            gain = len((set(r.get("matched_skills", [])) & req) - covered) * 10 + r.get("score", 0) / 10
            if gain > bg:
                best, bg = i, gain
        if best is None:
            break
        if budget is not None and per_hire_cost * (len(chosen) + 1) > budget:
            break
        chosen.append(best)
        covered |= set(reports[best].get("matched_skills", [])) & req
    return {"selected": [{"index": i, "name": (reports[i].get("cv_details") or {}).get("full_name", "Candidat"), "score": reports[i].get("score", 0)} for i in chosen],
            "coverage": round(100 * len(covered) / len(req)) if req else 100, "uncovered": sorted(req - covered),
            "cost": per_hire_cost * len(chosen)}
