"""Facade securite : en-tetes, CSRF, limitation de debit, PIN local, journal."""
import hashlib
import hmac
import os
import secrets
import time
from collections import defaultdict, deque

from .document_security_engine import SECURITY_HEADERS, escape_html, neutralize_cell, is_safe_url, anonymize_candidate  # noqa: F401
from . import _core, audit_trail_manager

_SECRET = secrets.token_hex(32)  # regenere a chaque demarrage : jetons CSRF jamais persistes
_HITS = defaultdict(deque)


def csrf_token():
    ts = str(int(time.time() // 3600))
    return ts + "." + hmac.new(_SECRET.encode(), ts.encode(), hashlib.sha256).hexdigest()[:32]


def csrf_valid(tok):
    try:
        ts, sig = (tok or "").split(".", 1)
    except ValueError:
        return False
    if abs(int(time.time() // 3600) - int(ts)) > 6:
        return False
    return hmac.compare_digest(sig, hmac.new(_SECRET.encode(), ts.encode(), hashlib.sha256).hexdigest()[:32])


def rate_limited(key, limit=60, window=60):
    q = _HITS[key]
    now = time.time()
    while q and now - q[0] > window:
        q.popleft()
    if len(q) >= limit:
        return True
    q.append(now)
    return False


def set_pin(pin):
    salt = os.urandom(16).hex()
    h = hashlib.pbkdf2_hmac("sha256", str(pin).encode(), salt.encode(), 120000).hex()
    _core.write_json("security", {"salt": salt, "hash": h})
    audit_trail_manager.log("pin_set")


def has_pin():
    return bool(_core.read_json("security"))


def check_pin(pin):
    s = _core.read_json("security")
    if not s:
        return True
    h = hashlib.pbkdf2_hmac("sha256", str(pin).encode(), s["salt"].encode(), 120000).hex()
    ok = hmac.compare_digest(h, s["hash"])
    audit_trail_manager.log("pin_ok" if ok else "pin_fail")
    return ok


def panic_wipe():
    _core.purge_all()
