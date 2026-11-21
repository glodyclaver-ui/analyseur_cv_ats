"""Données cartographiques du monde, créées À L'INTÉRIEUR de l'application.

Remplace la commande manuelle `python tools/fetch_world.py` : l'app télécharge une seule fois
les frontières Natural Earth 1:110m (domaine public) vers static/data/world.geojson, puis fonctionne
hors-ligne. Fonction OPTIONNELLE (Internet) : si le réseau est indisponible, la carte reste sur les
contours simplifiés intégrés. Aucun CV ni donnée personnelle n'est envoyé : simple GET d'un fichier public.
"""
import json
import os
import tempfile
import threading
import time
import urllib.request

URLS = [
    "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_admin_0_countries.geojson",
    "https://cdn.jsdelivr.net/gh/nvkelso/natural-earth-vector@master/geojson/ne_110m_admin_0_countries.geojson",
]
MIN_FEATURES = 150
MAX_BYTES = 8 * 1024 * 1024
_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_PATH = os.path.join(_BASE, "static", "data", "world.geojson")

_state = {"running": False, "last_error": "", "last_attempt": 0, "last_ok": 0}
_lock = threading.Lock()


def _rnd(c):
    return [round(c[0], 2), round(c[1], 2)] if isinstance(c[0], (int, float)) else [_rnd(x) for x in c]


def convert(data):
    """Natural Earth FeatureCollection -> version allégée (identique à tools/fetch_world.py)."""
    feats = []
    for f in (data or {}).get("features", []):
        p = f.get("properties") or {}
        g = f.get("geometry")
        if not g or "coordinates" not in g:
            continue
        feats.append({
            "type": "Feature",
            "properties": {
                "NAME": p.get("NAME") or p.get("ADMIN") or "",
                "NAME_FR": p.get("NAME_FR") or p.get("NAME") or "",
                "CONTINENT": p.get("CONTINENT") or "",
                "ISO_A3": p.get("ISO_A3") or p.get("ADM0_A3") or "",
            },
            "geometry": {"type": g["type"], "coordinates": _rnd(g["coordinates"])},
        })
    return {"type": "FeatureCollection", "features": feats}


def validate(fc):
    return isinstance(fc, dict) and fc.get("type") == "FeatureCollection" and len(fc.get("features", [])) >= MIN_FEATURES


def status(out_path=None):
    path = out_path or OUT_PATH
    present = os.path.isfile(path)
    n = 0
    if present:
        try:
            with open(path, encoding="utf-8") as fh:
                n = len(json.load(fh).get("features", []))
        except Exception:
            present = False
    return {"available": present and n >= MIN_FEATURES, "countries": n, "running": _state["running"],
            "last_error": _state["last_error"], "last_ok": _state["last_ok"],
            "note": "Optionnel : nécessite Internet une seule fois (fichier public Natural Earth)."}


def fetch(out_path=None, opener=None, timeout=45):
    """Télécharge, convertit, valide puis écrit de façon atomique. Retourne {ok, message, countries}."""
    path = out_path or OUT_PATH
    opener = opener or (lambda url: urllib.request.urlopen(url, timeout=timeout))
    with _lock:
        if _state["running"]:
            return {"ok": False, "message": "Téléchargement déjà en cours."}
        _state["running"] = True
    _state["last_attempt"] = time.time()
    errors = []
    try:
        for url in URLS:
            try:
                resp = opener(url)
                raw = resp.read(MAX_BYTES + 1)
                if len(raw) > MAX_BYTES:
                    raise ValueError("fichier trop volumineux")
                fc = convert(json.loads(raw.decode("utf-8")))
                if not validate(fc):
                    raise ValueError("données invalides (moins de %d pays)" % MIN_FEATURES)
                os.makedirs(os.path.dirname(path), exist_ok=True)
                fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    json.dump(fc, fh, ensure_ascii=False, separators=(",", ":"))
                os.replace(tmp, path)
                _state["last_error"] = ""
                _state["last_ok"] = time.time()
                return {"ok": True, "message": "Carte du monde créée.", "countries": len(fc["features"])}
            except Exception as e:  # noqa: BLE001
                errors.append(f"{type(e).__name__}: {e}")
        _state["last_error"] = " | ".join(errors)[:300]
        return {"ok": False, "message": "Téléchargement impossible (pas de connexion ?). La carte simplifiée intégrée reste utilisée.",
                "detail": _state["last_error"]}
    finally:
        _state["running"] = False


def auto_fetch_async(out_path=None, opener=None):
    """Tentative silencieuse en arrière-plan, une seule fois par session, uniquement si le fichier manque."""
    if status(out_path)["available"] or _state["last_attempt"]:
        return False
    threading.Thread(target=fetch, kwargs={"out_path": out_path, "opener": opener}, daemon=True).start()
    return True
