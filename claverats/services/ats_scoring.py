"""Score ATS : initial (PDF) vs corrige (edition manuelle). Logique pure, sans Flask."""


def compare_scores(initial, corrected):
    d = corrected - initial
    return {"initial": initial, "corrected": corrected, "delta": d,
            "label": "Score ameliore par vos corrections" if d > 0 else "Score reduit par vos corrections" if d < 0 else "Score inchange"}


def ats_readability(raw_text, report=None):
    """Indice de lisibilite ATS 0-100 : longueur, sections, contacts, mots-cles."""
    t = (raw_text or "")
    low = t.lower()
    pts, notes = 0, []
    n = len(t.split())
    if 250 <= n <= 1200:
        pts += 25
    else:
        notes.append("Longueur du CV atypique (%d mots)." % n)
    secs = [s for s in ("experience", "formation", "competences", "langues", "education", "skills") if s in low.replace("é", "e")]
    pts += min(30, 10 * len(secs))
    if len(secs) < 3:
        notes.append("Sections standard insuffisantes.")
    if "@" in t:
        pts += 15
    else:
        notes.append("E-mail introuvable.")
    if any(c.isdigit() for c in t):
        pts += 10
    if report:
        sc = report.get("stats", {})
        if sc.get("matched_count", 0) >= 5:
            pts += 20
        elif sc.get("matched_count", 0):
            pts += 10
    return {"score": min(100, pts), "notes": notes}


def format_quality(raw_text, details=None):
    """Qualite de MISE EN FORME estimee a partir du texte extrait (structure, sections, lisibilite).
    Explicable : chaque critere indique ses points et un conseil. La mise en page purement visuelle
    (couleurs, colonnes, polices) n'est pas evaluee ici et n'est donc pas pretendue."""
    import re
    t = raw_text or ""
    low = re.sub(r"[éèêë]", "e", t.lower())
    lines = [l for l in t.splitlines() if l.strip()]
    words = len(t.split())
    details = details or {}
    crit = []

    def add(label, ok, pts, mx, tip):
        crit.append({"label": label, "ok": bool(pts >= mx), "points": pts, "max": mx, "tip": "" if pts >= mx else tip})

    for names, lab in ((("experience", "parcours professionnel", "work experience"), "Section Expériences"),
                       (("formation", "education", "etudes", "diplome"), "Section Formation"),
                       (("competences", "skills", "aptitudes", "outils"), "Section Compétences")):
        add(lab, True, 10 if any(n in low for n in names) else 0, 10, "Ajoutez une rubrique clairement titrée « %s »." % lab.replace("Section ", ""))
    has_mail = bool(re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", t))
    has_tel = bool(re.search(r"(?<!\d)(?:\+|00)?\d[\d\s().-]{7,}\d", t))
    add("Coordonnées (e-mail et téléphone)", True, 8 * has_mail + 7 * has_tel, 15, "Indiquez un e-mail ET un téléphone en haut du CV.")
    add("Longueur adaptée (250-900 mots)", True, 15 if 250 <= words <= 900 else 8 if 150 <= words <= 1200 else 0, 15,
        "Visez 1 à 2 pages (≈250 à 900 mots) : %d mots actuellement." % words)
    bullets = sum(1 for l in lines if re.match(r"^\s*[-•*▪➢✔✓●◦·–]", l))
    add("Listes à puces (lisibilité)", True, 10 if bullets >= 4 else 5 if bullets >= 2 else 0, 10, "Présentez les missions sous forme de puces courtes.")
    dense = sum(1 for l in lines if len(l) > 220)
    add("Pas de blocs de texte trop denses", True, 10 if lines and dense / len(lines) < 0.05 else 4 if lines and dense / len(lines) < 0.15 else 0, 10,
        "Découpez les paragraphes longs en phrases courtes ou en puces.")
    dates = len(re.findall(r"\b(?:19|20)\d{2}\b", t))
    add("Dates / périodes lisibles", True, 10 if dates >= 4 else 5 if dates >= 2 else 0, 10, "Indiquez les périodes (mois/année) de chaque expérience.")
    has_nums = len(re.findall(r"\d+\s*(?:%|projets|clients|patients|personnes|membres|ans)", low))
    add("Résultats chiffrés", True, 5 if has_nums >= 2 else 2 if has_nums == 1 else 0, 5, "Ajoutez des chiffres (patients suivis, % d'amélioration, équipe encadrée…).")
    has_title = bool(details.get("main_profession")) and details.get("main_profession") not in ("Profil", "Non précisé")
    add("Titre / profil en en-tête", True, 5 if has_title else 0, 5, "Ajoutez un titre de profil clair sous votre nom.")
    total = sum(c["points"] for c in crit)
    return {"score": total, "level": "Très lisible" if total >= 80 else "Correct" if total >= 55 else "À améliorer", "criteria": crit,
            "note": "Évaluation du texte extrait (structure et lisibilité) ; la mise en page visuelle n'est pas jugée."}
