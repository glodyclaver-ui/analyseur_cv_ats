"""Referentiels de competences par metier (JSON editable), detection du metier vise, exigences de l'employeur,
liste anti-bruit robuste et appariement CV <-> exigences ponderees.  100 % local, sans IA externe.

Fichier de configuration : data/config/skills_referentials.json (lisible et modifiable a la main ou depuis l'interface).
Tout est valide a la lecture ; en cas de fichier corrompu on revient a la copie .bak puis aux valeurs par defaut.
"""
import copy
import json
import os
import re
import shutil
import tempfile
import threading
import unicodedata

from . import _core
from .referential_defaults import DEFAULTS

CONFIG_DIR = os.path.join(_core.DATA_DIR, "config")
CONFIG_PATH = os.path.join(CONFIG_DIR, "skills_referentials.json")
SCHEMA_VERSION = 1
MIN_REQUIRED = 5          # sous ce nombre de competences detectees dans l'offre, on complete avec le metier (marque « estime »)
MAX_ESTIMATED = 8
_LOCK = threading.RLock()


def norm(t):
    t = unicodedata.normalize("NFD", str(t or "").lower().replace("’", "'"))
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


# ---------------------------------------------------------------------------------------------
# 1. Anti-bruit : mots qui ne sont JAMAIS des competences
# ---------------------------------------------------------------------------------------------
_STOP_RAW = """
a au aux avec ce ces cet cette ceci cela comme dans de des du elle elles en entre est et etc eux il ils je la le les leur leurs lors
ma mais me mes moi mon ne ni nos notre nous on ou par pas pour qu que quel quelle quels quelles qui sa sans se ses si son sur ta te
tes toi ton tu un une vos votre vous y ete etre avoir fait faire sont sera seront ainsi aussi autre autres bien bon bonne chez comme
donc encore enfin plus moins tres tout tous toute toutes trop afin ainsi alors apres avant depuis lors pendant selon sous vers
the and for with of to in on or as by at an is are be from this that your our we you will
competence competences competent requis requise requises exige exiges exigee exigees souhaite souhaitee souhaites atout atouts
maitrise maitriser connaissance connaissances capacite capacites experience experiences profil profils poste postes mission missions
candidat candidats candidate candidature offre offres emploi contrat cdi cdd stage salaire remuneration avantages avantage lieu
ville pays adresse date dates annee annees ans an mois jours jour semaine temps plein partiel horaire horaires description
entreprise societe organisation employeur recrute recrutons recherche recherchons cherche cherchons rejoindre rejoignez postuler
postulez envoyer envoyez transmettre transmettez dossier dossiers lettre motivation cv curriculum vitae diplome diplomes niveau
formation formations etudes francais anglais langue langues bac licence master doctorat bonne bons excellent excellente
responsable responsabilites taches activites activite principales principaux principale general generale generaux
travail travailler travaille sein equipe equipes disponible disponibilite immediate immediatement urgent urgente
etc etc. cf ex exemple exemples tel telephone mail email courriel contact contactez www http https com org net
lundi mardi mercredi jeudi vendredi samedi dimanche janvier fevrier mars avril mai juin juillet aout septembre octobre novembre decembre
h hrs usd fc cdf eur xaf xof
oui non nb ps
"""
STOPWORDS = {w for w in _STOP_RAW.split() if w}
# mots qui font d'un groupe de mots une phrase de boilerplate (et non une competence)
_BANNED_IN_PHRASE = {"salaire", "contrat", "poste", "offre", "candidat", "candidate", "vous", "nous", "notre", "votre", "vos", "nos",
                     "recrute", "recrutons", "recherche", "recherchons", "rejoindre", "postuler", "envoyer", "envoyez", "adresse", "email",
                     "telephone", "remuneration", "avantages", "date", "limite", "cdi", "cdd", "mois", "ans", "annees", "diplome", "niveau"}
