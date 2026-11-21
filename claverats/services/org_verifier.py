"""Verification d'organisation : detection du nom, type (agence/employeur direct), domaine, TLD suspect,
punycode, prefixe telephonique vs pays, DNS/SSL facultatifs. Fonctionne hors-ligne (resultat 'non verifie')."""
import re
import socket
import ssl

from .document_security_engine import punycode_alert, is_safe_url

SUSPECT_TLD = {"xyz", "top", "click", "work", "loan", "gq", "tk", "ml", "cf", "ga", "icu", "buzz", "rest", "monster"}
FREE = {"gmail.com", "yahoo.com", "yahoo.fr", "hotmail.com", "outlook.com", "live.com", "icloud.com", "proton.me", "protonmail.com", "aol.com"}
AGENCY_WORDS = ("cabinet de recrutement", "agence de recrutement", "agence d'emploi", "chasseur de tetes", "headhunter",
                "recruitment agency", "staffing", "interim", "manpower", "randstad", "adecco", "michael page", "robert half", "pour le compte de", "client final")
SCAM_WORDS = ("frais de dossier", "payer pour", "western union", "mobile money avant", "virement", "carte cadeau", "gagnez",
              "sans experience 5000", "depot de garantie", "frais de formation obligatoire", "whatsapp uniquement")
PREFIX_COUNTRY = {"243": "RDC", "242": "Congo", "33": "France", "32": "Belgique", "225": "Cote d'Ivoire", "221": "Senegal",
                  "237": "Cameroun", "212": "Maroc", "216": "Tunisie", "213": "Algerie", "250": "Rwanda", "1": "USA/Canada", "44": "Royaume-Uni"}


def _norm(t):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", (t or "").lower()) if unicodedata.category(c) != "Mn")


def detect_org_name(text, emails=()):
    m = re.search(r"(?:entreprise|societe|organisation|employeur|cabinet|company|a propos de|about)\s*[:\-]\s*([^\n\r.;|]{2,60})", _norm(text) and text, re.I)
    if m:
        return m.group(1).strip()
    for e in emails:
        dom = e.split("@")[-1].lower()
        if dom not in FREE:
            return dom.split(".")[0].replace("-", " ").title()
    return ""


def domain_checks(domain, online=False):
    """Controles de domaine. online=True tente DNS + certificat SSL (echec = 'non verifie', jamais bloquant)."""
    d = (domain or "").lower().strip()
    res = {"domain": d, "flags": [], "dns": None, "ssl": None}
    if not d:
        return res
    tld = d.rsplit(".", 1)[-1]
    if tld in SUSPECT_TLD:
        res["flags"].append("Extension .%s frequemment utilisee dans des arnaques." % tld)
    if d in FREE:
        res["flags"].append("Adresse e-mail gratuite (non institutionnelle).")
    res["flags"] += punycode_alert(d)
    if d.count("-") >= 3 or len(d) > 40:
        res["flags"].append("Nom de domaine inhabituellement long/complexe.")
    if online and d not in FREE and is_safe_url("https://" + d):
        try:
            socket.setdefaulttimeout(3)
            res["dns"] = bool(socket.gethostbyname(d))
        except Exception:
            res["dns"] = False
        if res["dns"]:
            try:
                ctx = ssl.create_default_context()
                with socket.create_connection((d, 443), timeout=3) as s:
                    with ctx.wrap_socket(s, server_hostname=d) as ss:
                        res["ssl"] = bool(ss.getpeercert())
            except Exception:
                res["ssl"] = False
        else:
            res["flags"].append("Domaine introuvable (DNS).")
    return res


def phone_country(phone):
    d = re.sub(r"\D", "", phone or "")
    for L in (3, 2, 1):
        if d[:L] in PREFIX_COUNTRY:
            return PREFIX_COUNTRY[d[:L]]
    return ""


def verify(job_text, emails=(), links=(), phones=(), claimed_country="", online=False):
    """Retourne {org, kind, trust 0-100, level, flags[], checks[]}."""
    low = _norm(job_text)
    flags, checks, trust = [], [], 70
    org = detect_org_name(job_text, emails)
    kind = "agence" if any(w in low for w in AGENCY_WORDS) else "employeur direct"
    if kind == "agence":
        checks.append("Offre publiee par un intermediaire : demandez le nom du client final.")
    for w in SCAM_WORDS:
        if w in low:
            flags.append("Formulation a risque : « %s »." % w)
            trust -= 18
    doms = {e.split("@")[-1].lower() for e in emails if "@" in e}
    for u in links:
        m = re.match(r"https?://([^/\s:]+)", str(u))
        if m:
            doms.add(m.group(1).lower())
    if not doms:
        trust -= 10
        flags.append("Aucun contact institutionnel (domaine) fourni.")
    dres = []
    for d in sorted(doms):
        r = domain_checks(d, online)
        dres.append(r)
        trust -= 12 * len(r["flags"])
        flags += ["%s : %s" % (d, f) for f in r["flags"]]
        if r["ssl"]:
            trust += 8
    for p in phones:
        c = phone_country(p)
        if c and claimed_country and _norm(c) not in _norm(claimed_country) and _norm(claimed_country) not in _norm(c):
            flags.append("Prefixe telephonique (%s) different du pays annonce (%s)." % (c, claimed_country))
            trust -= 10
    if org and any(_norm(org).split()[0] in _norm(d) for d in doms if d not in FREE):
        trust += 10
        checks.append("Le nom de l'organisation correspond au domaine de contact.")
    trust = max(0, min(100, trust))
    return {"org": org or "Non determine", "kind": kind, "trust": trust,
            "level": "Fiable" if trust >= 70 else "A verifier" if trust >= 45 else "Risque eleve",
            "flags": flags[:10], "checks": checks, "domains": dres, "online_checked": bool(online)}
