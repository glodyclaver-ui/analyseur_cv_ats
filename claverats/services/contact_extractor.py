"""Extraction et classification des contacts/liens (texte + annotations PDF)."""
import re
from urllib.parse import urlparse

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?<!\d)(?:\+|00)?\d[\d\s().-]{7,17}\d")


def normalize_phone(p, default_cc="243"):
    """0812345678 -> +243 81 234 5678 (RDC par defaut) ; +33 6 ... conserve."""
    d = re.sub(r"[^\d+]", "", p)
    if d.startswith("00"):
        d = "+" + d[2:]
    if d.startswith("+"):
        digits = d[1:]
    elif d.startswith("0") and 9 <= len(d) <= 11:
        digits = default_cc + d[1:]
    elif len(d) == 9:
        digits = default_cc + d
    else:
        digits = d
    if not 9 <= len(digits) <= 15:
        return None
    cc = digits[:3] if digits[:3] in ("243", "242", "225", "221", "237", "212", "216", "213", "250", "257", "254", "255", "256") else digits[:2]
    rest = digits[len(cc):]
    return "+%s %s" % (cc, " ".join(rest[i:i + 3] for i in range(0, len(rest), 3)))


def classify_link(url):
    u = url.lower()
    host = (urlparse(u if "://" in u else "https://" + u).hostname or "")
    if "linkedin.com" in host:
        return "linkedin"
    if "github.com" in host or "gitlab.com" in host:
        return "github"
    if host.endswith(("wa.me", "whatsapp.com")):
        return "whatsapp"
    if any(x in host for x in ("behance.net", "dribbble.com", "medium.com")):
        return "portfolio"
    return "portfolio" if host else "other"


def extract(text, annotation_uris=()):
    emails = sorted({e.lower() for e in EMAIL_RE.findall(text or "")})
    for u in annotation_uris:
        if u.lower().startswith("mailto:"):
            emails.append(u[7:].split("?")[0].lower())
    phones = []
    for m in PHONE_RE.findall(text or ""):
        if re.search(r"(19|20)\d{2}\s*[-–]\s*(19|20)\d{2}", m):
            continue
        n = normalize_phone(m)
        if n and n not in phones:
            phones.append(n)
    links = []
    raw = list(annotation_uris) + re.findall(r"(?:https?://|www\.)[^\s<>\"')]+", text or "") \
        + re.findall(r"(?:linkedin\.com/in/|github\.com/)[^\s<>\"')]+", text or "")
    seen = set()
    for u in raw:
        if u.lower().startswith(("mailto:", "tel:")):
            continue
        u = u.rstrip(".,;")
        if not u.lower().startswith("http"):
            u = "https://" + u.lstrip("/")
        k = u.lower().rstrip("/")
        if k in seen:
            continue
        seen.add(k)
        links.append({"url": u, "type": classify_link(u)})
    return {"emails": sorted(set(emails)), "phones": phones, "links": links[:10]}
