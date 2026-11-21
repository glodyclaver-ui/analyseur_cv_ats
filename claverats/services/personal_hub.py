"""Espace personnel (100 % local) : objectifs de carrière + plan d'apprentissage généré depuis les compétences manquantes.

Données : data/store (enveloppe JSON _core : somme de contrôle, écriture atomique, sauvegardes). Aucune donnée n'est partagée avec l'espace RH.
"""
import time
import uuid
from . import _core
from .job_knowledge_base import TRAINING_HINTS

NAME = "personal_goals"
STATUSES = ("à faire", "en cours", "terminé")
MAX_GOALS = 200


def _all():
    return _core.read_json(NAME, {"goals": []}) or {"goals": []}


def list_goals():
    g = _all().get("goals", [])
    return sorted(g, key=lambda x: (x.get("status") == "terminé", x.get("due") or "9999"))


def _clean(d):
    title = str(d.get("title", "")).strip()[:120]
    if len(title) < 3:
        raise ValueError("Titre trop court (3 caractères minimum).")
    due = str(d.get("due", "") or "").strip()[:10]
    if due and not (len(due) == 10 and due[4] == "-" and due[7] == "-"):
        raise ValueError("Date invalide (format AAAA-MM-JJ).")
    status = d.get("status", "à faire")
    if status not in STATUSES:
        raise ValueError("Statut invalide.")
    progress = max(0, min(100, int(d.get("progress", 0) or 0)))
    return {"title": title, "due": due, "status": status, "progress": 100 if status == "terminé" else progress, "note": str(d.get("note", ""))[:400]}


def add_goal(d):
    db = _all()
    if len(db["goals"]) >= MAX_GOALS:
        raise ValueError("Nombre maximal d'objectifs atteint.")
    g = {"id": uuid.uuid4().hex[:10], "created": int(time.time()), **_clean(d)}
    db["goals"].append(g)
    _core.write_json(NAME, db)
    return g


def update_goal(gid, d):
    db = _all()
    for g in db["goals"]:
        if g["id"] == gid:
            g.update(_clean({**g, **d}))
            _core.write_json(NAME, db)
            return g
    raise ValueError("Objectif introuvable.")


def delete_goal(gid):
    db = _all()
    n = len(db["goals"])
    db["goals"] = [g for g in db["goals"] if g["id"] != gid]
    _core.write_json(NAME, db)
    return n - len(db["goals"])


def learning_plan(missing, weights=None, hours_per_week=5):
    """Plan d'apprentissage : compétences manquantes triées par coefficient (essentielles d'abord), 1 à 3 semaines chacune.
    Estimations INDICATIVES (règle : essentielle ×3 = 3 sem., importante ×2 = 2 sem., un plus = 1 sem., ajustées au temps disponible)."""
    weights = {str(k).lower(): v for k, v in (weights or {}).items()}
    hours_per_week = max(1, min(40, int(hours_per_week or 5)))
    factor = 5.0 / hours_per_week
    items = sorted(missing or [], key=lambda s: -float(weights.get(str(s).lower(), 2)))
    plan, week = [], 0.0
    for s in items:
        w = float(weights.get(str(s).lower(), 2))
        weeks = max(1, round({3: 3, 2: 2}.get(int(w), 1) * factor))
        plan.append({"skill": s, "priority": "essentielle" if w >= 3 else "importante" if w >= 2 else "un plus", "start_week": int(week) + 1,
                     "weeks": weeks, "hint": TRAINING_HINTS.get(str(s).lower(), "Cours en ligne gratuit, exercice pratique, puis une réalisation à montrer dans votre CV.")})
        week += weeks
    return {"hours_per_week": hours_per_week, "total_weeks": int(week), "items": plan,
            "note": "Durées indicatives : elles dépendent de votre niveau de départ."}
