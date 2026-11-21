"""Intelligence organisationnelle : synthese des offres/organisations rencontrees (JSON local)."""
import time
from . import _core, org_verifier

NAME = "organizations"


def record(job_details, phones=()):
    jd = job_details or {}
    v = org_verifier.verify(jd.get("raw_job_text", ""), jd.get("apply_emails", []), jd.get("apply_links", []), phones, "")
    db = _core.read_json(NAME, {}) or {}
    k = (v["org"] or "inconnu").lower()
    e = db.setdefault(k, {"name": v["org"], "seen": 0, "trust_min": 100, "kinds": []})
    e["seen"] += 1
    e["trust_min"] = min(e["trust_min"], v["trust"])
    e["last"] = int(time.time())
    if v["kind"] not in e["kinds"]:
        e["kinds"].append(v["kind"])
    _core.write_json(NAME, dict(list(db.items())[-200:]))
    return v


def overview():
    return sorted((_core.read_json(NAME, {}) or {}).values(), key=lambda x: -x.get("last", 0))
