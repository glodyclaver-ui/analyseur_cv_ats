"""Classement des candidats : score d'abord, puis critères de départage EXPLICITES (jamais d'égalité arbitraire).

Ordre : score -> couverture des compétences -> expérience -> fiabilité du document -> lisibilité -> dossier complet -> nom.
La même règle est reprise côté navigateur (rankCmp dans main.js) pour que l'ordre reste identique après une correction manuelle.
"""
_READ = {"clean": 3, "partial": 2, "unreadable": 0}

CRITERIA = [
    ("score", "score global"),
    ("coverage", "couverture des compétences exigées"),
    ("exp", "années d'expérience"),
    ("trust", "fiabilité du document"),
    ("read", "lisibilité du CV"),
    ("complete", "complétude du dossier (contact, expériences)"),
]


def _vals(c):
    m, ms = len(c.get("matched_skills") or []), len(c.get("missing_skills") or [])
    cov = (m / (m + ms)) if (m + ms) else 0.0
    complete = int(bool(c.get("emails") or c.get("email"))) + int(bool(c.get("phones") or c.get("phone"))) + int(bool(c.get("structured_experiences")))
    return {"score": float(c.get("score") or 0), "coverage": round(cov, 3), "exp": float(c.get("exp_years") or 0),
            "trust": float((c.get("doc_trust") or {}).get("score") or 0), "read": _READ.get(c.get("readability"), 1), "complete": complete}


def sort_key(c):
    v = _vals(c)
    return (-v["score"], -v["coverage"], -v["exp"], -v["trust"], -v["read"], -v["complete"], str(c.get("name") or "").lower())


def rank(candidates):
    """Trie sur place, renseigne rank / tie / rank_reason. Retourne la liste."""
    candidates.sort(key=sort_key)
    for i, c in enumerate(candidates):
        c["rank"] = i + 1
        c["rank_reason"] = ""
        c["tie"] = False
        if i + 1 < len(candidates):
            a, b = _vals(c), _vals(candidates[i + 1])
            for key, label in CRITERIA:
                if a[key] != b[key]:
                    c["rank_reason"] = ("devant le suivant grâce au " if key == "score" else "ex æquo au score, devant le suivant grâce à la ") + label if key != "score" else "meilleur score global"
                    c["tie"] = key != "score"
                    break
            else:
                c["rank_reason"] = "profil identique au suivant (départagé par l'ordre alphabétique)"
                c["tie"] = True
    for i, c in enumerate(candidates):
        if i > 0 and candidates[i - 1].get("tie") and not c.get("rank_reason"):
            c["tie"] = True
    return candidates
