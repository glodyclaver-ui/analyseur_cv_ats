"""Detection de doublons locale : SHA-256 du fichier + e-mail/telephone + nom flou."""
import re
from difflib import SequenceMatcher
from ._core import norm


def _digits(p):
    return re.sub(r"\D", "", str(p or ""))[-9:]


def _key_sets(c):
    emails = {str(e).lower() for e in (c.get("emails") or ([c.get("email")] if c.get("email") else []))}
    phones = {_digits(p) for p in (c.get("phones") or ([c.get("phone")] if c.get("phone") else [])) if len(_digits(p)) >= 7}
    return emails, phones


def similarity(a, b):
    if a.get("sha256") and a.get("sha256") == b.get("sha256"):
        return 1.0, "Fichier identique (SHA-256)"
    ea, pa = _key_sets(a)
    eb, pb = _key_sets(b)
    if ea & eb:
        return 0.97, "Meme e-mail"
    if pa & pb:
        return 0.95, "Meme telephone"
    na, nb = norm(a.get("full_name", "")), norm(b.get("full_name", ""))
    if na and nb:
        r = SequenceMatcher(None, " ".join(sorted(na.split())), " ".join(sorted(nb.split()))).ratio()
        if r >= 0.88:
            return round(0.6 + 0.3 * r, 2), "Nom tres proche"
    return 0.0, ""


def find_duplicates(candidates, threshold=0.85):
    out = []
    for i in range(len(candidates)):
        for j in range(i + 1, len(candidates)):
            s, why = similarity(candidates[i], candidates[j])
            if s >= threshold:
                out.append({"a": i, "b": j, "a_name": candidates[i].get("full_name", ""),
                            "b_name": candidates[j].get("full_name", ""), "score": s, "reason": why})
    return sorted(out, key=lambda x: -x["score"])
