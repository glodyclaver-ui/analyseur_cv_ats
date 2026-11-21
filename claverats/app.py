import io
import os
import re
import math
import socket
import base64
import unicodedata
from datetime import datetime, date, timedelta
from flask import Flask, render_template, request, jsonify, send_file
from pypdf import PdfReader
from PIL import Image
import requests
from bs4 import BeautifulSoup
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

try:
    import numpy as np
    import cv2
    HAS_CV2 = True
except ImportError:
    np = None
    cv2 = None
    HAS_CV2 = False

try:
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment
    HAS_OPENPYXL = True
except ImportError:
    openpyxl = None
    HAS_OPENPYXL = False

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 60 * 1024 * 1024  # plafond global ; chaque PDF est limite a 15 Mo
Image.MAX_IMAGE_PIXELS = 40_000_000  # protection contre les bombes de decompression

from services import geo_resolver, skills_referential
from services import pdf_vision_extractor, org_verifier, document_trust_analyzer, experience_analyzer, contact_extractor
from services import ranking, ocr_engine, document_security_engine as docsec, security_manager, audit_trail_manager, ats_scoring
from services.api import bp as services_bp
app.register_blueprint(services_bp)


@app.after_request
def add_security_headers(resp):
    for k, v in docsec.SECURITY_HEADERS.items():
        resp.headers.setdefault(k, v)
    if request.path.startswith("/api/"):
        resp.headers["Cache-Control"] = "no-store"
    return resp


def read_pdf_upload(file_storage):
    """Lit un PDF en RAM et le valide (signature %PDF-, 15 Mo, contenu actif). Retourne (bytes, validation)."""
    data = file_storage.read(docsec.MAX_PDF_BYTES + 1)
    if ocr_engine.detect_kind(data) in ("png", "jpg"):
        return data, ocr_engine.validate_image_bytes(data)  # CV en image : validation par octets magiques
    return data, docsec.validate_pdf_bytes(data)


def read_cv_content(raw, vres):
    """(texte, meta, pdf_info) : PDF texte, PDF scanné ou image -> OCR local avec repli honnête."""
    if vres.get("kind") == "image":
        text = ocr_engine.ocr_image(raw)
        return text, {"pages": 1, "has_images": True, "ocr": True, "ocr_available": ocr_engine.available()}, {}
    text, meta = extract_text_and_meta_from_pdf(raw)
    info = pdf_vision_extractor.analyze_pdf(raw)
    if len(text.strip()) < 40 and ocr_engine.available():
        t = ocr_engine.ocr_pdf(raw)
        if t:
            text, meta["ocr"] = t, True
    return text, meta, info


def build_job_requirements(final_job, job_skills):
    """Exigences reelles de l'employeur : competences ecrites dans l'offre + referentiel du metier detecte (marque « estime »)."""
    role_info = skills_referential.detect_role(final_job)
    return skills_referential.build_requirements(final_job, job_skills, role_info)


def categorize_required(name, role_label):
    low = name.lower()
    for cat, lst in SKILLS_DB.items():
        if any(low == str(x).lower() for x in lst):
            return cat
    return "Compétences du métier : " + role_label if role_label else "Autres exigences de l'offre"


def requirements_breakdown(reqs, matched):
    mset = {m.lower() for m in matched}
    role_label = (reqs.get("role") or {}).get("label", "")
    cats = {}
    for r in reqs["required"]:
        c = cats.setdefault(categorize_required(r["name"], role_label), {"matched": 0, "total": 0})
        c["total"] += 1
        c["matched"] += 1 if r["name"].lower() in mset else 0
    return [{"category": k, "matched": v["matched"], "total": v["total"], "percent": round(100 * v["matched"] / v["total"])} for k, v in cats.items()]


def apply_requirements(job_det, reqs):
    """Memorise dans les details de l'offre ce qui sert au score (coefficients, competences estimees, metier detecte)."""
    job_det["skill_weights"] = {r["name"].lower(): r["weight"] for r in reqs["required"]}
    job_det["estimated_skills"] = [r["name"] for r in reqs["required"] if r["source"].startswith("estim")]
    job_det["detected_role"] = reqs.get("role", {})
    job_det["requirements"] = [{"name": r["name"], "weight": r["weight"], "source": r["source"]} for r in reqs["required"]]
    return job_det


def enrich_experiences(exps):
    """Ajoute societe + duree exacte a chaque experience et retourne (experiences, analyse)."""
    for e in exps:
        # Format "Periode / Poste / Societe" : lignes courtes (sans ponctuation de phrase) juste apres la date
        if e.get("employer", "").startswith("Organisation") and e.get("tasks"):
            def _short(t):
                t = t.strip()
                return 2 <= len(t) <= 60 and len(t.split()) <= 6 and t[:1].isupper() and not re.search(r"[.;:]", t)
            lead = []
            for t in e["tasks"][:2]:
                if _short(t):
                    lead.append(t.strip())
                else:
                    break
            generic_role = normalize_text(e.get("role", "")) in ("poste occupe", "experience", "experiences", "parcours professionnel", "experience professionnelle")
            if len(lead) == 2 and generic_role is False and normalize_text(e.get("role", "")) == normalize_text(lead[0]):
                lead = lead[1:]
            if len(lead) == 2:
                e["role"], e["employer"] = lead[0][:90], lead[1][:90]
                e["tasks"] = e["tasks"][2:]
            elif len(lead) == 1:
                e["employer"] = lead[0][:90]
                e["tasks"] = e["tasks"][1:]
        e.setdefault("company", e.get("employer", ""))
        e["company"] = e.get("employer", "") or e.get("company", "")
    an = experience_analyzer.analyze(exps, (REF_YEAR, REF_MONTH))
    return an["experiences"], an

REF_YEAR = 2026
REF_MONTH = 11

SKILLS_DB = {
    "Langages de Programmation": [
        # Web, Frontend & Scripting
        "python", "javascript", "typescript", "html", "html5", "css", "css3",
        "sass", "scss", "less", "php", "ruby", "perl", "lua", "tcl", "coffeescript",
        "actionscript", "vbscript", "autohotkey",

        # Systèmes, Compilés & Bas Niveau
        "c", "c++", "c#", "objective-c", "java", "go", "golang", "rust",
        "zig", "nim", "d", "crystal", "assembly", "asm", "nasm", "masm",
        "pascal", "delphi", "object pascal", "ada", "cobol", "fortran", "basic",
        "visual basic", "vb.net", "vba",

        # Mobile & Multiplateforme
        "dart", "kotlin", "swift", "qml",

        # Fonctionnels, JVM & BEAM
        "scala", "groovy", "clojure", "haskell", "elixir", "erlang",
        "f#", "ocaml", "lisp", "common lisp", "scheme", "racket", "elm", "purescript",

        # Data Science, Calcul Scientifique & Statistiques
        "r", "matlab", "julia", "sas", "spss syntax", "stata", "octave",
        "wolfram", "mathematica", "maple", "scilab", "apl", "prolog",

        # Bases de Données & Requêtes
        "sql", "pl/sql", "t-sql", "pg/pgsql", "nosql", "graphql", "cypher",
        "sparql", "xquery", "xpath", "dax", "mdx", "abap", "apex",

        # Shell, DevOps & Configuration
        "bash", "shell", "sh", "zsh", "fish", "powershell", "batch", "cmd",
        "makefile", "cmake", "hcl", "terraform", "yaml", "json", "xml",

        # Smart Contracts, Shaders & Embarqué
        "solidity", "vyper", "move", "cairo", "vhdl", "verilog", "systemverilog",
        "glsl", "hlsl", "cuda", "opencl", "webassembly", "wasm", "scratch", "labview"
    ],
    "Logiciels & Outils": [
        # Bureautique & Collaboration
        "excel", "word", "powerpoint", "access", "outlook", "publisher", "visio",
        "office 365", "microsoft 365", "google workspace", "google sheets", "google docs",
        "ms project", "libreoffice", "notion", "trello", "asana", "jira", "slack", "teams", "zoom",
        # Data, BI & Bases de Données
        "power bi", "tableau", "looker", "qlik", "spss", "stata", "epidata", "kobotoolbox", "odk",
        "mysql", "postgresql", "mongodb", "firebase", "sqlite", "oracle", "sql server", "redis",
        # Design, Vidéo & Création
        "figma", "adobe xd", "photoshop", "illustrator", "indesign", "premiere pro", "after effects",
        "canva", "coreldraw", "lightroom", "capcut", "blender",
        # Gestion, Comptabilité, ERP & CRM
        "sage", "sage saari", "sage 100", "sap", "odoo", "erp", "crm", "salesforce", "hubspot",
        "quickbooks", "ciel compta", "tompro", "amplitude", "temenos", "navision", "dynamics 365",
        # Ingénierie, BTP, SIG & Industrie
        "autocad", "archicad", "revit", "solidworks", "catia", "sketchup", "robot structural",
        "arcgis", "qgis", "mapinfo", "matlab simulink", "labview", "plc", "scada",
        # Santé, Laboratoire & Pharmacie
        "dpi", "dossier patient informatisé", "crossway", "dx care", "lgpi", "winpharma",
        # Cloud, DevOps & Systèmes
        "git", "github", "gitlab", "docker", "kubernetes", "aws", "azure", "google cloud",
        "linux", "ubuntu", "debian", "windows server", "vmware", "virtualbox", "nginx", "apache",
        "wordpress", "shopify", "woocommerce", "postman"
    ],
    "Compétences Métiers & Techniques": [
        # Développement Web, Mobile, IA & Réseaux
        "flask", "django", "fastapi", "react", "react native", "vue.js", "angular", "next.js",
        "node.js", "express", "laravel", "symfony", "spring boot", ".net", "asp.net", "flutter",
        "api rest", "graphql", "machine learning", "deep learning", "nlp", "computer vision", "etl",
        "cybersécurité", "sécurité informatique", "pentest", "cisco", "tcp/ip", "active directory",
        "administration réseau", "maintenance informatique", "helpdesk", "support technique", "ui/ux",
        # Finance, Comptabilité, Banque & Audit
        "comptabilité", "comptabilité générale", "comptabilité analytique", "audit", "audit financier",
        "finance", "contrôle de gestion", "fiscalité", "trésorerie", "rapprochement bancaire",
        "analyse financière", "gestion budgétaire", "microfinance", "crédit bancaire", "recouvrement",
        "facturation", "caisse", "tenue de caisse", "bilan comptable",
        # Logistique, Achats, Mines & Supply Chain
        "logistique", "supply chain", "achats", "approvisionnement", "gestion de stock", "inventaire",
        "magasinage", "transit", "dédouanement", "import-export", "transport", "gestion de flotte",
        "chaîne du froid", "manutention", "extraction minière", "géologie", "topographie",
        # Ressources Humaines, Administration & Juridique
        "ressources humaines", "recrutement", "paie", "gestion de la paie", "administration du personnel",
        "formation", "gpec", "droit du travail", "droit des affaires", "rédaction de contrats",
        "contentieux", "secrétariat", "accueil", "archivage", "gestion administrative",
        # Santé, Médical, Pharmacie & Laboratoires
        "soins infirmiers", "premiers secours", "hygiène hospitalière", "prise de tension",
        "prise des signes vitaux", "administration des médicaments", "perfusion", "pansements",
        "triage patient", "pharmacologie", "dispensation de médicaments", "pédiatrie",
        "maternité", "obstétrique", "urgences", "réanimation", "chirurgie", "analyses biomédicales",
        "prélèvement sanguin", "stérilisation", "santé publique", "épidémiologie", "nutrition",
        # BTP, Électricité, Mécanique & Génie Civil
        "génie civil", "génie électrique", "génie mécanique", "électricité bâtiment", "électricité industrielle",
        "maintenance industrielle", "mécanique automobile", "soudure", "plomberie", "climatisation",
        "froid industriel", "conduite de travaux", "métré", "devis estimatif", "sécurité chantier",
        # Commerce, Marketing, Communication & ONG
        "marketing digital", "seo", "sea", "community management", "création de contenu",
        "prospection commerciale", "vente", "fidélisation client", "merchandising", "service après-vente",
        "gestion de projet", "agile", "scrum", "suivi-évaluation", "meal", "montage de projet",
        "plaidoyer", "enseignement", "animation pédagogique", "hôtellerie", "restauration", "cuisine"
    ],
    "Certifications & Formations": [
        # Santé, Médical & Secourisme
        "brevet de secourisme", "psc1", "sst", "bls", "acls", "pals", "gestes qui sauvent",
        "hygiène hospitalière", "pharmacovigilance", "ordre des infirmiers", "ordre des médecins",
        # Finance, Comptabilité, Audit & Banque
        "ohada", "syscohada", "ifrs", "acca", "cpa", "cfa", "cia", "dec", "dscg", "dcg",
        "audit interne", "lutte anti-blanchiment", "lab-ft", "conformité bancaire", "bâle iii",
        # Qualité, Sécurité, BTP & Industrie
        "iso 9001", "iso 14001", "iso 45001", "iso 22000", "iso 27001", "haccp", "qhse", "hse",
        "nebosh", "iosh", "habilitation électrique", "caces", "autocad certifié", "lean six sigma",
        # Gestion de Projet, RH, Logistique & Commerce
        "pmp", "prince2", "scrum master", "psm", "six sigma", "cipd", "shrm", "apics", "cscp",
        "incoterms", "douane et transit", "marchés publics", "passation des marchés",
        # Langues (Français, Anglais, International)
        "toefl", "ielts", "toeic", "cambridge", "delf", "dalf", "tcf", "tef", "dele", "goethe",
        # Informatique, Cloud & Cybersécurité
        "itil", "ccna", "ccnp", "comptia", "aws certified", "azure fundamentals", "google cloud certified",
        "cisa", "cissp", "ceh", "cka", "ckad", "togaf",
        # Mentions générales de diplômes / attestations
        "attestation", "certificat", "diplôme", "brevet", "habilitation", "accréditation", "licence professionnelle"
    ],
    "Attitudes & Savoir-être": [
        # Accueil, Relation Client & Service
        "souriant", "souriante", "accueil chaleureux", "sens du service", "sens du contact",
        "courtoisie", "politesse", "amabilité", "diplomatie", "tact", "écoute active",
        "relation client", "orientation client", "satisfaction client", "disponibilité",
        # Santé, Social, Éducation & Accompagnement
        "empathie", "bienveillance", "compassion", "humanisme", "patience", "douceur",
        "pédagogie", "sens de l'écoute", "soutien moral", "sang-froid", "maîtrise de soi",
        "calme", "résistance au stress", "gestion du stress", "gestion des urgences",
        # Éthique, Confidentialité & Intégrité (Banque, Droit, RH, Santé)
        "discrétion", "secret professionnel", "confidentialité", "intégrité", "honnêteté",
        "éthique professionnelle", "déontologie", "fiabilité", "loyauté", "transparence",
        "sens des responsabilités", "conscience professionnelle",
        # Ponctualité, Rigueur & Organisation
        "ponctualité", "assiduité", "rigueur", "minutie", "précision", "souci du détail",
        "organisation", "méthode", "méthodique", "gestion du temps", "gestion des priorités",
        "respect des délais", "planification", "discipline", "vigilance",
        # Collaboration, Esprit d'équipe & Communication
        "travail d'équipe", "esprit d'équipe", "collaboration", "coopération", "entraide",
        "communication", "aisance relationnelle", "aisance orale", "qualités rédactionnelles",
        "esprit de synthèse", "clarté", "persuasion", "force de proposition",
        # Autonomie, Adaptabilité & Résolution de problèmes
        "autonomie", "autonome", "adaptabilité", "flexibilité", "polyvalence", "réactivité",
        "proactivité", "esprit d'initiative", "curiosité intellectuelle", "apprentissage rapide",
        "résolution de problèmes", "esprit critique", "esprit d'analyse", "analyse", "synthèse",
        "créativité", "innovation", "ouverture d'esprit", "persévérance", "dynamisme", "dynamique",
        # Leadership, Management & Commerce
        "leadership", "management", "encadrement", "coordination", "supervision", "délégation",
        "prise de décision", "vision stratégique", "négociation", "force de conviction",
        "goût du challenge", "orientation résultats", "culture du résultat", "exemplarité"
    ]
}

SKILL_SYNONYMS = {
    # Informatique, Web, Data & Réseaux
    "js": "javascript",
    "ts": "typescript",
    "py": "python",
    "postgres": "postgresql",
    "mongo": "mongodb",
    "k8s": "kubernetes",
    "powerbi": "power bi",
    "ux": "ui/ux",
    "ui": "ui/ux",
    "rest": "api rest",
    "ml": "machine learning",
    "dl": "deep learning",
    "ia": "machine learning",
    "ai": "machine learning",
    "sysadmin": "administration réseau",
    "it": "maintenance informatique",
    "sav": "service après-vente",

    # Bureautique & ERP
    "bureautique": "excel",
    "pack office": "office 365",
    "ms office": "office 365",
    "m365": "office 365",
    "gsuite": "google workspace",
    "saari": "sage saari",

    # Santé, Médical & Secourisme
    "ide": "infirmier diplômé d'état",
    "secourisme": "premiers secours",
    "psc": "psc1",
    "tension": "prise de tension",
    "constantes": "prise des signes vitaux",
    "paramètres vitaux": "prise des signes vitaux",
    "pharmacie": "dispensation de médicaments",
    "labo": "analyses biomédicales",

    # Finance, Comptabilité, Audit & Banque
    "compta": "comptabilité",
    "comptabilité générale": "comptabilité",
    "contrôle budgétaire": "contrôle de gestion",
    "impôts": "fiscalité",
    "banque": "analyse financière",
    "syscohada": "ohada",
    "lab": "lutte anti-blanchiment",
    "aml": "lutte anti-blanchiment",

    # Logistique, Achats, Qualité & BTP
    "stock": "gestion de stock",
    "stocks": "gestion de stock",
    "appro": "approvisionnement",
    "douane": "dédouanement",
    "chantier": "conduite de travaux",
    "hse": "qhse",
    "sécurité": "qhse",
    "cao": "autocad",
    "dao": "autocad",
    "sig": "qgis",

    # Ressources Humaines, ONG & Commerce
    "rh": "ressources humaines",
    "grh": "ressources humaines",
    "suivi evaluation": "suivi-évaluation",
    "m&e": "suivi-évaluation",
    "meal": "suivi-évaluation",
    "cm": "community management",
    "b2b": "prospection commerciale",
    "b2c": "relation client"
}

OFFER_STOPWORDS_BASE = {
    "avec", "pour", "dans", "sous", "vers", "chez", "sans", "être", "avoir", "faire",
    "nous", "vous", "ils", "elles", "notre", "votre", "leur", "leurs", "cette", "ces",
    "celui", "celle", "ceux", "celles", "plus", "moins", "très", "bien", "aussi",
    "ainsi", "donc", "mais", "comme", "selon", "entre", "tout", "tous", "toute", "toutes",
    "autre", "autres", "même", "mêmes", "déjà", "encore", "toujours", "jamais",
    "poste", "offre", "emploi", "mission", "missions", "profil", "recherché", "recherche",
    "candidat", "candidate", "candidature", "entreprise", "société", "organisation",
    "équipe", "travail", "expérience", "expériences", "année", "années", "ans", "mois",
    "jour", "jours", "niveau", "diplôme", "formation", "études", "bac", "licence", "master",
    "compétence", "compétences", "connaissance", "connaissances", "maîtrise", "capacité",
    "capacités", "savoir", "bonne", "bon", "excellente", "excellent", "minimum", "requis",
    "souhaité", "souhaitée", "atout", "cadre", "sein", "projet", "projets", "activité",
    "activités", "service", "services", "client", "clients", "gestion", "suivi",
    "mise", "place", "développement", "réalisation", "participation", "contribution",
    "contrat", "cdi", "cdd", "stage", "freelance", "temps", "plein", "partiel",
    "lieu", "ville", "pays", "adresse", "contact", "email", "téléphone", "cv", "lettre",
    "motivation", "envoyer", "postuler", "date", "limite", "clôture", "janvier", "février",
    "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"
} 

POSTURE_LEXICON = {
    "Analytique": [
        # Data, Finance, Audit & Contrôle
        "analyse", "analytique", "données", "data", "statistique", "audit", "diagnostic",
        "évaluation", "indicateur", "kpi", "reporting", "modélisation", "recherche", "synthèse",
        "optimisation", "algorithme", "métrique", "contrôle", "vérification", "étude",
        # Santé, Laboratoire, Juridique & Qualité
        "examen", "dépistage", "auscultation", "prélèvement", "observation clinique",
        "conformité", "inspection", "expertise", "bilan", "inventaire", "traçabilité", "suivi-évaluation"
    ],
    "Managériale": [
        # Direction, Équipe & Stratégie
        "management", "manager", "pilotage", "piloter", "direction", "diriger", "supervision",
        "superviser", "encadrement", "encadrer", "équipe", "stratégie", "stratégique", "budget",
        "décision", "coordination", "coordonner", "leadership", "gouvernance", "planification",
        "négociation", "responsable", "chef", "déploiement",
        # Chantier, Service Médical, Magasin & Formation
        "chef de chantier", "conducteur de travaux", "surveillant", "major", "formation",
        "tutorat", "sensibilisation", "organisation", "répartition", "approvisionnement", "gestion"
    ],
    "Opérationnelle": [
        # Production, IT & Administration
        "réalisation", "réaliser", "exécution", "exécuter", "production", "produire", "terrain",
        "maintenance", "support", "installation", "développement", "développer", "conception",
        "concevoir", "mise en oeuvre", "implémentation", "traitement", "opérationnel", "technique",
        "intervention", "administration", "configuration", "rédaction",
        # Soins, Réparation, BTP, Logistique & Accueil
        "soins", "soigner", "réparation", "réparer", "dépannage", "câblage", "soudure",
        "construction", "livraison", "manutention", "conduite", "accueil", "vente",
        "caisse", "encaissement", "dispensation", "prélèvement", "stérilisation", "enseignement"
    ]
}
OFFER_STOPWORDS = set(OFFER_STOPWORDS_BASE) | set(skills_referential.STOPWORDS)

