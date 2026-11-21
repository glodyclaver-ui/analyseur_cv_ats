"""Centre d'alertes RH (règles explicites, 100 % local). Aucune décision automatique : ce sont des signaux à vérifier par un humain.

Entrée : rapport de campagne RH (candidats déjà analysés). Chaque alerte est expliquée (règle + preuve).
"""
from collections import defaultdict

LOW_SCORE = 45
SEVERITY = {"high": 3, "medium": 2, "info": 1}


def _id(c):
    return (c.get("email") or (c.get("emails") or [""])[0] or c.get("name") or c.get("filename") or "").strip().lower()


def build(report, now_days=None):
    cands = (report or {}).get("candidates") or []
    alerts = []

    def add(sev, kind, title, why, who=None):
        alerts.append({"severity": sev, "kind": kind, "title": title, "why": why, "candidate": who})

    if not cands:
        return {"alerts": [], "counts": {}, "note": "Aucun candidat analysé."}

    # 1. Doublons (même identité)
    groups = defaultdict(list)
    for c in cands:
        k = _id(c)
        if k:
            groups[k].append(c)
    for k, g in groups.items():
        if len(g) > 1:
            add("medium", "duplicate", "Candidature en double probable", f"{len(g)} dossiers partagent la même identité ({k}). Règle : même e-mail ou même nom.", g[0].get("name"))

    # 2. Dossiers incomplets / illisibles
    for c in cands:
        miss = []
        if not (c.get("emails") or c.get("email")):
            miss.append("e-mail")
        if not (c.get("phones") or c.get("phone")):
            miss.append("téléphone")
        if not c.get("structured_experiences"):
            miss.append("expériences")
        if c.get("readability") == "unreadable":
            add("high", "incomplete_document", "Document illisible", "Texte non extractible (PDF scanné sans OCR ?). Demandez une version lisible.", c.get("name"))
        elif miss:
            add("info", "incomplete_document", "Dossier incomplet", "Éléments non détectés : " + ", ".join(miss) + ". Détecté automatiquement, à vérifier sur le document.", c.get("name"))

    # 3. Offre sans correspondance
    good = [c for c in cands if (c.get("score") or 0) >= LOW_SCORE]
    if not good:
        add("high", "offer_without_match", "Aucun candidat compatible", f"Aucun des {len(cands)} dossiers n'atteint {LOW_SCORE} %. Vérifiez l'offre (exigences trop strictes ?) ou élargissez le sourcing.")
    # 4. Besoin de candidats de secours
    top = [c for c in cands if (c.get("score") or 0) >= 70]
    pos = int((report or {}).get("positions_count") or 0)
    if pos and len(top) < pos + 1:
        add("medium", "backup_needed", "Vivier de secours insuffisant", f"{len(top)} candidat(s) ≥ 70 % pour {pos} poste(s) : prévoyez au moins 1 candidat de réserve.")
    # 5. Scores proches (départage nécessaire)
    srt = sorted(cands, key=lambda c: -(c.get("score") or 0))
    for a, b in zip(srt, srt[1:3]):
        if a.get("score") is not None and b.get("score") is not None and 0 < a["score"] - b["score"] <= 3 and a["score"] >= LOW_SCORE:
            add("info", "close_scores", "Scores très proches", f"{a.get('name')} ({a['score']} %) et {b.get('name')} ({b['score']} %) : écart ≤ 3 points, départagez par entretien.", a.get("name"))
    # 6. Score peu fiable
    for c in cands:
        lvl = (c.get("score_confidence") or {}).get("level")
        if lvl in ("faible", "insuffisante"):
            add("medium", "low_confidence", "Score peu fiable", "Peu de compétences exploitables dans l'offre/CV : le score est à interpréter avec prudence.", c.get("name"))

    alerts.sort(key=lambda a: -SEVERITY[a["severity"]])
    counts = defaultdict(int)
    for a in alerts:
        counts[a["severity"]] += 1
    return {"alerts": alerts, "counts": dict(counts), "note": "Signaux d'aide à la décision : aucune action n'est prise automatiquement."}
