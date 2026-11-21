"""Blueprint Flask : expose les services locaux sous /api/svc/* (aucune dependance externe)."""
import os
from flask import Blueprint, jsonify, request, Response

from . import (_core, audit_trail_manager as audit, candidate_history_manager as hist, candidate_deduplication as dedup,
               career_path_simulator, career_recommender, skills_gap_analyzer, skill_relationship_engine as graph,
               talent_intelligence_engine as talent, candidate_potential_analyzer as potential, recruitment_decision_engine as decision,
               recruitment_scenario_engine as scenario, team_compatibility_engine as team, talent_discovery_engine as discovery,
               workforce_simulator as workforce, recruitment_analytics_engine as analytics, interview_intelligence_engine as interview,
               interview_manager, application_tracker, campaign_manager, report_generator, security_manager as sec, organizational_intelligence as orgs,
               experience_analyzer, profile_enricher, org_verifier, ats_scoring, data_manager)

bp = Blueprint("svc", __name__, url_prefix="/api/svc")


def _j():
    return request.get_json(silent=True) or {}


@bp.before_app_request
def _guard():
    p = request.path
    if not p.startswith("/api/"):
        return None
    if sec.rate_limited(request.remote_addr or "local", limit=240, window=60):
        return jsonify({"success": False, "message": "Trop de requetes : patientez quelques secondes."}), 429
    if request.method == "POST" and p != "/api/svc/csrf":
        if not sec.csrf_valid(request.headers.get("X-CSRF-Token", "")):
            return jsonify({"success": False, "message": "Jeton de securite expire : rechargez la page."}), 403
    return None


@bp.get("/csrf")
def csrf():
    return jsonify({"token": sec.csrf_token()})


@bp.get("/health")
def health():
    from . import pdf_vision_extractor as pv
    return jsonify({"success": True, "store": _core.health(), "backups": _core.list_backups(), "opencv": pv.HAS_CV2,
                    "ocr": pv.ocr_available(), "audit": audit.verify(), "pin": sec.has_pin(), "version": "2.1"})


@bp.post("/intel")
def intel():
    r = _j().get("report") or {}
    cv = r.get("cv_details") or {}
    sk = r.get("matched_skills", []) + r.get("bonus_skills", [])
    trust = (r.get("doc_trust") or {}).get("score")
    out = {"success": True, "talent": talent.profile(r), "potential": potential.analyze(r), "decision": decision.decide(r, trust),
           "gaps": skills_gap_analyzer.analyze(r), "careers": career_recommender.recommend(r),
           "path": career_path_simulator.simulate(sk), "next_skills": scenario.best_next_skills(r),
           "interview": interview.build_questions(r),
           "semantic": interview.semantic_match(r.get("raw_cv_text", ""), (r.get("job_details") or {}).get("raw_job_text", "")),
           "enrichment": profile_enricher.enrich(cv.get("links_detail", []), online=bool(_j().get("online")))}
    return jsonify(out)


@bp.post("/org-verify")
def org_verify():
    d = _j()
    return jsonify({"success": True, "result": org_verifier.verify(d.get("job_text", ""), d.get("emails", []), d.get("links", []),
                                                                  d.get("phones", []), d.get("country", ""), bool(d.get("online")))})


@bp.post("/answer-score")
def answer_score():
    d = _j()
    return jsonify({"success": True, **interview.score_answer(d.get("type", ""), d.get("answer", ""))})


@bp.post("/scenario")
def scen():
    d = _j()
    return jsonify({"success": True, **scenario.what_if(d.get("report") or {}, d.get("add_skills", []), d.get("tech_weight"))})


@bp.post("/team")
def team_():
    d = _j()
    return jsonify({"success": True, **team.analyze(d.get("reports", []), d.get("required", []))})


@bp.post("/search")
def search():
    d = _j()
    return jsonify({"success": True, "results": discovery.search(d.get("reports", []), d.get("query", ""))})


@bp.post("/workforce")
def wf():
    d = _j()
    return jsonify({"success": True, **workforce.simulate(d.get("reports", []), d.get("required", []), d.get("budget"), d.get("cost", 1200), int(d.get("seats", 3)))})


@bp.post("/analytics")
def an():
    return jsonify({"success": True, **analytics.analytics(_j().get("reports", []))})


@bp.post("/graph")
def gr():
    return jsonify({"success": True, **graph.build_graph(_j().get("reports", []))})


@bp.post("/dedupe")
def dd():
    return jsonify({"success": True, "duplicates": dedup.find_duplicates(_j().get("candidates", []))})


@bp.post("/durations")
def durations():
    return jsonify({"success": True, **experience_analyzer.analyze(_j().get("experiences", []))})


