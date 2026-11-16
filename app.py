import io
import csv
import re
import base64
import unicodedata
from datetime import datetime, date
from flask import Flask, render_template, request, jsonify, send_file
from pypdf import PdfReader
from PIL import Image
import requests
from bs4 import BeautifulSoup
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

app = Flask(__name__)

REF_YEAR = 2026
REF_MONTH = 11

SKILLS_DB = {
    "Langages & Web": [
        "python", "javascript", "typescript", "html", "html5", "css", "css3",
        "php", "java", "c#", "c++", "sql", "bash", "dart", "kotlin", "swift"
    ],
    "Frameworks & Bibliothèques": [
        "flask", "django", "fastapi", "react", "vue", "angular", "next.js",
        "node.js", "express", "laravel", "symfony", "bootstrap", "tailwind",
        "beautifulsoup", "pillow", "pandas", "numpy", "scikit-learn", "flutter"
    ],
    "Bases de données & Cloud": [
        "mysql", "postgresql", "sqlite", "mongodb", "redis", "firebase",
        "docker", "kubernetes", "aws", "azure", "google cloud", "linux", "nginx"
    ],
    "Outils, Design & Gestion": [
        "git", "github", "gitlab", "ci/cd", "api rest", "graphql", "seo",
        "cybersécurité", "rgpd", "agile", "scrum", "figma", "ui/ux", "photoshop",
        "illustrator", "indesign", "excel", "word", "power bi", "sage", "sap", "comptabilité", "logistique"
    ]
}

PROFESSION_KEYWORDS = [
    "développeur web", "développeur full stack", "développeur python", "développeur mobile",
    "administrateur systèmes et réseaux", "technicien informatique", "technicien maintenance",
    "ingénieur logiciel", "data analyst", "analyste de données", "infographiste", "designer ui/ux",
    "chef de projet", "comptable", "auditeur", "logisticien", "chargé de communication",
    "responsable rh", "assistant administratif", "consultant it", "formateur bureautique"
]

EDUCATION_LEVELS = [
    ("Doctorat / PhD (Bac+8)", 5, ["doctorat", "phd", "bac+8"]),
    ("Licence (Ancien Système) / Master / Ingénieur (Bac+5)", 4, [
        "master", "ingenieur", "bac+5", "m2", "mba", "dea", "l2", "licence ancien systeme"
    ]),
    ("Licence (LMD) / Bachelor / Graduat (Bac+3)", 3, [
        "licence", "bachelor", "bac+3", "l3", "graduat", "baccalaureat universitaire", "g3"
    ]),
    ("BTS / DUT / DEUG (Bac+2)", 2, ["bts", "dut", "bac+2", "deug"]),
    ("Diplôme d'État / Baccalauréat (Secondaire)", 1, ["diplome d'etat", "baccalaureat", "lycee", "humanites", "bac"])
]

LANGUAGES_LIST = ["francais", "anglais", "lingala", "swahili", "espagnol", "allemand", "portugais", "chinois", "arabe"]
FREE_EMAIL_DOMAINS = {"gmail.com", "yahoo.fr", "yahoo.com", "hotmail.com", "hotmail.fr", "outlook.com", "live.com"}
HR_PREFIXES = ("rh", "hr", "recrutement", "recruitment", "carrieres", "careers", "jobs", "talent", "emploi")

TRUSTED_JOB_PLATFORMS = (
    "linkedin.com", "indeed.com", "reliefweb.int", "unjobnet.org", "unjobs.org",
    "mediacongo.net", "emploi.cd", "talenteo.com", "welcometothejungle.com",
    "glassdoor.com", "apec.fr", "francetravail.fr", "greenhouse.io", "lever.co", "workday.com"
)

COUNTRY_CODES = {
    "243": "RDC (+243)", "242": "Congo (+242)", "1": "USA/CA (+1)",
    "33": "France (+33)", "32": "Belgique (+32)", "41": "Suisse (+41)"
}

MONTHS_MAP = {
    "janv": 1, "janvier": 1, "jan": 1, "january": 1,
    "fevr": 2, "fevrier": 2, "feb": 2, "february": 2,
    "mars": 3, "mar": 3, "march": 3,
    "avr": 4, "avril": 4, "apr": 4, "april": 4,
    "mai": 5, "may": 5,
    "juin": 6, "jun": 6, "june": 6,
    "juil": 7, "juillet": 7, "jul": 7, "july": 7,
    "aout": 8, "aug": 8, "august": 8,
    "sept": 9, "septembre": 9, "sep": 9, "september": 9,
    "oct": 10, "octobre": 10, "october": 10,
    "nov": 11, "novembre": 11, "november": 11,
    "dec": 12, "decembre": 12, "december": 12
}