_LEAD_INS = ["maitrise de la", "maitrise du", "maitrise des", "maitrise de l'", "maitrise de", "maitrise d'", "maitrise", "bonne maitrise de la",
             "bonne maitrise du", "bonne maitrise des", "bonne maitrise de", "bonne maitrise d'", "bonne connaissance de la", "bonne connaissance du",
             "bonne connaissance des", "bonne connaissance de", "bonne connaissance d'", "connaissance approfondie de", "connaissance de la",
             "connaissance du", "connaissance des", "connaissance de l'", "connaissance de", "connaissance d'", "connaissances en", "connaissance en",
             "capacite a", "capacite de", "aptitude a", "aptitude au", "experience en", "experience de", "experience dans", "experience avec",
             "experience du", "experience des", "experience d'", "competences en", "competence en", "competences requises", "competences",
             "savoir", "etre capable de", "etre capable d'", "sens de l'", "sens du", "sens de la", "esprit d'", "esprit de", "bonne", "bon",
             "pratique de", "pratique des", "utilisation de", "utilisation du", "utilisation des", "utilisation d'", "good knowledge of", "knowledge of",
             "experience with", "proficiency in", "ability to", "strong", "excellent", "excellente", "tres bonne", "tres bon"]
_LEAD_INS.sort(key=len, reverse=True)
_ACRONYM = re.compile(r"^[A-Z][A-Z0-9+#./&-]{1,9}$")


def is_noise(token):
    """True si ce mot / ce groupe de mots ne peut pas etre une competence."""
    t = norm(token).strip(" .,:;-–—()[]\"'")
    if not t or len(t) < 2:
        return True            # « D », « R » isoles, vide…
    if t.isdigit() or re.fullmatch(r"[\d\W_]+", t):
        return True
    words = re.findall(r"[a-z0-9+#']+", t)
    if not words:
        return True
    if all(w in STOPWORDS for w in words):
        return True
    if len(words) == 1 and (words[0] in STOPWORDS or len(words[0]) <= 2 and not re.fullmatch(r"(c|r|go|bi|ia|ai|ml|qa|ui|ux|it|ci|cd)", words[0])):
        return True
    if words[0] in ("etc", "etc.") or words[-1] in ("etc", "etc."):
        return True
    return False


def clean_skill_list(skills):
    """Retire le bruit et les doublons (insensible a la casse/accents), conserve l'ordre."""
    out, seen = [], set()
    for s in skills or []:
        s2 = str(s).strip().strip(".,;:")
        k = norm(s2)
        if not s2 or k in seen or is_noise(s2):
            continue
        seen.add(k)
        out.append(s2)
    return out


def phrases_from_requirement_line(line):
    """Extrait des competences (groupes de 1 a 5 mots) d'une ligne d'exigences, au lieu de mots isoles."""
    l = re.sub(r"^[\s\-•*▪➢✔✓►▶◦·\d+.)]+", "", str(line or "")).strip()
    if not l:
        return []
    l = re.sub(r"^[^:]{0,40}(comp[eé]tences?|profil|exigences?|requis|qualifications?)[^:]{0,30}:\s*", "", l, flags=re.I)
    parts = re.split(r"\s*[,;/•·|]\s*|\s+(?:et|ou|and|or)\s+|\s+&\s+", l)
    out = []
    for p in parts:
        p = p.strip(" .:-–—()[]\"'")
        changed = True
        while changed and p:
            changed = False
            np_ = norm(p)
            for lead in _LEAD_INS:
                if np_.startswith(lead + " ") or np_ == lead:
                    p = p[len(lead):].strip(" .:-–—'")
                    changed = True
                    break
        words = p.split()
        if not (1 <= len(words) <= 5) or not (3 <= len(p) <= 42):
            continue
        nw = re.findall(r"[a-z0-9']+", norm(p))
        if any(w in _BANNED_IN_PHRASE for w in nw) or re.search(r"[:$€@]|\d\s*(?:k|usd|fc|eur)\b", p.lower()):
            continue
        if is_noise(p):
            continue
        if len(words) == 1 and not (_ACRONYM.match(words[0]) or len(words[0]) >= 4):
            continue
        disp = p if _ACRONYM.match(p) else p[0].upper() + p[1:]
        if disp not in out:
            out.append(disp)
    return out


# ---------------------------------------------------------------------------------------------
# 2. Configuration JSON (lecture/ecriture validees)
# ---------------------------------------------------------------------------------------------
def validate_config(cfg):
    """Retourne (ok, erreurs). Verifie la structure sans rien modifier."""
    errs = []
    if not isinstance(cfg, dict) or not isinstance(cfg.get("sectors"), dict) or not cfg["sectors"]:
        return False, ["Structure invalide : « sectors » manquant."]
    for sk, sec in cfg["sectors"].items():
        if not isinstance(sec, dict) or not isinstance(sec.get("roles"), dict):
            errs.append("Secteur « %s » invalide." % sk)
            continue
        for rk, role in sec["roles"].items():
            if not isinstance(role, dict) or not isinstance(role.get("skills"), list):
                errs.append("Métier « %s » invalide." % rk)
                continue
            for i, s in enumerate(role["skills"]):
                if not isinstance(s, dict) or not str(s.get("name", "")).strip():
                    errs.append("%s/%s : compétence n°%d sans nom." % (sk, rk, i + 1))
                    continue
                w = s.get("weight", 2)
                if not isinstance(w, (int, float)) or not 0.5 <= w <= 5:
                    errs.append("%s/%s/%s : coefficient hors de 0,5-5." % (sk, rk, s["name"]))
    return (not errs), errs