@bp.post("/score-compare")
def score_cmp():
    d = _j()
    return jsonify({"success": True, **ats_scoring.compare_scores(d.get("initial", 0), d.get("corrected", 0))})


# --- historique & campagnes -------------------------------------------------------------
@bp.post("/history/record")
def h_rec():
    return jsonify({"success": True, "version": hist.record(_j().get("report"), _j().get("label", "analyse"))})


@bp.get("/history")
def h_list():
    return jsonify({"success": True, "candidates": hist.list_candidates()})


@bp.get("/history/evolution")
def h_evo():
    return jsonify({"success": True, **hist.evolution(request.args.get("name", ""))})


@bp.post("/history/compare")
def h_cmp():
    d = _j()
    return jsonify({"success": True, **hist.compare_versions(d.get("name", ""), int(d.get("i", 0)), int(d.get("j", 0)))})


@bp.post("/history/delete")
def h_del():
    hist.delete(_j().get("name", ""))
    return jsonify({"success": True})


@bp.post("/campaign/save")
def c_save():
    d = _j()
    hist.save_campaign(d.get("name", "campagne"), d.get("payload"))
    audit.log("campaign_save", d.get("name", ""))
    return jsonify({"success": True})


@bp.post("/campaign/load")
def c_load():
    p = hist.load_campaign(_j().get("name", ""))
    return jsonify({"success": p is not None, "payload": p})


@bp.get("/campaign/list")
def c_list():
    return jsonify({"success": True, "campaigns": hist.list_campaigns()})


@bp.post("/campaign/export")
def c_exp():
    return Response(campaign_manager.export_campaign(_j().get("payload")), mimetype="application/json",
                    headers={"Content-Disposition": "attachment; filename=campagne_claverats.json"})


@bp.post("/campaign/import")
def c_imp():
    try:
        return jsonify({"success": True, "payload": campaign_manager.import_campaign(request.get_data(as_text=True))})
    except ValueError as e:
        return jsonify({"success": False, "message": str(e)}), 400


# --- suivi entretiens / candidatures -------------------------------------------------------
@bp.get("/interviews")
def iv_list():
    return jsonify({"success": True, "items": interview_manager.list_all()})


@bp.post("/interviews")
def iv_add():
    d = _j()
    return jsonify({"success": True, "item": interview_manager.add(d.get("candidate", "")[:80], d.get("when", ""), d.get("mode", "visio"), d.get("notes", ""))})


@bp.post("/interviews/update")
def iv_up():
    d = _j()
    interview_manager.update(int(d.get("id", 0)), **{k: d[k] for k in ("when", "mode", "notes", "score", "done") if k in d})
    return jsonify({"success": True})


@bp.post("/interviews/delete")
def iv_del():
    interview_manager.remove(int(_j().get("id", 0)))
    return jsonify({"success": True})


@bp.get("/applications")
def ap_list():
    return jsonify({"success": True, **application_tracker.board()})


@bp.post("/applications")
def ap_add():
    d = _j()
    return jsonify({"success": True, "item": application_tracker.add(d.get("company", ""), d.get("title", ""), d.get("score"), d.get("url", ""))})


@bp.post("/applications/move")
def ap_move():
    d = _j()
    try:
        application_tracker.move(int(d.get("id", 0)), d.get("stage", ""))
    except ValueError as e:
        return jsonify({"success": False, "message": str(e)}), 400
    return jsonify({"success": True})


@bp.post("/applications/delete")
def ap_del():
    application_tracker.remove(int(_j().get("id", 0)))
    return jsonify({"success": True})


# --- rapport, audit, sauvegardes, securite --------------------------------------------------
@bp.post("/report-html")
def rep_html():
    r = _j().get("report") or {}
    ex = {"decision": decision.decide(r, (r.get("doc_trust") or {}).get("score"))}
    audit.log("report_html", (r.get("cv_details") or {}).get("full_name", "")[:2] + "***")
    return Response(report_generator.candidate_html(r, ex), mimetype="text/html")


@bp.get("/audit")
def audit_get():
    return jsonify({"success": True, "entries": audit.get(), "verify": audit.verify()})


@bp.get("/audit/export")
def audit_exp():
    import json
    return Response(json.dumps(audit.export_json(), ensure_ascii=False, indent=1), mimetype="application/json",
                    headers={"Content-Disposition": "attachment; filename=audit_claverats.json"})


@bp.post("/backup")
def backup():
    return jsonify({"success": True, "name": data_manager.backup()})


@bp.get("/backups")
def backups():
    return jsonify({"success": True, "items": data_manager.list_backups()})


@bp.post("/restore")
def restore():
    try:
        return jsonify({"success": True, "restored": data_manager.restore(_j().get("name", ""))})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400