ACTION_VERBS = [
    # Conception, Gestion & Pilotage
    "développé", "conçu", "piloté", "géré", "optimisé", "réduit", "augmenté", "créé",
    "mis en place", "coordonné", "supervisé", "analysé", "automatisé", "déployé",
    "négocié", "formé", "structuré", "amélioré", "lancé", "administré", "résolu",
    "élaboré", "dirigé", "accompagné", "assuré", "réalisé", "transformé", "planifié",

    # Santé, Médical, Soins & Pharmacie
    "soigné", "administré", "diagnostiqué", "examiné", "vacciné", "opéré", "pansé",
    "surveillé", "pris en charge", "trié", "dispensé", "stérilisé", "réanimé", "conseillé",

    # Réparation, Maintenance, BTP & Technique Terrain
    "réparé", "maintenu", "installé", "dépanné", "câblé", "soudé", "assemblé",
    "construit", "rénové", "calibré", "inspecté", "sécurisé", "diagnostiqué", "raccordé",

    # Logistique, Transport, Stock & Achats
    "acheminé", "livré", "stocké", "inventorié", "approvisionné", "dédouané",
    "expédié", "transporté", "conduit", "réceptionné", "emballé", "distribué",

    # Finance, Comptabilité, Audit & Droit
    "comptabilisé", "audité", "vérifié", "facturé", "encaissé", "recouvré",
    "budgétisé", "clôturé", "contrôlé", "rédigé", "plaidoirie", "défendu", "conformité",

    # Enseignement, Accueil, Commerce & Services
    "enseigné", "animé", "encadré", "sensibilisé", "accueilli", "orienté",
    "vendu", "prospecté", "fidélisé", "préparé", "cuisiné", "nettoyé", "entretenu"
]

PROFESSION_KEYWORDS = [
    # Informatique, Data & Digital
    "développeur web", "développeur full stack", "développeur python", "développeur mobile",
    "développeur logiciel", "administrateur systèmes et réseaux", "technicien informatique",
    "technicien maintenance informatique", "ingénieur logiciel", "data analyst",
    "analyste de données", "data scientist", "infographiste", "designer ui/ux",
    "consultant it", "formateur bureautique", "community manager", "spécialiste cybersécurité",

    # Santé, Médical & Pharmacie
    "infirmier", "infirmière", "infirmier diplômé d'état", "médecin", "médecin généraliste",
    "pharmacien", "pharmacienne", "préparateur en pharmacie", "technicien de laboratoire",
    "biologiste médical", "sage-femme", "aide-soignant", "aide-soignante", "nutritionniste",
    "kinésithérapeute", "dentiste", "chirurgien-dentiste", "agent de santé communautaire",

    # Finance, Comptabilité, Banque & Audit
    "comptable", "chef comptable", "assistant comptable", "auditeur", "auditeur interne",
    "auditeur financier", "contrôleur de gestion", "analyste financier", "caissier", "caissière",
    "gestionnaire de clientèle", "chargé de crédit", "agent de recouvrement", "fiscaliste",

    # Logistique, Achats, Transport & Mines
    "logisticien", "responsable logistique", "magasinier", "gestionnaire de stock",
    "acheteur", "approvisionneur", "déclarant en douane", "agent de transit",
    "chauffeur", "chauffeur poids lourd", "conducteur d'engins", "ingénieur des mines",
    "géologue", "topographe", "responsable hse", "animateur qhse",

    # BTP, Électricité, Mécanique & Génie Civil
    "ingénieur génie civil", "conducteur de travaux", "chef de chantier", "architecte",
    "électricien", "électricien bâtiment", "électricien industriel", "électromécanicien",
    "mécanicien", "mécanicien automobile", "soudeur", "plombier", "technicien froid et climatisation",
    "technicien maintenance industrielle",

    # Gestion, Administration, RH, Droit & ONG
    "chef de projet", "coordinateur de projet", "chargé de suivi-évaluation", "agent terrain",
    "responsable rh", "chargé de recrutement", "gestionnaire de paie", "assistant administratif",
    "secrétaire", "secrétaire de direction", "réceptionniste", "agent d'accueil",
    "juriste", "avocat", "conseiller juridique", "chargé de communication",

    # Commerce, Enseignement, Hôtellerie & Services
    "commercial", "chargé d'affaires", "délégué médical", "vendeur", "vendeuse",
    "responsable marketing", "enseignant", "professeur", "formateur", "instituteur",
    "cuisinier", "chef cuisinier", "serveur", "serveuse", "réceptionniste d'hôtel", "agent de sécurité"
]

EDUCATION_LEVELS = [
    ("Doctorat / PhD / Thèse (Bac+8)", 5, [
        # Francophone & International
        "doctorat", "phd", "ph.d", "doctorate", "bac+8", "these de doctorat",
        "post-doctorat", "postdoc", "hdr", "habilitation a diriger des recherches",
        # Anglo-Saxon & Spécialités
        "doctoral degree", "dphil", "edd", "dba", "juris doctor", "jd", "docteur en pharmacie"
    ]),
    ("Master (LMD) / Licence Ancien Système / Ingénieur (Bac+5)", 4, [
        # LMD & Europe
        "master", "master's", "msc", "m.sc", "ma", "m.a", "meng", "mba", "llm", "mph",
        "ingenieur", "ingenieur civil", "ingenieur commercial", "ingenieur industriel",
        "bac+5", "m2", "m1", "dea", "dess", "maitrise", "magistere", "mastere specialise",
        # RDC Ancien Système & Belgique
        "licence ancien systeme", "licence (ancien systeme)", "2eme licence", "l2",
        "graduat et licence", "docteur en medecine", "medecin generaliste",
        # Allemagne / Hispanophone / Lusophone
        "diplom", "staatsexamen", "mestrado", "maestria", "postgraduate"
    ]),
    ("Licence (LMD) / Graduat / Bachelor (Bac+3/+4)", 3, [
        # LMD & RDC
        "licence lmd", "licence (lmd)", "l3", "graduat", "gradue", "g3", "a1",
        "bac+3", "bac+4", "licence professionnelle", "licence",
        # Anglo-Saxon (USA, UK, Canada, Commonwealth)
        "bachelor", "bachelor's", "bsc", "b.sc", "ba", "b.a", "beng", "bba", "bcom",
        "honours degree", "undergraduate degree", "baccalaureat universitaire",
        # Hispanophone / Lusophone / Arabe
        "licenciatura", "grado", "bacharelado", "ijazah"
    ]),
    ("BTS / DUT / Associate Degree / HND (Bac+2)", 2, [
        # Francophone
        "bts", "dut", "but", "deug", "deust", "bac+2", "brevet de technicien superieur",
        "diplome universitaire de technologie", "technicien superieur",
        # Anglo-Saxon & Commonwealth
        "associate degree", "associate's", "hnd", "higher national diploma", "foundation degree",
        "diploma in", "advanced diploma", "dec", "cegep"
    ]),
    ("Diplôme d'État / Baccalauréat / High School (Secondaire)", 1, [
        # RDC & Francophone
        "diplome d'etat", "baccalaureat", "humanites", "lycee", "a2", "bac",
        "brevet professionnel", "cap", "bep", "delf b2",
        # Anglo-Saxon & International
        "high school", "high school diploma", "secondary school", "a-levels", "a levels",
        "gcse", "igcse", "ged", "matric", "wassce", "kcse", "abitur", "bachillerato"
    ])
]


LANGUAGES_LIST = [
    # Langues internationales & européennes
    "francais", "french", "anglais", "english", "espagnol", "spanish",
    "allemand", "german", "portugais", "portuguese", "italien", "italian",
    "neerlandais", "dutch", "russe", "russian", "chinois", "mandarin", "chinese",
    "japonais", "japanese", "coreen", "korean", "arabe", "arabic", "turc", "hindi",
    # Langues nationales & africaines (RDC & Continent)
    "lingala", "swahili", "kiswahili", "tshiluba", "kikongo", "kituba",
    "wolof", "bambara", "dioula", "peul", "fulfulde", "haoussa", "hausa",
    "yoruba", "igbo", "amharique", "kinyarwanda", "kirundi", "luganda",
    "zoulou", "zulu", "xhosa", "afrikaans", "malgache", "sango"
]

FREE_EMAIL_DOMAINS = {
    # Google, Yahoo & Microsoft
    "gmail.com", "googlemail.com", "yahoo.fr", "yahoo.com", "yahoo.co.uk", "yahoo.ca",
    "yahoo.es", "yahoo.de", "yahoo.it", "yahoo.com.br", "yahoo.co.jp", "ymail.com", "rocketmail.com",
    "hotmail.com", "hotmail.fr", "hotmail.co.uk", "hotmail.es", "hotmail.de", "hotmail.it",
    "outlook.com", "outlook.fr", "outlook.be", "outlook.ca", "outlook.es", "outlook.de",
    "live.com", "live.fr", "live.be", "live.ca", "live.co.uk", "msn.com", "windowslive.com",
    # Apple, AOL & Messageries Sécurisées
    "icloud.com", "me.com", "mac.com", "aol.com", "aim.com",
    "proton.me", "protonmail.com", "protonmail.ch", "pm.me",
    "tutanota.com", "tuta.io", "tutanota.de", "mailfence.com", "startmail.com", "fastmail.com",
    # Europe & Fournisseurs Télécoms Grand Public
    "gmx.com", "gmx.fr", "gmx.de", "gmx.net", "gmx.ch", "web.de", "t-online.de", "freenet.de",
    "orange.fr", "wanadoo.fr", "free.fr", "sfr.fr", "neuf.fr", "laposte.net", "bbox.fr",
    "skynet.be", "proximus.be", "telenet.be", "bluewin.ch", "hispeed.ch",
    "libero.it", "virgilio.it", "alice.it", "tin.it", "telefonica.net", "terra.es",
    # International (Russie, Asie, Amériques)
    "yandex.com", "yandex.ru", "ya.ru", "mail.ru", "inbox.ru", "list.ru", "bk.ru",
    "qq.com", "163.com", "126.com", "sina.com", "naver.com", "daum.net", "hanmail.net",
    "rediffmail.com", "zoho.com", "zohomail.com", "mail.com", "email.com", "usa.com", "uol.com.br", "bol.com.br",
    # Messageries Jetables / Temporaires (Risque élevé)
    "yopmail.com", "yopmail.fr", "tempmail.com", "10minutemail.com", "guerrillamail.com", "mailinator.com"
}

HR_PREFIXES = (
    # Français
    "rh", "drh", "recrutement", "recruteur", "recruteurs", "carriere", "carrieres",
    "emploi", "emplois", "offre", "offres", "candidature", "candidatures", "candidat",
    "ressourceshumaines", "ressources-humaines", "ressources_humaines", "selection",
    "embauche", "stage", "stages", "alternance", "mobilite", "talents", "talent",
    # Anglais
    "hr", "hrd", "hrm", "recruitment", "recruiting", "recruiter", "recruiters",
    "career", "careers", "job", "jobs", "apply", "application", "applications",
    "talent", "talents", "talentacquisition", "talent-acquisition", "acquisition",
    "staffing", "hiring", "people", "peopleops", "humanresources", "human-resources",
    "workwithus", "joinus", "join", "opportunities", "vacancies", "vacancy", "internships",
    # Espagnol, Portugais & Allemand
    "rrhh", "seleccion", "reclutamiento", "empleo", "empleos", "trabajo", "postulaciones",
    "recrutamento", "vagas", "carreiras", "personal", "karriere", "bewerbung", "stellen"
)


TRUSTED_JOB_PLATFORMS = (
    # Portails internationaux majeurs
    "linkedin.com", "indeed.com", "glassdoor.com", "monster.com", "ziprecruiter.com",
    "careerbuilder.com", "stepstone.com", "welcometothejungle.com", "talent.com",
    # Systèmes ATS officiels d'entreprises
    "greenhouse.io", "lever.co", "workday.com", "myworkdayjobs.com", "smartrecruiters.com",
    "icims.com", "taleo.net", "bamboohr.com", "recruitee.com", "ashbyhq.com", "jobvite.com",
    # ONG, Nations Unies & Institutions Internationales
    "reliefweb.int", "unjobnet.org", "unjobs.org", "inspira.un.org", "undp.org",
    "unicef.org", "who.int", "wfp.org", "unhcr.org", "icrc.org", "msf.org",
    "worldbank.org", "afdb.org", "europa.eu", "devex.com", "coordination-sud.org",
    # Portails Afrique, RDC & Francophonie
    "mediacongo.net", "emploi.cd", "talenteo.com", "educarriere.ci", "emploi.sn",
    "emploi.ma", "rekrute.com", "keejob.com", "tanitjobs.com", "brightermonday.co.ke",
    "careers24.com", "pnet.co.za", "apec.fr", "francetravail.fr", "pole-emploi.fr",
    "hellowork.com", "cadremploi.fr", "meteojob.com", "actiris.brussels", "leforem.be", "vdab.be"
)