def normalize_text(text):
    if not text:
        return ""
    text = text.lower()
    text = unicodedata.normalize("NFD", text)
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def extract_text_from_pdf(file_bytes):
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
        pages_text = []
        for page in reader.pages:
            t = page.extract_text()
            if t:
                pages_text.append(t)
        return "\n".join(pages_text)
    except Exception:
        return ""


def extract_cv_photo_base64(file_bytes):
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
        for page in reader.pages[:2]:
            if hasattr(page, "images"):
                for img in page.images:
                    try:
                        pil_img = Image.open(io.BytesIO(img.data))
                        w, h = pil_img.size
                        if w >= 60 and h >= 60:
                            pil_img = pil_img.convert("RGB")
                            out = io.BytesIO()
                            pil_img.save(out, format="PNG")
                            b64 = base64.b64encode(out.getvalue()).decode("utf-8")
                            return f"data:image/png;base64,{b64}"
                    except Exception:
                        continue
    except Exception:
        pass
    return None


def extract_text_from_url(url):
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0 Safari/537.36"}
    resp = requests.get(url, headers=headers, timeout=12)
    if resp.status_code in (401, 403, 429):
        raise ValueError("Site protégé (403/429). Collez directement le texte de l'offre ou importez son PDF.")
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
        tag.decompose()
    clean_text = soup.get_text(separator="\n", strip=True)
    if len(clean_text) < 100:
        raise ValueError("Contenu trop court ou protégé. Collez directement le texte de l'offre.")
    return clean_text, resp.url

def extract_clean_phones(text):
    if not text:
        return []
    cleaned = re.sub(r"\b\d{1,2}[/.-]\d{1,2}[/.-]20\d{2}\b", " ", text)
    pattern = r"(?:(?:\+|00)\s*\d{1,3}[\s.-]*)?(?:\(\s*\+?\d{1,4}\s*\)[\s.-]*)?(?:\d[\s.-]*){8,14}"
    valid = []
    for m in re.findall(pattern, cleaned):
        cand = m.strip()
        digits = re.sub(r"\D", "", cand)
        if 9 <= len(digits) <= 15 and not re.match(r"^(?:19|20)\d{6}$", digits):
            tag = ""
            for code, label in sorted(COUNTRY_CODES.items(), key=lambda x: len(x), reverse=True):
                if digits.startswith(code) or cand.startswith(f"+{code}"):
                    tag = f" [{label}]"
                    break
            val = f"{cand}{tag}"
            if val not in valid:
                valid.append(val)
    return valid[:2]


def extract_candidate_name(cv_text, fallback_filename=""):
    ignored = {
        "curriculum", "vitae", "cv", "resume", "profil", "contact", "telephone", "email",
        "adresse", "developpeur", "developer", "ingenieur", "consultant", "technicien",
        "manager", "analyste", "designer", "web", "full", "stack", "kinshasa", "paris",
        "rdc", "congo", "france", "experience", "formation", "competences"
    }
    lines = [l.strip() for l in cv_text.splitlines() if l.strip()]
    for line in lines[:10]:
        if "@" in line or "http" in line.lower() or re.search(r"\d{3,}", line):
            continue
        clean = re.sub(r"[^a-zA-ZÀ-ÿ\s-]", " ", line).strip()
        words = [w for w in clean.split() if len(w) >= 2]
        if 2 <= len(words) <= 4 and not any(normalize_text(w) in ignored for w in words):
            full = " ".join(w.capitalize() for w in words)
            return full, "".join(w.upper() for w in words[:2])

    email_m = re.search(r"([a-zA-Z]{2,})[._-]([a-zA-Z]{2,})@", cv_text)
    if email_m:
        p1, p2 = email_m.group(1).capitalize(), email_m.group(2).capitalize()
        return f"{p1} {p2}", f"{p1}{p2}"

    if fallback_filename:
        base = re.sub(r"\.pdf$", "", fallback_filename, flags=re.IGNORECASE)
        base = re.sub(r"(?:cv|resume|curriculum|vitae)[_\s-]*", "", base, flags=re.IGNORECASE)
        words = [w.capitalize() for w in re.split(r"[_\s-]+", base) if len(w) >= 2]
        if words:
            return " ".join(words[:3]), "".join(w.upper() for w in words[:2])

    return "Candidat", "CV"


