"""Base de connaissances metiers 100 % locale (dictionnaires Python, aucune base de donnees)."""
ROLES = {
    "Developpeur Web": {"core": ["html", "css", "javascript", "git"], "plus": ["react", "node.js", "typescript", "sql", "docker"],
                        "next": ["Developpeur Full-Stack", "Lead Developpeur"], "salary": 900},
    "Developpeur Full-Stack": {"core": ["javascript", "python", "sql", "git", "api"], "plus": ["react", "docker", "aws", "typescript", "node.js"],
                               "next": ["Architecte Logiciel", "Lead Developpeur"], "salary": 1500},
    "Data Analyst": {"core": ["sql", "excel", "python", "power bi"], "plus": ["tableau", "statistiques", "pandas"],
                     "next": ["Data Scientist", "Data Engineer"], "salary": 1100},
    "Data Scientist": {"core": ["python", "machine learning", "statistiques", "sql"], "plus": ["tensorflow", "pytorch", "pandas", "scikit-learn"],
                       "next": ["ML Engineer", "Lead Data"], "salary": 1800},
    "Data Engineer": {"core": ["python", "sql", "etl", "docker"], "plus": ["spark", "airflow", "aws", "kafka"],
                      "next": ["Architecte Data"], "salary": 1700},
    "DevOps": {"core": ["linux", "docker", "git", "ci/cd"], "plus": ["kubernetes", "terraform", "aws", "ansible"],
               "next": ["SRE", "Architecte Cloud"], "salary": 1700},
    "Administrateur Systemes & Reseaux": {"core": ["linux", "windows server", "reseaux", "tcp/ip"], "plus": ["cisco", "vmware", "active directory"],
                                          "next": ["DevOps", "Responsable IT"], "salary": 1000},
    "Cybersecurite": {"core": ["reseaux", "linux", "securite", "firewall"], "plus": ["pentest", "siem", "iso 27001"],
                      "next": ["RSSI"], "salary": 1800},
    "Chef de Projet": {"core": ["gestion de projet", "agile", "communication"], "plus": ["scrum", "jira", "pmp", "budget"],
                       "next": ["Directeur de Projet"], "salary": 1400},
    "Comptable": {"core": ["comptabilite", "excel", "fiscalite"], "plus": ["sage", "ohada", "audit"],
                  "next": ["Responsable Financier"], "salary": 800},
    "Marketing Digital": {"core": ["seo", "reseaux sociaux", "analytics"], "plus": ["google ads", "content", "email marketing"],
                          "next": ["Responsable Marketing"], "salary": 900},
    "Ressources Humaines": {"core": ["recrutement", "paie", "droit du travail"], "plus": ["gpec", "formation", "sirh"],
                            "next": ["Responsable RH"], "salary": 900},
}

RELATED = {
    "javascript": ["typescript", "react", "node.js", "vue", "angular"], "typescript": ["javascript", "react", "angular"],
    "python": ["django", "flask", "pandas", "numpy", "fastapi"], "java": ["spring", "kotlin", "maven"],
    "sql": ["mysql", "postgresql", "oracle", "power bi"], "docker": ["kubernetes", "ci/cd", "linux"],
    "react": ["javascript", "redux", "next.js"], "aws": ["azure", "gcp", "terraform"], "azure": ["aws", "gcp"],
    "machine learning": ["tensorflow", "pytorch", "scikit-learn", "statistiques"], "excel": ["power bi", "vba", "tableau"],
    "linux": ["bash", "docker", "reseaux"], "git": ["github", "gitlab", "ci/cd"], "scrum": ["agile", "jira", "kanban"],
    "html": ["css", "javascript"], "css": ["sass", "html", "bootstrap"], "php": ["laravel", "mysql", "symfony"],
    "seo": ["analytics", "content", "google ads"], "comptabilite": ["fiscalite", "sage", "audit"],
}

TRAINING_HINTS = {
    "docker": "Tutoriel officiel Docker (conteneurs, compose) - 2 a 3 semaines.",
    "kubernetes": "Apres Docker : pods, services, deployments - 4 semaines.",
    "sql": "SQL pratique : jointures, agregats, index - 2 semaines.",
    "python": "Bases Python + un mini-projet - 4 semaines.",
    "git": "Git : branches, merge, pull requests - 1 semaine.",
    "react": "React : composants, hooks, etat - 4 semaines.",
    "aws": "AWS Cloud Practitioner - 4 semaines.",
    "agile": "Agile/Scrum : cycle, rituels, backlog - 1 semaine.",
}


def role_for(skills):
    """Classe les metiers selon le recouvrement avec les competences (retourne [(role, score)])."""
    s = {x.lower() for x in skills}
    out = []
    for r, d in ROLES.items():
        core = sum(1 for k in d["core"] if k in s) / len(d["core"])
        plus = sum(1 for k in d["plus"] if k in s) / max(1, len(d["plus"]))
        out.append((r, round(core * 0.75 + plus * 0.25, 3)))
    return sorted(out, key=lambda x: -x[1])
