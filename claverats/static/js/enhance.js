/* CLAVERATS Pro v2.2 - couche d'amelioration (chargee apres main.js). 100 % local : fetch same-origin, localStorage, aucun service externe. */
(function () {
    "use strict";
    const $ = (id) => document.getElementById(id);
    const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
    const clone = (o) => JSON.parse(JSON.stringify(o == null ? null : o));
    const LS_CAND = "claverats_last_candidate", LS_HR = "claverats_last_hr", LS_HIST = "claverats_history_5";
    window.CE = { esc: esc, clone: clone };

    /* ---------- 1. CSRF : jeton ajoute automatiquement a tout POST /api/ ---------- */
    const _fetch = window.fetch.bind(window);
    let _tok = null;
    async function getTok(force) {
        if (_tok && !force) return _tok;
        const r = await _fetch("/api/svc/csrf");
        _tok = (await r.json()).token;
        return _tok;
    }
    window.fetch = async function (input, init) {
        init = init || {};
        const url = typeof input === "string" ? input : (input && input.url) || "";
        const isPost = String(init.method || "GET").toUpperCase() === "POST";
        if (!(isPost && url.indexOf("/api/") === 0)) return _fetch(input, init);
        for (let i = 0; i < 2; i++) {
            const h = new Headers(init.headers || {});
            h.set("X-CSRF-Token", await getTok(i === 1));
            const res = await _fetch(input, Object.assign({}, init, { headers: h }));
            if (res.status !== 403 || i === 1) return res;
        }
    };
    window.svc = async function (path, body) {
        const r = await fetch("/api/svc/" + path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) });
        return r.json();
    };
    window.svcGet = async function (path) { return (await _fetch("/api/svc/" + path)).json(); };

    /* ---------- 2. Icones SVG integrees (aucune dependance de police) ---------- */
    const P = {
        phone: "M6.6 10.8a15 15 0 0 0 6.6 6.6l2.2-2.2a1 1 0 0 1 1-.25 11 11 0 0 0 3.6.6 1 1 0 0 1 1 1V20a1 1 0 0 1-1 1A17 17 0 0 1 3 4a1 1 0 0 1 1-1h3.5a1 1 0 0 1 1 1c0 1.25.2 2.45.6 3.6a1 1 0 0 1-.25 1z",
        mail: "M4 5h16a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2zm0 2v.5l8 5 8-5V7zm16 10V10l-8 5-8-5v7z",
        linkedin: "M4.98 3.5a2.5 2.5 0 1 1 0 5 2.5 2.5 0 0 1 0-5zM3 9.5h4V21H3zM9.5 9.5h3.8v1.6h.05c.55-1 1.9-1.95 3.9-1.95 4.1 0 4.75 2.7 4.75 6.2V21h-4v-5c0-1.2 0-2.7-1.65-2.7S13.5 14.6 13.5 16v5h-4z",
        github: "M12 2a10 10 0 0 0-3.16 19.49c.5.09.68-.22.68-.48v-1.7c-2.78.6-3.37-1.34-3.37-1.34-.45-1.16-1.11-1.47-1.11-1.47-.9-.62.07-.6.07-.6 1 .07 1.53 1.03 1.53 1.03.89 1.52 2.34 1.08 2.9.83.09-.64.35-1.08.63-1.33-2.22-.25-4.55-1.11-4.55-4.94 0-1.09.39-1.98 1.03-2.68-.1-.25-.45-1.27.1-2.64 0 0 .84-.27 2.75 1.02a9.5 9.5 0 0 1 5 0c1.9-1.29 2.74-1.02 2.74-1.02.55 1.37.2 2.39.1 2.64.64.7 1.03 1.59 1.03 2.68 0 3.84-2.34 4.69-4.57 4.93.36.31.68.92.68 1.85v2.74c0 .27.18.58.69.48A10 10 0 0 0 12 2z",
        globe: "M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zm6.9 9h-3a15 15 0 0 0-1.2-5.2A8 8 0 0 1 18.9 11zM12 4c.9 1.2 1.6 3.1 1.9 5h-3.8c.3-1.9 1-3.8 1.9-5zM4.3 13h3a15 15 0 0 0 1.2 5.2A8 8 0 0 1 4.3 13zm3-2h-3a8 8 0 0 1 4.2-5.2A15 15 0 0 0 7.3 11zM12 20c-.9-1.2-1.6-3.1-1.9-5h3.8c-.3 1.9-1 3.8-1.9 5zm2.1-7H9.9a13 13 0 0 1 0-2h4.2a13 13 0 0 1 0 2zm.4 5.2a15 15 0 0 0 1.2-5.2h3a8 8 0 0 1-4.2 5.2z",
        wa: "M12 2a10 10 0 0 0-8.6 15.1L2 22l5-1.3A10 10 0 1 0 12 2zm5.2 14.1c-.2.6-1.3 1.2-1.8 1.2-.5.1-1 .2-3.3-.7a11 11 0 0 1-4.6-4c-.4-.5-1.1-1.5-1.1-2.8s.7-2 1-2.3a1 1 0 0 1 .7-.3h.5c.2 0 .4 0 .6.5l.8 1.9c.1.2.1.4 0 .6l-.4.6c-.1.2-.3.3-.1.6a6 6 0 0 0 2.9 2.4c.3.1.4.1.6-.1l.8-1c.2-.2.4-.2.6-.1l1.9.9c.3.1.5.2.5.3.1.2.1.7-.1 1.3z"
    };
    function ico(name) { return '<svg class="ce-ico" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="' + P[name] + '"/></svg>'; }
    function safeUrl(u) { return /^https?:\/\//i.test(u) ? u : "#"; }
    function shortUrl(u) { return String(u).replace(/^https?:\/\/(www\.)?/i, "").replace(/\/$/, ""); }
    function contactIcons(c) {
        const phones = (c.phones && c.phones.length ? c.phones : (c.phone ? [c.phone] : [])).map((p) => String(p).split("[")[0].trim()).filter(Boolean);
        const emails = c.emails && c.emails.length ? c.emails : (c.email ? [c.email] : []);
        const links = (c.links_detail && c.links_detail.length) ? c.links_detail : (c.links || []).map((u) => ({ url: u, type: /linkedin/i.test(u) ? "linkedin" : /github/i.test(u) ? "github" : "portfolio" }));
        const chips = [];
        phones.forEach((p) => {
            const d = p.replace(/\D/g, "");
            chips.push('<a class="contact-chip" href="tel:' + esc(p.replace(/[^\d+]/g, "")) + '">' + ico("phone") + "<span>" + esc(p) + "</span></a>");
            if (d.length >= 9) chips.push('<a class="contact-chip" target="_blank" rel="noopener noreferrer" href="https://wa.me/' + d + '" title="WhatsApp">' + ico("wa") + "<span>WhatsApp</span></a>");
        });
        emails.forEach((e) => chips.push('<a class="contact-chip" href="mailto:' + esc(e) + '">' + ico("mail") + "<span>" + esc(e) + "</span></a>"));
        links.forEach((l) => {
            const t = l.type === "linkedin" ? "linkedin" : l.type === "github" ? "github" : "globe";
            const lab = l.type === "linkedin" ? "LinkedIn" : l.type === "github" ? "GitHub" : (l.type === "portfolio" ? "Portfolio" : "Lien");
            chips.push('<a class="contact-chip" target="_blank" rel="noopener noreferrer" href="' + esc(safeUrl(l.url)) + '" title="' + esc(l.url) + '">' + ico(t) + "<span>" + lab + " · " + esc(shortUrl(l.url)) + "</span></a>");
        });
        if (!chips.length) return '<div class="contact-row"><span class="contact-chip is-muted">Aucun contact détecté</span></div>';
        return '<div class="contact-row">' + chips.join("") + "</div>";
    }
    window.CE.contactIcons = contactIcons;

    /* ---------- 3. Modele d'edition : valeurs PDF d'origine, champs modifies ---------- */
    const CAND_LABELS = { full_name: "Nom", main_profession: "Profession", location: "Localisation", exp_years: "Années d'expérience", education_label: "Diplôme", languages: "Langues", skills: "Compétences", experiences: "Expériences" };
    function snapCand(r) {
        const cv = r.cv_details || {};
        return { full_name: cv.full_name, main_profession: cv.main_profession, location: cv.location, exp_years: cv.exp_years, education_label: cv.education_label,
            languages: clone(cv.languages || []), skills: { matched: clone(r.matched_skills || []), missing: clone(r.missing_skills || []), bonus: clone(r.bonus_skills || []) },
            experiences: clone(cv.structured_experiences || []) };
    }
    function diffCand(cur, orig) {
        const out = {};
        Object.keys(CAND_LABELS).forEach((k) => { if (orig && JSON.stringify(cur[k]) !== JSON.stringify(orig[k])) out[k] = true; });
        if (orig && JSON.stringify((cur.skills || {}).matched) === JSON.stringify((orig.skills || {}).matched)) delete out.skills;
        return out;
    }
    const HR_LABELS = { name: "Nom", main_profession: "Profession", exp_years: "Expérience", location: "Localisation", phone: "Téléphone", email: "E-mail", education: "Diplôme", languages: "Langues", matched_skills: "Compétences", structured_experiences: "Expériences" };
    function snapHr(c) { const o = {}; Object.keys(HR_LABELS).forEach((k) => { o[k] = clone(c[k]); }); return o; }
    function diffHr(c, orig) { const out = {}; Object.keys(HR_LABELS).forEach((k) => { if (orig && JSON.stringify(c[k]) !== JSON.stringify(orig[k])) out[k] = true; }); return out; }

    function scoreBanner(initial, now) {
        if (initial == null) return "";
        const d = now - initial, cls = d > 0 ? "up" : d < 0 ? "down" : "same";
        const txt = d > 0 ? "+" + d + " pts grâce à vos corrections" : d < 0 ? "" + d + " pts après corrections" : "Score inchangé";
        return '<div class="score-compare"><span>Score initial (PDF)</span><span class="sc">' + initial + '%</span><span>→</span><span>Score corrigé</span><span class="sc">' + now + '%</span><span class="delta ' + cls + '">' + txt + "</span></div>";
    }

    /* ---------- 4. Blocs d'experience (Societe + duree exacte + Poste) ---------- */
    function expBlocks(exps, dark) {
        if (!exps || !exps.length) return '<p class="muted-small">Aucune expérience structurée détectée.</p>';
        return '<ul class="info-list" style="padding:0;margin:0">' + exps.map((e) =>
            '<li class="exp-block' + (dark ? " dark" : "") + '"><div class="exp-head"><span class="exp-company"><i class=\"ion-folder\"></i> ' + esc(e.company || e.employer || "Société non précisée") + '</span><span class="exp-dur">⏱ ' + esc(e.duration_label || "Durée non déterminée") + "</span></div>" +
            '<div class="exp-role"><i class=\"ion-person\"></i> ' + esc(e.role || "Poste non précisé") + '</div><div class="exp-period">' + esc(e.period || "") + "</div>" +
            (e.tasks && e.tasks.length ? '<div class="exp-tasks">' + esc(e.tasks.slice(0, 3).join(" • ")) + "</div>" : "") + "</li>").join("") + "</ul>";
    }
    window.CE.expBlocks = expBlocks;
    function expEditor(prefix, exps) {
        const rows = (exps || []).map((e, i) =>
            '<div class="exp-edit" data-i="' + i + '"><div class="field-box"><label>Société</label><input type="text" class="x-co" value="' + esc(e.company || e.employer || "") + '"></div>' +
            '<div class="field-box"><label>Durée / période exacte</label><input type="text" class="x-pe" value="' + esc(e.period || "") + '" placeholder="Mars 2020 - Juin 2022"></div>' +
            '<div class="field-box"><label>Poste</label><input type="text" class="x-ro" value="' + esc(e.role || "") + '"></div>' +
            '<button type="button" class="mini-btn danger" onclick="CE.removeExp(\'' + prefix + "'," + i + ')"><i class=\"ion-close-round\"></i></button>' +
            '<div class="exp-dur-live">⏱ ' + esc(e.duration_label || "-") + "</div></div>").join("");
        return '<div id="' + prefix + '_exp_root"><div class="soft-divider"><span>EXPÉRIENCES : SOCIÉTÉ • DURÉE • POSTE</span></div>' + rows +
            '<button type="button" class="mini-btn" onclick="CE.addExp(\'' + prefix + '\')">+ Ajouter une expérience</button></div>';
    }
    function readExp(prefix, previous) {
        const root = $(prefix + "_exp_root");
        if (!root) return null;
        return Array.prototype.map.call(root.querySelectorAll(".exp-edit"), (row) => {
            const i = parseInt(row.dataset.i, 10), old = (previous && previous[i]) || {};
            const co = row.querySelector(".x-co").value.trim(), pe = row.querySelector(".x-pe").value.trim(), ro = row.querySelector(".x-ro").value.trim();
            return Object.assign({}, old, { company: co, employer: co, period: pe, role: ro, tasks: old.tasks || [] });
        }).filter((e) => e.company || e.role || e.period);
    }
    async function withDurations(exps) {
        if (!exps) return null;
        const r = await svc("durations", { experiences: exps });
        return r.success ? r : null;
    }
    CE.addExp = function (prefix) {
        const cur = readExp(prefix, prefix === "cand" ? lastReport.cv_details.structured_experiences : null) || [];
        cur.push({ company: "", employer: "", period: "", role: "", tasks: [] });
        const root = $(prefix + "_exp_root");
        root.outerHTML = expEditor(prefix, cur);
    };
    CE.removeExp = function (prefix, i) {
        const cur = readExp(prefix, prefix === "cand" ? lastReport.cv_details.structured_experiences : (lastHrReport.candidates[editingHrCandidateIdx] || {}).structured_experiences) || [];
        cur.splice(i, 1);
        $(prefix + "_exp_root").outerHTML = expEditor(prefix, cur);
    };

    /* ---------- 5. Persistance locale (candidat) ---------- */
    function persistCandidate() {
        if (typeof lastReport === "undefined" || !lastReport) return;
        try {
            localStorage.setItem(LS_CAND, JSON.stringify(lastReport));
            const list = JSON.parse(localStorage.getItem(LS_HIST) || "[]");
            const nm = (lastReport.cv_details || {}).full_name, co = (lastReport.job_details || {}).company_name;
            const upd = list.map((x) => (x.name === nm && x.company === co ? Object.assign({}, x, { score: lastReport.score, report: lastReport }) : x));
            localStorage.setItem(LS_HIST, JSON.stringify(upd));
        } catch (e) { /* quota : on ignore, l'application reste fonctionnelle */ }
        svc("history/record", { report: lastReport, label: Object.keys(lastReport.manual_edits || {}).length ? "edition" : "analyse" }).catch(() => {});
    }
    window.CE.persistCandidate = persistCandidate;

    const _origRenderAll = renderAllViews;
    renderAllViews = function (data) {
        if (data && data.success && !data.pdf_original) data.pdf_original = snapCand(data);
        _origRenderAll(data);
        decorateProfile(data);
    };

    function decorateProfile(data) {
        if (!data || !data.cv_details) return;
        const cv = data.cv_details;
        /* blocs d'experience + indicateurs */
        const ul = $("structured_exp_list");
        if (ul) {
            const ea = cv.experience_analysis || {};
            const chips = ea.total_label ? '<div class="contact-row"><span class="tag ok">Total : ' + esc(ea.total_label) + '</span><span class="tag">Stabilité : ' + esc(ea.stability || "-") + '</span><span class="tag' + (ea.gaps ? " warn" : "") + '">Trous : ' + (ea.gaps || 0) + '</span><span class="tag">Cohérence : ' + (ea.consistency == null ? "-" : ea.consistency + "%") + "</span></div>" : "";
            ul.outerHTML = '<div id="structured_exp_list">' + chips + expBlocks(cv.structured_experiences) + "</div>";
            const holder = $("structured_exp_list");
            if (holder && !$("cand_exp_root")) holder.insertAdjacentHTML("afterend", expEditor("cand", cv.structured_experiences));
            else if ($("cand_exp_root")) $("cand_exp_root").outerHTML = expEditor("cand", cv.structured_experiences);
        }
        /* coordonnees avec icones */
        let box = $("cand_contact_box");
        const sum = $("profile_summary_list");
        if (!box) {
            box = document.createElement("div"); box.id = "cand_contact_box"; box.style.marginBottom = "12px";
            const anchor = $("structured_exp_list");
            if (anchor) anchor.parentNode.insertBefore(box, anchor.previousElementSibling || anchor);
        }
        box.innerHTML = '<div class="soft-divider"><span>COORDONNÉES & LIENS DÉTECTÉS</span></div>' + contactIcons(cv);
        if (sum && sum.lastElementChild) sum.lastElementChild.innerHTML = "<strong>Coordonnées & liens</strong>" + contactIcons(cv);
        window._skillsInitial = JSON.stringify(collectCategorizedSkills("edit_cat"));
        renderEditBar();
    }

    function renderEditBar() {
        const tab = $("tab-profile");
        if (!tab || typeof lastReport === "undefined" || !lastReport) return;
        let bar = $("edit_status_bar");
        if (!bar) { bar = document.createElement("div"); bar.id = "edit_status_bar"; tab.insertBefore(bar, tab.firstChild); }
        const edits = Object.keys(lastReport.manual_edits || {});
        const initial = lastReport.initial_score != null ? lastReport.initial_score : lastReport.score;
        bar.className = "edit-bar";
        bar.innerHTML = scoreBanner(initial, lastReport.score) +
            (edits.length ? '<div style="margin-top:6px">' + edits.map((k) => '<span class="edited-badge"><i class=\"ion-edit\"></i> Édité manuellement : ' + esc(CAND_LABELS[k] || k) + ' <button type="button" onclick="CE.restoreCand(\'' + k + '\')">Rétablir la valeur du PDF</button></span>').join("") +
                ' <button type="button" class="mini-btn" onclick="CE.restoreCand(\'*\')">Tout rétablir</button></div>' : '<p class="muted-small" style="margin:6px 0 0">Aucune modification manuelle : valeurs lues dans le PDF.</p>');
    }
    window.CE.renderEditBar = renderEditBar;

    async function recomputeCand() {
        const res = await fetch("/api/recalculate", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(lastReport) });
        const upd = await res.json();
        if (!upd.success) return false;
        lastReport = upd;
        lastReport.manual_edits = diffCand(snapCand(lastReport), lastReport.pdf_original);
        renderAllViews(lastReport);
        persistCandidate();
        return true;
    }
    CE.restoreCand = async function (key) {
        const o = lastReport.pdf_original;
        if (!o) return;
        const cv = lastReport.cv_details, keys = key === "*" ? Object.keys(CAND_LABELS) : [key];
        keys.forEach((k) => {
            if (k === "skills") { lastReport.matched_skills = clone(o.skills.matched); lastReport.missing_skills = clone(o.skills.missing); lastReport.bonus_skills = clone(o.skills.bonus); }
            else if (k === "experiences") cv.structured_experiences = clone(o.experiences);
            else cv[k] = clone(o[k]);
        });
        if (await recomputeCand()) showToast("Valeur du PDF rétablie.");
    };

    /* Ecrit les 4 champs de competences saisis dans l'objet categorise : evite que l'affichage "revienne" a l'ancienne valeur */
    function syncCategorized(prefix, holder) {
        const arr = (id) => ($(id) ? $(id).value : "").split(",").map((x) => x.trim()).filter(Boolean);
        const c = holder.categorized_skills = holder.categorized_skills || {};
        ["Langages de Programmation", "Logiciels & Outils", "Compétences Métiers & Techniques", "Certifications & Formations", "Attitudes & Savoir-être"].forEach((k) => { delete c[k]; });
        c.prog_langs = arr(prefix + "_prog"); c.software_tools = arr(prefix + "_tools");
        c.domain_skills = arr(prefix + "_domain"); c.certifications = []; c.attitudes = arr(prefix + "_soft");
    }

    const _origRecalc = recalculateReport;
    recalculateReport = async function () {
        if (!lastReport) return;
        const orig = lastReport.pdf_original || snapCand(lastReport);
        const exps = readExp("cand", lastReport.cv_details.structured_experiences);
        if (exps) {
            const d = await withDurations(exps);
            lastReport.cv_details.structured_experiences = d ? d.experiences : exps;
            if (d) lastReport.cv_details.experience_analysis = Object.assign({}, lastReport.cv_details.experience_analysis, { total_label: d.total_label, stability: d.stability, gaps: d.gaps, overlaps: d.overlaps, consistency: d.consistency, avg_months: d.avg_months, total_months: d.total_months });
        }
        lastReport.pdf_original = orig;
        /* competences non touchees : on ne laisse pas l'ancien code les recalculer depuis les champs (evite les derives de score) */
        const keep = collectCategorizedSkills;
        if (JSON.stringify(keep("edit_cat")) === window._skillsInitial) collectCategorizedSkills = function (p) { return p === "edit_cat" ? [] : keep(p); };
        else syncCategorized("edit_cat", lastReport.cv_details);
        try { await _origRecalc(); } finally { collectCategorizedSkills = keep; }
        if (!lastReport) return;
        lastReport.pdf_original = orig;
        lastReport.manual_edits = diffCand(snapCand(lastReport), orig);
        decorateProfile(lastReport);
        persistCandidate();
    };

    /* ---------- 6. Persistance & edition cote RH ---------- */
    let hrTimer = null;
    function persistHr() {
        if (typeof lastHrReport === "undefined" || !lastHrReport) return;
        const make = (light) => JSON.stringify(Object.assign({}, lastHrReport, { saved_at: Date.now(), active: activeHrDetailIdx, candidates: (lastHrReport.candidates || []).map((c) => {
            const k = Object.assign({}, c); delete k.pdf_url; if (light) { delete k.photo; delete k.raw_text; } return k; }) }));
        try { localStorage.setItem(LS_HR, make(false)); } catch (e) { try { localStorage.setItem(LS_HR, make(true)); } catch (e2) { /* trop volumineux */ } }
    }
    window.CE.persistHr = persistHr;
    const _origRefreshHr = refreshHrDashboardMetrics;
    refreshHrDashboardMetrics = function () {
        _origRefreshHr.apply(this, arguments);
        clearTimeout(hrTimer); hrTimer = setTimeout(persistHr, 250);
    };

    function hrDisplayed() {
        const list = lastHrReport.candidates.map((c, i) => ({ c: c, i: i })).filter((x) => x.c.score >= 45);
        if (!list.length) return null;
        const cur = lastHrReport.candidates[activeHrDetailIdx];
        return (cur && cur.score >= 45) ? { c: cur, i: activeHrDetailIdx } : list[0];
    }
    async function hrRecalc(cand) {
        const res = await fetch("/api/hr-recalculate-candidate", { method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ candidate: cand, job_details: lastHrReport.job_details || {}, job_skills: lastHrReport.job_skills || [], tech_weight: lastHrReport.tech_weight || 60 }) });
        const d = await res.json();
        return d.success ? d.candidate : null;
    }
    CE.restoreHr = async function (idx, key) {
        const cand = lastHrReport.candidates[idx];
        if (!cand || !cand.pdf_original) return;
        (key === "*" ? Object.keys(HR_LABELS) : [key]).forEach((k) => { cand[k] = clone(cand.pdf_original[k]); });
        const upd = await hrRecalc(cand);
        if (!upd) return;
        upd.manual_edits = diffHr(upd, upd.pdf_original);
        lastHrReport.candidates[idx] = upd;
        lastHrReport.candidates.sort(rankCmp);
        lastHrReport.candidates.forEach((c, i) => { c.rank = i + 1; });
        activeHrDetailIdx = Math.max(0, lastHrReport.candidates.indexOf(upd));
        refreshHrDashboardMetrics();
        showToast("Valeur du PDF rétablie pour " + upd.name + ".");
    };

    const _origOpenHr = openHrManualEditor;
    openHrManualEditor = function (idx) {
        _origOpenHr(idx);
        const cand = lastHrReport && lastHrReport.candidates && lastHrReport.candidates[idx];
        if (!cand) return;
        if (!cand.pdf_original) cand.pdf_original = snapHr(cand);
        const card = $("hr_manual_editor_card");
        const old = $("hr_exp_root");
        if (old) old.remove();
        const firstDivider = card.querySelector(".soft-divider");
        if (firstDivider) firstDivider.insertAdjacentHTML("beforebegin", expEditor("hr", cand.structured_experiences));
        const root = $("hr_exp_root");
        if (root) root.style.marginBottom = "12px";
        window._hrSkillsInitial = JSON.stringify(collectCategorizedSkills("hr_ed_cat"));
    };

    const _origSaveHr = saveHrManualCandidateEdit;
    saveHrManualCandidateEdit = async function () {
        if (!lastHrReport || editingHrCandidateIdx == null) return;
        const cand = lastHrReport.candidates[editingHrCandidateIdx];
        if (!cand) return;
        if (!cand.pdf_original) cand.pdf_original = snapHr(cand);
        const key = cand.sha256 || cand.filename;
        const exps = readExp("hr", cand.structured_experiences);
        if (exps) {
            const d = await withDurations(exps);
            cand.structured_experiences = d ? d.experiences : exps;
            if (d) cand.experience_analysis = Object.assign({}, cand.experience_analysis, { total_label: d.total_label, stability: d.stability, gaps: d.gaps, consistency: d.consistency });
        }
        const keepC = collectCategorizedSkills;
        if (JSON.stringify(keepC("hr_ed_cat")) === window._hrSkillsInitial) { const base = clone((cand.matched_skills || []).concat(cand.bonus_skills || [])); collectCategorizedSkills = function (p) { return p === "hr_ed_cat" ? base : keepC(p); }; }
        else syncCategorized("hr_ed_cat", cand);
        try { await _origSaveHr(); } finally { collectCategorizedSkills = keepC; }
        const upd = lastHrReport.candidates.find((c) => c.pdf_original && (c.sha256 || c.filename) === key);
        if (upd) { upd.manual_edits = diffHr(upd, upd.pdf_original); refreshHrDashboardMetrics(); }
    };

    const _origTable = renderHrTableAndMaster;
    renderHrTableAndMaster = function () {
        _origTable.apply(this, arguments);
        const tb = $("hr_table_body");
        if (!tb || !lastHrReport) return;
        tb.querySelectorAll("tr").forEach((tr) => {
            const m = /selectHrDetailCandidate\((\d+)\)/.exec(tr.getAttribute("onclick") || "");
            if (!m) return;
            const c = lastHrReport.candidates[parseInt(m[1], 10)];
            if (!c) return;
            const tds = tr.children;
            if (tds[2] && c.rank_reason && !tds[2].querySelector(".tie-badge")) {
                const st = tds[2].querySelector("strong");
                if (st) st.insertAdjacentHTML("afterend", '<span class="tie-badge" title="' + esc(c.rank_reason) + '">' + (c.tie ? "Départagé" : "#" + c.rank) + "</span>");
            }
            if (tds[2] && c.manual_edits && Object.keys(c.manual_edits).length) tds[2].querySelector("strong").insertAdjacentHTML("afterend", '<span class="edited-tag"><i class=\"ion-edit\"></i> Édité manuellement</span>');
            if (tds[3] && c.experience_analysis && c.experience_analysis.total_label) tds[3].insertAdjacentHTML("beforeend", '<div class="muted-small">Cumul : ' + esc(c.experience_analysis.total_label) + "</div>");
            if (tds[5]) tds[5].innerHTML = contactIcons(c);
        });
    };

    const _origMaster = renderHrMasterDetail;
    renderHrMasterDetail = function () {
        _origMaster.apply(this, arguments);
        const pane = $("hr_dark_detail_pane");
        if (!pane || !lastHrReport || !lastHrReport.candidates || !lastHrReport.candidates.length) return;
        const d = hrDisplayed();
        if (!d || !pane.firstElementChild) return;
        const c = d.c, edits = Object.keys(c.manual_edits || {});
        const html = '<div class="edit-bar dark" style="margin-bottom:10px">' + scoreBanner(c.initial_score, c.score) +
            (edits.length ? '<div>' + edits.map((k) => '<span class="edited-badge"><i class=\"ion-edit\"></i> Édité manuellement : ' + esc(HR_LABELS[k] || k) + ' <button type="button" onclick="CE.restoreHr(' + d.i + ",'" + k + '\')">Rétablir la valeur du PDF</button></span>').join("") + "</div>" : "") +
            "</div>" + contactIcons(c) +
            ((c.pdf_warnings || []).length ? '<p style="font-size:.76rem;color:#FCD34D"><i class=\"ion-information-circled\"></i> ' + esc(c.pdf_warnings.join(" ")) + "</p>" : "") +
            (c.doc_trust ? '<p style="font-size:.76rem;color:#9CA3AF">Confiance du document : <b>' + esc(c.doc_trust.level) + " (" + c.doc_trust.score + "/100)</b>" + (c.doc_trust.flags.length ? " - " + esc(c.doc_trust.flags.join(" ")) : "") + "</p>" : "") +
            expBlocks(c.structured_experiences, true);
        const host = pane.firstElementChild;
        const old = host.querySelector(".hr-extra");
        if (old) old.remove();
        host.insertAdjacentHTML("beforeend", '<div class="hr-extra" style="margin-top:12px">' + html + "</div>");
    };

    /* bandeau de reprise de la campagne RH */
    function hrResumeBar() {
        const tab = $("tab-hr");
        if (!tab || $("hr_resume_bar")) return;
        let raw = null;
        try { raw = localStorage.getItem(LS_HR); } catch (e) {}
        if (!raw || (typeof lastHrReport !== "undefined" && lastHrReport)) return;
        let p; try { p = JSON.parse(raw); } catch (e) { return; }
        if (!p || !p.candidates || !p.candidates.length) return;
        const bar = document.createElement("div");
        bar.id = "hr_resume_bar"; bar.className = "resume-bar";
        bar.innerHTML = "<span><i class=\"ion-folder\"></i> Campagne précédente : <b>" + p.candidates.length + " candidat(s)</b>" + (p.saved_at ? " • " + new Date(p.saved_at).toLocaleString("fr-FR") : "") + ' <small>(les aperçus PDF ne sont pas conservés)</small></span><span><button class="mini-btn primary" type="button">Reprendre</button> <button class="mini-btn" type="button">Effacer</button></span>';
        tab.insertBefore(bar, tab.firstChild);
        const b = bar.querySelectorAll("button");
        b[0].onclick = function () {
            lastHrReport = p; activeHrDetailIdx = p.active || 0;
            const area = $("hr_results_area"); if (area) area.classList.remove("hidden");
            refreshHrDashboardMetrics(); bar.remove();
        };
        b[1].onclick = function () { try { localStorage.removeItem(LS_HR); } catch (e) {} bar.remove(); };
    }
    hrResumeBar();

    /* ---------- 7. PWA : service worker, banniere de mise a jour, installation ---------- */
    let deferred = null;
    window.installPwa = async function () {
        if (!deferred) return;
        deferred.prompt(); await deferred.userChoice; deferred = null;
        const b = $("btn_pwa_install"); if (b) b.style.display = "none";
    };
    window.addEventListener("beforeinstallprompt", (e) => { e.preventDefault(); deferred = e; const b = $("btn_pwa_install"); if (b) b.style.display = ""; });
    function updateBanner(reg) {
        if ($("pwa_update")) return;
        const d = document.createElement("div");
        d.id = "pwa_update"; d.className = "pwa-banner";
        d.innerHTML = "<span><i class=\"ion-refresh\"></i> Nouvelle version de CLAVERATS disponible.</span><button type='button'>Mettre à jour</button><button type='button' class='x'><i class=\"ion-close-round\"></i></button>";
        document.body.appendChild(d);
        d.children[1].onclick = function () { if (reg.waiting) reg.waiting.postMessage("SKIP_WAITING"); };
        d.children[2].onclick = function () { d.remove(); };
    }
    if ("serviceWorker" in navigator && (location.protocol === "https:" || location.hostname === "localhost" || location.hostname === "127.0.0.1")) {
        let reloading = false;
        navigator.serviceWorker.addEventListener("controllerchange", () => { if (!reloading) { reloading = true; location.reload(); } });
        navigator.serviceWorker.register("/sw.js").then((reg) => {
            if (reg.waiting && navigator.serviceWorker.controller) updateBanner(reg);
            reg.addEventListener("updatefound", () => {
                const nw = reg.installing;
                if (nw) nw.addEventListener("statechange", () => { if (nw.state === "installed" && navigator.serviceWorker.controller) updateBanner(reg); });
            });
            setInterval(() => reg.update().catch(() => {}), 3600 * 1000);
        }).catch(() => {});
    }

    /* barre d'etat locale */
    const strip = document.createElement("div");
    strip.className = "status-strip";
    function paintStrip() { strip.innerHTML = "<i class='" + (navigator.onLine ? "" : "off") + "'></i> " + (navigator.onLine ? "Local • en ligne" : "Hors-ligne • tout fonctionne") + " • v2.2"; }
    window.addEventListener("online", paintStrip); window.addEventListener("offline", paintStrip);
    paintStrip(); document.body.appendChild(strip);

    /* ---------- 8. Verrou PIN + verrouillage automatique ---------- */
    let pinSet = false, idle = null;
    function lockScreen() {
        if ($("lock_ov")) return;
        const o = document.createElement("div");
        o.id = "lock_ov"; o.className = "lock-overlay";
        o.innerHTML = "<h2><i class=\"ion-locked\"></i> CLAVERATS verrouillé</h2><input type='password' id='lock_pin' inputmode='numeric' autocomplete='off' placeholder='••••'><button class='mini-btn primary' type='button'>Déverrouiller</button><small id='lock_msg'></small>";
        document.body.appendChild(o);
        const go = async function () {
            const r = await svc("pin/check", { pin: $("lock_pin").value });
            if (r.success) { o.remove(); armIdle(); } else { $("lock_msg").textContent = r.message || "PIN incorrect."; $("lock_pin").value = ""; }
        };
        o.querySelector("button").onclick = go;
        $("lock_pin").addEventListener("keydown", (e) => { if (e.key === "Enter") go(); });
        $("lock_pin").focus();
    }
    function armIdle() {
        if (!pinSet) return;
        const reset = function () { clearTimeout(idle); idle = setTimeout(lockScreen, 15 * 60 * 1000); };
        ["click", "keydown", "mousemove", "touchstart"].forEach((ev) => document.addEventListener(ev, reset, { passive: true }));
        reset();
    }
    window.CE.lockNow = lockScreen;
    window.CE.setPinState = function (v) { pinSet = v; if (v) armIdle(); };
    svcGet("health").then((h) => { if (h && h.pin) { pinSet = true; lockScreen(); } }).catch(() => {});

    /* applique le decor aux sessions restaurees */
    if (typeof lastReport !== "undefined" && lastReport) decorateProfile(lastReport);
})();

/* ---- Carte du monde créée en interne (remplace "python tools/fetch_world.py") ---- */
(function () {
    async function worldInit() {
        try {
            const r = await fetch("/api/svc/world/status");
            const st = await r.json();
            if (st.available) return;
            let tries = 0;
            const t = setInterval(async () => {
                tries++;
                try {
                    const s = await (await fetch("/api/svc/world/status")).json();
                    if (s.available) {
                        clearInterval(t);
                        if (window.GeoMap) window.GeoMap.loadCountries("/static/data/world.geojson");
                    } else if (!s.running && tries > 1) clearInterval(t);
                } catch (e) { clearInterval(t); }
                if (tries > 8) clearInterval(t);
            }, 4000);
        } catch (e) { /* hors-ligne : carte simplifiée intégrée */ }
    }
    window.worldFetchNow = async function () {
        const r = await fetch("/api/svc/world/fetch", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
        const d = await r.json().catch(() => ({}));
        if (d.success && window.GeoMap) window.GeoMap.loadCountries("/static/data/world.geojson");
        alert(d.message || "Terminé");
    };
    window.addEventListener("load", () => setTimeout(worldInit, 1500));
})();
