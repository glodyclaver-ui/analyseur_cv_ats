"""Suivi local des entretiens : planification, notes, scores (JSON)."""
import time
from . import _core

NAME = "interviews"


def _all():
    return _core.read_json(NAME, []) or []


def add(candidate, when, mode="visio", notes=""):
    items = _all()
    it = {"id": int(time.time() * 1000), "candidate": candidate, "when": when, "mode": mode, "notes": notes[:2000], "score": None, "done": False}
    items.append(it)
    _core.write_json(NAME, items[-500:])
    return it


def update(iid, **kw):
    items = _all()
    for it in items:
        if it["id"] == iid:
            for k in ("when", "mode", "notes", "score", "done"):
                if k in kw:
                    it[k] = kw[k]
    _core.write_json(NAME, items)
    return items


def list_all():
    return sorted(_all(), key=lambda x: x["when"])


def remove(iid):
    _core.write_json(NAME, [i for i in _all() if i["id"] != iid])