COUNTRY_CODES = {
    # Afrique Centrale & Australe
    "243": "RDC (+243)", "242": "Congo (+242)", "244": "Angola (+244)",
    "260": "Zambie (+260)", "250": "Rwanda (+250)", "257": "Burundi (+257)",
    "237": "Cameroun (+237)", "241": "Gabon (+241)", "236": "Centrafrique (+236)",
    "235": "Tchad (+235)", "240": "Guinée Éq. (+240)", "27": "Afrique du Sud (+27)",
    "264": "Namibie (+264)", "267": "Botswana (+267)", "263": "Zimbabwe (+263)",
    "258": "Mozambique (+258)", "261": "Madagascar (+261)", "230": "Maurice (+230)",
    # Afrique de l'Ouest, de l'Est & du Nord
    "225": "Côte d'Ivoire (+225)", "221": "Sénégal (+221)", "223": "Mali (+223)",
    "226": "Burkina Faso (+226)", "227": "Niger (+227)", "228": "Togo (+228)",
    "229": "Bénin (+229)", "224": "Guinée (+224)", "222": "Mauritanie (+222)",
    "234": "Nigeria (+234)", "233": "Ghana (+233)", "254": "Kenya (+254)",
    "256": "Ouganda (+256)", "255": "Tanzanie (+255)", "251": "Éthiopie (+251)",
    "212": "Maroc (+212)", "213": "Algérie (+213)", "216": "Tunisie (+216)", "20": "Égypte (+20)",
    # Europe, Amériques, Moyen-Orient & Asie
    "33": "France (+33)", "32": "Belgique (+32)", "41": "Suisse (+41)",
    "352": "Luxembourg (+352)", "44": "Royaume-Uni (+44)", "353": "Irlande (+353)",
    "49": "Allemagne (+49)", "34": "Espagne (+34)", "39": "Italie (+39)",
    "31": "Pays-Bas (+31)", "351": "Portugal (+351)", "46": "Suède (+46)",
    "47": "Norvège (+47)", "45": "Danemark (+45)", "48": "Pologne (+48)", "90": "Turquie (+90)",
    "1": "USA/Canada (+1)", "52": "Mexique (+52)", "55": "Brésil (+55)",
    "54": "Argentine (+54)", "57": "Colombie (+57)", "56": "Chili (+56)",
    "971": "Émirats/Dubaï (+971)", "966": "Arabie Saoudite (+966)", "974": "Qatar (+974)",
    "91": "Inde (+91)", "86": "Chine (+86)", "81": "Japon (+81)",
    "82": "Corée du Sud (+82)", "65": "Singapour (+65)", "61": "Australie (+61)"
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

CITY_COORDS = {
    # --- PARTIE 1 / 7 : VILLES & 26 PROVINCES DE LA RDC + CONGO ---
    "kinshasa": {"lat": -4.4419, "lon": 15.2663, "label": "Kinshasa, RDC", "salary_ref": 1200, "tension": "Élevée"},
    "lubumbashi": {"lat": -11.6876, "lon": 27.5026, "label": "Lubumbashi, RDC", "salary_ref": 1150, "tension": "Moyenne"},
    "goma": {"lat": -1.6585, "lon": 29.2205, "label": "Goma, RDC", "salary_ref": 1100, "tension": "Moyenne"},
    "matadi": {"lat": -5.8167, "lon": 13.4500, "label": "Matadi, RDC", "salary_ref": 950, "tension": "Faible"},
    "kisangani": {"lat": 0.5153, "lon": 25.1910, "label": "Kisangani, RDC", "salary_ref": 900, "tension": "Faible"},
    "kolwezi": {"lat": -10.7167, "lon": 25.4667, "label": "Kolwezi, RDC", "salary_ref": 1250, "tension": "Moyenne"},
    "bukavu": {"lat": -2.5083, "lon": 28.8608, "label": "Bukavu, RDC", "salary_ref": 950, "tension": "Faible"},
    "likasi": {"lat": -10.9833, "lon": 26.7333, "label": "Likasi, RDC", "salary_ref": 1100, "tension": "Moyenne"},
    "kananga": {"lat": -5.8962, "lon": 22.4166, "label": "Kananga, RDC", "salary_ref": 850, "tension": "Faible"},
    "mbuji-mayi": {"lat": -6.1360, "lon": 23.5898, "label": "Mbuji-Mayi, RDC", "salary_ref": 900, "tension": "Faible"},
    "mbandaka": {"lat": 0.0487, "lon": 18.2603, "label": "Mbandaka, RDC", "salary_ref": 850, "tension": "Faible"},
    "beni": {"lat": 0.4911, "lon": 29.4731, "label": "Beni, RDC", "salary_ref": 950, "tension": "Moyenne"},
    "butembo": {"lat": 0.1416, "lon": 29.2912, "label": "Butembo, RDC", "salary_ref": 950, "tension": "Moyenne"},
    "boma": {"lat": -5.8509, "lon": 13.0536, "label": "Boma, RDC", "salary_ref": 900, "tension": "Faible"},
    "kindu": {"lat": -2.9437, "lon": 25.9224, "label": "Kindu, RDC", "salary_ref": 850, "tension": "Faible"},
    "bunia": {"lat": 1.5594, "lon": 30.2522, "label": "Bunia, RDC", "salary_ref": 950, "tension": "Moyenne"},
    "mbanza-ngungu": {"lat": -5.2500, "lon": 14.8667, "label": "Mbanza-Ngungu, RDC", "salary_ref": 900, "tension": "Moyenne"},
    "kasongo": {"lat": -4.4553, "lon": 26.6667, "label": "Kasongo, RDC", "salary_ref": 850, "tension": "Moyenne"},
    "lodja": {"lat": -3.4833, "lon": 23.4333, "label": "Lodja, RDC", "salary_ref": 850, "tension": "Moyenne"},
    "laval": {"lat": 48.0698, "lon": -0.7733, "label": "Laval, France", "salary_ref": 1800, "tension": "Normale"},
    "uvira": {"lat": -3.3953, "lon": 29.1378, "label": "Uvira, RDC", "salary_ref": 900, "tension": "Faible"},
    "kalemie": {"lat": -5.9325, "lon": 29.1947, "label": "Kalemie, RDC", "salary_ref": 900, "tension": "Faible"},
    "kamina": {"lat": -8.7351, "lon": 24.9979, "label": "Kamina, RDC", "salary_ref": 850, "tension": "Faible"},
    "kikwit": {"lat": -5.0333, "lon": 18.8167, "label": "Kikwit, RDC", "salary_ref": 850, "tension": "Faible"},
    "bandundu": {"lat": -3.3167, "lon": 17.3667, "label": "Bandundu, RDC", "salary_ref": 850, "tension": "Faible"},
    "isiro": {"lat": 2.7667, "lon": 27.6167, "label": "Isiro, RDC", "salary_ref": 850, "tension": "Faible"},
    "buta": {"lat": 2.8000, "lon": 24.7333, "label": "Buta, RDC", "salary_ref": 850, "tension": "Faible"},
    "gemena": {"lat": 3.2500, "lon": 19.7833, "label": "Gemena, RDC", "salary_ref": 850, "tension": "Faible"},
    "gbadolite": {"lat": 4.2833, "lon": 21.0000, "label": "Gbadolite, RDC", "salary_ref": 850, "tension": "Faible"},
    "lisala": {"lat": 2.1500, "lon": 21.5167, "label": "Lisala, RDC", "salary_ref": 850, "tension": "Faible"},
    "boende": {"lat": -0.2167, "lon": 20.8667, "label": "Boende, RDC", "salary_ref": 850, "tension": "Faible"},
    "inongo": {"lat": -1.9500, "lon": 18.2667, "label": "Inongo, RDC", "salary_ref": 850, "tension": "Faible"},
    "kenge": {"lat": -4.8333, "lon": 16.9000, "label": "Kenge, RDC", "salary_ref": 850, "tension": "Faible"},
    "tshikapa": {"lat": -6.4167, "lon": 20.8000, "label": "Tshikapa, RDC", "salary_ref": 850, "tension": "Faible"},
    "kabinda": {"lat": -6.1333, "lon": 24.4833, "label": "Kabinda, RDC", "salary_ref": 850, "tension": "Faible"},
    "lusambo": {"lat": -4.9667, "lon": 23.4333, "label": "Lusambo, RDC", "salary_ref": 850, "tension": "Faible"},
    "haut-katanga": {"lat": -11.6876, "lon": 27.5026, "label": "Haut-Katanga, RDC", "salary_ref": 1200, "tension": "Moyenne"},
    "haut katanga": {"lat": -11.6876, "lon": 27.5026, "label": "Haut-Katanga, RDC", "salary_ref": 1200, "tension": "Moyenne"},
    "katanga": {"lat": -11.6876, "lon": 27.5026, "label": "Haut-Katanga, RDC", "salary_ref": 1200, "tension": "Moyenne"},
    "lualaba": {"lat": -10.7167, "lon": 25.4667, "label": "Lualaba, RDC", "salary_ref": 1250, "tension": "Moyenne"},
    "haut-lomami": {"lat": -8.7351, "lon": 24.9979, "label": "Haut-Lomami, RDC", "salary_ref": 900, "tension": "Faible"},
    "tanganyika": {"lat": -5.9325, "lon": 29.1947, "label": "Tanganyika, RDC", "salary_ref": 900, "tension": "Faible"},
    "nord-kivu": {"lat": -1.6585, "lon": 29.2205, "label": "Nord-Kivu, RDC", "salary_ref": 1100, "tension": "Moyenne"},
    "sud-kivu": {"lat": -2.5083, "lon": 28.8608, "label": "Sud-Kivu, RDC", "salary_ref": 950, "tension": "Faible"},
    "maniema": {"lat": -2.9437, "lon": 25.9224, "label": "Maniema, RDC", "salary_ref": 850, "tension": "Faible"},
    "ituri": {"lat": 1.5594, "lon": 30.2522, "label": "Ituri, RDC", "salary_ref": 950, "tension": "Moyenne"},
    "tshopo": {"lat": 0.5153, "lon": 25.1910, "label": "Tshopo, RDC", "salary_ref": 900, "tension": "Faible"},
    "bas-uele": {"lat": 2.8000, "lon": 24.7333, "label": "Bas-Uele, RDC", "salary_ref": 850, "tension": "Faible"},
    "haut-uele": {"lat": 2.7667, "lon": 27.6167, "label": "Haut-Uele, RDC", "salary_ref": 850, "tension": "Faible"},
    "kongo-central": {"lat": -5.8167, "lon": 13.4500, "label": "Kongo-Central, RDC", "salary_ref": 950, "tension": "Faible"},
    "kwilu": {"lat": -5.0333, "lon": 18.8167, "label": "Kwilu, RDC", "salary_ref": 850, "tension": "Faible"},
    "kwango": {"lat": -6.4333, "lon": 16.9667, "label": "Kwango, RDC", "salary_ref": 850, "tension": "Faible"},
    "mai-ndombe": {"lat": -1.9500, "lon": 18.2667, "label": "Mai-Ndombe, RDC", "salary_ref": 850, "tension": "Faible"},
    "equateur": {"lat": 0.0487, "lon": 18.2603, "label": "Équateur, RDC", "salary_ref": 850, "tension": "Faible"},
    "mongala": {"lat": 2.1500, "lon": 21.5167, "label": "Mongala, RDC", "salary_ref": 850, "tension": "Faible"},
    "nord-ubangi": {"lat": 4.2833, "lon": 21.0000, "label": "Nord-Ubangi, RDC", "salary_ref": 850, "tension": "Faible"},
    "sud-ubangi": {"lat": 3.2500, "lon": 19.7833, "label": "Sud-Ubangi, RDC", "salary_ref": 850, "tension": "Faible"},
    "tshuapa": {"lat": -0.2167, "lon": 20.8667, "label": "Tshuapa, RDC", "salary_ref": 850, "tension": "Faible"},
    "kasai": {"lat": -6.4667, "lon": 20.8000, "label": "Kasaï, RDC", "salary_ref": 850, "tension": "Faible"},
    "kasai-central": {"lat": -5.8962, "lon": 22.4166, "label": "Kasaï-Central, RDC", "salary_ref": 850, "tension": "Faible"},
    "kasai-oriental": {"lat": -6.1360, "lon": 23.5898, "label": "Kasaï-Oriental, RDC", "salary_ref": 900, "tension": "Faible"},
    "lomami": {"lat": -6.1333, "lon": 24.4833, "label": "Lomami, RDC", "salary_ref": 850, "tension": "Faible"},
    "sankuru": {"lat": -3.3667, "lon": 23.4333, "label": "Sankuru, RDC", "salary_ref": 850, "tension": "Faible"},
    "brazzaville": {"lat": -4.2634, "lon": 15.2429, "label": "Brazzaville, Congo", "salary_ref": 1100, "tension": "Moyenne"},
    "pointe-noire": {"lat": -4.7761, "lon": 11.8636, "label": "Pointe-Noire, Congo", "salary_ref": 1150, "tension": "Moyenne"},

    # --- PARTIE 2 / 7 : AFRIQUE FRANCOPHONE & ANGLOPHONE ---
    "abidjan": {"lat": 5.3600, "lon": -4.0083, "label": "Abidjan, Côte d'Ivoire", "salary_ref": 1300, "tension": "Élevée"},
    "yamoussoukro": {"lat": 6.8276, "lon": -5.2893, "label": "Yamoussoukro, Côte d'Ivoire", "salary_ref": 1100, "tension": "Moyenne"},
    "bouake": {"lat": 7.6939, "lon": -5.0303, "label": "Bouaké, Côte d'Ivoire", "salary_ref": 1000, "tension": "Faible"},
    "dakar": {"lat": 14.7167, "lon": -17.4677, "label": "Dakar, Sénégal", "salary_ref": 1250, "tension": "Moyenne"},
    "douala": {"lat": 4.0511, "lon": 9.7679, "label": "Douala, Cameroun", "salary_ref": 1100, "tension": "Moyenne"},
    "yaounde": {"lat": 3.8480, "lon": 11.5021, "label": "Yaoundé, Cameroun", "salary_ref": 1050, "tension": "Moyenne"},
    "libreville": {"lat": 0.4162, "lon": 9.4673, "label": "Libreville, Gabon", "salary_ref": 1400, "tension": "Moyenne"},
    "port-gentil": {"lat": -0.7193, "lon": 8.7815, "label": "Port-Gentil, Gabon", "salary_ref": 1450, "tension": "Moyenne"},
    "lome": {"lat": 6.1375, "lon": 1.2123, "label": "Lomé, Togo", "salary_ref": 1000, "tension": "Moyenne"},
    "cotonou": {"lat": 6.3703, "lon": 2.3912, "label": "Cotonou, Bénin", "salary_ref": 1000, "tension": "Moyenne"},
    "ouagadougou": {"lat": 12.3714, "lon": -1.5197, "label": "Ouagadougou, Burkina Faso", "salary_ref": 950, "tension": "Faible"},
    "bamako": {"lat": 12.6392, "lon": -8.0029, "label": "Bamako, Mali", "salary_ref": 950, "tension": "Faible"},
    "niamey": {"lat": 13.5116, "lon": 2.1254, "label": "Niamey, Niger", "salary_ref": 900, "tension": "Faible"},
    "conakry": {"lat": 9.6412, "lon": -13.5784, "label": "Conakry, Guinée", "salary_ref": 950, "tension": "Faible"},
    "ndjamena": {"lat": 12.1348, "lon": 15.0557, "label": "N'Djamena, Tchad", "salary_ref": 950, "tension": "Faible"},
    "bangui": {"lat": 4.3947, "lon": 18.5582, "label": "Bangui, Centrafrique", "salary_ref": 850, "tension": "Faible"},
    "antananarivo": {"lat": -18.8792, "lon": 47.5079, "label": "Antananarivo, Madagascar", "salary_ref": 900, "tension": "Moyenne"},
    "kigali": {"lat": -1.9441, "lon": 30.0619, "label": "Kigali, Rwanda", "salary_ref": 1200, "tension": "Moyenne"},
    "bujumbura": {"lat": -3.3822, "lon": 29.3644, "label": "Bujumbura, Burundi", "salary_ref": 900, "tension": "Faible"},
    "nairobi": {"lat": -1.2921, "lon": 36.8219, "label": "Nairobi, Kenya", "salary_ref": 1350, "tension": "Élevée"},
    "mombasa": {"lat": -4.0435, "lon": 39.6682, "label": "Mombasa, Kenya", "salary_ref": 1150, "tension": "Moyenne"},
    "kampala": {"lat": 0.3476, "lon": 32.5825, "label": "Kampala, Uganda", "salary_ref": 1100, "tension": "Moyenne"},
    "dar es salaam": {"lat": -6.7924, "lon": 39.2083, "label": "Dar es Salaam, Tanzania", "salary_ref": 1100, "tension": "Moyenne"},
    "addis ababa": {"lat": 9.0320, "lon": 38.7469, "label": "Addis Ababa, Ethiopia", "salary_ref": 1050, "tension": "Moyenne"},
    "addis-abeba": {"lat": 9.0320, "lon": 38.7469, "label": "Addis-Abeba, Éthiopie", "salary_ref": 1050, "tension": "Moyenne"},
    "lagos": {"lat": 6.5244, "lon": 3.3792, "label": "Lagos, Nigeria", "salary_ref": 1400, "tension": "Élevée"},
    "abuja": {"lat": 9.0765, "lon": 7.3986, "label": "Abuja, Nigeria", "salary_ref": 1350, "tension": "Moyenne"},
    "accra": {"lat": 5.6037, "lon": -0.1870, "label": "Accra, Ghana", "salary_ref": 1250, "tension": "Moyenne"},
    "johannesburg": {"lat": -26.2041, "lon": 28.0473, "label": "Johannesburg, South Africa", "salary_ref": 2200, "tension": "Élevée"},
    "cape town": {"lat": -33.9249, "lon": 18.4241, "label": "Cape Town, South Africa", "salary_ref": 2100, "tension": "Élevée"},
    "le cap": {"lat": -33.9249, "lon": 18.4241, "label": "Le Cap, Afrique du Sud", "salary_ref": 2100, "tension": "Élevée"},
    "pretoria": {"lat": -25.7479, "lon": 28.2293, "label": "Pretoria, South Africa", "salary_ref": 2000, "tension": "Moyenne"},
    "lusaka": {"lat": -15.3875, "lon": 28.3228, "label": "Lusaka, Zambia", "salary_ref": 1150, "tension": "Moyenne"},
    "ndola": {"lat": -12.9587, "lon": 28.6366, "label": "Ndola, Zambia", "salary_ref": 1100, "tension": "Moyenne"},
    "kitwe": {"lat": -12.8024, "lon": 28.2132, "label": "Kitwe, Zambia", "salary_ref": 1100, "tension": "Moyenne"},
    "harare": {"lat": -17.8252, "lon": 31.0335, "label": "Harare, Zimbabwe", "salary_ref": 1050, "tension": "Faible"},
    "luanda": {"lat": -8.8390, "lon": 13.2894, "label": "Luanda, Angola", "salary_ref": 1500, "tension": "Moyenne"},
    "gaborone": {"lat": -24.6282, "lon": 25.9231, "label": "Gaborone, Botswana", "salary_ref": 1300, "tension": "Moyenne"},
    "windhoek": {"lat": -22.5609, "lon": 17.0658, "label": "Windhoek, Namibia", "salary_ref": 1300, "tension": "Moyenne"},
    "maputo": {"lat": -25.9692, "lon": 32.5732, "label": "Maputo, Mozambique", "salary_ref": 1000, "tension": "Faible"},
    "casablanca": {"lat": 33.5731, "lon": -7.5898, "label": "Casablanca, Maroc", "salary_ref": 1500, "tension": "Élevée"},
    "rabat": {"lat": 34.0209, "lon": -6.8416, "label": "Rabat, Maroc", "salary_ref": 1450, "tension": "Moyenne"},
    "marrakech": {"lat": 31.6295, "lon": -7.9811, "label": "Marrakech, Maroc", "salary_ref": 1300, "tension": "Moyenne"},
    "tunis": {"lat": 36.8065, "lon": 10.1815, "label": "Tunis, Tunisie", "salary_ref": 1300, "tension": "Moyenne"},
    "alger": {"lat": 36.7538, "lon": 3.0588, "label": "Alger, Algérie", "salary_ref": 1250, "tension": "Moyenne"},
    "algiers": {"lat": 36.7538, "lon": 3.0588, "label": "Algiers, Algeria", "salary_ref": 1250, "tension": "Moyenne"},
    "le caire": {"lat": 30.0444, "lon": 31.2357, "label": "Le Caire, Égypte", "salary_ref": 1200, "tension": "Élevée"},
    "cairo": {"lat": 30.0444, "lon": 31.2357, "label": "Cairo, Egypt", "salary_ref": 1200, "tension": "Élevée"},

    # --- PARTIE 3 / 7 : EUROPE FRANCOPHONE & ANGLOPHONE ---
    "paris": {"lat": 48.8566, "lon": 2.3522, "label": "Paris, France", "salary_ref": 3600, "tension": "Très élevée"},
    "lyon": {"lat": 45.7640, "lon": 4.8357, "label": "Lyon, France", "salary_ref": 3100, "tension": "Élevée"},
    "marseille": {"lat": 43.2965, "lon": 5.3698, "label": "Marseille, France", "salary_ref": 2900, "tension": "Moyenne"},
    "bordeaux": {"lat": 44.8378, "lon": -0.5792, "label": "Bordeaux, France", "salary_ref": 3000, "tension": "Élevée"},
    "lille": {"lat": 50.6292, "lon": 3.0573, "label": "Lille, France", "salary_ref": 2950, "tension": "Moyenne"},
    "toulouse": {"lat": 43.6047, "lon": 1.4442, "label": "Toulouse, France", "salary_ref": 3050, "tension": "Élevée"},
    "nantes": {"lat": 47.2184, "lon": -1.5536, "label": "Nantes, France", "salary_ref": 3000, "tension": "Élevée"},
    "nice": {"lat": 43.7102, "lon": 7.2620, "label": "Nice, France", "salary_ref": 3000, "tension": "Moyenne"},
    "strasbourg": {"lat": 48.5734, "lon": 7.7521, "label": "Strasbourg, France", "salary_ref": 2950, "tension": "Moyenne"},
    "bruxelles": {"lat": 50.8503, "lon": 4.3517, "label": "Bruxelles, Belgique", "salary_ref": 3400, "tension": "Élevée"},
    "brussels": {"lat": 50.8503, "lon": 4.3517, "label": "Brussels, Belgium", "salary_ref": 3400, "tension": "Élevée"},
    "anvers": {"lat": 51.2194, "lon": 4.4025, "label": "Anvers, Belgique", "salary_ref": 3350, "tension": "Moyenne"},
    "antwerp": {"lat": 51.2194, "lon": 4.4025, "label": "Antwerp, Belgium", "salary_ref": 3350, "tension": "Moyenne"},
    "liege": {"lat": 50.6326, "lon": 5.5797, "label": "Liège, Belgique", "salary_ref": 3100, "tension": "Moyenne"},
    "geneve": {"lat": 46.2044, "lon": 6.1432, "label": "Genève, Suisse", "salary_ref": 5800, "tension": "Élevée"},
    "geneva": {"lat": 46.2044, "lon": 6.1432, "label": "Geneva, Switzerland", "salary_ref": 5800, "tension": "Élevée"},
    "zurich": {"lat": 47.3769, "lon": 8.5417, "label": "Zurich, Suisse", "salary_ref": 6200, "tension": "Élevée"},
    "lausanne": {"lat": 46.5197, "lon": 6.6323, "label": "Lausanne, Suisse", "salary_ref": 5500, "tension": "Élevée"},
    "luxembourg": {"lat": 49.6116, "lon": 6.1319, "label": "Luxembourg", "salary_ref": 4800, "tension": "Élevée"},
    "londres": {"lat": 51.5074, "lon": -0.1278, "label": "Londres, Royaume-Uni", "salary_ref": 4500, "tension": "Très élevée"},
    "london": {"lat": 51.5074, "lon": -0.1278, "label": "London, UK", "salary_ref": 4500, "tension": "Très élevée"},
    "manchester": {"lat": 53.4808, "lon": -2.2426, "label": "Manchester, UK", "salary_ref": 3600, "tension": "Élevée"},
    "birmingham": {"lat": 52.4862, "lon": -1.8904, "label": "Birmingham, UK", "salary_ref": 3400, "tension": "Moyenne"},
    "edinburgh": {"lat": 55.9533, "lon": -3.1883, "label": "Edinburgh, UK", "salary_ref": 3600, "tension": "Élevée"},
    "dublin": {"lat": 53.3498, "lon": -6.2603, "label": "Dublin, Ireland", "salary_ref": 4200, "tension": "Très élevée"},
    "berlin": {"lat": 52.5200, "lon": 13.4050, "label": "Berlin, Germany", "salary_ref": 3900, "tension": "Élevée"},
    "munich": {"lat": 48.1351, "lon": 11.5820, "label": "Munich, Germany", "salary_ref": 4400, "tension": "Élevée"},
    "frankfurt": {"lat": 50.1109, "lon": 8.6821, "label": "Frankfurt, Germany", "salary_ref": 4300, "tension": "Élevée"},
    "amsterdam": {"lat": 52.3676, "lon": 4.9041, "label": "Amsterdam, Netherlands", "salary_ref": 4100, "tension": "Très élevée"},
    "rotterdam": {"lat": 51.9244, "lon": 4.4777, "label": "Rotterdam, Netherlands", "salary_ref": 3800, "tension": "Élevée"},
    "madrid": {"lat": 40.4168, "lon": -3.7038, "label": "Madrid, Spain", "salary_ref": 2800, "tension": "Élevée"},
    "barcelone": {"lat": 41.3851, "lon": 2.1734, "label": "Barcelone, Espagne", "salary_ref": 2750, "tension": "Élevée"},
    "barcelona": {"lat": 41.3851, "lon": 2.1734, "label": "Barcelona, Spain", "salary_ref": 2750, "tension": "Élevée"},
    "rome": {"lat": 41.9028, "lon": 12.4964, "label": "Rome, Italy", "salary_ref": 2700, "tension": "Moyenne"},
    "milan": {"lat": 45.4642, "lon": 9.1900, "label": "Milan, Italy", "salary_ref": 3100, "tension": "Élevée"},
    "lisbonne": {"lat": 38.7223, "lon": -9.1393, "label": "Lisbonne, Portugal", "salary_ref": 2200, "tension": "Moyenne"},
    "lisbon": {"lat": 38.7223, "lon": -9.1393, "label": "Lisbon, Portugal", "salary_ref": 2200, "tension": "Moyenne"},
    "stockholm": {"lat": 59.3293, "lon": 18.0686, "label": "Stockholm, Sweden", "salary_ref": 4100, "tension": "Élevée"},
    "oslo": {"lat": 59.9139, "lon": 10.7522, "label": "Oslo, Norway", "salary_ref": 4600, "tension": "Moyenne"},
    "copenhagen": {"lat": 55.6761, "lon": 12.5683, "label": "Copenhagen, Denmark", "salary_ref": 4400, "tension": "Élevée"},
    "vienne": {"lat": 48.2082, "lon": 16.3738, "label": "Vienne, Autriche", "salary_ref": 3700, "tension": "Moyenne"},
    "vienna": {"lat": 48.2082, "lon": 16.3738, "label": "Vienna, Austria", "salary_ref": 3700, "tension": "Moyenne"},
    "varsovie": {"lat": 52.2297, "lon": 21.0122, "label": "Varsovie, Pologne", "salary_ref": 2300, "tension": "Élevée"},
    "warsaw": {"lat": 52.2297, "lon": 21.0122, "label": "Warsaw, Poland", "salary_ref": 2300, "tension": "Élevée"},

    # --- PARTIE 4 / 7 : AMÉRIQUE DU NORD & DU SUD ---
    "montreal": {"lat": 45.5017, "lon": -73.5673, "label": "Montréal, Canada", "salary_ref": 3800, "tension": "Élevée"},
    "toronto": {"lat": 43.6532, "lon": -79.3832, "label": "Toronto, Canada", "salary_ref": 4200, "tension": "Élevée"},
    "vancouver": {"lat": 49.2827, "lon": -123.1207, "label": "Vancouver, Canada", "salary_ref": 4100, "tension": "Élevée"},
    "ottawa": {"lat": 45.4215, "lon": -75.6972, "label": "Ottawa, Canada", "salary_ref": 3900, "tension": "Moyenne"},
    "quebec": {"lat": 46.8139, "lon": -71.2080, "label": "Québec, Canada", "salary_ref": 3500, "tension": "Moyenne"},
    "calgary": {"lat": 51.0447, "lon": -114.0719, "label": "Calgary, Canada", "salary_ref": 4000, "tension": "Moyenne"},
    "new york": {"lat": 40.7128, "lon": -74.0060, "label": "New York, USA", "salary_ref": 5800, "tension": "Très élevée"},
    "san francisco": {"lat": 37.7749, "lon": -122.4194, "label": "San Francisco, USA", "salary_ref": 6500, "tension": "Très élevée"},
    "los angeles": {"lat": 34.0522, "lon": -118.2437, "label": "Los Angeles, USA", "salary_ref": 5200, "tension": "Élevée"},
    "chicago": {"lat": 41.8781, "lon": -87.6298, "label": "Chicago, USA", "salary_ref": 4900, "tension": "Élevée"},
    "boston": {"lat": 42.3601, "lon": -71.0589, "label": "Boston, USA", "salary_ref": 5300, "tension": "Élevée"},
    "seattle": {"lat": 47.6062, "lon": -122.3321, "label": "Seattle, USA", "salary_ref": 5600, "tension": "Élevée"},
    "austin": {"lat": 30.2672, "lon": -97.7431, "label": "Austin, USA", "salary_ref": 4800, "tension": "Élevée"},
    "miami": {"lat": 25.7617, "lon": -80.1918, "label": "Miami, USA", "salary_ref": 4600, "tension": "Élevée"},
    "washington": {"lat": 38.9072, "lon": -77.0369, "label": "Washington D.C., USA", "salary_ref": 5200, "tension": "Élevée"},
    "houston": {"lat": 29.7604, "lon": -95.3698, "label": "Houston, USA", "salary_ref": 4700, "tension": "Moyenne"},
    "atlanta": {"lat": 33.7490, "lon": -84.3880, "label": "Atlanta, USA", "salary_ref": 4600, "tension": "Élevée"},
    "mexico": {"lat": 19.4326, "lon": -99.1332, "label": "Mexico City, Mexico", "salary_ref": 1800, "tension": "Élevée"},
    "sao paulo": {"lat": -23.5505, "lon": -46.6333, "label": "São Paulo, Brazil", "salary_ref": 1900, "tension": "Élevée"},
    "rio de janeiro": {"lat": -22.9068, "lon": -43.1729, "label": "Rio de Janeiro, Brazil", "salary_ref": 1750, "tension": "Moyenne"},
    "buenos aires": {"lat": -34.6037, "lon": -58.3816, "label": "Buenos Aires, Argentina", "salary_ref": 1600, "tension": "Moyenne"},
    "bogota": {"lat": 4.7110, "lon": -74.0721, "label": "Bogotá, Colombia", "salary_ref": 1500, "tension": "Moyenne"},
    "santiago": {"lat": -33.4489, "lon": -70.6693, "label": "Santiago, Chile", "salary_ref": 1800, "tension": "Moyenne"},
    "lima": {"lat": -12.0464, "lon": -77.0428, "label": "Lima, Peru", "salary_ref": 1450, "tension": "Moyenne"},

    # --- PARTIE 5 / 7 : ASIE, MOYEN-ORIENT & OCÉANIE ---
    "dubai": {"lat": 25.2048, "lon": 55.2708, "label": "Dubaï, Émirats Arabes Unis", "salary_ref": 4500, "tension": "Élevée"},
    "abu dhabi": {"lat": 24.4539, "lon": 54.3773, "label": "Abu Dhabi, UAE", "salary_ref": 4400, "tension": "Élevée"},
    "riyadh": {"lat": 24.7136, "lon": 46.6753, "label": "Riyadh, Saudi Arabia", "salary_ref": 4100, "tension": "Élevée"},
    "riyad": {"lat": 24.7136, "lon": 46.6753, "label": "Riyad, Arabie Saoudite", "salary_ref": 4100, "tension": "Élevée"},
    "doha": {"lat": 25.2854, "lon": 51.5310, "label": "Doha, Qatar", "salary_ref": 4300, "tension": "Élevée"},
    "istanbul": {"lat": 41.0082, "lon": 28.9784, "label": "Istanbul, Turkey", "salary_ref": 1800, "tension": "Élevée"},
    "tokyo": {"lat": 35.6762, "lon": 139.6503, "label": "Tokyo, Japan", "salary_ref": 4200, "tension": "Élevée"},
    "seoul": {"lat": 37.5665, "lon": 126.9780, "label": "Seoul, South Korea", "salary_ref": 3800, "tension": "Élevée"},
    "pekin": {"lat": 39.9042, "lon": 116.4074, "label": "Pékin, Chine", "salary_ref": 2800, "tension": "Élevée"},
    "beijing": {"lat": 39.9042, "lon": 116.4074, "label": "Beijing, China", "salary_ref": 2800, "tension": "Élevée"},
    "shanghai": {"lat": 31.2304, "lon": 121.4737, "label": "Shanghai, China", "salary_ref": 2900, "tension": "Élevée"},
    "hong kong": {"lat": 22.3193, "lon": 114.1694, "label": "Hong Kong", "salary_ref": 4600, "tension": "Très élevée"},
    "singapour": {"lat": 1.3521, "lon": 103.8198, "label": "Singapour", "salary_ref": 4800, "tension": "Très élevée"},
    "singapore": {"lat": 1.3521, "lon": 103.8198, "label": "Singapore", "salary_ref": 4800, "tension": "Très élevée"},
    "bangalore": {"lat": 12.9716, "lon": 77.5946, "label": "Bangalore, India", "salary_ref": 1800, "tension": "Élevée"},
    "bengaluru": {"lat": 12.9716, "lon": 77.5946, "label": "Bengaluru, India", "salary_ref": 1800, "tension": "Élevée"},
    "mumbai": {"lat": 19.0760, "lon": 72.8777, "label": "Mumbai, India", "salary_ref": 1750, "tension": "Élevée"},
    "new delhi": {"lat": 28.6139, "lon": 77.2090, "label": "New Delhi, India", "salary_ref": 1700, "tension": "Élevée"},
    "kuala lumpur": {"lat": 3.1390, "lon": 101.6869, "label": "Kuala Lumpur, Malaysia", "salary_ref": 1900, "tension": "Moyenne"},
    "bangkok": {"lat": 13.7563, "lon": 100.5018, "label": "Bangkok, Thailand", "salary_ref": 1700, "tension": "Moyenne"},
    "jakarta": {"lat": -6.2088, "lon": 106.8456, "label": "Jakarta, Indonesia", "salary_ref": 1500, "tension": "Moyenne"},
    "manille": {"lat": 14.5995, "lon": 120.9842, "label": "Manille, Philippines", "salary_ref": 1400, "tension": "Moyenne"},
    "manila": {"lat": 14.5995, "lon": 120.9842, "label": "Manila, Philippines", "salary_ref": 1400, "tension": "Moyenne"},
    "sydney": {"lat": -33.8688, "lon": 151.2093, "label": "Sydney, Australia", "salary_ref": 4600, "tension": "Élevée"},
    "melbourne": {"lat": -37.8136, "lon": 144.9631, "label": "Melbourne, Australia", "salary_ref": 4400, "tension": "Élevée"},
    "auckland": {"lat": -36.8485, "lon": 174.7633, "label": "Auckland, New Zealand", "salary_ref": 3900, "tension": "Moyenne"},

    # --- PARTIE 6 / 7 : PAYS MONDIAUX (FRANÇAIS & ANGLAIS) ---
    "rdc": {"lat": -4.4419, "lon": 15.2663, "label": "RDC", "salary_ref": 1150, "tension": "Moyenne"},
    "drc": {"lat": -4.4419, "lon": 15.2663, "label": "DRC", "salary_ref": 1150, "tension": "Moyenne"},
    "republique democratique du congo": {"lat": -4.4419, "lon": 15.2663, "label": "RDC", "salary_ref": 1150, "tension": "Moyenne"},
    "democratic republic of the congo": {"lat": -4.4419, "lon": 15.2663, "label": "DRC", "salary_ref": 1150, "tension": "Moyenne"},
    "congo": {"lat": -4.2634, "lon": 15.2429, "label": "Congo", "salary_ref": 1100, "tension": "Moyenne"},
    "france": {"lat": 48.8566, "lon": 2.3522, "label": "France", "salary_ref": 3300, "tension": "Élevée"},
    "belgique": {"lat": 50.8503, "lon": 4.3517, "label": "Belgique", "salary_ref": 3400, "tension": "Élevée"},
    "belgium": {"lat": 50.8503, "lon": 4.3517, "label": "Belgium", "salary_ref": 3400, "tension": "Élevée"},
    "suisse": {"lat": 46.2044, "lon": 6.1432, "label": "Suisse", "salary_ref": 5500, "tension": "Élevée"},
    "switzerland": {"lat": 46.2044, "lon": 6.1432, "label": "Switzerland", "salary_ref": 5500, "tension": "Élevée"},
    "canada": {"lat": 45.5017, "lon": -73.5673, "label": "Canada", "salary_ref": 3800, "tension": "Élevée"},
    "etats-unis": {"lat": 40.7128, "lon": -74.0060, "label": "États-Unis", "salary_ref": 5000, "tension": "Élevée"},
    "united states": {"lat": 40.7128, "lon": -74.0060, "label": "United States", "salary_ref": 5000, "tension": "Élevée"},
    "usa": {"lat": 40.7128, "lon": -74.0060, "label": "USA", "salary_ref": 5000, "tension": "Élevée"},
    "royaume-uni": {"lat": 51.5074, "lon": -0.1278, "label": "Royaume-Uni", "salary_ref": 4200, "tension": "Élevée"},
    "united kingdom": {"lat": 51.5074, "lon": -0.1278, "label": "United Kingdom", "salary_ref": 4200, "tension": "Élevée"},
    "uk": {"lat": 51.5074, "lon": -0.1278, "label": "UK", "salary_ref": 4200, "tension": "Élevée"},
    "allemagne": {"lat": 52.5200, "lon": 13.4050, "label": "Allemagne", "salary_ref": 3800, "tension": "Élevée"},
    "germany": {"lat": 52.5200, "lon": 13.4050, "label": "Germany", "salary_ref": 3800, "tension": "Élevée"},
    "espagne": {"lat": 40.4168, "lon": -3.7038, "label": "Espagne", "salary_ref": 2700, "tension": "Élevée"},
    "spain": {"lat": 40.4168, "lon": -3.7038, "label": "Spain", "salary_ref": 2700, "tension": "Élevée"},
    "italie": {"lat": 41.9028, "lon": 12.4964, "label": "Italie", "salary_ref": 2800, "tension": "Moyenne"},
    "italy": {"lat": 41.9028, "lon": 12.4964, "label": "Italy", "salary_ref": 2800, "tension": "Moyenne"},
    "pays-bas": {"lat": 52.3676, "lon": 4.9041, "label": "Pays-Bas", "salary_ref": 4000, "tension": "Élevée"},
    "netherlands": {"lat": 52.3676, "lon": 4.9041, "label": "Netherlands", "salary_ref": 4000, "tension": "Élevée"},
    "portugal": {"lat": 38.7223, "lon": -9.1393, "label": "Portugal", "salary_ref": 2200, "tension": "Moyenne"},
    "irlande": {"lat": 53.3498, "lon": -6.2603, "label": "Irlande", "salary_ref": 4100, "tension": "Élevée"},
    "ireland": {"lat": 53.3498, "lon": -6.2603, "label": "Ireland", "salary_ref": 4100, "tension": "Élevée"},
    "suede": {"lat": 59.3293, "lon": 18.0686, "label": "Suède", "salary_ref": 4000, "tension": "Élevée"},
    "sweden": {"lat": 59.3293, "lon": 18.0686, "label": "Sweden", "salary_ref": 4000, "tension": "Élevée"},
    "norvege": {"lat": 59.9139, "lon": 10.7522, "label": "Norvège", "salary_ref": 4500, "tension": "Moyenne"},
    "norway": {"lat": 59.9139, "lon": 10.7522, "label": "Norway", "salary_ref": 4500, "tension": "Moyenne"},
    "cote d'ivoire": {"lat": 5.3600, "lon": -4.0083, "label": "Côte d'Ivoire", "salary_ref": 1300, "tension": "Élevée"},
    "ivory coast": {"lat": 5.3600, "lon": -4.0083, "label": "Ivory Coast", "salary_ref": 1300, "tension": "Élevée"},
    "senegal": {"lat": 14.7167, "lon": -17.4677, "label": "Sénégal", "salary_ref": 1250, "tension": "Moyenne"},
    "cameroun": {"lat": 4.0511, "lon": 9.7679, "label": "Cameroun", "salary_ref": 1100, "tension": "Moyenne"},
    "cameroon": {"lat": 4.0511, "lon": 9.7679, "label": "Cameroon", "salary_ref": 1100, "tension": "Moyenne"},
    "rwanda": {"lat": -1.9441, "lon": 30.0619, "label": "Rwanda", "salary_ref": 1200, "tension": "Moyenne"},
    "kenya": {"lat": -1.2921, "lon": 36.8219, "label": "Kenya", "salary_ref": 1350, "tension": "Élevée"},
    "uganda": {"lat": 0.3476, "lon": 32.5825, "label": "Uganda", "salary_ref": 1100, "tension": "Moyenne"},
    "ouganda": {"lat": 0.3476, "lon": 32.5825, "label": "Ouganda", "salary_ref": 1100, "tension": "Moyenne"},
    "tanzania": {"lat": -6.7924, "lon": 39.2083, "label": "Tanzania", "salary_ref": 1100, "tension": "Moyenne"},
    "tanzanie": {"lat": -6.7924, "lon": 39.2083, "label": "Tanzanie", "salary_ref": 1100, "tension": "Moyenne"},
    "nigeria": {"lat": 6.5244, "lon": 3.3792, "label": "Nigeria", "salary_ref": 1350, "tension": "Élevée"},
    "ghana": {"lat": 5.6037, "lon": -0.1870, "label": "Ghana", "salary_ref": 1250, "tension": "Moyenne"},
    "afrique du sud": {"lat": -26.2041, "lon": 28.0473, "label": "Afrique du Sud", "salary_ref": 2200, "tension": "Élevée"},
    "south africa": {"lat": -26.2041, "lon": 28.0473, "label": "South Africa", "salary_ref": 2200, "tension": "Élevée"},
    "maroc": {"lat": 33.5731, "lon": -7.5898, "label": "Maroc", "salary_ref": 1500, "tension": "Élevée"},
    "morocco": {"lat": 33.5731, "lon": -7.5898, "label": "Morocco", "salary_ref": 1500, "tension": "Élevée"},
    "tunisie": {"lat": 36.8065, "lon": 10.1815, "label": "Tunisie", "salary_ref": 1300, "tension": "Moyenne"},
    "tunisia": {"lat": 36.8065, "lon": 10.1815, "label": "Tunisia", "salary_ref": 1300, "tension": "Moyenne"},
    "algerie": {"lat": 36.7538, "lon": 3.0588, "label": "Algérie", "salary_ref": 1250, "tension": "Moyenne"},
    "algeria": {"lat": 36.7538, "lon": 3.0588, "label": "Algeria", "salary_ref": 1250, "tension": "Moyenne"},
    "egypte": {"lat": 30.0444, "lon": 31.2357, "label": "Égypte", "salary_ref": 1200, "tension": "Élevée"},
    "egypt": {"lat": 30.0444, "lon": 31.2357, "label": "Egypt", "salary_ref": 1200, "tension": "Élevée"},
    "gabon": {"lat": 0.4162, "lon": 9.4673, "label": "Gabon", "salary_ref": 1400, "tension": "Moyenne"},
    "angola": {"lat": -8.8390, "lon": 13.2894, "label": "Angola", "salary_ref": 1500, "tension": "Moyenne"},
    "zambie": {"lat": -15.3875, "lon": 28.3228, "label": "Zambie", "salary_ref": 1100, "tension": "Moyenne"},
    "zambia": {"lat": -15.3875, "lon": 28.3228, "label": "Zambia", "salary_ref": 1100, "tension": "Moyenne"},
    "burundi": {"lat": -3.3822, "lon": 29.3644, "label": "Burundi", "salary_ref": 900, "tension": "Faible"},
    "togo": {"lat": 6.1375, "lon": 1.2123, "label": "Togo", "salary_ref": 1000, "tension": "Moyenne"},
    "benin": {"lat": 6.3703, "lon": 2.3912, "label": "Bénin", "salary_ref": 1000, "tension": "Moyenne"},
    "mali": {"lat": 12.6392, "lon": -8.0029, "label": "Mali", "salary_ref": 950, "tension": "Faible"},
    "burkina faso": {"lat": 12.3714, "lon": -1.5197, "label": "Burkina Faso", "salary_ref": 950, "tension": "Faible"},
    "guinee": {"lat": 9.6412, "lon": -13.5784, "label": "Guinée", "salary_ref": 950, "tension": "Faible"},
    "guinea": {"lat": 9.6412, "lon": -13.5784, "label": "Guinea", "salary_ref": 950, "tension": "Faible"},
    "madagascar": {"lat": -18.8792, "lon": 47.5079, "label": "Madagascar", "salary_ref": 900, "tension": "Moyenne"},
    "inde": {"lat": 20.5937, "lon": 78.9629, "label": "Inde", "salary_ref": 1750, "tension": "Élevée"},
    "india": {"lat": 20.5937, "lon": 78.9629, "label": "India", "salary_ref": 1750, "tension": "Élevée"},
    "chine": {"lat": 35.8617, "lon": 104.1954, "label": "Chine", "salary_ref": 2800, "tension": "Élevée"},
    "china": {"lat": 35.8617, "lon": 104.1954, "label": "China", "salary_ref": 2800, "tension": "Élevée"},
    "japon": {"lat": 36.2048, "lon": 138.2529, "label": "Japon", "salary_ref": 4200, "tension": "Élevée"},
    "japan": {"lat": 36.2048, "lon": 138.2529, "label": "Japan", "salary_ref": 4200, "tension": "Élevée"},
    "australie": {"lat": -25.2744, "lon": 133.7751, "label": "Australie", "salary_ref": 4400, "tension": "Élevée"},
    "australia": {"lat": -25.2744, "lon": 133.7751, "label": "Australia", "salary_ref": 4400, "tension": "Élevée"},
    "bresil": {"lat": -14.2350, "lon": -51.9253, "label": "Brésil", "salary_ref": 1800, "tension": "Élevée"},
    "brazil": {"lat": -14.2350, "lon": -51.9253, "label": "Brazil", "salary_ref": 1800, "tension": "Élevée"},
    "emirats arabes unis": {"lat": 23.4241, "lon": 53.8478, "label": "Émirats Arabes Unis", "salary_ref": 4400, "tension": "Élevée"},
    "uae": {"lat": 23.4241, "lon": 53.8478, "label": "UAE", "salary_ref": 4400, "tension": "Élevée"},
    "arabie saoudite": {"lat": 23.8859, "lon": 45.0792, "label": "Arabie Saoudite", "salary_ref": 4100, "tension": "Élevée"},
    "saudi arabia": {"lat": 23.8859, "lon": 45.0792, "label": "Saudi Arabia", "salary_ref": 4100, "tension": "Élevée"},
    "qatar": {"lat": 25.3548, "lon": 51.1839, "label": "Qatar", "salary_ref": 4300, "tension": "Élevée"},
    "turquie": {"lat": 38.9637, "lon": 35.2433, "label": "Turquie", "salary_ref": 1800, "tension": "Élevée"},
    "turkey": {"lat": 38.9637, "lon": 35.2433, "label": "Turkey", "salary_ref": 1800, "tension": "Élevée"}
}


def normalize_text(text):
    if not text:
        return ""
    text = text.lower()
    text = unicodedata.normalize("NFD", text)
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def extract_text_and_meta_from_pdf(file_bytes):
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
        pages_text = []
        num_pages = len(reader.pages)
        has_images = False
        for page in reader.pages:
            t = page.extract_text()
            if t:
                pages_text.append(t)
            if hasattr(page, "images") and len(page.images) > 0:
                has_images = True
        full_text = "\n".join(pages_text)
        return full_text, {"pages": num_pages, "has_images": has_images}
    except Exception:
        return "", {"pages": 0, "has_images": False}


def extract_cv_photo_base64(file_bytes):
    """Extrait la photo portrait du candidat via OpenCV si possible, avec repli garanti sur l'image portrait du CV."""
    try:
        _r = pdf_vision_extractor.extract_photo(PdfReader(io.BytesIO(file_bytes)))
        return _r["photo_base64"]
    except Exception:
        pass
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
        face_cascade = None
        if HAS_CV2:
            cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            face_cascade = cv2.CascadeClassifier(cascade_path)

        best_fallback = None
        best_area = 0

        for page in reader.pages[:2]:
            if not hasattr(page, "images"):
                continue
            for img in page.images:
                try:
                    pil_img = Image.open(io.BytesIO(img.data)).convert("RGB")
                    w, h = pil_img.size
                    if w < 50 or h < 50 or w > 3000 or h > 3000:
                        continue
                    ratio = w / float(h)
                    if ratio < 0.45 or ratio > 1.85:
                        continue

                    if HAS_CV2 and face_cascade is not None:
                        np_img = np.array(pil_img)
                        bgr = cv2.cvtColor(np_img, cv2.COLOR_RGB2BGR)
                        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
                        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.08, minNeighbors=3, minSize=(24, 24))

                        if len(faces) > 0:
                            x, y, fw, fh = max(faces, key=lambda f: f[2] * f[3])
                            pad_x = int(fw * 0.45)
                            pad_y = int(fh * 0.55)
                            x1 = max(0, x - pad_x)
                            y1 = max(0, y - pad_y)
                            x2 = min(w, x + fw + pad_x)
                            y2 = min(h, y + fh + pad_y)
                            cropped = pil_img.crop((x1, y1, x2, y2)).resize((160, 160))
                            out = io.BytesIO()
                            cropped.save(out, format="PNG")
                            b64 = base64.b64encode(out.getvalue()).decode("utf-8")
                            return f"data:image/png;base64,{b64}"

                    # Repli fiable : garde la photo portrait (ni bannière trop large ni icône minuscule)
                    if 0.52 <= ratio <= 1.55 and (w * h) > best_area:
                        best_area = w * h
                        resized = pil_img.resize((160, 160))
                        out = io.BytesIO()
                        resized.save(out, format="PNG")
                        b64 = base64.b64encode(out.getvalue()).decode("utf-8")
                        best_fallback = f"data:image/png;base64,{b64}"
                except Exception:
                    continue

        return best_fallback
    except Exception:
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
        return f"{p1} {p2}", f"{p1[0]}{p2[0]}"

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


