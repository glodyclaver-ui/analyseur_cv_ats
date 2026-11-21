"""Historique local des candidats (JSON) : versions, evolution des scores, comparateur de CV."""
import time
from . import _core

NAME = "candidate_history"
MAX = 300


def _all():
    return _core.read_json(NAME, {}) or {}


def _key(report):
    cv = report.get("cv_details", {}) or {}
    return (cv.get("full_name") or "Candidat").strip().lower()


def record(report, label="analyse"):
    """Enregistre une version (score, competences, experiences) du candidat."""
    if not report or not report.get("success"):
        return None
    cv = report.get("cv_details", {}) or {}
    jd = report.get("job_details", {}) or {}
    db = _all()
    k = _key(report)
    ver = {"ts": int(time.time()), "label": label, "score": report.get("score", 0),
           "initial_score": report.get("initial_score", report.get("score", 0)),
           "company": jd.get("company_name", ""), "matched": report.get("matched_skills", [])[:60],
           "missing": report.get("missing_skills", [])[:60], "exp_years": cv.get("exp_years", 0),
           "n_experiences": len(cv.get("structured_experiences", []) or []),
           "edited": bool(report.get("manual_edits"))}
    entry = db.setdefault(k, {"name": cv.get("full_name", "Candidat"), "versions": []})
    entry["name"] = cv.get("full_name", entry["name"])
    entry["versions"] = (entry["versions"] + [ver])[-30:]
    if len(db) > MAX:
        for old in sorted(db, key=lambda x: db[x]["versions"][-1]["ts"])[:len(db) - MAX]:
            db.pop(old)
    _core.write_json(NAME, db)
    return ver


def evolution(name):
    e = _all().get(str(name).strip().lower())
    if not e:
        return {"name": name, "versions": [], "trend": 0}
    v = e["versions"]
    return {"name": e["name"], "versions": v, "trend": (v[-1]["score"] - v[0]["score"]) if len(v) > 1 else 0}


def list_candidates():
    return [{"key": k, "name": v["name"], "versions": len(v["versions"]), "last_score": v["versions"][-1]["score"],
             "last_ts": v["versions"][-1]["ts"]} for k, v in _all().items()]


def compare_versions(name, i, j):
    e = _all().get(str(name).strip().lower())
    if not e or max(i, j) >= len(e["versions"]):
        return {"error": "versions introuvables"}
    a, b = e["versions"][i], e["versions"][j]
    sa, sb = set(a["matched"]), set(b["matched"])
    return {"score_delta": b["score"] - a["score"], "skills_added": sorted(sb - sa), "skills_removed": sorted(sa - sb),
            "exp_delta": round(b["exp_years"] - a["exp_years"], 1)}


def delete(name):
    db = _all()
    db.pop(str(name).strip().lower(), None)
    _core.write_json(NAME, db)


def save_campaign(name, payload):
    camps = _core.read_json("campaigns", {}) or {}
    camps[str(name)[:60]] = {"ts": int(time.time()), "payload": payload}
    _core.write_json("campaigns", camps)


def load_campaign(name):
    return ((_core.read_json("campaigns", {}) or {}).get(str(name)[:60]) or {}).get("payload")


def list_campaigns():
    return [{"name": k, "ts": v["ts"]} for k, v in (_core.read_json("campaigns", {}) or {}).items()]


def clear_all():
    """Supprime tout l'historique serveur (action explicite de l'utilisateur)."""
    n = len(_all())
    _core.write_json(NAME, {})
    return n