def parse_single_date_token(token_str, is_end=False):
    norm = normalize_text(token_str).strip()
    if not norm:
        return None
    present_keys = ("jusqu'a ce jour", "jusqua ce jour", "a ce jour", "present", "actuel", "en cours", "depuis", "current", "now", "ongoing")
    if any(k in norm for k in present_keys):
        return (REF_YEAR, REF_MONTH)

    m_num = re.search(r"\b(0?[1-9]|1[0-2])[/.-](20\d{2})\b", norm)
    if m_num:
        return (int(m_num.group(2)), int(m_num.group(1)))

    year_m = re.search(r"\b(20\d{2})\b", norm)
    if year_m:
        y = int(year_m.group(1))
        for m_name, m_val in MONTHS_MAP.items():
            if re.search(r"\b" + m_name + r"\b", norm):
                return (y, m_val)
        if is_end:
            return (REF_YEAR, REF_MONTH) if y >= REF_YEAR else (y, 12)
        return (y, 1)
    return None


def extract_experience_years(cv_text):
    clean_text = re.sub(r"\([^)]*\)", " ", cv_text)
    work_lines = []
    in_edu = False
    for line in clean_text.splitlines():
        nl = normalize_text(line).strip()
        if re.match(r"^(?:formation|education|etudes|diplomes)\b", nl):
            in_edu = True
            continue
        if re.match(r"^(?:experience|parcours professionnel|experiences|emplois|stages|competences)\b", nl):
            in_edu = False
        if not in_edu:
            work_lines.append(line)

    work_text = "\n".join(work_lines)
    pat = re.compile(
        r"((?:[0-3]?\d\s+)?(?:[a-zA-Zéû]+\.?\s+)?20\d{2}|(?:0?[1-9]|1[0-2])[/.-]20\d{2})"
        r"\s*(?:-|–|—|/|au|à|to)\s*"
        r"((?:[0-3]?\d\s+)?(?:[a-zA-Zéû]+\.?\s+)?20\d{2}|(?:0?[1-9]|1[0-2])[/.-]20\d{2}|"
        r"jusqu['’]?\s*à\s*ce\s*jour|à\s*ce\s*jour|pr[ée]sent|actuel(?:lement)?|en\s*cours|present|current|now|ongoing)",
        re.IGNORECASE
    )

    intervals = []
    for s_tok, e_tok in pat.findall(work_text):
        s_ym = parse_single_date_token(s_tok, is_end=False)
        e_ym = parse_single_date_token(e_tok, is_end=True)
        if s_ym and e_ym:
            s_idx = s_ym[0] * 12 + s_ym[1]
            e_idx = max(s_idx + 1, e_ym[0] * 12 + e_ym[1] + 1)
            intervals.append([s_idx, e_idx])

    if not intervals:
        norm = normalize_text(work_text)
        m = re.findall(r"(\d+)\s*(?:\+|ans|annees)\s*(?:d['’]?experience)", norm)
        return max([int(x) for x in m if 0 < int(x) <= 35], default=0)

    intervals.sort(key=lambda x: x[0])
    merged = []
    for iv in intervals:
        if not merged or iv[0] > merged[-1][1]:
            merged.append(iv)
        else:
            merged[-1][1] = max(merged[-1][1], iv[1])

    total_months = sum(m[1] - m[0] for m in merged)
    return round(total_months / 12, 1)

def detect_education(text):
    norm = normalize_text(text)
    for label, rank, keywords in EDUCATION_LEVELS:
        for kw in keywords:
            if re.search(r"(?<![a-z0-9])" + re.escape(kw) + r"(?![a-z0-9])", norm):
                return label, rank
    return "Non précisé", 0


def detect_languages(text):
    norm = normalize_text(text)
    return ["Français" if l == "francais" else l.capitalize() for l in LANGUAGES_LIST if re.search(r"\b" + l + r"\b", norm)]


