"""Campagnes RH : sauvegarde/chargement JSON local + export/import fichier avec validation."""
import json
from . import _core
from .candidate_history_manager import save_campaign, load_campaign, list_campaigns  # noqa: F401


def export_campaign(payload):
    body = {"app": "CLAVERATS", "v": 1, "payload": payload}
    body["sha256"] = _core._sha(payload)
    return json.dumps(body, ensure_ascii=False)


def import_campaign(text):
    try:
        b = json.loads(text)
    except Exception:
        raise ValueError("Fichier JSON illisible.")
    if b.get("app") != "CLAVERATS" or "payload" not in b:
        raise ValueError("Ce fichier n'est pas une campagne CLAVERATS.")
    if b.get("sha256") != _core._sha(b["payload"]):
        raise ValueError("Campagne alteree ou corrompue (empreinte invalide).")
    return b["payload"]