def extract_experience_and_gaps(cv_text):
    """Calcule la durée totale d'expérience et repère les trous chronologiques > 6 mois."""
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
        years = max([int(x) for x in m if 0 < int(x) <= 35], default=0)
        return years, []

    intervals.sort(key=lambda x: x[0])
    merged = []
    gaps = []

    for iv in intervals:
        if not merged:
            merged.append([iv[0], iv[1]])
        else:
            prev_end = merged[-1][1]
            gap_months = iv[0] - prev_end
            if gap_months > 6:
                py, pm = divmod(prev_end - 1, 12)
                ny, nm = divmod(iv[0] - 1, 12)
                gaps.append(f"Période inactive de {gap_months} mois détectée ({pm + 1:02d}/{py} à {nm + 1:02d}/{ny})")
            if iv[0] > prev_end:
                merged.append([iv[0], iv[1]])
            else:
                merged[-1][1] = max(merged[-1][1], iv[1])

    total_months = sum(m[1] - m[0] for m in merged)
    return round(total_months / 12, 1), gaps

def detect_education(text):
    norm = normalize_text(text)

    # Règle spécifique RDC Ancien Système : Graduat (3 ans) + Licence (2 ans) = Bac+5 (Rang 4)
    if "graduat" in norm and "licence" in norm and "lmd" not in norm:
        return "Licence (Ancien Système : Graduat + 2 ans / Bac+5)", 4

    for label, rank, keywords in EDUCATION_LEVELS:
        for kw in keywords:
            if re.search(r"(?<![a-z0-9])" + re.escape(kw) + r"(?![a-z0-9])", norm):
                m_spec = re.search(
                    r"\b(?:" + re.escape(kw) + r")\s+(?:en|de|d['’]|in|of)\s+([A-Za-zÀ-ÿ\s&'-]{3,48})",
                    text,
                    re.IGNORECASE
                )
                if m_spec:
                    spec = m_spec.group(1).strip(" .,-–—\n\r")
                    return f"{label.split('(')[0].strip()} en {spec}", rank
                return label, rank
    return "Non précisé", 0

def detect_languages(text):
    norm = normalize_text(text)
    return ["Français" if l == "francais" else l.capitalize() for l in LANGUAGES_LIST if re.search(r"\b" + l + r"\b", norm)]