def _write_plain(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path):
        try:
            shutil.copy2(path, path + ".bak")
        except OSError:
            pass
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


_CACHE = {"mtime": None, "cfg": None, "path": None}


def load():
    """Charge la configuration (cache par date de modification). Cree le fichier par defaut si absent."""
    with _LOCK:
        path = os.path.join(_core.DATA_DIR, "config", "skills_referentials.json")
        if not os.path.exists(path):
            _write_plain(path, DEFAULTS)
        mt = os.path.getmtime(path)
        if _CACHE["path"] == path and _CACHE["mtime"] == mt and _CACHE["cfg"]:
            return _CACHE["cfg"]
        cfg = None
        for p in (path, path + ".bak"):
            if os.path.exists(p):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        c = json.load(f)
                    ok, _ = validate_config(c)
                    if ok:
                        cfg = c
                        break
                except (OSError, ValueError):
                    continue
        if cfg is None:
            cfg = copy.deepcopy(DEFAULTS)
        _CACHE.update(mtime=mt, cfg=cfg, path=path)
        return cfg


def save(cfg):
    ok, errs = validate_config(cfg)
    if not ok:
        raise ValueError("; ".join(errs[:5]))
    cfg["version"] = SCHEMA_VERSION
    with _LOCK:
        _write_plain(os.path.join(_core.DATA_DIR, "config", "skills_referentials.json"), cfg)
        _CACHE["cfg"] = None
    return True


def reset_defaults():
    with _LOCK:
        _write_plain(os.path.join(_core.DATA_DIR, "config", "skills_referentials.json"), DEFAULTS)
        _CACHE["cfg"] = None
    return load()


def overview():
    """Liste compacte : secteurs -> metiers -> competences (pour l'editeur de l'interface)."""
    cfg = load()
    return [{"sector": sk, "label": s.get("label", sk), "roles": [
        {"role": rk, "label": r.get("label", rk), "keywords": r.get("title_keywords", []), "skills": r["skills"]}
        for rk, r in s["roles"].items()]} for sk, s in cfg["sectors"].items()]


def _find_role(cfg, sector, role):
    try:
        return cfg["sectors"][sector]["roles"][role]
    except KeyError:
        raise ValueError("Métier introuvable.")


def upsert_skill(sector, role, name, weight=2, aliases=None, old_name=None):
    name = str(name or "").strip()
    if not name or is_noise(name):
        raise ValueError("Nom de compétence invalide.")
    try:
        weight = float(weight)
    except (TypeError, ValueError):
        raise ValueError("Coefficient invalide.")
    if not 0.5 <= weight <= 5:
        raise ValueError("Le coefficient doit être compris entre 0,5 et 5.")
    cfg = copy.deepcopy(load())
    r = _find_role(cfg, sector, role)
    al = [a.strip() for a in (aliases or []) if a and a.strip()]
    target = norm(old_name or name)
    for s in r["skills"]:
        if norm(s["name"]) == target:
            s.update(name=name, weight=weight, aliases=al or s.get("aliases", []))
            break
    else:
        r["skills"].append({"name": name, "weight": weight, "aliases": al})
    save(cfg)
    return True


def delete_skill(sector, role, name):
    cfg = copy.deepcopy(load())
    r = _find_role(cfg, sector, role)
    n0 = len(r["skills"])
    r["skills"] = [s for s in r["skills"] if norm(s["name"]) != norm(name)]
    if len(r["skills"]) == n0:
        raise ValueError("Compétence introuvable.")
    save(cfg)
    return True


def add_role(sector, role_key, label, keywords):
    cfg = copy.deepcopy(load())
    if sector not in cfg["sectors"]:
        raise ValueError("Secteur introuvable.")
    rk = re.sub(r"[^a-z0-9_]+", "_", norm(role_key or label)).strip("_")
    if not rk or not str(label).strip():
        raise ValueError("Nom de métier requis.")
    cfg["sectors"][sector]["roles"].setdefault(rk, {"label": str(label).strip(), "title_keywords": [k.strip().lower() for k in keywords if k.strip()], "skills": []})
    save(cfg)
    return rk


