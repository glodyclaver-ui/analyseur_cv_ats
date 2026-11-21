"""Calculateur de progression de carrière (1 / 3 / 5 ans) - INDICATIF, explicable, 100 % local.

Règles transparentes (aucune donnée inventée) :
  * l'échelon actuel vient du métier détecté + années d'expérience déclarées ;
  * rythme d'avancement : 3 ans par échelon (2 ans si couverture des compétences >= 70 %, 4 ans si < 40 %) ;
  * les compétences à acquérir viennent du référentiel de métiers éditable (compétences du métier cible non détectées dans le CV).
Les échelles ci-dessous sont indicatives et modifiables dans data/config/career_ladders.json.
"""
import json
import os
from . import _core, skills_referential as sr

DEFAULT_LADDERS = {
    "sante": {
        "pab": ["Préposé(e) aux bénéficiaires", "Aide-soignant(e)", "Infirmier(ère) auxiliaire", "Infirmier(ère)"],
        "aide_soignant": ["Aide-soignant(e)", "Infirmier(ère) auxiliaire", "Infirmier(ère)", "Infirmier(ère) titulaire"],
        "infirmier": ["Infirmier(ère)", "Infirmier(ère) titulaire", "Infirmier(ère) superviseur", "Responsable des soins / Infirmier chef"],
        "*": ["Professionnel de santé", "Professionnel de santé confirmé", "Responsable de service", "Coordinateur / Directeur technique"],
    },
    "it": {
        "*": ["Technicien / Développeur junior", "Développeur / Technicien confirmé", "Développeur senior / Référent technique", "Lead technique / Architecte / Chef de projet IT"],
    },
    "gestion": {
        "*": ["Assistant(e) / Agent", "Gestionnaire / Chargé(e)", "Responsable d'équipe", "Responsable de département / Manager"],
    },
    "education": {"*": ["Enseignant(e)", "Enseignant(e) confirmé(e)", "Responsable pédagogique / Préfet", "Directeur / Inspecteur"]},
    "humanitaire": {"*": ["Assistant(e) de programme", "Chargé(e) de programme", "Responsable de programme", "Coordinateur / Chef de projet pays"]},
    "_default": ["Profil débutant", "Profil confirmé", "Profil senior / responsable", "Manager / Expert référent"],
}
CONFIG_NAME = "career_ladders.json"


def _ladders():
    path = os.path.join(_core.DATA_DIR, "config", CONFIG_NAME)
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        if isinstance(d, dict) and d:
            return d
    except Exception:
        pass
    return DEFAULT_LADDERS


def _ladder_for(sector, role):
    L = _ladders()
    sec = L.get(sector) or {}
    return sec.get(role) or sec.get("*") or L.get("_default") or DEFAULT_LADDERS["_default"]


def _start_index(ladder, exp_years, edu_rank):
    """Échelon actuel : 0 sous 2 ans ; +1 vers 3-5 ans ; +2 au-delà de 8 ans (borné)."""
    i = 0 if exp_years < 3 else 1 if exp_years < 8 else 2
    return min(i, len(ladder) - 1)


def project(cv_text, exp_years=0, edu_rank=0, matched_ratio=None, profession_hint="", horizons=(1, 3, 5)):
    info = sr.detect_role(cv_text or "", profession_hint or "")
    sector, role = info.get("sector"), info.get("role")
    ladder = _ladder_for(sector, role)
    start = _start_index(ladder, float(exp_years or 0), int(edu_rank or 0))
    if matched_ratio is None:
        pace, pace_why = 3.0, "rythme standard de 3 ans par échelon (couverture des compétences inconnue)"
    elif matched_ratio >= 0.7:
        pace, pace_why = 2.0, f"couverture des compétences élevée ({round(matched_ratio*100)} %) : progression plus rapide (2 ans/échelon)"
    elif matched_ratio < 0.4:
        pace, pace_why = 4.0, f"couverture des compétences faible ({round(matched_ratio*100)} %) : progression plus lente (4 ans/échelon)"
    else:
        pace, pace_why = 3.0, f"couverture des compétences moyenne ({round(matched_ratio*100)} %) : rythme standard (3 ans/échelon)"

    cfg = sr.load()
    role_skills = []
    try:
        role_skills = [s["name"] for s in cfg["sectors"][sector]["roles"][role]["skills"]]
    except Exception:
        pass
    low = (cv_text or "").lower()
    todo = [s for s in role_skills if s.lower() not in low]

    out = []
    for h in horizons:
        steps = int(h // pace)
        idx = min(start + steps, len(ladder) - 1)
        capped = start + steps > len(ladder) - 1
        learn = todo[:3] if idx == start else (todo[:2] + ["Encadrement d'équipe / gestion"] if idx >= 2 else todo[:3])
        out.append({
            "years": h, "level": ladder[idx], "step": idx - start,
            "total_experience": round(float(exp_years or 0) + h, 1),
            "to_acquire": learn,
            "reading": ("Poste plausible : " if idx > start else "Consolidation du poste actuel : ") + ladder[idx] + (" (sommet de l'échelle connue)" if capped else ""),
        })
    return {
        "indicative": True, "role": info, "current_level": ladder[start], "ladder": ladder, "pace_years_per_step": pace,
        "explanation": f"Métier détecté : {info.get('label') or 'non déterminé'} ; échelon actuel estimé « {ladder[start]} » d'après {exp_years} an(s) d'expérience ; {pace_why}.",
        "disclaimer": "Projection indicative fondée sur des règles simples et modifiables ; elle ne garantit aucune évolution réelle.",
        "projections": out,
    }
