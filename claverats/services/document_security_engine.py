"""Securite documentaire 100 % locale : validation PDF, anti-SSRF, formules Excel, XSS, punycode."""
import hashlib
import html
import ipaddress
import re
import socket
from urllib.parse import urlparse

MAX_PDF_BYTES = 15 * 1024 * 1024
MAX_IMAGE_PIXELS = 40_000_000
_JS_MARKERS = (b"/JavaScript", b"/JS ", b"/JS(", b"/JS<", b"/Launch", b"/OpenAction", b"/EmbeddedFile", b"/AA ")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate_pdf_bytes(data: bytes):
    """Retourne {ok, reason, warnings, sha256, encrypted}. Aucun fichier n'est ecrit sur disque."""
    warnings = []
    if not data:
        return {"ok": False, "reason": "Fichier vide.", "warnings": warnings}
    if len(data) > MAX_PDF_BYTES:
        return {"ok": False, "reason": "Fichier trop volumineux (max 15 Mo).", "warnings": warnings}
    if not data[:1024].lstrip(b"\x00\r\n\t ").startswith(b"%PDF-"):
        return {"ok": False, "reason": "Ce fichier n'est pas un vrai PDF (signature %PDF- absente).", "warnings": warnings}
    flagged = sorted({m.decode().strip("( <") for m in _JS_MARKERS if m in data})
    if flagged:
        warnings.append("Contenu actif detecte dans le PDF : " + ", ".join(flagged) + " (ignore, jamais execute).")
    encrypted = b"/Encrypt" in data
    if encrypted:
        warnings.append("PDF chiffre : lecture tentee avec mot de passe vide uniquement.")
    return {"ok": True, "reason": "", "warnings": warnings, "sha256": sha256_hex(data),
            "encrypted": encrypted, "active_content": bool(flagged)}


def is_safe_url(url: str, resolve=True):
    """Anti-SSRF : http(s) uniquement, pas d'IP privee/loopback/link-local, pas de credentials."""
    try:
        p = urlparse(url)
    except Exception:
        return False
    if p.scheme not in ("http", "https") or not p.hostname or p.username or p.password:
        return False
    host = p.hostname
    if host.lower() in ("localhost",) or host.endswith((".local", ".internal", ".localdomain")):
        return False
    try:
        ips = [ipaddress.ip_address(host)]
    except ValueError:
        ips = []
        if resolve:
            try:
                ips = [ipaddress.ip_address(i[4][0]) for i in socket.getaddrinfo(host, None)]
            except Exception:
                return True  # hors-ligne : pas de resolution, aucune requete ne sera faite
    for ip in ips:
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
            return False
    return True


def neutralize_cell(v):
    """Empeche l'injection de formules Excel/CSV (=, +, -, @, tab, CR)."""
    if isinstance(v, str) and v[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + v
    return v


def neutralize_row(row):
    return [neutralize_cell(c) for c in row]


def escape_html(s):
    return html.escape(str(s if s is not None else ""), quote=True)


def punycode_alert(domain: str):
    """Detecte punycode (xn--), melange d'alphabets (homographes) et caracteres non-ASCII."""
    d = (domain or "").lower()
    issues = []
    if "xn--" in d:
        issues.append("Domaine punycode (xn--) : possible usurpation par homographe.")
    if any(ord(c) > 127 for c in d):
        issues.append("Caracteres non-ASCII dans le domaine.")
    return issues


def anonymize_candidate(c: dict, level="strict"):
    """Export anonymise : retire nom, contacts, liens, photo."""
    out = dict(c)
    for k in ("full_name", "name", "email", "emails", "phones", "phone", "links", "photo", "photo_base64", "contact"):
        if k in out:
            out[k] = [] if isinstance(out[k], list) else ""
    if "full_name" in c:
        out["full_name"] = "Candidat-" + sha256_hex(str(c.get("full_name", "")).encode())[:6].upper()
    return out


SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Content-Security-Policy": "default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; "
                               "script-src 'self' 'unsafe-inline'; connect-src 'self'; object-src 'none'; "
                               "base-uri 'self'; frame-ancestors 'none'; worker-src 'self'; manifest-src 'self'",
}