@bp.post("/purge")
def purge():
    d = _j()
    if d.get("panic"):
        data_manager.purge()
        return jsonify({"success": True, "message": "Toutes les donnees locales ont ete effacees."})
    n = data_manager.purge(int(d.get("days", 30)))
    audit.log("purge", "days=%s n=%s" % (d.get("days"), n))
    return jsonify({"success": True, "removed": n})


@bp.post("/pin/set")
def pin_set():
    pin = str(_j().get("pin", ""))
    if not (4 <= len(pin) <= 12):
        return jsonify({"success": False, "message": "Le PIN doit contenir 4 a 12 caracteres."}), 400
    sec.set_pin(pin)
    return jsonify({"success": True})


@bp.post("/pin/check")
def pin_check():
    if sec.rate_limited("pin:" + (request.remote_addr or ""), limit=8, window=60):
        return jsonify({"success": False, "message": "Trop d'essais."}), 429
    return jsonify({"success": sec.check_pin(str(_j().get("pin", ""))), "has_pin": sec.has_pin()})


@bp.post("/orgs/record")
def org_rec():
    return jsonify({"success": True, "result": orgs.record(_j().get("job_details") or {})})


@bp.get("/orgs")
def org_list():
    return jsonify({"success": True, "items": orgs.overview()})


# --- referentiels de competences (JSON editable) -----------------------------------------------
from . import skills_referential as _sr  # noqa: E402


@bp.get("/referentials")
def ref_list():
    return jsonify({"success": True, "sectors": _sr.overview(), "path": "data/config/skills_referentials.json"})


@bp.post("/referentials/skill")
def ref_skill():
    d = _j()
    try:
        _sr.upsert_skill(d.get("sector", ""), d.get("role", ""), d.get("name", ""), d.get("weight", 2), d.get("aliases") or [], d.get("old_name"))
    except ValueError as e:
        return jsonify({"success": False, "message": str(e)}), 400
    audit.log("referential_skill", "%s/%s" % (d.get("sector"), d.get("role")))
    return jsonify({"success": True})


@bp.post("/referentials/skill/delete")
def ref_skill_del():
    d = _j()
    try:
        _sr.delete_skill(d.get("sector", ""), d.get("role", ""), d.get("name", ""))
    except ValueError as e:
        return jsonify({"success": False, "message": str(e)}), 400
    audit.log("referential_skill_delete", "%s/%s" % (d.get("sector"), d.get("role")))
    return jsonify({"success": True})


@bp.post("/referentials/role")
def ref_role():
    d = _j()
    try:
        key = _sr.add_role(d.get("sector", ""), d.get("key", ""), d.get("label", ""), d.get("keywords") or [])
    except ValueError as e:
        return jsonify({"success": False, "message": str(e)}), 400
    return jsonify({"success": True, "role": key})


@bp.post("/referentials/reset")
def ref_reset():
    _sr.reset_defaults()
    audit.log("referential_reset")
    return jsonify({"success": True})


@bp.post("/referentials/detect")
def ref_detect():
    d = _j()
    info = _sr.detect_role(d.get("text", ""), d.get("title", ""))
    reqs = _sr.build_requirements(d.get("text", ""), d.get("skills") or [], info)
    return jsonify({"success": True, "role": info, "required": reqs["required"], "estimated_count": reqs["estimated_count"]})


# ---- Carte du monde créée en interne (remplace tools/fetch_world.py) ----
from . import world_data as _wd


@bp.get("/world/status")
def world_status():
    if not os.environ.get("CLAVERATS_NO_NET"):
        _wd.auto_fetch_async()
    return jsonify({"success": True, **_wd.status()})


@bp.post("/world/fetch")
def world_fetch():
    r = _wd.fetch()
    audit.log("world_fetch", {"ok": r.get("ok")})
    return jsonify({"success": bool(r.get("ok")), **r}), (200 if r.get("ok") else 502)


@bp.post("/history/clear")
def history_clear():
    n = hist.clear_all()
    audit.log("history_clear", {"count": n})
    return jsonify({"success": True, "deleted": n})


from . import career_progression as _cp


@bp.post("/career/progression")
def career_progression():
    d = _j()
    r = d.get("report") or {}
    cv = r.get("cv_details", {}) or {}
    mt, ms = len(r.get("matched_skills", [])), len(r.get("missing_skills", []))
    ratio = (mt / (mt + ms)) if (mt + ms) else None
    out = _cp.project(r.get("raw_cv_text", ""), cv.get("exp_years", 0), cv.get("education_rank", 0), ratio, cv.get("main_profession", ""))
    return jsonify({"success": True, **out})


from . import hr_alerts as _hra


@bp.post("/hr/alerts")
def hr_alerts_route():
    return jsonify({"success": True, **_hra.build(_j().get("report") or {})})


from . import ocr_engine as _ocr


