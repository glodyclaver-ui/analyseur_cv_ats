"""Moteur d'entretien 100 % local : similarite TF-IDF (cosinus) + questions comportementales STAR."""
from ._core import tfidf_vectors, cosine

STAR = ("Situation", "Tache", "Action", "Resultat")


def semantic_match(cv_text, job_text):
    """Similarite semantique pure Python (0-100) entre CV et offre."""
    v, _ = tfidf_vectors([cv_text or "", job_text or ""])
    return round(100 * cosine(v[0], v[1]))


_NOISE = {"d", "c", "competences", "competence", "experience", "francais", "formation", "langues", "anglais", "profil"}


def _clean(skills):
    return [s for s in skills if len(s.strip(" .")) >= 2 and s.lower().strip(" .") not in _NOISE and not s.endswith(".")]


def build_questions(report, n=10):
    report = dict(report, missing_skills=_clean(report.get("missing_skills", [])), matched_skills=_clean(report.get("matched_skills", [])))
    cv = report.get("cv_details", {}) or {}
    jd = report.get("job_details", {}) or {}
    qs = []
    for s in report.get("missing_skills", [])[:3]:
        qs.append({"type": "Ecart", "q": "Vous n'avez pas mentionne %s : comment comptez-vous combler cet ecart ?" % s,
                   "star": "Decrivez un cas ou vous avez appris vite une technologie nouvelle (S-T-A-R)."})
    for s in report.get("matched_skills", [])[:3]:
        qs.append({"type": "Technique", "q": "Racontez un projet concret ou vous avez utilise %s." % s,
                   "star": "Situation, tache, vos actions precises, resultat chiffre."})
    for e in (cv.get("structured_experiences") or [])[:2]:
        qs.append({"type": "Parcours", "q": "Chez %s (%s), quelle a ete votre plus grande realisation ?" %
                   (e.get("company", "cette societe"), e.get("duration_label", "periode")),
                   "star": "Mettez en avant un resultat mesurable."})
    ea = cv.get("experience_analysis") or {}
    if ea.get("gaps"):
        qs.append({"type": "Parcours", "q": "Votre parcours presente une interruption : que faisiez-vous durant cette periode ?", "star": "Restez factuel."})
    if ea.get("stability") == "Mobile":
        qs.append({"type": "Stabilite", "q": "Vos missions sont courtes : qu'est-ce qui vous motive a vous engager durablement chez nous ?", "star": ""})
    org = jd.get("company_name", "notre organisation")
    qs += [{"type": "Motivation", "q": "Pourquoi %s et ce poste ?" % org, "star": ""},
           {"type": "Comportemental", "q": "Decrivez un conflit d'equipe que vous avez resolu.", "star": "S-T-A-R"},
           {"type": "Comportemental", "q": "Parlez d'un echec et de ce que vous en avez retenu.", "star": "S-T-A-R"}]
    return qs[:n]


def score_answer(question_type, answer):
    """Evalue localement une reponse : structure STAR, chiffres, longueur."""
    a = (answer or "").lower()
    hits = {"Situation": any(w in a for w in ("contexte", "situation", "lorsque", "quand", "etait")),
            "Tache": any(w in a for w in ("objectif", "mission", "devais", "charge de", "tache")),
            "Action": any(w in a for w in ("j'ai", "j ai", "mis en place", "realise", "developpe", "organise")),
            "Resultat": any(w in a for w in ("resultat", "grace", "permis", "augmente", "reduit", "%", "economis"))}
    n = len(a.split())
    pts = 25 * sum(hits.values()) + (0 if n >= 40 else -10)
    return {"score": max(0, min(100, pts)), "star": hits, "length": n,
            "advice": [("Ajoutez : " + k) for k, v in hits.items() if not v] + (["Reponse trop courte (<40 mots)."] if n < 40 else [])}
