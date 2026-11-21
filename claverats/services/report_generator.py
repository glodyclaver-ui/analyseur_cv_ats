"""Generation de rapports locaux (HTML autonome, imprimable en PDF par le navigateur / ReportLab cote app)."""
import time
from .document_security_engine import escape_html as e


def candidate_html(report, extras=None):
    cv = report.get("cv_details", {}) or {}
    jd = report.get("job_details", {}) or {}
    ex = extras or {}
    rows = "".join("<li>%s</li>" % e(s) for s in report.get("missing_skills", [])[:15])
    mat = ", ".join(e(s) for s in report.get("matched_skills", []))
    exps = "".join("<tr><td>%s</td><td>%s</td><td>%s</td></tr>" % (e(x.get("company")), e(x.get("role") or x.get("title")), e(x.get("duration_label", "")))
                   for x in cv.get("structured_experiences", []) or [])
    dec = ex.get("decision", {})
    return ("<!doctype html><meta charset='utf-8'><title>Rapport CLAVERATS</title><style>body{font-family:system-ui;margin:32px;color:#111}"
            "h1{margin:0}.s{font-size:42px;font-weight:800}table{border-collapse:collapse;width:100%%}td,th{border:1px solid #ccc;padding:6px;text-align:left}"
            ".w{position:fixed;top:40%%;left:10%%;font-size:80px;color:rgba(0,0,0,.05);transform:rotate(-25deg)}</style>"
            "<div class='w'>CONFIDENTIEL</div><h1>%s</h1><p>Offre : %s - %s</p><div class='s'>%s%%</div><p>Decision : <b>%s</b></p>"
            "<h3>Competences validees</h3><p>%s</p><h3>Competences manquantes</h3><ul>%s</ul><h3>Experiences</h3><table><tr><th>Societe</th><th>Poste</th><th>Duree</th></tr>%s</table>"
            "<p style='color:#666;font-size:12px'>Genere localement le %s - aucune donnee transmise.</p>") % (
        e(cv.get("full_name")), e(jd.get("company_name")), e(jd.get("contract_type")), e(report.get("score")), e(dec.get("verdict", "-")),
        mat, rows, exps, time.strftime("%d/%m/%Y %H:%M"))