def extract_skills(text):
    norm_text = normalize_text(text)
    found_skills = {}
    for category, skills_list in SKILLS_DB.items():
        matched = []
        for skill in skills_list:
            norm_skill = normalize_text(skill)
            if re.search(r"(?<![a-z0-9])" + re.escape(norm_skill) + r"(?![a-z0-9])", norm_text):
                matched.append(skill.upper() if len(skill) <= 3 else skill.capitalize())
        if matched:
            found_skills[category] = sorted(list(set(matched)))
    all_flat = sorted({s for sub in found_skills.values() for s in sub})
    return found_skills, all_flat


def extract_professions_and_objective(cv_text, all_skills):
    norm = normalize_text(cv_text)
    roles = [r.title() for r in PROFESSION_KEYWORDS if normalize_text(r) in norm]
    main_role = roles[0] if roles else "Profil Technique / Polyvalent"
    sec_roles = roles[1:4]

    obj_m = re.search(r"(?:profil|objectif|a propos|resume|accroche|summary)\s*[:\-]?\s*([^\n]{25,220})", cv_text, re.IGNORECASE)
    if obj_m:
        objective = obj_m.group(1).strip()
    else:
        sk = ", ".join(all_skills[:4]) if all_skills else "ses compétences métier"
        objective = f"Professionnel maîtrisant {sk}, prêt à contribuer aux projets de l'organisation."
    return main_role, sec_roles, objective


def extract_universal_location(text):
    if not text:
        return ""
    for pat in [r"(?:lieu|location|ville|pays|bas[eé]\s+[aà]|poste\s+[aà])\s*[:\-]\s*([^\n\r.;|]{2,45})", r"(?:adresse|address)\s*[:\-]\s*([^\n\r;|]{3,50})"]:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return ""


def evaluate_recruiter_trust(emails, links=None):
    links = links or []
    best = 50
    reason = "Aucun e-mail professionnel ni lien officiel reconnu — 50 % de vigilance"
    for email in emails:
        local_p, _, domain = email.lower().partition("@")
        if domain and domain not in FREE_EMAIL_DOMAINS:
            if any(local_p.startswith(p) for p in HR_PREFIXES):
                return {"trust_pct": 100, "badge": "100 % Fiabilité Certifiée", "details": f"Adresse RH officielle ({email})"}
            if best < 70:
                best = 70
                reason = f"Domaine d'entreprise reconnu ({email})"
    for link in links:
        low = link.lower()
        if any(p in low for p in TRUSTED_JOB_PLATFORMS):
            return {"trust_pct": 100, "badge": "100 % Fiabilité Certifiée", "details": "Offre publiée sur une plateforme officielle reconnue"}
        if low.startswith("https://") and best < 70:
            best = 70
            reason = "Lien web sécurisé (HTTPS) vérifié"
    return {"trust_pct": best, "badge": f"{best} % Fiabilité Recruteur", "details": reason}