_PROG_CONTEXT = re.compile(r"(programm|d[eé]velop|\bcode\b|coder|logiciel|software|algorithm|data|statisti)", re.I)


def extract_skills(text, is_offer=False, reference_offer_skills=None):
    """Extrait 100 % des compétences (base élargie + synonymes + extraction dynamique depuis l'offre)."""
    # adresses e-mail et liens ne sont jamais des compétences (ex. "rh@..." ne doit pas donner "Ressources humaines")
    text = re.sub(r"https?://\S+|[\w.+-]+@[\w-]+(?:\.[\w-]+)+", " ", text or "")
    norm_text = normalize_text(text)
    for syn, canonical in SKILL_SYNONYMS.items():
        norm_text = re.sub(r"(?<![a-z0-9])" + re.escape(syn) + r"(?![a-z0-9])", canonical, norm_text)

    found_skills = {}
    skill_freq = {}

    for category, skills_list in SKILLS_DB.items():
        matched = []
        for skill in skills_list:
            norm_skill = normalize_text(skill)
            if len(norm_skill) <= 2 and norm_skill.isalpha() or norm_skill in ("go", "sh"):
                # « D », « R », « C », « Go » : acceptes seulement ecrits en majuscule isolee ET dans un contexte de programmation
                if not (_PROG_CONTEXT.search(text) and re.search(r"(?<![A-Za-z0-9'’])" + re.escape(skill.capitalize() if len(skill) > 1 else skill.upper()) + r"(?![A-Za-z0-9'’])", text)):
                    continue
            matches = re.findall(r"(?<![a-z0-9])" + re.escape(norm_skill) + r"(?![a-z0-9])", norm_text)
            if matches:
                disp = skill.upper() if len(skill) <= 3 else skill.capitalize()
                matched.append(disp)
                skill_freq[disp] = len(matches)
        if matched:
            found_skills[category] = sorted(list(set(matched)))

    if is_offer:
        dynamic_reqs = []
        known_norm = {normalize_text(s) for sub in found_skills.values() for s in sub}
        for line in text.splitlines():
            clean_l = line.strip()
            if len(clean_l) < 4 or len(clean_l) > 160:
                continue
            if re.match(r"^[-•*▪➢✔✓►◦·\d+.)]", clean_l) or any(k in normalize_text(clean_l) for k in ("maitrise", "connaissance", "competence", "outil", "logiciel", "exige", "requis")):
                for phrase in skills_referential.phrases_from_requirement_line(clean_l):
                    np_ = normalize_text(phrase)
                    if np_ not in known_norm and phrase not in dynamic_reqs:
                        dynamic_reqs.append(phrase)
                        known_norm.add(np_)
        if dynamic_reqs:
            found_skills["Compétences Spécifiques de l'Offre"] = sorted(dynamic_reqs[:25])

    if not is_offer and reference_offer_skills:
        extra_cv = []
        for req_s in reference_offer_skills:
            n_req = normalize_text(req_s)
            if n_req and re.search(r"(?<![a-z0-9])" + re.escape(n_req) + r"(?![a-z0-9])", norm_text):
                extra_cv.append(req_s)
        if extra_cv:
            existing = set(found_skills.get("Compétences Spécifiques de l'Offre", []))
            found_skills["Compétences Spécifiques de l'Offre"] = sorted(list(existing | set(extra_cv)))

    for _cat in list(found_skills):
        found_skills[_cat] = skills_referential.clean_skill_list(found_skills[_cat])
        if not found_skills[_cat]:
            del found_skills[_cat]
    all_flat = sorted({s for sub in found_skills.values() for s in sub})
    return found_skills, all_flat, skill_freq


def analyze_posture_and_impact(cv_text):
    """Analyse la posture dominante (Analytique/Managériale/Opérationnelle) et l'impact rédactionnel."""
    norm = normalize_text(cv_text)
    scores = {}
    for posture, kws in POSTURE_LEXICON.items():
        count = sum(len(re.findall(r"\b" + re.escape(normalize_text(k)) + r"\b", norm)) for k in kws)
        scores[posture] = count

    dominant = max(scores, key=scores.get) if any(scores.values()) else "Polyvalente"

    verbs_found = [v.capitalize() for v in ACTION_VERBS if re.search(r"\b" + re.escape(normalize_text(v)) + r"\b", norm)]
    metrics_found = re.findall(r"(?:\+?\d+\s*%|\d+\s*(?:projets|clients|personnes|membres|ans|k€|k\$|\$|€|millions?))", norm)

    impact_score = min(100, (len(verbs_found) * 8) + (len(metrics_found) * 12) + 20)
    return {
        "posture": dominant,
        "posture_scores": scores,
        "action_verbs_count": len(verbs_found),
        "action_verbs_sample": verbs_found[:6],
        "metrics_count": len(metrics_found),
        "impact_score": impact_score
    }


def audit_ats_readiness(cv_text, pdf_meta=None):
    """Vérifie la lisibilité technique ATS du CV."""
    pdf_meta = pdf_meta or {"pages": 1, "has_images": False}
    norm = normalize_text(cv_text)
    checks = []

    text_ok = len(cv_text.strip()) >= 180
    checks.append({
        "label": "Texte 100 % extractible (non scanné en image)",
        "ok": text_ok,
        "detail": "Texte natif lisible par les robots ATS." if text_ok else "Texte très court ou PDF image."
    })

    pages = pdf_meta.get("pages", 1)
    pages_ok = 1 <= pages <= 3
    checks.append({
        "label": f"Longueur optimale ({pages} page(s))",
        "ok": pages_ok,
        "detail": "Format idéal (1 à 2 pages)." if pages <= 2 else "CV long, veillez à synthétiser."
    })

    has_exp = any(k in norm for k in ("experience", "parcours", "emploi"))
    has_edu = any(k in norm for k in ("formation", "etude", "diplome", "education"))
    has_sk = any(k in norm for k in ("competence", "outil", "technique", "skill"))
    struct_ok = has_exp and has_edu and has_sk
    checks.append({
        "label": "Rubriques ATS standards (Expérience, Formation, Compétences)",
        "ok": struct_ok,
        "detail": "Toutes les sections clés sont identifiées." if struct_ok else "Une section standard manque de titre clair."
    })

    has_contact = ("@" in cv_text) and bool(re.search(r"\d{8,}", re.sub(r"\D", "", cv_text)))
    checks.append({
        "label": "Coordonnées directes (E-mail & Téléphone)",
        "ok": has_contact,
        "detail": "Coordonnées exploitables détectées." if has_contact else "E-mail ou téléphone manquant."
    })

    passed = sum(1 for c in checks if c["ok"])
    ats_pct = round((passed / len(checks)) * 100)
    return {"ats_ready_pct": ats_pct, "checks": checks}

def extract_professions_and_objective(cv_text, all_skills):
    norm = normalize_text(cv_text)
    roles = [r.title() for r in PROFESSION_KEYWORDS if normalize_text(r) in norm]

    # Si le métier exact n'est pas dans la liste fixe, on relève directement le titre écrit en haut du CV
    if not roles:
        ignore_words = ("curriculum", "vitae", "cv", "resume", "contact", "telephone", "email", "adresse", "profil", "experience", "formation")
        for line in [l.strip() for l in cv_text.splitlines() if l.strip()][:8]:
            nl = normalize_text(line)
            if "@" in line or "http" in nl or re.search(r"\d{3,}", line):
                continue
            if any(w in nl for w in ignore_words):
                continue
            words = line.split()
            if 2 <= len(words) <= 6:
                roles.append(line.strip(" -–—|:•").title())
                break

    main_role = roles[0] if roles else (f"Spécialiste {all_skills[0]}" if all_skills else "Professionnel")
    sec_roles = roles[1:]

    obj_m = re.search(r"(?:profil|objectif|a propos|resume|accroche|summary)\s*[:\-]?\s*([^\n]{25,220})", cv_text, re.IGNORECASE)
    if obj_m:
        objective = obj_m.group(1).strip()
    else:
        sk = ", ".join(all_skills[:4]) if all_skills else "ses compétences métier"
        objective = f"Professionnel maîtrisant {sk}, prêt à contribuer aux projets de l'organisation."
    return main_role, sec_roles, objective

_SKILL_WORDS_CACHE = None


def _all_skill_words():
    global _SKILL_WORDS_CACHE
    if _SKILL_WORDS_CACHE is None:
        _SKILL_WORDS_CACHE = {str(x).lower() for lst in SKILLS_DB.values() for x in lst}
    return _SKILL_WORDS_CACHE


def extract_universal_location(text):
    if not text:
        return ""

    # 1. Mentions explicites (Lieu, Adresse, Ville, Pays, Location, Based in...)
    for pat in [
        r"(?:lieu|location|ville|pays|bas[eé]\s+[aà]|poste\s+[aà]|based\s+in)\s*[:\-]\s*([^\n\r.;|]{2,60})",
        r"(?:adresse|address)\s*[:\-]\s*([^\n\r;|]{3,70})"
    ]:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()

    # 2. Format universel "Quartier/Commune, Ville, Pays" ou "Ville, Pays" dans les 15 premières lignes
    header_lines = [l.strip() for l in text.splitlines() if l.strip()][:15]
    for line in header_lines:
        if "@" in line or "http" in line.lower():
            continue
        m_city_country = re.search(
            r"\b([A-ZÀ-Ÿ][a-zA-ZÀ-ÿ'-]{2,25}(?:\s*,\s*[A-ZÀ-Ÿ][a-zA-ZÀ-ÿ'-]{2,25}){1,2})\b",
            line
        )
        if m_city_country:
            cand_loc = m_city_country.group(1).strip()
            parts_lc = [x.strip().lower() for x in cand_loc.split(",")]
            looks_like_skills = any(x in _all_skill_words() for x in parts_lc)  # "Python, SQL, Docker" n'est pas un lieu
            if not looks_like_skills and not any(w in normalize_text(cand_loc) for w in ("experience", "formation", "competence", "curriculum", "profil")):
                return cand_loc

        # Format code postal + ville (ex: 75008 Paris, 1000 Bruxelles, H3B 2Y5 Montréal)
        m_zip = re.search(r"\b(\d{4,5}\s+[A-ZÀ-Ÿ][a-zA-ZÀ-ÿ'-]{2,25}(?:\s*,\s*[A-ZÀ-Ÿ][a-zA-ZÀ-ÿ'-]{2,25})?)\b", line)
        if m_zip:
            return m_zip.group(1).strip()

    # 3. Recherche parmi les grandes villes internationales connues
    norm = normalize_text(text)
    for city_key, info in CITY_COORDS.items():
        if re.search(r"\b" + re.escape(city_key) + r"\b", norm):
            return info["label"]

    # 4. Pays seul (sans ville) sur une ligne courte de l'en-tete : "RDC", "Cameroun", "Pays : France"
    for line in header_lines:
        if "@" in line or "http" in line.lower() or len(line.split()) > 5:
            continue
        k = geo_resolver.find_country(line)
        if k:
            return geo_resolver.country_label(k)

    return ""

def resolve_city_geo(loc_str):
    """Ville connue en priorite (mot entier : 'Benin' n'est plus pris pour 'Beni') ; si seul le PAYS est indique,
    renvoie une position approximative du pays (niveau 'country') et non celle de sa capitale."""
    norm = normalize_text(loc_str)
    if not norm:
        return None
    country_hit = None
    for key, info in CITY_COORDS.items():
        if re.search(r"(?<![a-z0-9])" + re.escape(key) + r"(?![a-z0-9])", norm):
            if "," not in info["label"] and (geo_resolver.find_country(key) or (key == "congo" and geo_resolver.find_country(loc_str))):
                country_hit = country_hit or geo_resolver.find_country(key) or geo_resolver.find_country(loc_str)
                continue  # entree "pays" : on cherche d'abord une vraie ville dans le texte
            return {"key": key, "level": "city", "approx": False, **info}
    if country_hit:
        return geo_resolver.country_geo(country_hit)
    return geo_resolver.resolve_country(loc_str)


def _geo_country(geo):
    return geo.get("country") or geo_resolver.find_country(geo.get("label", "")) if geo else None


def compute_geo_intelligence(cand_loc, job_loc):
    """Calcule distance, temps de trajet, empreinte CO2 et attractivité locale."""
    c_geo = resolve_city_geo(cand_loc)
    j_geo = resolve_city_geo(job_loc)

    if not c_geo or not j_geo:
        return {
            "known": False,
            "distance_km": None,
            "commute_min": None,
            "co2_annual_kg": None,
            "market_tension": j_geo["tension"] if j_geo else "Normale",
            "salary_benchmark": j_geo["salary_ref"] if j_geo else 1200,
            "cand_coords": c_geo,
            "job_coords": j_geo
        }

    approx_geo = c_geo.get("level") == "country" or j_geo.get("level") == "country"
    if approx_geo and _geo_country(c_geo) and _geo_country(c_geo) == _geo_country(j_geo):
        # Meme pays mais ville non precisee : aucune distance fiable n'est inventee
        return {
            "known": False, "same_country": True, "approx": True,
            "distance_km": None, "commute_min": None, "co2_annual_kg": None,
            "market_tension": j_geo["tension"], "salary_benchmark": j_geo["salary_ref"],
            "cand_coords": c_geo, "job_coords": j_geo
        }
    if c_geo["key"] == j_geo["key"]:
        dist_km = 11.5
        commute_min = 28
    else:
        r = 6371.0
        lat1, lon1 = math.radians(c_geo["lat"]), math.radians(c_geo["lon"])
        lat2, lon2 = math.radians(j_geo["lat"]), math.radians(j_geo["lon"])
        dlat, dlon = lat2 - lat1, lon2 - lon1
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        dist_km = round(r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)) * 1.22, 1)
        commute_min = round((dist_km / 48.0) * 60)

    co2_annual_kg = round(dist_km * 2 * 220 * 0.14)
    return {
        "known": True,
        "approx": approx_geo,
        "distance_km": dist_km,
        "commute_min": commute_min,
        "co2_annual_kg": co2_annual_kg,
        "market_tension": j_geo["tension"],
        "salary_benchmark": j_geo["salary_ref"],
        "cand_coords": c_geo,
        "job_coords": j_geo
    }


SUSPICIOUS_DOMAINS_OR_KEYWORDS = (
    "bit.ly", "tinyurl.com", "t.me", "telegram", "wa.me", "://whatsapp.com",
    "forms.gle", "://google.com", "casino", "crypto", "bonus", "win-", "free-money"
)

HIGH_RISK_TLDS = (
    ".co", ".xyz", ".tk", ".ml", ".ga", ".cf", ".gq", ".top", ".site",
    ".online", ".icu", ".work", ".click", ".buzz", ".info", ".biz"
)

def check_domain_exists_and_live(domain):
    """Vérifie via DNS si le domaine de la société ou du lien existe réellement."""
    if not domain or domain in ("localhost", "127.0.0.1"):
        return True
    try:
        socket.setdefaulttimeout(2.5)
        socket.gethostbyname(domain)
        return True
    except Exception:
        return False

def extract_domain_from_url(url):
    m = re.match(r"^https?://([^/:\s?#]+)", url.strip().lower())
    return m.group(1).lstrip("www.") if m else ""

def evaluate_recruiter_trust(emails, links=None, job_text="", company_name=""):
    """Algorithme strict d'audit d'existence réelle de la société et de fiabilité du recruteur."""
    links = [l.strip() for l in (links or []) if l.strip()]
    emails = [e.strip().lower() for e in (emails or []) if e.strip()]
    norm_txt = normalize_text(job_text)
    norm_comp = normalize_text(company_name)

    # 1. Arnaque financière explicite dans le texte
    if any(w in norm_txt for w in ("frais de dossier", "paiement mobile", "orange money", "mpesa", "airtel money", "western union", "envoyer de l'argent")):
        return {
            "trust_pct": 5,
            "badge": "5 % CRITIQUE - Demande Financière / Arnaque",
            "details": "ALERTE ROUGE : L'annonce mentionne un paiement ou des frais. Ne postulez jamais !"
        }

    # 2. Vérification de chaque lien (Plateforme officielle vs Domaine inexistant vs Extension .co suspecte)
    for link in links:
        low = link.lower()
        dom = extract_domain_from_url(low)

        if any(bad in low for bad in SUSPICIOUS_DOMAINS_OR_KEYWORDS):
            return {
                "trust_pct": 15,
                "badge": "15 % CRITIQUE - Lien Raccourci / Formulaire Suspect",
                "details": f"Lien non officiel détecté ({dom}). Évitez de transmettre vos données personnelles."
            }

        if any(plat in dom for plat in TRUSTED_JOB_PLATFORMS):
            return {
                "trust_pct": 100,
                "badge": "100 % Fiabilité Certifiée (Portail Officiel)",
                "details": f"Offre hébergée sur une plateforme certifiée ({dom})."
            }

        if low.startswith("http://") and "127.0.0.1" not in dom:
            return {
                "trust_pct": 20,
                "badge": "20 % CRITIQUE - Site Non Sécurisé (HTTP)",
                "details": f"Le site ({dom}) n'est pas chiffré en HTTPS."
            }

        # Vérifie si le domaine existe réellement sur Internet (DNS)
        if dom and not check_domain_exists_and_live(dom):
            return {
                "trust_pct": 10,
                "badge": "10 % CRITIQUE - Site / Domaine Inexistant",
                "details": f"ALERTE : Le domaine '{dom}' est introuvable ou inactif. Société potentiellement fictive !"
            }

        # Vérifie les extensions à risque comme .co, .xyz, .site, .online...
        if any(dom.endswith(tld) for tld in HIGH_RISK_TLDS):
            return {
                "trust_pct": 30,
                "badge": f"30 % CRITIQUE - Extension Suspecte ({dom})",
                "details": f"Vigilance : le domaine '{dom}' utilise une extension fréquente dans les fausses offres. Vérifiez l'existence légale de {company_name}."
            }

    # 3. Vérification des adresses e-mail (Existence DNS de la société + Cohérence nom)
    has_free_mail = False
    for email in emails:
        local_p, _, domain = email.partition("@")
        if not domain:
            continue
        if domain in FREE_EMAIL_DOMAINS:
            has_free_mail = True
            continue

        if any(domain.endswith(tld) for tld in HIGH_RISK_TLDS):
            return {
                "trust_pct": 30,
                "badge": f"30 % CRITIQUE - Domaine E-mail Suspect ({domain})",
                "details": f"L'extension du domaine '{domain}' présente un risque élevé. Vérifiez la société avant de répondre."
            }

        if not check_domain_exists_and_live(domain):
            return {
                "trust_pct": 10,
                "badge": "10 % CRITIQUE - Société / Domaine Inexistant",
                "details": f"ALERTE : Le domaine e-mail '{domain}' n'existe pas. Adresse fictive ou invalide !"
            }

        # Cohérence entre le nom de la société annoncée et le domaine e-mail
        comp_tokens = [w for w in re.split(r"[^a-z0-9]+", norm_comp) if len(w) >= 4 and w not in ("employeur", "entreprise", "societe", "organisation", "sarl", "sasu")]
        domain_matches_company = (not comp_tokens) or any(tok in domain for tok in comp_tokens)

        if any(local_p.startswith(p) for p in HR_PREFIXES) and domain_matches_company:
            return {
                "trust_pct": 100,
                "badge": "100 % Fiabilité Certifiée (E-mail RH & Domaine Vérifiés)",
                "details": f"Société existante et adresse RH officielle vérifiée ({email})."
            }
        if domain_matches_company:
            return {
                "trust_pct": 75,
                "badge": "75 % Passable (Société Vérifiée, Contact Nominatif)",
                "details": f"Le domaine '{domain}' existe bien, mais l'adresse ({email}) n'est pas une boîte RH dédiée."
            }
        return {
            "trust_pct": 35,
            "badge": "35 % CRITIQUE - Incohérence Société / E-mail",
            "details": f"Attention : l'annonce cite '{company_name}' mais l'e-mail utilise un autre domaine ({domain})."
        }

    # 4. Lien HTTPS valide (hors extensions à risque)
    for link in links:
        dom = extract_domain_from_url(link)
        if link.lower().startswith("https://") and dom:
            return {
                "trust_pct": 75,
                "badge": "75 % Passable (Site Web d'Entreprise Vérifié)",
                "details": f"Le site '{dom}' est actif et sécurisé en HTTPS."
            }

    if has_free_mail:
        return {
            "trust_pct": 30,
            "badge": "30 % CRITIQUE - Messagerie Gratuite Sans Site Officiel",
            "details": f"Vigilance : recruteur utilisant uniquement {emails[0]} sans domaine d'entreprise vérifiable."
        }

    return {
        "trust_pct": 40,
        "badge": "40 % À Vérifier - Aucun Contact ni Site Vérifiable",
        "details": "Impossible de vérifier l'existence de la société : aucun site web ni e-mail officiel fourni."
    }


def extract_structured_experiences(cv_text):
    """Extrait chaque expérience (Employeur, Poste, Période, Tâches) depuis le CV."""
    lines = [l.strip() for l in cv_text.splitlines() if l.strip()]
    experiences = []
    date_pat = re.compile(
        r"((?:[0-3]?\d\s+)?(?:[a-zA-Zéû]+\.?\s+)?20\d{2}|(?:0?[1-9]|1[0-2])[/.-]20\d{2})"
        r"\s*(?:-|–|—|/|au|à|to)\s*"
        r"((?:[0-3]?\d\s+)?(?:[a-zA-Zéû]+\.?\s+)?20\d{2}|(?:0?[1-9]|1[0-2])[/.-]20\d{2}|"
        r"jusqu['’]?\s*à\s*ce\s*jour|à\s*ce\s*jour|pr[ée]sent|actuel(?:lement)?|en\s*cours|present|current|now|ongoing)",
        re.IGNORECASE
    )
    in_edu = False
    current_exp = None

    for i, line in enumerate(lines):
        nl = normalize_text(line)
        if re.match(r"^(?:formation|education|etudes|diplomes)\b", nl):
            in_edu = True
            if current_exp:
                experiences.append(current_exp)
                current_exp = None
            continue
        if re.match(r"^(?:experience|parcours professionnel|experiences|emplois|stages)\b", nl):
            in_edu = False
            continue
        if re.match(r"^(?:competences|langues|centres d'interet|loisirs|references)\b", nl):
            if current_exp:
                experiences.append(current_exp)
                current_exp = None
            break
        if in_edu:
            continue

        m_date = date_pat.search(line)
        if m_date:
            if current_exp:
                experiences.append(current_exp)
            period_str = m_date.group(0).strip()
            rest = line.replace(m_date.group(0), "").strip(" -–—|•:")
            prev_line = lines[i - 1] if i > 0 and not date_pat.search(lines[i - 1]) else ""
            role = rest if len(rest) >= 3 else (prev_line or "Poste occupé")
            employer = prev_line if (rest and prev_line and prev_line != role) else "Organisation / Entreprise"
            current_exp = {
                "period": period_str,
                "role": role[:90],
                "employer": employer[:90],
                "tasks": []
            }
        elif current_exp and len(current_exp["tasks"]) < 5:
            if len(line) >= 12:
                current_exp["tasks"].append(line.lstrip("-•*▪➢ "))

    if current_exp:
        experiences.append(current_exp)
    return experiences[:8]