@bp.get("/vision/status")
def vision_status():
    return jsonify({"success": True, **_ocr.diagnostics()})


# ---- Espace personnel / fiche 360 / export-import des donnees -------------------------------------
from . import personal_hub as _ph, candidate360 as _c360
import io as _io, json as _json, time as _time, zipfile as _zf


@bp.get("/personal/goals")
def personal_goals():
    return jsonify({"success": True, "goals": _ph.list_goals()})


def _personal(fn):
    try:
        return jsonify({"success": True, **fn()})
    except ValueError as e:
        return jsonify({"success": False, "message": str(e)}), 400


@bp.post("/personal/goals")
def personal_goal_add():
    return _personal(lambda: {"goal": _ph.add_goal(_j())})


@bp.post("/personal/goals/update")
def personal_goal_update():
    d = _j()
    return _personal(lambda: {"goal": _ph.update_goal(d.get("id", ""), d)})


@bp.post("/personal/goals/delete")
def personal_goal_delete():
    return jsonify({"success": True, "deleted": _ph.delete_goal(_j().get("id", ""))})


@bp.post("/personal/learning-plan")
def personal_plan():
    d = _j()
    r = d.get("report") or {}
    weights = (r.get("job_details") or {}).get("skill_weights") or {}
    return jsonify({"success": True, **_ph.learning_plan(r.get("missing_skills") or [], weights, d.get("hours_per_week", 5))})


@bp.post("/hr/candidate360")
def hr_candidate360():
    d = _j()
    cands = (d.get("report") or {}).get("candidates") or []
    i = int(d.get("index", 0))
    if not (0 <= i < len(cands)):
        return jsonify({"success": False, "message": "Candidat introuvable."}), 400
    return jsonify({"success": True, "sheet": _c360.sheet(cands[i], len(cands))})


@bp.post("/hr/compare")
def hr_compare():
    d = _j()
    cands = (d.get("report") or {}).get("candidates") or []
    try:
        a, b = cands[int(d.get("a"))], cands[int(d.get("b"))]
    except (TypeError, ValueError, IndexError):
        return jsonify({"success": False, "message": "Choisissez deux candidats valides."}), 400
    return jsonify({"success": True, **_c360.compare(a, b)})


@bp.get("/data/export")
def data_export():
    """Archive .zip de tout le dossier data/store (+ config) : à garder ou à réimporter sur un autre poste."""
    import os
    buf = _io.BytesIO()
    with _zf.ZipFile(buf, "w", _zf.ZIP_DEFLATED) as z:
        for sub in ("store", "config"):
            root = os.path.join(_core.DATA_DIR, sub)
            for dp, _, fs in os.walk(root):
                for f in fs:
                    if f.endswith((".json", ".bak")):
                        full = os.path.join(dp, f)
                        z.write(full, os.path.relpath(full, _core.DATA_DIR))
    audit.log("data_export")
    return Response(buf.getvalue(), mimetype="application/zip", headers={"Content-Disposition": "attachment; filename=claverats_donnees_%s.zip" % _time.strftime("%Y%m%d")})


@bp.post("/data/import")
def data_import():
    """Réimporte une archive exportée. Sauvegarde automatique avant, validation stricte des noms et du JSON."""
    import os
    f = request.files.get("archive")
    if not f:
        return jsonify({"success": False, "message": "Aucun fichier reçu."}), 400
    raw = f.read(40 * 1024 * 1024 + 1)
    if len(raw) > 40 * 1024 * 1024:
        return jsonify({"success": False, "message": "Archive trop volumineuse."}), 400
    try:
        z = _zf.ZipFile(_io.BytesIO(raw))
    except _zf.BadZipFile:
        return jsonify({"success": False, "message": "Ce fichier n'est pas une archive valide."}), 400
    plan = []
    for info in z.infolist():
        n = info.filename.replace("\\", "/")
        if info.is_dir():
            continue
        if n.startswith("/") or ".." in n.split("/") or n.split("/")[0] not in ("store", "config") or not n.endswith((".json", ".bak")) or info.file_size > 20 * 1024 * 1024:
            return jsonify({"success": False, "message": "Archive refusée : contenu inattendu (%s)." % n[:60]}), 400
        try:
            _json.loads(z.read(info).decode("utf-8"))
        except Exception:
            if not n.endswith(".bak"):
                return jsonify({"success": False, "message": "Fichier JSON invalide dans l'archive : %s" % n[:60]}), 400
        plan.append((n, info))
    _core.make_backup()
    for n, info in plan:
        dest = os.path.join(_core.DATA_DIR, *n.split("/"))
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "wb") as out:
            out.write(z.read(info))
    audit.log("data_import", {"files": len(plan)})
    return jsonify({"success": True, "restored": len(plan)})
