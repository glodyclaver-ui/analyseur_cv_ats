"""Suivi des candidatures (cote candidat) : pipeline local JSON."""
import time
from . import _core

NAME = "applications"
STAGES = ["A postuler", "Postule", "Entretien", "Test", "Offre", "Refuse", "Accepte"]


def _all():
    return _core.read_json(NAME, []) or []


def add(company, title, score=None, url=""):
    items = _all()
    it = {"id": int(time.time() * 1000), "company": company[:80], "title": title[:80], "score": score, "url": url[:300],
          "stage": "A postuler", "history": [{"ts": int(time.time()), "stage": "A postuler"}]}
    items.append(it)
    _core.write_json(NAME, items[-300:])
    return it


def move(iid, stage):
    if stage not in STAGES:
        raise ValueError("etape inconnue")
    items = _all()
    for it in items:
        if it["id"] == iid and it["stage"] != stage:
            it["stage"] = stage
            it["history"].append({"ts": int(time.time()), "stage": stage})
    _core.write_json(NAME, items)


def remove(iid):
    _core.write_json(NAME, [i for i in _all() if i["id"] != iid])


def board():
    items = _all()
    return {"stages": STAGES, "items": items,
            "stats": {s: sum(1 for i in items if i["stage"] == s) for s in STAGES}}
