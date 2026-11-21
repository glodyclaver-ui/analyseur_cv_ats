"""Graphe de relations entre competences : table locale + co-occurrences apprises sur les CV charges."""
from collections import Counter
from itertools import combinations
from .job_knowledge_base import RELATED


def build_graph(reports, min_weight=1):
    """Noeuds = competences, aretes = connaissance a priori + co-occurrence dans les CV."""
    cnt, edges = Counter(), Counter()
    for r in reports:
        sk = sorted({s.lower() for s in (r.get("matched_skills", []) + r.get("missing_skills", []) + r.get("bonus_skills", []))})
        cnt.update(sk)
        for a, b in combinations(sk, 2):
            edges[(a, b)] += 1
    for a, lst in RELATED.items():
        for b in lst:
            k = tuple(sorted((a, b)))
            edges[k] += 1
            cnt.setdefault(a, 0)
            cnt.setdefault(b, 0)
    nodes = [{"id": k, "weight": v} for k, v in cnt.most_common(60)]
    ids = {n["id"] for n in nodes}
    links = [{"source": a, "target": b, "weight": w} for (a, b), w in edges.items() if a in ids and b in ids and w >= min_weight]
    return {"nodes": nodes, "links": links[:200]}


def neighbors(skill, depth=1):
    seen, front = {skill.lower()}, {skill.lower()}
    rel = {}
    for k, v in RELATED.items():
        rel.setdefault(k, set()).update(v)
        for x in v:
            rel.setdefault(x, set()).add(k)
    for _ in range(depth):
        nxt = set()
        for f in front:
            nxt |= rel.get(f, set())
        front = nxt - seen
        seen |= nxt
    return sorted(seen - {skill.lower()})


def transferability(have, missing):
    """Pour chaque competence manquante : proximite avec ce que le candidat maitrise (0-100)."""
    have = {h.lower() for h in have}
    out = []
    for m in missing:
        near = [x for x in neighbors(m) if x in have]
        out.append({"skill": m, "closeness": min(100, 35 * len(near)), "via": near[:4]})
    return sorted(out, key=lambda x: -x["closeness"])
