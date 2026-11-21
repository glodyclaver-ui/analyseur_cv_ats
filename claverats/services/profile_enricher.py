"""Enrichissement de profil : GitHub public (optionnel, en ligne) + analyse locale des liens.
Hors-ligne : retourne uniquement l'analyse locale, sans erreur."""
import re
from .document_security_engine import is_safe_url


def github_username(url):
    m = re.match(r"https?://(?:www\.)?github\.com/([A-Za-z0-9-]{1,39})/?$", url or "")
    return m.group(1) if m else None


def enrich(links, online=False, timeout=4):
    """links: [{url,type}]. Retourne {github:{...}|None, notes[], online}."""
    out = {"github": None, "notes": [], "online": False, "linkedin": None, "portfolio": []}
    for l in links or []:
        t, u = l.get("type"), l.get("url", "")
        if t == "linkedin":
            out["linkedin"] = u
            if "/in/" not in u:
                out["notes"].append("Lien LinkedIn non nominatif (pas de /in/).")
        elif t == "portfolio":
            out["portfolio"].append(u)
        elif t == "github" and not out["github"]:
            user = github_username(u)
            out["github"] = {"url": u, "user": user}
            if not user:
                out["notes"].append("Lien GitHub pointant vers un depot et non un profil.")
    g = out["github"]
    if online and g and g.get("user") and is_safe_url("https://api.github.com"):
        try:
            import requests
            r = requests.get("https://api.github.com/users/" + g["user"], timeout=timeout, headers={"Accept": "application/vnd.github+json"})
            if r.ok:
                j = r.json()
                g.update({"repos": j.get("public_repos"), "followers": j.get("followers"), "created": (j.get("created_at") or "")[:10]})
                out["online"] = True
        except Exception:
            out["notes"].append("GitHub injoignable : analyse locale uniquement.")
    if not out["linkedin"]:
        out["notes"].append("Aucun profil LinkedIn detecte.")
    return out
