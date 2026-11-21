"""Potentiel d'evolution : proximite des competences manquantes + diversite + trajectoire."""
from .skill_relationship_engine import transferability


def analyze(report):
    have = report.get("matched_skills", []) + report.get("bonus_skills", [])
    miss = report.get("missing_skills", [])
    tr = transferability(have, miss)
    closeness = sum(t["closeness"] for t in tr) / len(tr) if tr else 100
    diversity = min(100, len(set(have)) * 6)
    years = float((report.get("cv_details") or {}).get("exp_years", 0) or 0)
    growth = 80 if years < 3 and len(have) >= 6 else 60 if years < 6 else 45
    pot = round(0.45 * closeness + 0.3 * diversity + 0.25 * growth)
    return {"potential": pot, "label": "Fort potentiel" if pot >= 70 else "Potentiel moyen" if pot >= 45 else "Potentiel limite",
            "learnable_fast": [t["skill"] for t in tr if t["closeness"] >= 70][:5], "closeness": round(closeness), "diversity": diversity}
