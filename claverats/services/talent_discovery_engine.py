"""Recherche locale dans le vivier : requete libre -> classement TF-IDF des candidats."""
from ._core import tfidf_vectors, cosine, tokens


def _doc(r):
    cv = r.get("cv_details", {}) or {}
    return " ".join([cv.get("full_name", "")] + r.get("matched_skills", []) * 2 + r.get("bonus_skills", []) +
                    [e.get("company", "") + " " + (e.get("role") or e.get("title") or "") for e in cv.get("structured_experiences", []) or []] +
                    [cv.get("location", ""), cv.get("education_label", "")])


def search(reports, query, top=10):
    if not reports or not tokens(query):
        return []
    vecs, idf = tfidf_vectors([_doc(r) for r in reports] + [query])
    q = vecs[-1]
    out = [(cosine(q, v), i) for i, v in enumerate(vecs[:-1])]
    out.sort(reverse=True)
    return [{"index": i, "name": (reports[i].get("cv_details") or {}).get("full_name", "Candidat"),
             "relevance": round(100 * s), "score": reports[i].get("score", 0)} for s, i in out[:top] if s > 0]