# ---------------------------------------------------------------------------------------------
# 3. Detection du metier et exigences de l'employeur
# ---------------------------------------------------------------------------------------------
def _contains(text_norm, kw):
    k = norm(kw)
    return bool(k) and re.search(r"(?<![a-z0-9])" + re.escape(k) + r"(?![a-z0-9])", text_norm) is not None


def detect_role(text, title_hint=""):
    """Metier le plus probable : mots-cles du titre (x4 si dans le titre/les 300 1ers caracteres, x1 ailleurs) + competences du metier trouvees."""
    cfg = load()
    head = norm((title_hint + " " + text[:300]))
    body = norm(text)
    ranked = []
    for sk, sec in cfg["sectors"].items():
        for rk, r in sec["roles"].items():
            sc = 0.0
            for kw in r.get("title_keywords", []):
                if _contains(head, kw):
                    sc += 4
                elif _contains(body, kw):
                    sc += 1
            names = [s for s in r["skills"]]
            hits = sum(1 for s in names if any(_contains(body, a) for a in [s["name"]] + s.get("aliases", [])))
            sc += 0.6 * hits
            if sc > 0:
                ranked.append((sc, sk, rk, r.get("label", rk), hits, len(names)))
    ranked.sort(reverse=True)
    if not ranked or ranked[0][0] < 3:
        return {"detected": False, "sector": None, "role": None, "label": "", "confidence": 0, "alternatives": []}
    top = ranked[0]
    second = ranked[1][0] if len(ranked) > 1 else 0
    conf = max(0.2, min(0.95, (top[0] - second * 0.5) / (top[0] + 4)))
    return {"detected": True, "sector": top[1], "role": top[2], "label": top[3], "confidence": round(conf, 2),
            "alternatives": [{"role": r[2], "label": r[3]} for r in ranked[1:3]]}


def _skill_in_text(text_norm, spec):
    return any(_contains(text_norm, a) for a in [spec["name"]] + list(spec.get("aliases", [])))


# ---- Nettoyage des exigences dynamiques : fragments de phrases -> competences propres --------------------
_DET = ("les", "des", "le", "la", "l'", "un", "une", "du", "de", "d'", "leur", "leurs", "vos", "votre", "notre", "nos", "ses", "son", "sa", "ce", "cet", "cette", "ces")
_POSSESSIVE = {"leur", "leurs", "vos", "votre", "notre", "nos", "ses", "son", "sa"}
_VERB_LEAD = re.compile(r"^(aider a|aider|appuyer|maintenir|organiser|organisant|compiler|collecter|creer|assurer|participer a|participer|contribuer a|contribuer|realiser|effectuer|preparer|gerer|elaborer|rediger|produire|saisir|suivre|animer|coordonner|developper|mettre en place|mettre a jour|faire|etre|avoir|pouvoir|savoir|capacite|aptitude)\b\s*")
_FILLER = {"pertinent", "pertinents", "pertinente", "pertinentes", "partage", "partages", "partagee", "partagees", "partagé", "partagés", "generales", "generale", "organisation", "organisationnelle", "organisationnelles", "equipes", "terrain"}
_GENERIC_ONLY = {"tableaux", "graphiques", "outils", "supports", "ateliers", "dossiers", "rapports", "donnees", "informations", "information", "documents", "taches", "activites", "missions", "objectifs", "normes", "enseignement", "referentiels", "presentations", "formation", "organisation", "equipe", "projet", "projets"}


def tidy_one(name):
    """Fragment de phrase -> competence propre, ou None si ce n'en est pas une."""
    raw = str(name or "").strip()
    n = norm(raw)
    if not n:
        return None
    if re.search(r"(^|\s)(leur|leurs|vos|votre|notre|nos|ses)(\s|$)", n):
        return None
    changed = True
    while changed:
        changed = False
        m = _VERB_LEAD.match(n)
        if m and m.end() < len(n):
            n = n[m.end():]; changed = True
        elif m:
            return None                     # « Aider à collecter », « Compiler » : un verbe seul n'est pas une competence
        for d in sorted(_DET, key=len, reverse=True):
            if n.startswith(d + " ") or (d.endswith("'") and n.startswith(d)):
                n = n[len(d):].lstrip(" '"); changed = True; break
    words = re.findall(r"[a-z0-9+#']+", n)
    if not words or len(words) > 4:
        return None
    if any(w in _FILLER for w in words):
        return None
    if len(words) == 1 and words[0] in _GENERIC_ONLY:
        return None
    if all(w in _GENERIC_ONLY or w in STOPWORDS for w in words):
        return None
    # on garde la graphie d'origine : on reprend les derniers mots du texte brut correspondant au reste normalise
    toks = raw.replace("’", "'").split()
    keep = []
    for k in range(len(toks)):
        if norm(" ".join(toks[k:])) == n:
            keep = toks[k:]; break
    disp = " ".join(keep) if keep else n
    disp = disp.strip(" .,;:'")
    return disp if _ACRONYM.match(disp) else disp[:1].upper() + disp[1:]


