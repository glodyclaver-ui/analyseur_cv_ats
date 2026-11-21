"""Compatibilite d'equipe : couverture, complementarite et redondance des competences."""


def analyze(reports, required=()):
    sets = [set(r.get("matched_skills", []) + r.get("bonus_skills", [])) for r in reports]
    names = [(r.get("cv_details") or {}).get("full_name", "Candidat") for r in reports]
    union = set().union(*sets) if sets else set()
    req = set(required) or set().union(*[set(r.get("matched_skills", []) + r.get("missing_skills", [])) for r in reports]) if reports else set()
    cover = len(req & union) / len(req) if req else 1
    from collections import Counter
    c = Counter(s for st in sets for s in st)
    redundant = sorted([s for s, n in c.items() if n >= max(2, len(sets) - 0)])[:8]
    unique = {n: sorted(st - set().union(*[o for j, o in enumerate(sets) if o is not st])) [:6] for n, st in zip(names, sets)}
    return {"coverage": round(100 * cover), "uncovered": sorted(req - union)[:12], "redundant": redundant,
            "unique_by_member": unique, "size": len(reports),
            "advice": "Equipe complementaire" if cover >= .8 and len(redundant) < 4 else "Ajouter un profil couvrant : " + ", ".join(sorted(req - union)[:3]) if req - union else "Equipe homogene : attention a la diversite."}
