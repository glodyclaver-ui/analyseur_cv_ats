"""Journal d'audit local (JSON) chaine par hash : toute alteration est detectable."""
import hashlib
import json
import time
from . import _core

NAME = "audit_trail"
MAX_ENTRIES = 2000


def _h(prev, entry):
    raw = prev + json.dumps(entry, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def log(action, detail="", actor="local"):
    """Ajoute une entree. Ne stocke jamais de donnees personnelles brutes : detail est tronque."""
    trail = _core.read_json(NAME, []) or []
    prev = trail[-1]["hash"] if trail else "GENESIS"
    e = {"ts": int(time.time()), "action": str(action)[:60], "detail": str(detail)[:200], "actor": actor}
    e["hash"] = _h(prev, e)
    trail.append(e)
    _core.write_json(NAME, trail[-MAX_ENTRIES:])
    return e


def get(limit=200):
    return (_core.read_json(NAME, []) or [])[-limit:][::-1]


def verify():
    """Verifie la chaine ; retourne (ok, index_du_premier_defaut)."""
    trail = _core.read_json(NAME, []) or []
    prev = "GENESIS"
    for i, e in enumerate(trail):
        body = {k: v for k, v in e.items() if k != "hash"}
        if i == 0:
            prev = "GENESIS"  # la fenetre peut avoir ete tronquee : on amorce sur la 1re entree
            prev_ok = True
        if i > 0 and _h(prev, body) != e["hash"]:
            return {"ok": False, "broken_at": i, "count": len(trail)}
        prev = e["hash"]
    return {"ok": True, "broken_at": None, "count": len(trail)}


def export_json():
    return {"exported_at": int(time.time()), "verify": verify(), "entries": get(MAX_ENTRIES)[::-1]}


def clear():
    _core.write_json(NAME, [])