def drop_contained(items):
    """Retire « Nettoyage » si « Nettoyage et qualite des donnees » est present (idem « Excel » / « Excel avance »)."""
    keys = [norm(x["name"]) for x in items]
    out = []
    for i, it in enumerate(items):
        k = keys[i]
        if any(j != i and k != keys[j] and re.search(r"(?<![a-z0-9])" + re.escape(k) + r"(?![a-z0-9])", keys[j]) for j in range(len(items))) and it["source"] == "offre" and not it.get("aliases"):
            continue
        out.append(it)
    return out


def build_requirements(job_text, detected_skills, role_info=None):
    """Competences REELLEMENT attendues par l'employeur.
    1. celles ecrites dans l'offre (liste nettoyee + competences du referentiel du metier retrouvees dans l'offre) ;
    2. si moins de MIN_REQUIRED, completees par les competences essentielles du metier, marquees « estime ».
    Retourne {role, required:[{name, weight, aliases, source}], detected_count, estimated_count, confidence}."""
    role_info = role_info or detect_role(job_text)
    tn = norm(job_text)
    required, seen = [], set()

    def add(name, weight, aliases, source):
        k = norm(name)
        if k in seen:
            return
        seen.add(k)
        required.append({"name": name, "weight": weight, "aliases": list(aliases), "source": source})

    spec_list = []
    if role_info.get("detected"):
        spec_list = load()["sectors"][role_info["sector"]]["roles"][role_info["role"]]["skills"]
        for s in spec_list:
            if _skill_in_text(tn, s):
                add(s["name"], float(s.get("weight", 2)), s.get("aliases", []), "offre")
    # competences du referentiel du metier dont un synonyme equivaut a un nom detecte par ailleurs
    alias_to_spec = {}
    for s in spec_list:
        for a in [s["name"]] + s.get("aliases", []):
            alias_to_spec[norm(a)] = s
    for name in clean_skill_list(detected_skills):
        spec = alias_to_spec.get(norm(name))
        if spec:
            add(spec["name"], float(spec.get("weight", 2)), spec.get("aliases", []), "offre")
        else:
            tidy = tidy_one(name)
            if tidy and not is_noise(tidy):
                add(tidy, 2.0, [], "offre")
    required[:] = drop_contained(required)
    detected_count = len(required)
    estimated = 0
    if role_info.get("detected") and detected_count < MIN_REQUIRED:
        for s in sorted(spec_list, key=lambda x: -float(x.get("weight", 2))):
            if len(required) >= max(MIN_REQUIRED + 3, MAX_ESTIMATED) or estimated >= MAX_ESTIMATED:
                break
            if norm(s["name"]) in seen or float(s.get("weight", 2)) < 2:
                continue
            add(s["name"], float(s.get("weight", 2)), s.get("aliases", []), "estimé (métier)")
            estimated += 1
    return {"role": role_info, "required": required, "detected_count": detected_count, "estimated_count": estimated}


def match_cv(cv_text, requirements):
    """Apparie le CV aux exigences. Retourne matched/missing (noms) et le dict des coefficients."""
    tn = norm(cv_text)
    matched, missing, weights = [], [], {}
    for r in requirements["required"]:
        weights[r["name"].lower()] = r["weight"]
        (matched if _skill_in_text(tn, r) else missing).append(r["name"])
    return {"matched": matched, "missing": missing, "weights": weights,
            "estimated": [r["name"] for r in requirements["required"] if r["source"].startswith("estim")]}


def weighted_ratio(matched, missing, weights):
    wm = sum(weights.get(m.lower(), 2.0) for m in matched)
    wt = wm + sum(weights.get(m.lower(), 2.0) for m in missing)
    return (wm / wt) if wt else None
