"""Analytique RH : entonnoir, distribution, podium, heatmap competences x candidats."""
from collections import Counter


def analytics(reports, thresholds=(75, 55, 35)):
    sc = [r.get("score", 0) for r in reports]
    dist = Counter(("Excellent" if s >= thresholds[0] else "Bon" if s >= thresholds[1] else "Moyen" if s >= thresholds[2] else "Faible") for s in sc)
    order = sorted(range(len(reports)), key=lambda i: -sc[i])
    skills = Counter(s for r in reports for s in r.get("matched_skills", []))
    top_sk = [s for s, _ in skills.most_common(12)]
    return {"count": len(sc), "avg": round(sum(sc) / len(sc), 1) if sc else 0,
            "funnel": [{"stage": "Recus", "n": len(sc)}, {"stage": ">= 35", "n": sum(s >= thresholds[2] for s in sc)},
                       {"stage": ">= 55", "n": sum(s >= thresholds[1] for s in sc)}, {"stage": ">= 75", "n": sum(s >= thresholds[0] for s in sc)}],
            "distribution": dict(dist),
            "podium": [{"rank": k + 1, "name": (reports[i].get("cv_details") or {}).get("full_name", "Candidat"), "score": sc[i]} for k, i in enumerate(order[:3])],
            "heatmap": {"skills": top_sk, "rows": [{"name": (r.get("cv_details") or {}).get("full_name", "Candidat"),
                                                      "cells": [1 if s in r.get("matched_skills", []) else 0 for s in top_sk]} for r in reports[:30]]},
            "top_missing": Counter(s for r in reports for s in r.get("missing_skills", [])).most_common(8)}