def extract_cv_details(cv_text, photo_b64=None, filename="", pdf_meta=None, pdf_info=None):
    full_name, initials = extract_candidate_name(cv_text, filename)
    emails = sorted(list(set(re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", cv_text))))
    phones = extract_clean_phones(cv_text)
    links = sorted(list(set(re.findall(r"https?://[^\s<>\"')]+|github\.com/[^\s<>\"')]+|linkedin\.com/in/[^\s<>\"')]+", cv_text, re.IGNORECASE))))
    edu_label, edu_rank = detect_education(cv_text)
    structured_exps, exp_analysis = enrich_experiences(extract_structured_experiences(cv_text))
    _ct = contact_extractor.extract(cv_text, [l["url"] for l in (pdf_info or {}).get("links", [])] + list((pdf_info or {}).get("qr_links", [])))
    emails = sorted(set(emails) | set(_ct["emails"]))
    links_detail = _ct["links"]
    strict_name = pdf_vision_extractor.extract_name_strict(cv_text, emails[0] if emails else "")
    if strict_name and (full_name in ("Candidat", "") or len(full_name.split()) > 4 or any(ch.isdigit() for ch in full_name)):
        full_name = strict_name
        initials = "".join(w[0].upper() for w in full_name.split()[:2])

    # Fusionne le texte brut et les tâches extraites pour ne rater aucune compétence cachée
    tasks_blob = " ".join(t for exp in structured_exps for t in exp.get("tasks", []))
    enriched_text = f"{cv_text}\n{tasks_blob}"

    _, all_skills, _ = extract_skills(enriched_text)

    skills_by_cat, all_skills, _ = extract_skills(enriched_text)
    categorized_profile = {
        "prog_langs": skills_by_cat.get("Langages de Programmation", []),
        "software_tools": skills_by_cat.get("Logiciels & Outils", []),
        "domain_skills": skills_by_cat.get("Compétences Métiers & Techniques", []),
        "certifications": skills_by_cat.get("Certifications & Formations", []),
        "attitudes": skills_by_cat.get("Attitudes & Savoir-être", [])
    }
 
    main_role, sec_roles, objective = extract_professions_and_objective(enriched_text, all_skills)
    exp_years, chrono_gaps = extract_experience_and_gaps(cv_text)
    posture_impact = analyze_posture_and_impact(enriched_text)
    ats_audit = audit_ats_readiness(cv_text, pdf_meta)

    seniority = "Junior (0-2 ans)" if exp_years < 2 else ("Confirmé (2-5 ans)" if exp_years < 5 else "Senior (5+ ans)")

    return {
        "full_name": full_name,
        "initials": (re.sub(r"[^A-Za-zÀ-ÿ]", "", initials or "") or "CV")[:2].upper(),
        "photo": photo_b64,
        "main_profession": main_role,
        "secondary_professions": sec_roles,
        "objective": objective,
        "location": extract_universal_location(cv_text) or "Non précisée",
        "country_hint": geo_resolver.country_label(geo_resolver.country_from_phone(phones[0] if phones else "") or ""),
        "emails": emails,
        "phones": phones,
        "links": [l["url"] for l in links_detail][:6] or links[:4],
        "links_detail": links_detail,
        "phones_norm": _ct["phones"],
        "experience_analysis": {k: v for k, v in exp_analysis.items() if k != "experiences"},
        "languages": detect_languages(cv_text),
        "exp_years": exp_years,
        "seniority": seniority,
        "structured_experiences": structured_exps,
        "chrono_gaps": chrono_gaps,
        "education_label": edu_label,
        "education_rank": edu_rank,
        "posture_info": posture_impact,
        "ats_audit": ats_audit,
        "categorized_skills": categorized_profile
    }

def detect_document_language(text):
    norm = normalize_text(text)
    en_markers = len(re.findall(r"\b(?:the|and|with|requirements|responsibilities|skills|experience|apply|job|role|team)\b", norm))
    fr_markers = len(re.findall(r"\b(?:les|des|avec|pour|dans|competences|experience|poste|offre|candidature|equipe|missions)\b", norm))
    return "en" if en_markers > fr_markers + 2 else "fr"


def extract_mobility_and_permits(text):
    norm = normalize_text(text)
    items = []
    for p_lbl, pat in [
        ("Permis B", r"\bpermis\s*(?:de\s*conduire\s*)?b\b|\bdriver'?s?\s*license\b"),
        ("Permis Poids Lourd (C/D)", r"\bpermis\s*[cd]\b"),
        ("Passeport valide", r"\bpasseport\b|\bpassport\b"),
        ("Mobilité terrain / Missions", r"\bmobilite\b|\bdeplacements?\b|\bmissions?\s*terrain\b|\btravel\b")
    ]:
        if re.search(pat, norm):
            items.append(p_lbl)
    return items


def extract_offer_timing_details(job_text):
    norm = normalize_text(job_text)
    start_info = "Dès que possible / Non précisée"
    if re.search(r"\b(?:immediat|immediate|des\s*que\s*possible|asap)\b", norm):
        start_info = "Prise de fonction immédiate"
    else:
        m_start = re.search(r"(?:debut|prise\s*de\s*fonction|demarrage|start\s*date)\s*[:\-]?\s*([a-z0-9\s/.-]{3,28})", norm)
        if m_start:
            start_info = m_start.group(1).strip().capitalize()

    duration_info = "Indéterminée / Non précisée"
    m_dur = re.search(r"\b(\d{1,2})\s*(mois|ans|annees|months|years)\b", norm)
    if m_dur:
        duration_info = f"{m_dur.group(1)} {m_dur.group(2)}"

    return start_info, duration_info


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

    deadline_info = {
        "deadline_date": "Non précisée",
        "deadline_iso": "",
        "days_left": 14,
        "status": "unknown",
        "status_label": "Date limite non mentionnée",
        "favorable_dates": []
    }

    end_limit = today + timedelta(days=14)
    if found_dates:
        dl = max(found_dates)
        diff = (dl - today).days
        deadline_info["deadline_date"] = dl.strftime("%d/%m/%Y")
        deadline_info["deadline_iso"] = dl.isoformat()
        deadline_info["days_left"] = diff
        deadline_info["status"] = "active" if diff >= 0 else "expired"
        deadline_info["status_label"] = f"En cours ({diff} j restants)" if diff >= 0 else f"Dépassée ({abs(diff)} j)"
        if diff >= 0:
            end_limit = dl

    fav_dates = []
    cursor = today
    limit_scan = min(end_limit, today + timedelta(days=45))
    while cursor <= limit_scan:
        if cursor.weekday() in (1, 2, 3):
            fav_dates.append(cursor.isoformat())
        cursor += timedelta(days=1)
    if not fav_dates and today <= end_limit:
        fav_dates.append(today.isoformat())
    deadline_info["favorable_dates"] = fav_dates[:12]

    contract = "Non précisé"
    for c_lbl, keys in [("CDI", ["cdi"]), ("CDD", ["cdd"]), ("Freelance", ["freelance", "consultant"]), ("Stage", ["stage", "stagiaire"])]:
        if any(re.search(r"\b" + k + r"\b", norm_job) for k in keys):
            contract = c_lbl
            break

    comp_m = re.search(
        r"(?:entreprise|soci[ée]t[ée]|organisation|employeur|structure|cabinet|company|recruteur|a\s+propos\s+de)\s*[:\-]\s*([^\n\r.;|]{2,55})",
        job_text,
        re.IGNORECASE
    )
    company = comp_m.group(1).strip() if comp_m else ""

    if not company and apply_emails:
        for em in apply_emails:
            _, _, dom = em.lower().partition("@")
            if dom and dom not in FREE_EMAIL_DOMAINS:
                org_part = dom.split(".")[0]
                if len(org_part) >= 2:
                    company = org_part.replace("-", " ").title()
                    break

    if not company:
        ignored_headers = ("offre d'emploi", "avis de recrutement", "recrutement", "description du poste", "profil recherche", "missions")
        for line in [l.strip() for l in job_text.splitlines() if l.strip()][:5]:
            nl = normalize_text(line)
            if "@" in line or "http" in nl or re.search(r"\d{4}", line):
                continue
            if not any(h in nl for h in ignored_headers) and 2 <= len(line.split()) <= 5:
                company = line.strip(" -–—|:•")
                break

    if not company:
        company = "Employeur Non Précisé"

    m_exp = re.findall(r"(\d+)\s*(?:\+|ans|annees)\s*(?:d['’]?experience|minimum|requis)?", norm_job)
    req_exp = max([int(x) for x in m_exp if 0 < int(x) <= 35], default=0)
    req_edu_label, req_edu_rank = detect_education(job_text)

    sal_m = re.search(r"(\d{3,5})\s*(?:\$|usd|€|eur)", norm_job)
    offered_salary = int(sal_m.group(1)) if sal_m else None

    offer_lang = detect_document_language(job_text)
    start_date_str, duration_str = extract_offer_timing_details(job_text)
    required_permits = extract_mobility_and_permits(job_text)

    return {
        "raw_job_text": job_text,
        "company_name": company,
        "location": extract_universal_location(job_text) or "Non déterminé (À vérifier)",
        "job_coords": resolve_city_geo(extract_universal_location(job_text)),
        "contract_type": contract,
        "apply_emails": apply_emails,
        "email_audit": evaluate_recruiter_trust(apply_emails, apply_links, job_text, company),
        "apply_links": apply_links[:4],
        "deadline": deadline_info,
        "required_exp_years": req_exp,
        "required_edu_label": req_edu_label,
        "required_edu_rank": req_edu_rank,
        "required_languages": detect_languages(job_text),
        "offer_language": offer_lang,
        "start_date_info": start_date_str,
        "contract_duration": duration_str,
        "required_permits": required_permits,
        "offered_salary": offered_salary,
    }

def evaluate_geo(cand_loc, job_loc, job_text):
    nj = normalize_text(job_text)
    nc = normalize_text(cand_loc)
    nt = normalize_text(job_loc)
    geo_intel = compute_geo_intelligence(cand_loc, job_loc)

    if any(k in nj for k in ["teletravail", "remote", "a distance"]):
        return {
            "status": "compatible",
            "chance_pct": 100,
            "badge": "100 % Éligible (Télétravail)",
            "message": "Poste en télétravail compatible.",
            "intel": geo_intel
        }
    if not nt or nt == "non precisee" or not nc or nc == "non precisee":
        return {
            "status": "uncertain",
            "chance_pct": 50,
            "badge": "50 % de chance (Lieu à vérifier)",
            "message": "Ville/Pays non précisé sur le CV ou l'offre.",
            "intel": geo_intel
        }
    cg, jg = resolve_city_geo(cand_loc), resolve_city_geo(job_loc)
    if cg and jg and (cg.get("level") == "country" or jg.get("level") == "country"):
        cc, jc = _geo_country(cg), _geo_country(jg)
        if cc and cc == jc and cg.get("level") == "country" and jg.get("level") == "country":
            return {
                "status": "compatible", "chance_pct": 100,
                "badge": "100 % Éligible (Même pays)",
                "message": f"Même pays ({geo_resolver.country_label(cc)}) : « {cand_loc} » et « {job_loc} » désignent le même pays.",
                "intel": geo_intel
            }
        if cc and cc == jc:
            return {
                "status": "compatible", "chance_pct": 75,
                "badge": "75 % Éligible (Même pays, ville non précisée)",
                "message": f"Même pays ({geo_resolver.country_label(cc)}) : la ville n'est pas indiquée sur {'le CV' if cg.get('level') == 'country' else 'l offre'}, distance non calculée.",
                "intel": geo_intel
            }
        if cc and jc:
            return {
                "status": "uncertain", "chance_pct": 35,
                "badge": "35 % de chance (Pays différent)",
                "message": f"Pays différent ({geo_resolver.country_label(cc)} vs {geo_resolver.country_label(jc)}) : distance approximative entre capitales/centres.",
                "intel": geo_intel
            }
    # Comparaison canonique : "RDC" == "République démocratique du Congo", ordre des mots indifférent
    if cg and jg and cg.get("level") == "city" and jg.get("level") == "city":
        if cg.get("key") == jg.get("key"):
            return {
                "status": "compatible", "chance_pct": 100,
                "badge": "100 % Éligible (Même ville)",
                "message": f"Même ville ({cg['label']}) : « {cand_loc} » et « {job_loc} » désignent le même lieu.",
                "intel": geo_intel
            }
    c_tok = {w for w in re.split(r"[\s,./()-]+", nc) if len(w) >= 3}
    t_tok = {w for w in re.split(r"[\s,./()-]+", nt) if len(w) >= 3}
    if cg and jg and cg.get("level") == "city" and jg.get("level") == "city" and cg.get("key") != jg.get("key"):
        cc, jc = _geo_country(cg), _geo_country(jg)
        if cc and cc == jc:
            return {
                "status": "uncertain", "chance_pct": 60,
                "badge": "60 % de chance (Même pays, villes différentes)",
                "message": f"Même pays ({geo_resolver.country_label(cc)}) mais villes différentes ({cg['label']} / {jg['label']}).",
                "intel": geo_intel
            }
    if c_tok & t_tok:
        return {
            "status": "compatible",
            "chance_pct": 100,
            "badge": "100 % Éligible (Même zone)",
            "message": f"Localisation compatible ({cand_loc} / {job_loc}).",
            "intel": geo_intel
        }
    return {
        "status": "uncertain",
        "chance_pct": 50,
        "badge": "50 % de chance (Lieu différent)",
        "message": f"Lieu différent ({cand_loc} vs {job_loc}).",
        "intel": geo_intel
    }


def get_match_tier(score):
    if score >= 75:
        return {"code": "max", "label": "Élevé / Max"}
    if score >= 45:
        return {"code": "mid", "label": "Moyen"}
    return {"code": "low", "label": "Petit / Faible"}


def build_predictive_questions(cv_details, job_details, matched_skills, missing_skills):
    lang = job_details.get("offer_language", "fr")
    cand_exp = cv_details.get("exp_years", 0)
    cv_profs = ", ".join([cv_details.get("main_profession", "")] + cv_details.get("secondary_professions", []))
    skills_str = ", ".join(matched_skills[:6]) if matched_skills else ("the target field" if lang == "en" else "le domaine visé")
    org = job_details.get("company_name", "the organization" if lang == "en" else "l'organisation")
    gaps = cv_details.get("chrono_gaps", [])

    if lang == "en":
        questions = [
            f"Your resume shows {cand_exp} year(s) of experience as {cv_profs}: which achievement using {skills_str} best demonstrates your impact?",
            f"What do you know about {org}'s core activities and current priorities?",
            f"The role requires {', '.join(missing_skills[:4]) if missing_skills else 'fast adaptation'} (not listed on your CV): how do you plan to bridge this gap?",
            f"You are based in {cv_details.get('location', 'your city')} for a role in {job_details.get('location', 'this location')}: what are your relocation or commuting arrangements?",
            f"With a {cv_details.get('posture_info', {}).get('posture', 'versatile')} profile, how do you manage tight deadlines?"
        ]
        for g in gaps:
            questions.append(f"[Chronological Gap] {g}: could you walk us through your activities during this period?")
        return questions

    questions = [
        f"Votre CV indique {cand_exp} an(s) d'expérience en tant que {cv_profs} : quelle réalisation concrète avec {skills_str} illustre le mieux votre impact ?",
        f"Que savez-vous des enjeux et des activités de {org} ?",
        f"L'offre exige {', '.join(missing_skills[:4]) if missing_skills else 'une montée en compétence rapide'} (absent de votre CV) : comment abordez-vous ce point ?",
        f"Vous êtes basé(e) à {cv_details.get('location', 'votre ville')} pour un poste à {job_details.get('location', 'ce lieu')} : quelles sont vos modalités de déplacement ?",
        f"Avec une posture {cv_details.get('posture_info', {}).get('posture', 'polyvalente')}, comment gérez-vous les priorités sous contrainte de délai ?"
    ]
    for g in gaps:
        questions.append(f"[Anomalie Chronologique] {g} : pouvez-vous expliquer vos activités durant cette période ?")
    return questions


def compute_final_report(cv_details, job_details, matched_skills, missing_skills, bonus_skills, category_breakdown, raw_cv_text="", tech_weight=60):
    total_job = len(matched_skills) + len(missing_skills)
    weights = job_details.get("skill_weights") or {}
    # Score technique PONDERE par les coefficients du referentiel (competences essentielles = 3, importantes = 2, un plus = 1)
    w_ratio = skills_referential.weighted_ratio(matched_skills, missing_skills, weights) if weights else None
    if w_ratio is not None:
        skills_ratio = w_ratio
    else:
        skills_ratio = (len(matched_skills) / total_job) if total_job > 0 else None
    skills_known = skills_ratio is not None
    if not skills_known:
        skills_ratio = 0.0
    fmt = ats_scoring.format_quality(raw_cv_text, cv_details) if (raw_cv_text or "").strip() else None
    fmt_ratio = (fmt["score"] / 100.0) if fmt else None

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

    cand_loc = cv_details.get("location", "")
    hint = cv_details.get("country_hint", "")
    used_hint = False
    if hint and normalize_text(cand_loc) in ("", "non precisee") and not resolve_city_geo(cand_loc):
        cand_loc = hint  # aucun lieu sur le CV : pays deduit de l'indicatif telephonique
        used_hint = True
    geo = evaluate_geo(cand_loc, job_details.get("location", ""), job_details.get("raw_job_text", ""))
    if used_hint:
        geo["message"] = geo.get("message", "") + " (pays déduit du téléphone, à confirmer)"
    # Pondérations : compétences (tech_weight) + exp / diplômes / langues / mise en forme sur le reste.
    eff_tech = tech_weight if skills_known else 0
    rem_w = 100 - eff_tech
    if fmt_ratio is not None:
        sub = {"exp": 0.34, "edu": 0.30, "lang": 0.21, "fmt": 0.15}
    else:
        sub = {"exp": 0.40, "edu": 0.35, "lang": 0.25, "fmt": 0.0}
    comp_pts = {
        "exp": exp_ratio * rem_w * sub["exp"], "edu": edu_ratio * rem_w * sub["edu"],
        "lang": lang_ratio * rem_w * sub["lang"], "fmt": (fmt_ratio or 0) * rem_w * sub["fmt"],
    }
    base = skills_ratio * eff_tech + sum(comp_pts.values())
    proj = eff_tech + sum(comp_pts.values())
    if geo["status"] == "uncertain":
        base *= 0.85
        proj *= 0.85

    no_data_cap = False
    if not skills_known:
        # Aucune compétence exigée détectable : le score ne peut pas être présenté comme fiable (jamais artificiellement élevé)
        if base > 70:
            base, no_data_cap = 70.0, True
        proj = min(proj, 70.0)
    # Si l'offre exige des compétences et que le CV n'en possède AUCUNE, le profil est hors-sujet (< 35%)
    if total_job > 0 and len(matched_skills) == 0:
        base = min(base * 0.45, 28.0)

    est = set(s.lower() for s in (job_details.get("estimated_skills") or []))
    n_est = sum(1 for m in list(matched_skills) + list(missing_skills) if m.lower() in est)
    n_det = total_job - n_est
    if not skills_known:
        conf_level, conf_why = "insuffisante", ["Aucune compétence exigée n'a pu être déterminée à partir de l'offre ni du métier : score plafonné à 70 %."]
    elif n_det >= 5 and n_est == 0:
        conf_level, conf_why = "élevée", ["%d compétences exigées explicitement dans l'offre." % n_det]
    elif n_det >= 3:
        conf_level, conf_why = "moyenne", ["%d compétences lues dans l'offre" % n_det + (", %d complétées d'après le métier (estimées)." % n_est if n_est else ".")]
    else:
        conf_level, conf_why = "faible", ["Peu de compétences explicites dans l'offre (%d) : %d estimées d'après le métier détecté." % (n_det, n_est)]
    if fmt is None:
        conf_why.append("Mise en forme non évaluée (texte du CV absent).")
    explanation = [
        {"label": "Compétences exigées par l'employeur" + (" (pondérées)" if weights else ""), "ratio": round(skills_ratio * 100) if skills_known else None,
         "weight": eff_tech, "points": round(skills_ratio * eff_tech, 1),
         "detail": ("%d/%d validées" % (len(matched_skills), total_job) + (" • %d estimées d'après le métier" % n_est if n_est else "")) if skills_known else "non déterminable"},
        {"label": "Expérience", "ratio": round(exp_ratio * 100), "weight": round(rem_w * sub["exp"], 1), "points": round(comp_pts["exp"], 1), "detail": exp_status},
        {"label": "Diplôme", "ratio": round(edu_ratio * 100), "weight": round(rem_w * sub["edu"], 1), "points": round(comp_pts["edu"], 1), "detail": edu_status},
        {"label": "Langues", "ratio": round(lang_ratio * 100), "weight": round(rem_w * sub["lang"], 1), "points": round(comp_pts["lang"], 1), "detail": lang_status},
    ]
    if fmt is not None:
        explanation.append({"label": "Mise en forme du CV", "ratio": fmt["score"], "weight": round(rem_w * sub["fmt"], 1), "points": round(comp_pts["fmt"], 1), "detail": fmt["level"]})
    if geo["status"] == "uncertain":
        explanation.append({"label": "Localisation incertaine", "ratio": None, "weight": 0, "points": 0, "detail": "score × 0,85 (%s)" % geo.get("badge", "")})
    if no_data_cap:
        explanation.append({"label": "Plafond (données insuffisantes)", "ratio": None, "weight": 0, "points": 0, "detail": "70 % maximum"})

    final_score = round(base)
    tier = get_match_tier(final_score)

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
        f"Objet : Candidature - {name} ({skills_str})\n\nMadame, Monsieur,\n\n"
        f"Votre offre ({job_details.get('contract_type', 'Poste')}) au sein de {org} a retenu toute mon attention. "
        f"Titulaire d'un niveau {cv_details.get('education_label')} avec {cand_exp} an(s) d'expérience et maîtrisant "
        f"{skills_str}, je souhaite rejoindre votre équipe.\n\nJe reste disponible au {phone}.\n\nCordialement,\n{name}"
    )

    questions = build_predictive_questions(cv_details, job_details, matched_skills, missing_skills)

    intel = geo.get("intel", {})
    bench = intel.get("salary_benchmark", 1200)
    off_sal = job_details.get("offered_salary")
    market_alert = "Exigences cohérentes avec le bassin d'emploi local."
    if off_sal and off_sal < bench * 0.75 and total_job >= 6:
        market_alert = f"Alerte Attractivité : Salaire proposé ({off_sal}) inférieur au standard local ({bench}) pour {total_job} compétences exigées."

    return {
        "success": True,
        "score": final_score,
        "match_tier": tier,
        "projected_score": round(proj),
        "radar_axes": radar_axes,
        "raw_cv_text": raw_cv_text,
        "stats": {"job_skills_count": total_job, "matched_count": len(matched_skills), "missing_count": len(missing_skills),
                  "estimated_count": n_est, "detected_count": n_det},
        "score_explanation": explanation,
        "score_confidence": {"level": conf_level, "reasons": conf_why},
        "format_quality": fmt,
        "comparison": {"exp_status": exp_status, "edu_status": edu_status, "lang_status": lang_status, "geo": geo, "market_alert": market_alert},
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


@app.route("/sw.js")
def service_worker():
    resp = send_file(os.path.join(app.root_path, "static", "sw.js"), mimetype="application/javascript")
    resp.headers["Service-Worker-Allowed"] = "/"
    resp.headers["Cache-Control"] = "no-cache"
    return resp


@app.route("/manifest.json")
def pwa_manifest():
    return send_file(os.path.join(app.root_path, "static", "manifest.json"), mimetype="application/manifest+json")


@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    cv_text_in = request.form.get("cv_text", "").strip()
    cv_file = request.files.get("cv_pdf")
    final_cv, photo_b64, fname, pdf_meta = "", None, "", {"pages": 1, "has_images": False}
    pdf_info, vres = {}, {}

    if cv_file and cv_file.filename:
        fname = cv_file.filename
        raw, vres = read_pdf_upload(cv_file)
        if not vres["ok"]:
            return jsonify({"success": False, "message": vres["reason"]}), 400
        final_cv, pdf_meta, pdf_info = read_cv_content(raw, vres)
        if pdf_info.get("locked"):
            return jsonify({"success": False, "message": "Ce PDF est protégé par mot de passe : déverrouillez-le puis réimportez-le."}), 400
        photo_b64 = pdf_info.get("photo_base64")
    elif cv_text_in:
        final_cv = cv_text_in

    if len(final_cv.strip()) < 10:
        return jsonify({"success": False, "message": "Impossible de lire le CV (document vide ou illisible" + ("" if ocr_engine.available() else " ; OCR non disponible sur ce poste") + "). Collez le texte du CV."}), 400

    job_text_in = request.form.get("job_text", "").strip()
    job_url_in = request.form.get("job_url", "").strip()
    job_file = request.files.get("job_pdf")
    final_job, res_url = "", ""

    if job_file and job_file.filename:
        final_job, _ = extract_text_and_meta_from_pdf(job_file.read())
    elif job_url_in:
        try:
            final_job, res_url = extract_text_from_url(job_url_in)
        except Exception as e:
            return jsonify({"success": False, "message": str(e)}), 400
    elif job_text_in:
        final_job = job_text_in

    if len(final_job.strip()) < 10:
        return jsonify({"success": False, "message": "Fournissez le texte ou le PDF de l'offre d'emploi."}), 400

    job_by_cat, job_skills, _ = extract_skills(final_job, is_offer=True)
    reqs = build_job_requirements(final_job, job_skills)
    _, cv_skills, cv_freq = extract_skills(final_cv, is_offer=False, reference_offer_skills=job_skills)

    cv_det = extract_cv_details(final_cv, photo_b64, fname, pdf_meta, pdf_info)
    tasks_blob = " ".join(t for exp in cv_det.get("structured_experiences", []) for t in exp.get("tasks", []))
    cv_full_text = f"{final_cv}\n{tasks_blob}" if tasks_blob else final_cv
    if tasks_blob:
        _, cv_skills, cv_freq = extract_skills(cv_full_text, is_offer=False, reference_offer_skills=job_skills)
    mres = skills_referential.match_cv(cv_full_text, reqs)
    matched, missing = mres["matched"], mres["missing"]
    req_keys = set()
    for r in reqs["required"]:
        req_keys.add(normalize_text(r["name"]))
        req_keys.update(normalize_text(a) for a in r.get("aliases", []))
    bonus = [s for s in skills_referential.clean_skill_list(cv_skills) if normalize_text(s) not in req_keys]
    breakdown = requirements_breakdown(reqs, matched)

    cv_det["skill_frequencies"] = cv_freq
    job_det = apply_requirements(extract_job_details(final_job, res_url), reqs)
    rep_out = compute_final_report(cv_det, job_det, matched, missing, bonus, breakdown, final_cv)
    rep_out["initial_score"] = rep_out["score"]
    rep_out["initial_matched_skills"] = list(rep_out["matched_skills"])
    rep_out["manual_edits"] = {}
    rep_out["doc_trust"] = document_trust_analyzer.analyze(final_cv, cv_det, vres)
    rep_out["pdf_warnings"] = vres.get("warnings", [])
    rep_out["sha256"] = vres.get("sha256", "")
    try:
        rep_out["org_check"] = org_verifier.verify(final_job, job_det.get("apply_emails", []), job_det.get("apply_links", []),
                                                    [], job_det.get("location", ""))
    except Exception:
        rep_out["org_check"] = None
    audit_trail_manager.log("analyze", "score=%s" % rep_out["score"])
    return jsonify(rep_out)


@app.route("/api/multi-offer-simulate", methods=["POST"])
def api_multi_offer_simulate():
    cv_text = request.form.get("raw_cv_text", "").strip()
    if len(cv_text) < 10:
        return jsonify({"success": False, "message": "Lancez d'abord l'analyse de votre CV avant d'utiliser le simulateur."}), 400

    cv_det = extract_cv_details(cv_text)
    structured_exps = cv_det.get("structured_experiences", [])
    tasks_blob = " ".join(t for exp in structured_exps for t in exp.get("tasks", []))
    enriched_cv = f"{cv_text}\n{tasks_blob}"

    offers_to_eval = []

    # 1. Inclusion automatique de l'offre initiale déjà analysée
    base_job_text = request.form.get("base_job_text", "").strip()
    base_job_title = request.form.get("base_job_title", "").strip() or "Offre Initiale (Actuelle)"
    if len(base_job_text) >= 10:
        offers_to_eval.append({"title": base_job_title, "text": base_job_text, "is_base": True})

    # 2. Lecture des offres supplémentaires (PDF, URL ou Texte)
    for i in range(1, 5):
        o_title = request.form.get(f"mo_title_{i}", "").strip() or f"Offre Comparée #{i}"
        o_text = request.form.get(f"mo_text_{i}", "").strip()
        o_url = request.form.get(f"mo_url_{i}", "").strip()
        o_pdf = request.files.get(f"mo_pdf_{i}")

        final_o_text = ""
        if o_pdf and o_pdf.filename:
            final_o_text, _ = extract_text_and_meta_from_pdf(o_pdf.read())
        elif o_url:
            try:
                final_o_text, _ = extract_text_from_url(o_url)
            except Exception as e:
                return jsonify({"success": False, "message": f"Erreur URL Offre #{i} : {str(e)}"}), 400
        elif o_text:
            final_o_text = o_text

        if len(final_o_text.strip()) >= 10:
            offers_to_eval.append({"title": o_title, "text": final_o_text, "is_base": False})

    if len(offers_to_eval) < 2:
        return jsonify({"success": False, "message": "Ajoutez au moins 1 offre supplémentaire (PDF, lien URL ou texte) pour la comparer à votre offre actuelle."}), 400

    matrix = []
    for off in offers_to_eval[:5]:
        o_text = off["text"]
        _, job_skills, _ = extract_skills(o_text, is_offer=True)
        _, cv_skills, _ = extract_skills(enriched_cv, is_offer=False, reference_offer_skills=job_skills)

        cv_set = {s.lower(): s for s in cv_skills}
        job_set = {s.lower(): s for s in job_skills}
        matched = sorted([job_set[k] for k in job_set if k in cv_set])
        missing = sorted([job_set[k] for k in job_set if k not in cv_set])

        job_det = extract_job_details(o_text)
        rep = compute_final_report(cv_det, job_det, matched, missing, [], [], enriched_cv)
        geo_info = rep["comparison"]["geo"]
        intel = geo_info.get("intel", {})
        tension = intel.get("market_tension", "Moyenne")

        tension_penalty = {"Faible": 0, "Normale": 3, "Moyenne": 5, "Élevée": 10, "Très élevée": 15}.get(tension, 5)
        geo_bonus = 5 if geo_info.get("status") == "compatible" else -8
        win_chance = max(10, min(98, rep["score"] + geo_bonus - tension_penalty))

        matrix.append({
            "rank": 0,
            "is_base": off.get("is_base", False),
            "title": off["title"],
            "company": job_det.get("company_name", "Entreprise"),
            "location": job_det.get("location", "Non précisée"),
            "contract_type": job_det.get("contract_type", "Non précisé"),
            "tech_score": rep["score"],
            "radar_axes": rep["radar_axes"],
            "geo_badge": geo_info.get("badge", ""),
            "distance_km": intel.get("distance_km"),
            "market_tension": tension,
            "win_chance": win_chance,
            "matched_skills": matched,
            "missing_skills": missing,
            "matched_count": len(matched),
            "missing_count": len(missing)
        })

    matrix.sort(key=lambda x: x["win_chance"], reverse=True)
    for idx, item in enumerate(matrix):
        item["rank"] = idx + 1

    return jsonify({"success": True, "matrix": matrix})

@app.route("/api/recalculate", methods=["POST"])
def api_recalculate():
    data = request.get_json(silent=True) or {}
    out = compute_final_report(
        data.get("cv_details", {}), data.get("job_details", {}),
        data.get("matched_skills", []), data.get("missing_skills", []),
        data.get("bonus_skills", []), data.get("category_breakdown", []),
        data.get("raw_cv_text", "")
    )
    for k in ("initial_score", "initial_matched_skills", "manual_edits", "pdf_original", "doc_trust", "pdf_warnings", "sha256", "org_check"):
        if k in data:
            out[k] = data[k]
    out.setdefault("initial_score", out["score"])
    out["score_comparison"] = ats_scoring.compare_scores(out["initial_score"], out["score"])
    return jsonify(out)

@app.route("/api/reanalyze-offer", methods=["POST"])
def api_reanalyze_offer():
    """Edition manuelle des informations de l'employeur / de l'offre (entreprise, e-mail, lien, description) puis nouvelle analyse."""
    data = request.get_json(silent=True) or {}
    offer = data.get("offer") or {}
    cv_det = data.get("cv_details") or {}
    old_job = data.get("job_details") or {}
    cv_text = data.get("raw_cv_text", "") or ""
    desc = (offer.get("description") if offer.get("description") is not None else old_job.get("raw_job_text", "")) or ""
    if len(desc.strip()) < 10:
        return jsonify({"success": False, "message": "La description de l'offre est trop courte pour relancer l'analyse."}), 400
    changed_desc = desc.strip() != (old_job.get("raw_job_text", "") or "").strip()
    url = (offer.get("offer_url") or "").strip()
    if url and not re.match(r"^https?://", url):
        return jsonify({"success": False, "message": "Le lien de l'offre doit commencer par http:// ou https://"}), 400
    email = (offer.get("contact_email") or "").strip()
    if email and not re.match(r"^[\w.+-]+@[\w-]+(\.[\w-]+)+$", email):
        return jsonify({"success": False, "message": "Adresse e-mail de l'employeur invalide."}), 400

    if changed_desc:
        _, job_skills, _ = extract_skills(desc, is_offer=True)
        reqs = build_job_requirements(desc, job_skills)
        tasks_blob = " ".join(t for exp in cv_det.get("structured_experiences", []) for t in exp.get("tasks", []))
        full = f"{cv_text}\n{tasks_blob}" if tasks_blob else cv_text
        _, cv_skills, _f = extract_skills(full, is_offer=False, reference_offer_skills=job_skills)
        mres = skills_referential.match_cv(full, reqs)
        matched, missing = mres["matched"], mres["missing"]
        keys = set()
        for r in reqs["required"]:
            keys.add(normalize_text(r["name"])); keys.update(normalize_text(a) for a in r.get("aliases", []))
        bonus = [x for x in skills_referential.clean_skill_list(cv_skills) if normalize_text(x) not in keys]
        breakdown = requirements_breakdown(reqs, matched)
        job_det = apply_requirements(extract_job_details(desc, url), reqs)
    else:
        job_det = dict(old_job)
        matched, missing = data.get("matched_skills", []), data.get("missing_skills", [])
        bonus, breakdown = data.get("bonus_skills", []), data.get("category_breakdown", [])
    if (offer.get("company_name") or "").strip():
        job_det["company_name"] = offer["company_name"].strip()
    if (offer.get("job_title") or "").strip():
        job_det["job_title"] = offer["job_title"].strip()
    if email:
        job_det["apply_emails"] = [email] + [e for e in job_det.get("apply_emails", []) if e != email]
    if url:
        job_det["apply_links"] = [url] + [l for l in job_det.get("apply_links", []) if l != url]
    job_det["raw_job_text"] = desc
    job_det["manual_offer_edit"] = True
    try:
        job_det["email_audit"] = evaluate_recruiter_trust(job_det.get("apply_emails", []), job_det.get("apply_links", []), desc, job_det.get("company_name", ""))
    except Exception:
        pass
    out = compute_final_report(cv_det, job_det, matched, missing, bonus, breakdown, cv_text)
    for k in ("initial_score", "initial_matched_skills", "manual_edits", "pdf_original", "doc_trust", "pdf_warnings", "sha256"):
        if k in data:
            out[k] = data[k]
    out.setdefault("initial_score", out["score"])
    out["score_comparison"] = ats_scoring.compare_scores(out["initial_score"], out["score"])
    audit_trail_manager.log("reanalyze_offer", "score=%s" % out["score"])
    return jsonify(out)


@app.route("/api/hr-batch", methods=["POST"])
def api_hr_batch():
    job_text_in = request.form.get("hr_job_text", "").strip()
    job_url_in = request.form.get("hr_job_url", "").strip()
    job_pdf = request.files.get("hr_job_pdf")
    positions_count = int(request.form.get("positions_count", "3") or 3)
    tech_weight = int(request.form.get("tech_weight", "60") or 60)

    final_job, res_url = "", ""
    if job_pdf and job_pdf.filename:
        final_job, _ = extract_text_and_meta_from_pdf(job_pdf.read())
    elif job_url_in:
        try:
            final_job, res_url = extract_text_from_url(job_url_in)
        except Exception as e:
            return jsonify({"success": False, "message": str(e)}), 400
    elif job_text_in:
        final_job = job_text_in

    if not (len(final_job.strip()) >= 10):
        return jsonify({"success": False, "message": "Veuillez renseigner l'offre d'emploi (texte, lien URL ou fichier PDF) avant de lancer l'analyse."}), 400

    files = request.files.getlist("hr_cv_files")
    valid_files = [f for f in files if f and f.filename and f.filename.lower().endswith((".pdf", ".png", ".jpg", ".jpeg"))][:50]
    if not valid_files:
        return jsonify({"success": False, "message": "Veuillez importer au moins un fichier CV (.PDF) avant d'analyser."}), 400

    _, job_skills, _ = extract_skills(final_job, is_offer=True)
    reqs = build_job_requirements(final_job, job_skills)
    job_det = apply_requirements(extract_job_details(final_job, res_url), reqs)
    job_skills = [r["name"] for r in reqs["required"]]  # exigences reelles (offre + metier), sans bruit

    candidates = []
    rejected_files = []
    seen_hashes = set()
    seen_identities = set()
    duplicates_count = 0
    last_market_alert = ""
    readability_stats = {"clean": 0, "partial": 0, "unreadable": 0}

    for f in valid_files:
        try:
            raw_bytes, vres = read_pdf_upload(f)
            if not vres["ok"]:
                rejected_files.append({"filename": f.filename, "reason": vres["reason"]})
                continue
            text, pdf_meta, pdf_info = read_cv_content(raw_bytes, vres)
            pdf_b64 = base64.b64encode(raw_bytes).decode("utf-8")
            _mime = "application/pdf" if vres.get("kind") != "image" else ("image/png" if vres.get("image_type") == "png" else "image/jpeg")
            pdf_data_url = f"data:{_mime};base64,{pdf_b64}"
            photo_b64 = pdf_info.get("photo_base64")

            clean_len = len(text.strip())
            if not (clean_len >= 25):
                readability = "unreadable"
                readability_stats["unreadable"] += 1
            elif (not (clean_len >= 260)) or ("@" not in text):
                readability = "partial"
                readability_stats["partial"] += 1
            else:
                readability = "clean"
                readability_stats["clean"] += 1

            cv_det = extract_cv_details(text, photo_b64, f.filename, pdf_meta, pdf_info)
            tasks_blob = " ".join(t for exp in cv_det.get("structured_experiences", []) for t in exp.get("tasks", []))
            enriched_cv = f"{text}\n{tasks_blob}"

            _, cv_skills, _ = extract_skills(enriched_cv, is_offer=False, reference_offer_skills=job_skills)
            mres = skills_referential.match_cv(enriched_cv, reqs)
            matched, missing = mres["matched"], mres["missing"]
            req_keys = set()
            for r in reqs["required"]:
                req_keys.add(normalize_text(r["name"]))
                req_keys.update(normalize_text(a) for a in r.get("aliases", []))
            bonus = [s for s in skills_referential.clean_skill_list(cv_skills) if normalize_text(s) not in req_keys]

            email_key = cv_det["emails"][0].lower() if cv_det["emails"] else ""
            name_key = normalize_text(cv_det["full_name"])
            identity_key = email_key or name_key
            is_duplicate = False
            file_hash = vres.get("sha256", "")
            if file_hash and file_hash in seen_hashes:
                is_duplicate = True
                duplicates_count += 1
            seen_hashes.add(file_hash)
            if is_duplicate:
                pass
            elif identity_key and identity_key in seen_identities and cv_det["full_name"] != "Candidat":
                is_duplicate = True
                duplicates_count += 1
            elif identity_key and cv_det["full_name"] != "Candidat":
                seen_identities.add(identity_key)

            rep = compute_final_report(cv_det, job_det, matched, missing, bonus, [], enriched_cv, tech_weight)
            last_market_alert = rep["comparison"]["market_alert"]
            score = 0 if readability == "unreadable" else rep["score"]
            tier = get_match_tier(score)
            geo_intel = rep["comparison"]["geo"].get("intel", {})

            candidates.append({
                "filename": f.filename,
                "raw_text": text,
                "pdf_url": pdf_data_url,
                "readability": readability,
                "name": cv_det["full_name"],
                "initials": cv_det["initials"],
                "photo": photo_b64,
                "is_duplicate": is_duplicate,
                "main_profession": cv_det["main_profession"],
                "secondary_professions": cv_det["secondary_professions"],
                "objective": cv_det["objective"],
                "posture": cv_det["posture_info"]["posture"],
                "seniority": cv_det["seniority"],
                "structured_experiences": cv_det["structured_experiences"],
                "chrono_gaps": cv_det["chrono_gaps"],
                "email": cv_det["emails"][0] if cv_det["emails"] else "",
                "phone": cv_det["phones"][0] if cv_det["phones"] else "",
                "location": cv_det["location"],
                "languages": cv_det["languages"],
                "distance_km": geo_intel.get("distance_km"),
                "commute_min": geo_intel.get("commute_min"),
                "co2_annual_kg": geo_intel.get("co2_annual_kg"),
                "city_coords": geo_intel.get("cand_coords"),
                "exp_years": cv_det["exp_years"],
                "education": cv_det["education_label"],
                "score": score,
                "match_tier": tier,
                "radar_axes": rep["radar_axes"],
                "matched_skills": matched,
                "bonus_skills": bonus,
                "missing_skills": missing,
                "predictive_questions": rep["interview_questions"],
                "categorized_skills": cv_det.get("categorized_skills", {}),
                "emails": cv_det["emails"],
                "country_hint": cv_det.get("country_hint", ""),
                "phones": cv_det["phones"],
                "links": cv_det.get("links", []),
                "links_detail": cv_det.get("links_detail", []),
                "experience_analysis": cv_det.get("experience_analysis", {}),
                "initial_score": score,
                "manual_edits": {},
                "sha256": file_hash,
                "pdf_warnings": vres.get("warnings", []),
                "encrypted": pdf_info.get("encrypted", False),
                "doc_trust": document_trust_analyzer.analyze(text, cv_det, vres),
                "hr_status": "À convoquer" if score >= 45 else "Écarté",
                "hr_note": ""
            })
        except Exception:
            continue

    ranking.rank(candidates)  # score puis criteres de departage explicites (couverture, experience, fiabilite...)

    top_c = sum(1 for c in candidates if c["score"] >= 75)
    mid_c = sum(1 for c in candidates if 45 <= c["score"] and c["score"] <= 74)
    low_c = sum(1 for c in candidates if not (c["score"] >= 45))
    avg_s = round(sum(c["score"] for c in candidates) / max(1, len(candidates)))

    city_clusters = {}
    for c in candidates:
        loc = c["location"] or "Non précisée"
        if loc not in city_clusters:
            city_clusters[loc] = {
                "city": loc,
                "count": 0,
                "avg_score": 0,
                "coords": c.get("city_coords"),
                "distance_km": c.get("distance_km"),
                "commute_min": c.get("commute_min"),
                "co2_annual_kg": c.get("co2_annual_kg")
            }
        city_clusters[loc]["count"] += 1
        city_clusters[loc]["avg_score"] += c["score"]

    for cl in city_clusters.values():
        cl["avg_score"] = round(cl["avg_score"] / cl["count"])

    return jsonify({
        "success": True,
        "job_details": job_det,
        "job_coords": job_det.get("job_coords"),
        "job_skills": job_skills,
        "tech_weight": tech_weight,
        "total_received": len(candidates),
        "duplicates_count": duplicates_count,
        "rejected_files": rejected_files,
        "readability_stats": readability_stats,
        "positions_count": positions_count,
        "avg_score": avg_s,
        "market_alert": last_market_alert,
        "city_clusters": list(city_clusters.values()),
        "summary": {"top": top_c, "mid": mid_c, "low": low_c},
        "candidates": candidates
    })


@app.route("/api/export-xlsx", methods=["POST"])
def api_export_xlsx():
    """Génère un fichier Excel (.xlsx) si openpyxl est installé, sinon bascule en CSV propre."""
    data = request.get_json(silent=True) or {}
    candidates = data.get("candidates", [])
    if not candidates:
        return jsonify({"success": False, "message": "Aucun candidat sélectionné."}), 400

    headers = [
        "Rang", "Nom Complet", "Profession", "Posture", "Séniorité",
        "Expérience (ans)", "Adresse / Ville", "Trajet (km)", "CO2/an (kg)",
        "Score (%)", "Niveau Match", "Téléphone", "E-mail", "Compétences Validées", "Statut RH"
    ]

    rows = []
    for c in candidates:
        tier_lbl = (c.get("match_tier") or {}).get("label", "")
        rows.append([
            c.get("rank", ""),
            c.get("name", ""),
            c.get("main_profession", ""),
            c.get("posture", ""),
            c.get("seniority", ""),
            c.get("exp_years", 0),
            c.get("location", ""),
            c.get("distance_km") if c.get("distance_km") is not None else "N/A",
            c.get("co2_annual_kg") if c.get("co2_annual_kg") is not None else "N/A",
            c.get("score", 0),
            tier_lbl,
            c.get("phone", "") or "Non détecté",
            c.get("email", "") or "Non détecté",
            ", ".join(c.get("matched_skills", [])),
            c.get("hr_status", "À convoquer")
        ])

    if HAS_OPENPYXL:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Shortlist RH CLAVERATS"
        ws.append(headers)

        header_fill = PatternFill(start_color="4A72FF", end_color="4A72FF", fill_type="solid")
        header_font = Font(color="FFFFFF", bold=True)
        for col_idx in range(1, len(headers) + 1):
            cell = ws.cell(row=1, column=col_idx)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center")

        for r in rows:
            ws.append(r)

        for col in ws.columns:
            max_len = max((len(str(cell.value or "")) for cell in col), default=12)
            ws.column_dimensions[col.column_letter].width = min(max_len + 4, 42)

        mem = io.BytesIO()
        wb.save(mem)
        mem.seek(0)
        return send_file(
            mem,
            as_attachment=True,
            download_name=f"Shortlist_RH_CLAVERATS_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    import csv
    output = io.StringIO()
    output.write("\ufeff")
    writer = csv.writer(output, delimiter=";")
    writer.writerow(headers)
    writer.writerows(rows)

    mem = io.BytesIO(output.getvalue().encode("utf-8"))
    mem.seek(0)
    return send_file(
        mem,
        as_attachment=True,
        download_name=f"Shortlist_RH_CLAVERATS_{datetime.now().strftime('%Y%m%d')}.csv",
        mimetype="text/csv"
    )

@app.route("/api/export-predictive-txt", methods=["POST"])
def api_export_predictive_txt():
    data = request.get_json(silent=True) or {}
    c = data.get("candidate", {})
    if not c:
        return jsonify({"success": False, "message": "Candidat introuvable."}), 400

    lines = [
        "============================================================",
        "GUIDE D'ENTRETIEN PRÉDICTIF - CLAVERATS PRO",
        f"Candidat : {c.get('name', 'Candidat')} (#{c.get('rank', '-')})",
        f"Profil : {c.get('main_profession', '')} | Séniorité : {c.get('seniority', '')} | Posture : {c.get('posture', '')}",
        f"Score Global : {c.get('score', 0)}% ({(c.get('match_tier') or {}).get('label', '')})",
        "============================================================\n",
        "1. ANOMALIES & POINTS DE VIGILANCE DÉTECTÉS :"
    ]
    gaps = c.get("chrono_gaps", [])
    if gaps:
        for g in gaps:
            lines.append(f"   - [Trou chronologique] {g}")
    else:
        lines.append("   - Aucun trou chronologique majeur (> 6 mois) détecté.")

    missing = c.get("missing_skills", [])
    if missing:
        lines.append(f"   - [Compétences requises absentes du CV] : {', '.join(missing)}")

    lines.append("\n2. QUESTIONS PRÉDICTIVES À POSER EN ENTRETIEN :")
    for idx, q in enumerate(c.get("predictive_questions", []), 1):
        lines.append(f"   Q{idx}. {q}\n")

    mem = io.BytesIO("\n".join(lines).encode("utf-8"))
    mem.seek(0)
    safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", c.get("name", "Candidat"))
    return send_file(mem, as_attachment=True, download_name=f"Entretien_Predictif_{safe_name}.txt", mimetype="text/plain")

@app.route("/api/export-scorecard-pdf", methods=["POST"])
def api_export_scorecard_pdf():
    data = request.get_json(silent=True) or {}
    c = data.get("candidate", {})
    if not c:
        return jsonify({"success": False, "message": "Candidat introuvable."}), 400

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()

    elements = [
        Paragraph(f"Fiche d'Évaluation Entretien RH - {c.get('name', 'Candidat')}", styles["Title"]),
        Spacer(1, 10),
        Paragraph(f"<b>Poste / Profil :</b> {c.get('main_profession', '')} | <b>Expérience :</b> {c.get('exp_years', 0)} an(s) ({c.get('seniority', '')})", styles["Normal"]),
        Paragraph(f"<b>Score Matching ATS :</b> {c.get('score', 0)}% ({(c.get('match_tier') or {}).get('label', '')}) | <b>Posture :</b> {c.get('posture', '')}", styles["Normal"]),
        Paragraph(f"<b>Localisation :</b> {c.get('location', 'Non précisée')} | <b>Contact :</b> {c.get('phone', 'N/A')} - {c.get('email', 'N/A')}", styles["Normal"]),
        Spacer(1, 14),
        Paragraph("Grille de Notation Recruteur (1 = Insuffisant, 5 = Excellent)", styles["Heading2"]),
    ]

    table_data = [
        ["Critère d'évaluation", "Note (/5)", "Observations du recruteur"],
        ["Maîtrise technique & compétences clés", "[  ] 1  [  ] 2  [  ] 3  [  ] 4  [  ] 5", ""],
        ["Expérience & réalisations concrètes", "[  ] 1  [  ] 2  [  ] 3  [  ] 4  [  ] 5", ""],
        ["Communication & clarté des réponses", "[  ] 1  [  ] 2  [  ] 3  [  ] 4  [  ] 5", ""],
        ["Adéquation culturelle & motivation", "[  ] 1  [  ] 2  [  ] 3  [  ] 4  [  ] 5", ""],
        ["Décision finale", "[  ] Retenu   [  ] Vivier   [  ] Refusé", ""]
    ]
    tbl = Table(table_data, colWidths=[195, 165, 130])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4A72FF")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.6, colors.HexColor("#CBD5E1")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("PADDING", (0, 0), (-1, -1), 8),
    ]))
    elements.append(tbl)
    elements.append(Spacer(1, 14))
    elements.append(Paragraph("Questions prédictives & points à vérifier :", styles["Heading3"]))
    for q in c.get("predictive_questions", [])[:5]:
        elements.append(Paragraph(f"• {q}", styles["Normal"]))
        elements.append(Spacer(1, 4))

    doc.build(elements)
    buffer.seek(0)
    safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", c.get("name", "Candidat"))
    return send_file(buffer, as_attachment=True, download_name=f"Scorecard_RH_{safe_name}.pdf", mimetype="application/pdf")


@app.route("/api/export-pdf", methods=["POST"])
def api_export_pdf():
    data = request.get_json(silent=True) or {}
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    cv = data.get("cv_details", {})

    elements = [
        Paragraph(f"Bilan Audit CV - {cv.get('full_name', 'Candidat')}", styles["Title"]),
        Spacer(1, 12),
        Paragraph(f"Score Global : {data.get('score', 0)} % (Potentiel : {data.get('projected_score', 0)} %)", styles["Heading2"]),
        Paragraph(f"Profession : {cv.get('main_profession', '')} | Expérience : {cv.get('exp_years', 0)} an(s) | Posture : {(cv.get('posture_info') or {}).get('posture', '')}", styles["Normal"]),
        Paragraph(f"Compétences validées ({len(data.get('matched_skills', []))}) : {', '.join(data.get('matched_skills', [])) or 'Aucune'}", styles["Normal"]),
        Paragraph(f"Compétences manquantes ({len(data.get('missing_skills', []))}) : {', '.join(data.get('missing_skills', [])) or 'Aucune'}", styles["Normal"])
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

@app.route("/api/hr-recalculate-candidate", methods=["POST"])
def api_hr_recalculate_candidate():
    """Recalcule instantanément le score et le statut d'un candidat édité manuellement par la RH."""
    data = request.get_json(silent=True) or {}
    cand = data.get("candidate", {})
    job_det = data.get("job_details", {})
    job_skills = data.get("job_skills", [])
    tech_weight = int(data.get("tech_weight", 60) or 60)

    manual_skills = cand.get("matched_skills", [])
    if isinstance(manual_skills, str):
        manual_skills = [s.strip() for s in manual_skills.split(",") if s.strip()]

    job_set = {s.lower(): s for s in job_skills}
    cand_set = {s.lower(): s for s in manual_skills}

    # seules les competences EXIGEES comptent dans le score ; les autres competences saisies sont des « bonus » (jamais comptees comme exigences)
    matched = sorted([job_set[k] for k in job_set if k in cand_set])
    missing = sorted([job_set[k] for k in job_set if k not in cand_set])
    bonus_manual = [s for s in manual_skills if s.lower() not in job_set]

    cv_det = {
        "full_name": cand.get("name", "Candidat"),
        "initials": "".join(w[0].upper() for w in cand.get("name", "CV").split()[:2]) or "CV",
        "photo": cand.get("photo"),
        "main_profession": cand.get("main_profession", "Profil"),
        "secondary_professions": cand.get("secondary_professions", []),
        "objective": cand.get("objective", ""),
        "location": cand.get("location", "Non précisée"),
        "emails": [cand["email"]] if cand.get("email") else [],
        "phones": [cand["phone"]] if cand.get("phone") else [],
        "languages": cand.get("languages", ["Français"]),
        "exp_years": float(cand.get("exp_years", 0) or 0),
        "education_label": cand.get("education", "Non précisé"),
        "education_rank": 3 if "licence" in normalize_text(cand.get("education", "")) else (4 if "master" in normalize_text(cand.get("education", "")) else 2),
        "posture_info": {"posture": cand.get("posture", "Polyvalente")},
        "chrono_gaps": cand.get("chrono_gaps", []),
        "structured_experiences": cand.get("structured_experiences", []),
        "country_hint": cand.get("country_hint", ""),
        "links": cand.get("links", []),
        "categorized_skills": cand.get("categorized_skills", {}),
    }
    if cand.get("emails"):
        cv_det["emails"] = cand["emails"]
    if cand.get("phones"):
        cv_det["phones"] = cand["phones"]

    rep = compute_final_report(cv_det, job_det, matched, missing, bonus_manual, [], cand.get("raw_text", ""), tech_weight)
    geo_intel = rep["comparison"]["geo"].get("intel", {})
    cand["bonus_skills"] = bonus_manual
    cand["score_explanation"] = rep.get("score_explanation")
    cand["score_confidence"] = rep.get("score_confidence")

    cand.setdefault("initial_score", cand.get("score", rep["score"]))
    cand["score"] = rep["score"]
    cand["score_comparison"] = ats_scoring.compare_scores(cand["initial_score"], rep["score"])
    cand["match_tier"] = rep["match_tier"]
    cand["radar_axes"] = rep["radar_axes"]
    cand["matched_skills"] = matched
    cand["missing_skills"] = missing
    cand["readability"] = "clean"
    cand["distance_km"] = geo_intel.get("distance_km")
    cand["commute_min"] = geo_intel.get("commute_min")
    cand["co2_annual_kg"] = geo_intel.get("co2_annual_kg")
    cand["city_coords"] = geo_intel.get("cand_coords")
    cand["predictive_questions"] = rep["interview_questions"]

    return jsonify({"success": True, "candidate": cand})


@app.route("/api/export-multi-offer-pdf", methods=["POST"])
def api_export_multi_offer_pdf():
    """Exporte en PDF le classement comparatif Multi-Offres (Matrice de Chance)."""
    data = request.get_json(silent=True) or {}
    matrix = data.get("matrix", [])
    cand_name = data.get("candidate_name", "Candidat")
    if not matrix:
        return jsonify({"success": False, "message": "Aucune comparaison disponible."}), 400

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()

    elements = [
        Paragraph(f"Matrice Comparative Multi-Offres - {cand_name}", styles["Title"]),
        Spacer(1, 12)
    ]
    for item in matrix:
        elements.append(Paragraph(
            f"<b>#{item.get('rank')} - {item.get('title')}</b> ({item.get('company')} • {item.get('location')})",
            styles["Heading3"]
        ))
        elements.append(Paragraph(
            f"Chance globale : <b>{item.get('win_chance')}%</b> | Score technique : {item.get('tech_score')}% | Tension marché : {item.get('market_tension')}",
            styles["Normal"]
        ))
        elements.append(Paragraph(
            f"Compétences validées ({item.get('matched_count')}) : {', '.join(item.get('matched_skills', [])) or 'Aucune'}",
            styles["Normal"]
        ))
        elements.append(Paragraph(
            f"Compétences manquantes ({item.get('missing_count')}) : {', '.join(item.get('missing_skills', [])) or 'Aucune'}",
            styles["Normal"]
        ))
        elements.append(Spacer(1, 10))

    doc.build(elements)
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name="Matrice_Multi_Offres_CLAVERATS.pdf", mimetype="application/pdf")

@app.route("/api/hr-inspect-candidate", methods=["POST"])
def api_hr_inspect_candidate():
    """Bascule un candidat sélectionné côté RH vers le bilan complet détaillé."""
    data = request.get_json(silent=True) or {}
    cand = data.get("candidate", {})
    job_det = data.get("job_details", {})
    job_skills = data.get("job_skills", [])
    tech_weight = int(data.get("tech_weight", 60) or 60)

    matched = cand.get("matched_skills", [])
    missing = cand.get("missing_skills", [])
    bonus = cand.get("bonus_skills", [])

    cv_det = {
        "full_name": cand.get("name", "Candidat"),
        "initials": cand.get("initials", "CV"),
        "photo": cand.get("photo"),
        "main_profession": cand.get("main_profession", "Profil"),
        "secondary_professions": cand.get("secondary_professions", []),
        "objective": cand.get("objective", ""),
        "location": cand.get("location", "Non précisée"),
        "emails": [cand["email"]] if cand.get("email") else [],
        "phones": [cand["phone"]] if cand.get("phone") else [],
        "links": [],
        "languages": cand.get("languages", ["Français"]),
        "exp_years": float(cand.get("exp_years", 0) or 0),
        "seniority": cand.get("seniority", "Junior"),
        "structured_experiences": cand.get("structured_experiences", []),
        "chrono_gaps": cand.get("chrono_gaps", []),
        "education_label": cand.get("education", "Non précisé"),
        "education_rank": 3 if "licence" in normalize_text(cand.get("education", "")) else (4 if "master" in normalize_text(cand.get("education", "")) else 2),
        "posture_info": {"posture": cand.get("posture", "Polyvalente"), "impact_score": 70},
        "ats_audit": {"ats_ready_pct": 90, "checks": []}
    }

    total_job = max(1, len(job_skills))
    breakdown = [{
        "category": "Compétences du poste RH",
        "matched": len(matched),
        "total": len(job_skills),
        "percent": round((len(matched) / total_job) * 100)
    }]

    report = compute_final_report(cv_det, job_det, matched, missing, bonus, breakdown, "", tech_weight)
    return jsonify(report)

@app.route("/api/export-optimized-cv", methods=["POST"])
def api_export_optimized_cv():
    """Génère un CV PDF propre, structuré et 100 % ATS à partir des données corrigées du candidat."""
    data = request.get_json(silent=True) or {}
    cv = data.get("cv_details", {})
    matched = data.get("matched_skills", [])
    bonus = data.get("bonus_skills", [])
    all_sk = sorted(list(set(matched + bonus)))

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()

    elements = [
        Paragraph(f"<b>{cv.get('full_name', 'Candidat').upper()}</b>", styles["Title"]),
        Paragraph(f"<b>{cv.get('main_profession', '')}</b>", styles["Heading2"]),
        Paragraph(
            f"Localisation : {cv.get('location', 'Non précisée')} | "
            f"Tél : {', '.join(cv.get('phones', [])) or 'N/A'} | "
            f"E-mail : {', '.join(cv.get('emails', [])) or 'N/A'}",
            styles["Normal"]
        ),
        Spacer(1, 12),
        Paragraph("PROFIL PROFESSIONNEL", styles["Heading3"]),
        Paragraph(cv.get("objective", ""), styles["Normal"]),
        Spacer(1, 10),
        Paragraph("COMPÉTENCES & OUTILS MAÎTRISÉS", styles["Heading3"]),
        Paragraph(", ".join(all_sk) if all_sk else "Compétences métier validées", styles["Normal"]),
        Spacer(1, 10),
        Paragraph("EXPÉRIENCES PROFESSIONNELLES", styles["Heading3"]),
    ]

    for exp in cv.get("structured_experiences", []):
        elements.append(Paragraph(f"<b>{exp.get('role', '')}</b> - {exp.get('employer', '')} ({exp.get('period', '')})", styles["Normal"]))
        for t in exp.get("tasks", []):
            elements.append(Paragraph(f"• {t}", styles["Normal"]))
        elements.append(Spacer(1, 6))

    elements.append(Spacer(1, 8))
    elements.append(Paragraph("FORMATION & LANGUES", styles["Heading3"]))
    elements.append(Paragraph(f"<b>Diplôme :</b> {cv.get('education_label', 'Non précisé')}", styles["Normal"]))
    elements.append(Paragraph(f"<b>Langues :</b> {', '.join(cv.get('languages', [])) or 'Français'}", styles["Normal"]))

    doc.build(elements)
    buffer.seek(0)
    safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", cv.get("full_name", "Candidat"))
    return send_file(buffer, as_attachment=True, download_name=f"CV_Optimise_ATS_{safe_name}.pdf", mimetype="application/pdf")


@app.route("/api/export-hr-campaign-pdf", methods=["POST"])
def api_export_hr_campaign_pdf():
    """Exporte un rapport exécutif PDF de toute la campagne de recrutement RH."""
    data = request.get_json(silent=True) or {}
    cands = data.get("candidates", [])
    job = data.get("job_details", {})
    if not cands:
        return jsonify({"success": False, "message": "Aucune donnée de campagne disponible."}), 400

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()

    good_c = sum(1 for c in cands if c.get("score", 0) >= 45)
    avg_s = round(sum(c.get("score", 0) for c in cands) / max(1, len(cands)))

    elements = [
        Paragraph("Rapport Exécutif de Campagne RH - CLAVERATS Pro", styles["Title"]),
        Spacer(1, 10),
        Paragraph(f"<b>Organisation :</b> {job.get('company_name', 'Entreprise')} | <b>Lieu du poste :</b> {job.get('location', 'Non précisé')}", styles["Normal"]),
        Paragraph(f"<b>CV Analysés :</b> {len(cands)} | <b>Bons Profils (≥ 45%) :</b> {good_c} | <b>Score Moyen Cohorte :</b> {avg_s}%", styles["Normal"]),
        Spacer(1, 14),
        Paragraph("Classement des Candidats Analysés", styles["Heading2"]),
    ]

    table_data = [["Rang", "Nom Complet", "Profession", "Exp.", "Ville / Pays", "Score", "Statut"]]
    for c in cands[:25]:
        table_data.append([
            f"#{c.get('rank', '')}",
            c.get("name", "")[:22],
            c.get("main_profession", "")[:24],
            f"{c.get('exp_years', 0)} an(s)",
            c.get("location", "")[:18],
            f"{c.get('score', 0)}%",
            c.get("hr_status", "")
        ])

    tbl = Table(table_data, colWidths=[35, 110, 115, 45, 85, 45, 65])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4A72FF")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(tbl)

    doc.build(elements)
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name=f"Rapport_Campagne_RH_{datetime.now().strftime('%Y%m%d')}.pdf", mimetype="application/pdf")


@app.errorhandler(Exception)
def handle_unexpected_error(err):
    from werkzeug.exceptions import HTTPException
    if isinstance(err, HTTPException):
        return err  # 404/405... restent des erreurs HTTP normales (ex. world.geojson absent -> 404 et non 500)
    return jsonify({"success": False, "message": f"Erreur serveur Python : {str(err)}"}), 500


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5002, debug=False)
