"""Socle commun : stockage JSON local sur, valide, sauvegarde, restaurable."""
import hashlib
import json
import os
import shutil
import tempfile
import threading
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.environ.get("CLAVERATS_DATA_DIR") or os.path.join(BASE_DIR, "data")
STORE_DIR = os.path.join(DATA_DIR, "store")
BACKUP_DIR = os.path.join(DATA_DIR, "backups")
MAX_BACKUPS = 10
_LOCK = threading.RLock()


def _ensure():
    os.makedirs(STORE_DIR, exist_ok=True)
    os.makedirs(BACKUP_DIR, exist_ok=True)


def _sha(obj):
    raw = json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def store_path(name):
    safe = "".join(c for c in name if c.isalnum() or c in "-_")[:60] or "store"
    return os.path.join(STORE_DIR, safe + ".json")


def write_json(name, data):
    """Ecriture atomique + enveloppe verifiee + copie de securite .bak."""
    with _LOCK:
        _ensure()
        path = store_path(name)
        env = {"v": 1, "saved_at": int(time.time()), "sha256": _sha(data), "data": data}
        if os.path.exists(path):
            try:
                shutil.copy2(path, path + ".bak")
            except OSError:
                pass
        fd, tmp = tempfile.mkstemp(dir=STORE_DIR, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(env, f, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)
        return True


def _load_env(path):
    with open(path, "r", encoding="utf-8") as f:
        env = json.load(f)
    if not isinstance(env, dict) or "data" not in env:
        raise ValueError("enveloppe invalide")
    if env.get("sha256") != _sha(env["data"]):
        raise ValueError("empreinte SHA-256 incorrecte (fichier corrompu)")
    return env["data"]


def read_json(name, default=None):
    """Lecture validee. Si corrompu : bascule sur .bak, puis sur default."""
    with _LOCK:
        path = store_path(name)
        for p in (path, path + ".bak"):
            if os.path.exists(p):
                try:
                    return _load_env(p)
                except (ValueError, OSError, json.JSONDecodeError):
                    try:
                        shutil.move(p, p + ".corrupt-" + str(int(time.time())))
                    except OSError:
                        pass
        return default


def health():
    """Etat d'integrite de tous les fichiers du store."""
    _ensure()
    out = []
    for fn in sorted(os.listdir(STORE_DIR)):
        if not fn.endswith(".json"):
            continue
        p = os.path.join(STORE_DIR, fn)
        try:
            _load_env(p)
            out.append({"file": fn, "ok": True, "size": os.path.getsize(p)})
        except Exception as e:
            out.append({"file": fn, "ok": False, "error": str(e)[:80]})
    return out


def make_backup():
    with _LOCK:
        _ensure()
        snap = {}
        for fn in os.listdir(STORE_DIR):
            if fn.endswith(".json"):
                try:
                    snap[fn[:-5]] = _load_env(os.path.join(STORE_DIR, fn))
                except Exception:
                    continue
        env = {"v": 1, "created": int(time.time()), "sha256": _sha(snap), "stores": snap}
        name = "backup-%s.json" % time.strftime("%Y%m%d-%H%M%S")
        with open(os.path.join(BACKUP_DIR, name), "w", encoding="utf-8") as f:
            json.dump(env, f, ensure_ascii=False)
        files = sorted(x for x in os.listdir(BACKUP_DIR) if x.startswith("backup-"))
        for old in files[:-MAX_BACKUPS]:
            try:
                os.remove(os.path.join(BACKUP_DIR, old))
            except OSError:
                pass
        return name


def list_backups():
    _ensure()
    return sorted((x for x in os.listdir(BACKUP_DIR) if x.startswith("backup-")), reverse=True)


def restore_backup(name):
    if "/" in name or "\\" in name or not name.startswith("backup-"):
        raise ValueError("nom de sauvegarde invalide")
    with open(os.path.join(BACKUP_DIR, name), "r", encoding="utf-8") as f:
        env = json.load(f)
    if env.get("sha256") != _sha(env.get("stores", {})):
        raise ValueError("sauvegarde corrompue")
    for k, v in env["stores"].items():
        write_json(k, v)
    return len(env["stores"])


def purge_all():
    """Effacement total (panic wipe) des donnees locales."""
    with _LOCK:
        for d in (STORE_DIR, BACKUP_DIR):
            if os.path.isdir(d):
                shutil.rmtree(d, ignore_errors=True)
        _ensure()


def purge_older_than(days):
    cutoff = time.time() - days * 86400
    n = 0
    for d in (STORE_DIR, BACKUP_DIR):
        if os.path.isdir(d):
            for fn in os.listdir(d):
                p = os.path.join(d, fn)
                if os.path.isfile(p) and os.path.getmtime(p) < cutoff:
                    os.remove(p)
                    n += 1
    return n


# ---- utilitaires texte purs (sans dependance a app.py) ----
import re
import unicodedata
import math
from collections import Counter


def norm(t):
    t = unicodedata.normalize("NFD", str(t or "").lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def tokens(t):
    return [w for w in re.findall(r"[a-z0-9+#.]{2,}", norm(t)) if w not in _STOP]


_STOP = set("le la les de des du un une et en au aux pour par sur avec dans est sont que qui the and for with of to in a an on or as by at".split())


def tfidf_vectors(docs):
    toks = [Counter(tokens(d)) for d in docs]
    n = len(docs) or 1
    df = Counter()
    for c in toks:
        df.update(c.keys())
    idf = {w: math.log((1 + n) / (1 + k)) + 1 for w, k in df.items()}
    return [{w: tf * idf[w] for w, tf in c.items()} for c in toks], idf


def cosine(a, b):
    if not a or not b:
        return 0.0
    dot = sum(v * b.get(k, 0) for k, v in a.items())
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0
