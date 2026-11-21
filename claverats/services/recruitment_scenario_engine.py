"""Scenarios 'et si' : ajout de competences, changement de poids, seuil. Calcul local."""


def what_if(report, add_skills=(), tech_weight=None):
    matched = set(report.get("matched_skills", []))
    miss = set(report.get("missing_skills", []))
    add = {s for s in add_skills if s in miss}
    total = len(matched) + len(miss)
    base = report.get("score", 0)
    if total == 0:
        return {"base": base, "scenario": base, "gain": 0, "added": []}
    tw = tech_weight if tech_weight is not None else 60
    gain = round(tw * len(add) / total)
    new = min(100, base + gain)
    return {"base": base, "scenario": new, "gain": new - base, "added": sorted(add), "tech_weight": tw}


def best_next_skills(report, k=3):
    """Quelles competences manquantes rapportent le plus ? (egales en gain, tri par proximite)"""
    from .skill_relationship_engine import transferability
    tr = transferability(report.get("matched_skills", []), report.get("missing_skills", []))
    return [dict(t, **what_if(report, [t["skill"]])) for t in tr[:k]]