def extract_cv_details(cv_text, photo_b64=None, filename=""):
    full_name, initials = extract_candidate_name(cv_text, filename)
    emails = sorted(list(set(re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", cv_text))))
    phones = extract_clean_phones(cv_text)
    links = sorted(list(set(re.findall(r"https?://[^\s<>\"')]+|github\.com/[^\s<>\"')]+|linkedin\.com/in/[^\s<>\"')]+", cv_text, re.IGNORECASE))))
    edu_label, edu_rank = detect_education(cv_text)
    _, all_skills = extract_skills(cv_text)
    main_role, sec_roles, objective = extract_professions_and_objective(cv_text, all_skills)

    return {
        "full_name": full_name,
        "initials": initials,
        "photo": photo_b64,
        "main_profession": main_role,
        "secondary_professions": sec_roles,
        "objective": objective,
        "location": extract_universal_location(cv_text) or "Non précisée",
        "emails": emails,
        "phones": phones,
        "links": links[:4],
        "languages": detect_languages(cv_text),
        "exp_years": extract_experience_years(cv_text),
        "education_label": edu_label,
        "education_rank": edu_rank
    }


def extract_job_details(job_text, source_url=""):
    today = date.today()
    norm_job = normalize_text(job_text)
    apply_emails = sorted(list(set(re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", job_text))))
    apply_links = sorted(list(set(re.findall(r"https?://[^\s<>\"')]+", job_text))))
    if source_url and source_url not in apply_links:
        apply_links.insert(0, source_url)

    found_dates = []
    for d, m, y in re.findall(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](20\d{2})\b", job_text):
        try:
            found_dates.append(date(int(y), int(m), int(d)))
        except ValueError:
            pass
    for d, m_str, y in re.findall(r"\b(\d{1,2})\s+([a-z]+)\s+(20\d{2})\b", norm_job):
        if m_str in MONTHS_MAP:
            try:
                found_dates.append(date(int(y), MONTHS_MAP[m_str], int(d)))
            except ValueError:
                pass

    deadline_info = {"deadline_date": "Non précisée", "deadline_iso": "", "days_left": 0, "status": "unknown", "status_label": "Date limite non mentionnée"}
    if found_dates:
        dl = max(found_dates)
        diff = (dl - today).days
        deadline_info["deadline_date"] = dl.strftime("%d/%m/%Y")
        deadline_info["deadline_iso"] = dl.isoformat()
        deadline_info["days_left"] = diff
        deadline_info["status"] = "active" if diff >= 0 else "expired"
        deadline_info["status_label"] = f"En cours ({diff} j restants)" if diff >= 0 else f"Dépassée ({abs(diff)} j)"

    contract = "Non précisé"
    for c_lbl, keys in [("CDI", ["cdi"]), ("CDD", ["cdd"]), ("Freelance", ["freelance", "consultant"]), ("Stage", ["stage", "stagiaire"])]:
        if any(re.search(r"\b" + k + r"\b", norm_job) for k in keys):
            contract = c_lbl
            break

    comp_m = re.search(r"(?:entreprise|societe|organisation|company|recruteur)\s*[:\-]\s*([^\n\r.;|]{2,45})", job_text, re.IGNORECASE)
    company = comp_m.group(1).strip() if comp_m else "Organisation / Entreprise"

    m_exp = re.findall(r"(\d+)\s*(?:\+|ans|annees)\s*(?:d['’]?experience|minimum|requis)?", norm_job)
    req_exp = max([int(x) for x in m_exp if 0 < int(x) <= 35], default=0)
    req_edu_label, req_edu_rank = detect_education(job_text)

    return {
        "raw_job_text": job_text,
        "company_name": company,
        "location": extract_universal_location(job_text) or "Non précisée",
        "contract_type": contract,
        "apply_emails": apply_emails,
        "email_audit": evaluate_recruiter_trust(apply_emails, apply_links),
        "apply_links": apply_links[:4],
        "deadline": deadline_info,
        "required_exp_years": req_exp,
        "required_edu_label": req_edu_label,
        "required_edu_rank": req_edu_rank,
        "required_languages": detect_languages(job_text)
    }


def evaluate_geo(cand_loc, job_loc, job_text):
    nj = normalize_text(job_text)
    nc = normalize_text(cand_loc)
    nt = normalize_text(job_loc)
    if any(k in nj for k in ["teletravail", "remote", "a distance"]):
        return {"status": "compatible", "chance_pct": 100, "badge": "100 % Éligible (Télétravail)", "message": "Poste en télétravail compatible."}
    if not nt or nt == "non precisee" or not nc or nc == "non precisee":
        return {"status": "uncertain", "chance_pct": 50, "badge": "50 % de chance (Lieu à vérifier)", "message": "Ville/Pays non précisé sur le CV ou l'offre."}
    c_tok = {w for w in re.split(r"[\s,./()-]+", nc) if len(w) >= 3}
    t_tok = {w for w in re.split(r"[\s,./()-]+", nt) if len(w) >= 3}
    if c_tok & t_tok:
        return {"status": "compatible", "chance_pct": 100, "badge": "100 % Éligible (Même zone)", "message": f"Localisation compatible ({cand_loc} / {job_loc})."}
    return {"status": "uncertain", "chance_pct": 50, "badge": "50 % de chance (Lieu différent)", "message": f"Lieu différent ({cand_loc} vs {job_loc})."}


def compute_final_report(cv_details, job_details, matched_skills, missing_skills, bonus_skills, category_breakdown, raw_cv_text="", tech_weight=60):
    total_job = len(matched_skills) + len(missing_skills)
    skills_ratio = (len(matched_skills) / total_job) if total_job > 0 else 1.0

    req_exp = float(job_details.get("required_exp_years", 0))
    cand_exp = float(cv_details.get("exp_years", 0))
    exp_ratio = 1.0 if (req_exp <= 0 or cand_exp >= req_exp) else max(0.3, cand_exp / req_exp)
    exp_status = "Conforme" if exp_ratio == 1.0 else f"Écart ({cand_exp} an(s) vs {req_exp} an(s) requis)"

    req_edu = int(job_details.get("required_edu_rank", 0))
    cand_edu = int(cv_details.get("education_rank", 0))
    edu_ratio = 1.0 if (req_edu <= 0 or cand_edu >= req_edu) else 0.5
    edu_status = "Conforme" if edu_ratio == 1.0 else "Inférieur au diplôme requis"

    req_langs = [l.lower() for l in job_details.get("required_languages", [])]
    cand_langs = [l.lower() for l in cv_details.get("languages", [])]
    if not req_langs:
        lang_ratio = 1.0
        lang_status = "Aucune langue imposée"
    else:
        matched_l = [l for l in req_langs if l in cand_langs]
        lang_ratio = len(matched_l) / len(req_langs)
        lang_status = "Langues maîtrisées" if lang_ratio == 1.0 else f"Manque : {', '.join(l.capitalize() for l in req_langs if l not in cand_langs)}"

    geo = evaluate_geo(cv_details.get("location", ""), job_details.get("location", ""), job_details.get("raw_job_text", ""))
    rem_w = 100 - tech_weight
    base = (skills_ratio * tech_weight) + (exp_ratio * rem_w * 0.40) + (edu_ratio * rem_w * 0.35) + (lang_ratio * rem_w * 0.25)
    proj = tech_weight + (exp_ratio * rem_w * 0.40) + (edu_ratio * rem_w * 0.35) + (lang_ratio * rem_w * 0.25)
    if geo["status"] == "uncertain":
        base *= 0.85
        proj *= 0.85

    final_score = round(base)
    radar_axes = {
        "Technique": round(skills_ratio * 100),
        "Expérience": round(exp_ratio * 100),
        "Diplômes": round(edu_ratio * 100),
        "Langues": round(lang_ratio * 100),
        "Adéquation": final_score
    }

    name = cv_details.get("full_name", "Candidat")
    skills_str = ", ".join(matched_skills[:6]) if matched_skills else "le domaine visé"
    phone = cv_details["phones"][0] if cv_details.get("phones") else "[Votre Téléphone]"
    org = job_details.get("company_name", "votre organisation")

    pitch = (
        f"Objet : Candidature — {name} ({skills_str})\n\nMadame, Monsieur,\n\n"
        f"Votre offre ({job_details.get('contract_type', 'Poste')}) au sein de {org} a retenu toute mon attention. "
        f"Titulaire d'un niveau {cv_details.get('education_label')} avec {cand_exp} an(s) d'expérience et maîtrisant "
        f"{skills_str}, je souhaite rejoindre votre équipe.\n\nJe reste disponible au {phone}.\n\nCordialement,\n{name}"
    )

    cv_profs = ", ".join([cv_details.get("main_profession", "")] + cv_details.get("secondary_professions", []))
    questions = [
        f"Votre CV indique {cand_exp} an(s) d'expérience en tant que {cv_profs} : quelle réalisation concrète avec {skills_str} illustre le mieux votre niveau ?",
        f"Que savez-vous des objectifs et des activités de {org} ?",
        f"L'offre exige {', '.join(missing_skills[:3]) if missing_skills else 'une adaptation rapide'} (non mentionné sur votre CV) : comment comptez-vous combler cet écart ?",
        f"Vous êtes basé(e) à {cv_details.get('location', 'votre ville')} pour un poste à {job_details.get('location', 'ce lieu')} : quelles sont vos conditions de mobilité ?",
        f"Avec votre niveau {cv_details.get('education_label', 'académique')}, comment organisez-vous vos priorités face à des délais serrés ?"
    ]

    return {
        "success": True,
        "score": final_score,
        "projected_score": round(proj),
        "radar_axes": radar_axes,
        "raw_cv_text": raw_cv_text,
        "stats": {"job_skills_count": total_job, "matched_count": len(matched_skills), "missing_count": len(missing_skills)},
        "comparison": {"exp_status": exp_status, "edu_status": edu_status, "lang_status": lang_status, "geo": geo},
        "interview_questions": questions,
        "matched_skills": sorted(matched_skills),
        "missing_skills": sorted(missing_skills),
        "bonus_skills": sorted(bonus_skills),
        "category_breakdown": category_breakdown,
        "cv_details": cv_details,
        "job_details": job_details,
        "cover_pitch": pitch
    }

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    cv_text_in = request.form.get("cv_text", "").strip()
    cv_file = request.files.get("cv_pdf")
    final_cv, photo_b64, fname = "", None, ""

    if cv_file and cv_file.filename:
        fname = cv_file.filename
        raw = cv_file.read()
        final_cv = extract_text_from_pdf(raw)
        photo_b64 = extract_cv_photo_base64(raw)
    elif cv_text_in:
        final_cv = cv_text_in

    if len(final_cv.strip()) < 10:
        return jsonify({"success": False, "message": "Impossible de lire le CV (PDF scanné ou vide). Collez le texte du CV."}), 400

    job_text_in = request.form.get("job_text", "").strip()
    job_url_in = request.form.get("job_url", "").strip()
    job_file = request.files.get("job_pdf")
    final_job, res_url = "", ""

    if job_file and job_file.filename:
        final_job = extract_text_from_pdf(job_file.read())
    elif job_url_in:
        try:
            final_job, res_url = extract_text_from_url(job_url_in)
        except Exception as e:
            return jsonify({"success": False, "message": str(e)}), 400
    elif job_text_in:
        final_job = job_text_in

    if len(final_job.strip()) < 10:
        return jsonify({"success": False, "message": "Fournissez le texte ou le PDF de l'offre d'emploi."}), 400

    _, cv_skills = extract_skills(final_cv)
    job_by_cat, job_skills = extract_skills(final_job)
    cv_set = {s.lower(): s for s in cv_skills}
    job_set = {s.lower(): s for s in job_skills}

    matched = [job_set[k] for k in job_set if k in cv_set]
    missing = [job_set[k] for k in job_set if k not in cv_set]
    bonus = [cv_set[k] for k in cv_set if k not in job_set]

    breakdown = []
    for cat, req_list in job_by_cat.items():
        has = [s for s in req_list if s.lower() in cv_set]
        breakdown.append({"category": cat, "matched": len(has), "total": len(req_list), "percent": round((len(has) / len(req_list)) * 100)})

    cv_det = extract_cv_details(final_cv, photo_b64, fname)
    job_det = extract_job_details(final_job, res_url)
    return jsonify(compute_final_report(cv_det, job_det, matched, missing, bonus, breakdown, final_cv))


@app.route("/api/recalculate", methods=["POST"])
def api_recalculate():
    data = request.get_json(silent=True) or {}
    return jsonify(compute_final_report(
        data.get("cv_details", {}), data.get("job_details", {}),
        data.get("matched_skills", []), data.get("missing_skills", []),
        data.get("bonus_skills", []), data.get("category_breakdown", []),
        data.get("raw_cv_text", "")
    ))

@app.route("/api/hr-batch", methods=["POST"])
def api_hr_batch():
    job_text = request.form.get("hr_job_text", "").strip()
    positions_count = int(request.form.get("positions_count", "3") or 3)
    tech_weight = int(request.form.get("tech_weight", "60") or 60)
    files = request.files.getlist("hr_cv_files")
    valid_files = [f for f in files if f and f.filename and f.filename.lower().endswith(".pdf")]

    if not job_text:
        return jsonify({"success": False, "message": "Collez la description du poste recherché."}), 400
    if not valid_files:
        return jsonify({"success": False, "message": "Sélectionnez au moins un fichier CV (.PDF)."}), 400

    _, job_skills = extract_skills(job_text)
    job_set = {s.lower(): s for s in job_skills}
    job_det = extract_job_details(job_text)

    candidates = []
    for f in valid_files:
        try:
            text = extract_text_from_pdf(f.read())
            if len(text.strip()) < 15:
                continue
            _, cv_skills = extract_skills(text)
            cv_set = {s.lower(): s for s in cv_skills}
            matched = [job_set[k] for k in job_set if k in cv_set]
            missing = [job_set[k] for k in job_set if k not in cv_set]
            bonus = [cv_set[k] for k in cv_set if k not in job_set]

            cv_det = extract_cv_details(text, None, f.filename)
            rep = compute_final_report(cv_det, job_det, matched, missing, bonus, [], text, tech_weight)
            score = rep["score"]

            candidates.append({
                "name": cv_det["full_name"],
                "main_profession": cv_det["main_profession"],
                "secondary_professions": cv_det["secondary_professions"],
                "objective": cv_det["objective"],
                "email": cv_det["emails"][0] if cv_det["emails"] else "",
                "phone": cv_det["phones"][0] if cv_det["phones"] else "",
                "location": cv_det["location"],
                "exp_years": cv_det["exp_years"],
                "education": cv_det["education_label"],
                "score": score,
                "radar_axes": rep["radar_axes"],
                "matched_skills": matched,
                "bonus_skills": bonus,
                "missing_skills": missing,
                "hr_status": "À convoquer",
                "hr_note": ""
            })
        except Exception:
            continue

    if not candidates:
        return jsonify({"success": False, "message": "Aucun texte lisible extrait. Vérifiez que vos PDF ne sont pas de simples images scannées."}), 400

    candidates.sort(key=lambda x: x["score"], reverse=True)
    for idx, c in enumerate(candidates):
        c["rank"] = idx + 1

    top_c = sum(1 for c in candidates if c["score"] >= 70)
    mid_c = sum(1 for c in candidates if 45 <= c["score"] < 70)
    low_c = sum(1 for c in candidates if c["score"] < 45)
    avg_s = round(sum(c["score"] for c in candidates) / len(candidates))

    return jsonify({
        "success": True,
        "total_received": len(candidates),
        "positions_count": positions_count,
        "avg_score": avg_s,
        "summary": {"top": top_c, "mid": mid_c, "low": low_c},
        "candidates": candidates
    })

@app.route("/api/export-xlsx", methods=["POST"])
def api_export_xlsx():
    data = request.get_json(silent=True) or {}
    candidates = data.get("candidates", [])
    if not candidates:
        return jsonify({"success": False, "message": "Aucun candidat sélectionné."}), 400

    output = io.StringIO()
    output.write("\ufeff")
    writer = csv.writer(output, delimiter=";")
    writer.writerow(["Rang", "Nom Complet", "Profession", "Autres Professions", "Expérience (ans)", "Score (%)", "Téléphone", "E-mail", "Statut RH", "Note"])

    for c in candidates:
        writer.writerow([
            c.get("rank", ""), c.get("name", ""), c.get("main_profession", ""),
            ", ".join(c.get("secondary_professions", [])) or "Aucune",
            c.get("exp_years", 0), c.get("score", 0),
            c.get("phone", "") or "Non détecté", c.get("email", "") or "Non détecté",
            c.get("hr_status", "À convoquer"), c.get("hr_note", "")
        ])

    mem = io.BytesIO(output.getvalue().encode("utf-8"))
    mem.seek(0)
    return send_file(mem, as_attachment=True, download_name=f"Shortlist_RH_CLAVERATS_{datetime.now().strftime('%Y%m%d')}.csv", mimetype="text/csv")


@app.route("/api/export-pdf", methods=["POST"])
def api_export_pdf():
    data = request.get_json(silent=True) or {}
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    cv = data.get("cv_details", {})

    elements = [
        Paragraph(f"Bilan Audit CV — {cv.get('full_name', 'Candidat')}", styles["Title"]),
        Spacer(1, 12),
        Paragraph(f"Score Global : {data.get('score', 0)} % (Potentiel : {data.get('projected_score', 0)} %)", styles["Heading2"]),
        Paragraph(f"Profession : {cv.get('main_profession', '')} | Expérience : {cv.get('exp_years', 0)} an(s)", styles["Normal"]),
        Paragraph(f"Compétences validées : {', '.join(data.get('matched_skills', [])) or 'Aucune'}", styles["Normal"]),
        Paragraph(f"Compétences manquantes : {', '.join(data.get('missing_skills', [])) or 'Aucune'}", styles["Normal"])
    ]
    doc.build(elements)
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name="Bilan_CLAVERATS.pdf", mimetype="application/pdf")


@app.route("/api/export-cover-letter", methods=["POST"])
def api_export_cover_letter():
    data = request.get_json(silent=True) or {}
    cv = data.get("cv_details", {})
    text = data.get("custom_text") or data.get("cover_pitch", "")
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = [Paragraph(f"<b>{cv.get('full_name', 'Candidat')}</b>", styles["Normal"]), Spacer(1, 16)]
    for p in text.split("\n\n"):
        if p.strip():
            elements.append(Paragraph(p.replace("\n", "<br/>"), styles["Normal"]))
            elements.append(Spacer(1, 10))
    doc.build(elements)
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name="Lettre_Motivation_CLAVERATS.pdf", mimetype="application/pdf")


@app.errorhandler(Exception)
def handle_unexpected_error(err):
    return jsonify({"success": False, "message": f"Erreur serveur Python : {str(err)}"}), 500


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5002, debug=True)
