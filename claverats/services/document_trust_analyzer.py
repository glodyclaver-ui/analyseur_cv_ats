"""Confiance d'un document CV : coherence interne (dates, contacts, doublons de texte, contenu actif)."""
import re


def analyze(raw_text, details=None, validation=None, ref_year=2026):
    flags, score = [], 100
    t = raw_text or ""
    for y in re.findall(r"\b(20\d{2})\b", t):
        if int(y) > ref_year + 1:
            flags.append("Annee future dans le CV (%s)." % y)
            score -= 10
            break
    words = re.findall(r"\w{4,}", t.lower())
    if words and len(set(words)) / len(words) < 0.25:
        flags.append("Texte tres repetitif (possible bourrage de mots-cles).")
        score -= 20
    if len(t.split()) < 80:
        flags.append("CV tres court / peu de texte extractible.")
        score -= 10
    if validation and validation.get("active_content"):
        flags.append("Le PDF contient du contenu actif (neutralise).")
        score -= 15
    d = details or {}
    if d and not d.get("emails"):
        flags.append("Aucun e-mail detecte.")
        score -= 10
    exps = d.get("structured_experiences") or []
    if exps and (d.get("experience_analysis") or {}).get("overlaps", 0) > 1:
        flags.append("Plusieurs experiences se chevauchent.")
        score -= 10
    # Texte cache : tres haute proportion de mots-cles techniques sans contexte
    score = max(0, min(100, score))
    return {"score": score, "level": "Fiable" if score >= 75 else "Prudence" if score >= 50 else "Suspect", "flags": flags}
