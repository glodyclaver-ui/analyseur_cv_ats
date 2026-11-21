/* CLAVERATS Pro - onglet "Intelligence locale" : moteurs Python locaux, aucun service externe. */
(function () {
    "use strict";
    const $ = (id) => document.getElementById(id);
    const esc = CE.esc;
    let section = "cand", lastIntel = null;

    const card = (t, body, wide) => '<div class="intel-card' + (wide ? " wide" : "") + '"><h3>' + t + "</h3>" + body + "</div>";
    const bar = (v, cls) => '<div class="bar ' + (cls || "") + '"><i style="width:' + Math.max(0, Math.min(100, v)) + '%"></i></div>';
    const gauge = (v, lab) => '<div style="display:flex;align-items:center;gap:12px"><div class="gauge" style="--p:' + v + '"><b>' + v + '</b></div><small>' + esc(lab || "") + "</small></div>";
    const tags = (a, cls) => (a || []).map((x) => '<span class="tag ' + (cls || "") + '">' + esc(x) + "</span>").join("") || '<span class="muted-small">-</span>';
    const asReport = (c) => ({ success: true, score: c.score, matched_skills: c.matched_skills || [], missing_skills: c.missing_skills || [], bonus_skills: c.bonus_skills || [],
        cv_details: { full_name: c.name, structured_experiences: c.structured_experiences || [], location: c.location, education_label: c.education, exp_years: c.exp_years },
        sha256: c.sha256, emails: c.emails, phones: c.phones });
    const hrReports = () => (typeof lastHrReport !== "undefined" && lastHrReport && lastHrReport.candidates ? lastHrReport.candidates.map(asReport) : []);
    const empty = (m) => '<div class="intel-card wide"><p>' + m + "</p></div>";

    function render() {
        const r = $("intel_root");
        if (!r) return;
        const nav = [["cand", "Mon profil"], ["rh", "Vivier RH"], ["suivi", "Suivi & historique"]];
        r.innerHTML = '<div class="intel-head"><div><h1 style="margin:0">Intelligence <span class="underline-blue">locale</span></h1><p class="muted-small" style="margin:4px 0 0">Analyses calculées par Python sur cet appareil : aucune donnée n\'est envoyée sur Internet.</p></div></div>' +
            '<div class="intel-nav">' + nav.map((n) => '<button type="button" class="' + (section === n[0] ? "on" : "") + '" data-s="' + n[0] + '">' + n[1] + "</button>").join("") + '</div><div id="intel_body" class="intel-grid"></div>';
        r.querySelectorAll(".intel-nav button").forEach((b) => { b.onclick = function () { section = b.dataset.s; render(); }; });
        ({ cand: secCand, rh: secRh, suivi: secSuivi })[section]();
    }
    window.renderIntel = render;
    window.renderControlCenter = function (el) { return secCtrl(el); };
    const _sw = switchTab;
    switchTab = function (id) { _sw(id); if (id === "tab-intel") render(); };

    /* ---------- Mon profil ---------- */
    async function secCand() {
        const b = $("intel_body");
        if (typeof lastReport === "undefined" || !lastReport) { b.innerHTML = empty("Lancez d'abord un audit (onglet « Nouvelle analyse ») pour voir l'analyse approfondie de votre profil."); return; }
        b.innerHTML = empty("Analyse en cours…");
        const rep = lastReport;
        const d = await svc("intel", { report: rep });
        lastIntel = d;
        if (!d.success) { b.innerHTML = empty("Analyse indisponible."); return; }
        const cv = rep.cv_details || {}, ea = cv.experience_analysis || {}, t = d.talent, p = d.potential, dec = d.decision;
        let h = "";
        h += card("Décision & indice de talent", '<span class="verdict v-' + esc(dec.verdict.split(" ")[0]) + '">' + esc(dec.verdict) + "</span>" + '<ul>' + dec.why.map((w) => "<li>" + esc(w) + "</li>").join("") + "</ul>" +
            '<div class="kpi-row"><div class="kpi"><small>Indice de talent</small><b>' + t.talent_index + '</b></div><div class="kpi"><small>Séniorité</small><b>' + esc(t.seniority) + '</b></div><div class="kpi"><small>Potentiel</small><b>' + p.potential + "</b></div></div>");
        h += card("Cohérence du parcours", gauge(ea.consistency == null ? 0 : ea.consistency, "Stabilité : " + (ea.stability || "-") + " • trous : " + (ea.gaps || 0) + " • chevauchements : " + (ea.overlaps || 0)) + timeline(cv.structured_experiences || []));
        h += card("Métiers qui vous correspondent", d.careers.map((c) => "<p><b>" + esc(c.role) + "</b> - " + c.fit + "%" + bar(c.fit) + '<small>À acquérir : ' + esc(c.missing_core.join(", ") || "rien d'essentiel") + " • évolution : " + esc(c.next_roles.join(", ")) + "</small></p>").join(""));
        h += card("Plan de montée en compétences", d.gaps.gaps.length ? "<ul>" + d.gaps.gaps.map((g) => "<li><b>" + esc(g.skill) + "</b> (effort " + esc(g.effort) + (g.via.length ? ", proche de " + esc(g.via.join(", ")) : "") + ") - " + esc(g.hint) + "</li>").join("") + "</ul>" : "<p>Aucun écart : vous couvrez toutes les compétences demandées.</p>");
        h += card("Trajectoire vers « " + esc(d.path.target) + " »", '<p>Préparation actuelle : <b>' + d.path.readiness_now + "%</b> • durée estimée : <b>" + d.path.months_total + " mois</b></p>" + d.path.steps.map((s) => '<div class="tl-row"><span class="lab">' + esc(s.skill) + '</span><div class="tl-track"><div class="tl-seg" style="left:0;width:' + Math.min(100, s.month / Math.max(1, d.path.months_total) * 100) + '%"></div></div><small>' + s.month + " m</small></div>").join("") + "<p><small>Ensuite : " + esc(d.path.then.join(", ")) + "</small></p>");
        h += card("Simulateur « et si j'apprenais… ? »", '<p class="muted-small">Cochez des compétences manquantes :</p>' + (rep.missing_skills || []).map((s, i) => '<label style="display:inline-flex;gap:4px;margin:2px 8px 2px 0;font-size:.8rem"><input type="checkbox" class="whatif" value="' + esc(s) + '">' + esc(s) + "</label>").join("") +
            '<div class="row2"><button class="mini-btn primary" id="wi_go" type="button">Simuler</button><b id="wi_out"></b></div>' + (d.next_skills.length ? "<p><small>Meilleurs gains : " + d.next_skills.map((n) => esc(n.skill) + " (+" + n.gain + ")").join(", ") + "</small></p>" : ""));
        h += card("Cohérence texte CV ↔ offre (sémantique)", gauge(d.semantic, "Similarité TF-IDF calculée localement") + "<p><small>Complète le score par compétences : mesure le vocabulaire commun, pas seulement les mots-clés.</small></p>");
        h += card("Confiance du document", rep.doc_trust ? '<p><b>' + esc(rep.doc_trust.level) + "</b> (" + rep.doc_trust.score + "/100)</p>" + bar(rep.doc_trust.score, rep.doc_trust.score >= 75 ? "mint" : rep.doc_trust.score >= 50 ? "amber" : "red") + tags(rep.doc_trust.flags, "warn") + tags(rep.pdf_warnings, "warn") : "<p>Non évaluée (CV collé en texte).</p>");
        const oc = rep.org_check;
        h += card("Vérification de l'organisation / de l'offre", oc ? "<p><b>" + esc(oc.org) + "</b> • " + esc(oc.kind) + " • confiance <b>" + oc.trust + "/100 (" + esc(oc.level) + ")</b></p>" + bar(oc.trust, oc.trust >= 70 ? "mint" : oc.trust >= 45 ? "amber" : "red") + tags(oc.flags, "warn") + tags(oc.checks, "ok") +
            '<div class="row2"><button class="mini-btn" id="org_online" type="button">Vérifier en ligne (DNS/SSL)</button></div><div id="org_online_out"></div>' : "<p>Aucune offre vérifiable.</p>");
        const en = d.enrichment;
        h += card("Présence en ligne (liens du CV)", CE.contactIcons(cv) + tags(en.notes) + (en.github && en.github.repos != null ? "<p>GitHub : " + en.github.repos + " dépôts • " + en.github.followers + " abonnés • depuis " + esc(en.github.created) + "</p>" : "") + '<div class="row2"><button class="mini-btn" id="gh_online" type="button">Enrichir via GitHub (en ligne)</button></div>');
        const TYPE_ICON = { "Technique": "ion-gear-b", "Motivation": "ion-flash", "Comportemental": "ion-person", "Écart": "ion-information-circled", "Ecart": "ion-information-circled" };
        h += card("Préparation à l'entretien (questions STAR)", '<p class="star-intro">Entraînez-vous à répondre avec la méthode <b>STAR</b> : Situation, Tâche, Action, Résultat.</p><div class="star-list">' + d.interview.map((q, i) =>
            '<div class="star-q"><div class="star-head"><span class="star-n">' + (i + 1) + '</span><span class="star-type t-' + esc(String(q.type).toLowerCase().replace(/[^a-z]/g, "")) + '"><i class="' + (TYPE_ICON[q.type] || "ion-chatboxes") + '"></i> ' + esc(q.type) + "</span></div>" +
            '<div class="star-text">' + esc(q.q) + "</div>" + (q.star ? '<div class="star-hint"><i class="ion-information-circled"></i><span>' + esc(q.star) + "</span></div>" : "") +
            '<div class="star-actions"><button class="mini-btn primary answer-btn" data-i="' + i + '" type="button"><i class="ion-edit"></i> Répondre</button></div></div>').join("") + '</div><div id="ans_box" class="star-answer"></div>', true);
        b.innerHTML = h;
        $("wi_go").onclick = async function () {
            const add = Array.prototype.map.call(document.querySelectorAll(".whatif:checked"), (x) => x.value);
            const r = await svc("scenario", { report: rep, add_skills: add });
            $("wi_out").textContent = "Score " + r.base + "% → " + r.scenario + "% (+" + r.gain + ")";
        };
        const oo = $("org_online");
        if (oo) oo.onclick = async function () {
            $("org_online_out").textContent = "Vérification…";
            const j = rep.job_details || {};
            const r = await svc("org-verify", { job_text: j.raw_job_text || "", emails: j.apply_emails || [], links: j.apply_links || [], online: true });
            $("org_online_out").innerHTML = r.success ? "<p>Confiance : <b>" + r.result.trust + "/100</b> • " + r.result.domains.map((x) => esc(x.domain) + " DNS:" + (x.dns === null ? "n/a" : x.dns ? "ok" : "échec") + " SSL:" + (x.ssl === null ? "n/a" : x.ssl ? "ok" : "échec")).join(" ; ") + "</p>" : "Indisponible.";
        };
        const go = $("gh_online");
        if (go) go.onclick = async function () {
            go.textContent = "…";
            const r = await svc("intel", { report: rep, online: true });
            lastIntel = r; secCand();
        };
        document.querySelectorAll(".answer-btn").forEach((btn) => {
            btn.onclick = function () {
                const q = d.interview[parseInt(btn.dataset.i, 10)];
                $("ans_box").innerHTML = '<p><b>' + esc(q.q) + '</b></p><textarea id="ans_txt" rows="5" placeholder="Situation, Tâche, Action, Résultat…"></textarea><div class="row2"><button class="mini-btn primary" id="ans_go" type="button">Évaluer ma réponse</button></div><div id="ans_res"></div>';
                $("ans_go").onclick = async function () {
                    const r = await svc("answer-score", { type: q.type, answer: $("ans_txt").value });
                    $("ans_res").innerHTML = "<p>Score : <b>" + r.score + "/100</b> (" + r.length + " mots)</p>" + bar(r.score, r.score >= 70 ? "mint" : "amber") + tags(Object.keys(r.star).filter((k) => r.star[k]), "ok") + tags(r.advice, "warn");
                };
            };
        });
    }
    function timeline(exps) {
        const sp = exps.filter((e) => e.duration_months);
        if (!sp.length) return "";
        const mx = Math.max.apply(null, sp.map((e) => e.duration_months));
        return '<div class="timeline">' + sp.map((e) => '<div class="tl-row"><span class="lab" title="' + esc(e.company || e.employer) + '">' + esc(e.company || e.employer) + '</span><div class="tl-track"><div class="tl-seg" style="left:0;width:' + Math.round(e.duration_months / mx * 100) + '%"></div></div><small>' + esc(e.duration_label) + "</small></div>").join("") + "</div>";
    }

    /* ---------- Vivier RH ---------- */
    async function secRh() {
        const b = $("intel_body"), reps = hrReports();
        if (!reps.length) { b.innerHTML = empty("Analysez d'abord un lot de CV dans l'« Espace Équipe RH » (ou reprenez une campagne enregistrée) pour voir l'analytique du vivier."); return; }
        const required = (lastHrReport.job_skills || []);
        const [an, tm, gr, dd] = await Promise.all([svc("analytics", { reports: reps }), svc("team", { reports: reps.slice(0, 3), required: required }), svc("graph", { reports: reps }),
            svc("dedupe", { candidates: lastHrReport.candidates.map((c) => ({ full_name: c.name, emails: c.emails || (c.email ? [c.email] : []), phones: c.phones || (c.phone ? [c.phone] : []), sha256: c.sha256 })) })]);
        let h = "";
        h += card("Entonnoir de recrutement", an.funnel.map((f) => "<div><small>" + esc(f.stage) + " - <b>" + f.n + "</b></small>" + bar(an.count ? f.n / an.count * 100 : 0) + "</div>").join("") + "<p><small>Score moyen : <b>" + an.avg + "%</b></small></p>");
        h += card("Podium", an.podium.map((p) => '<p>' + ["1er", "2e", "3e"][p.rank - 1] + " <b>" + esc(p.name) + "</b> - " + p.score + "%</p>").join("") + "<p><small>Compétences les plus manquantes : " + esc(an.top_missing.map((m) => m[0] + " (" + m[1] + ")").join(", ") || "-") + "</small></p>");
        h += card("Carte de chaleur compétences × candidats", '<div style="overflow:auto"><table class="heat"><tr><th></th>' + an.heatmap.skills.map((s) => "<th>" + esc(s) + "</th>").join("") + "</tr>" +
            an.heatmap.rows.map((r) => '<tr><td class="n">' + esc(r.name) + "</td>" + r.cells.map((c) => '<td class="h' + c + '">' + (c ? "✓" : "") + "</td>").join("") + "</tr>").join("") + "</table></div>", true);
        h += card("Compatibilité d'équipe (top 3)", '<div class="kpi-row"><div class="kpi"><small>Couverture</small><b>' + tm.coverage + '%</b></div><div class="kpi"><small>Redondance</small><b>' + tm.redundant.length + "</b></div></div><p>" + esc(tm.advice) + "</p>" + tags(tm.uncovered, "warn"));
        h += card("Doublons détectés", dd.duplicates.length ? "<ul>" + dd.duplicates.map((x) => "<li>" + esc(x.a_name) + " ↔ " + esc(x.b_name) + " - " + esc(x.reason) + " (" + Math.round(x.score * 100) + "%)</li>").join("") + "</ul>" : "<p>Aucun doublon.</p>");
        h += card("Recherche dans le vivier", '<input type="text" id="srch_q" placeholder="ex. python docker kinshasa"><div class="row2"><button class="mini-btn primary" id="srch_go" type="button">Rechercher</button></div><div id="srch_out"></div>');
        h += card("Simulateur d'embauche", '<div class="row2"><input type="number" id="wf_seats" value="3" min="1" max="10" style="width:90px"><input type="number" id="wf_cost" value="1200" style="width:110px"><button class="mini-btn primary" id="wf_go" type="button">Simuler</button></div><div id="wf_out"></div>');
        h += card("Graphe des compétences", graphSvg(gr), true);
        b.innerHTML = h;
        $("srch_go").onclick = async function () {
            const r = await svc("search", { reports: reps, query: $("srch_q").value });
            $("srch_out").innerHTML = r.results.length ? "<ol>" + r.results.map((x) => "<li>" + esc(x.name) + " - pertinence " + x.relevance + "% • score " + x.score + "%</li>").join("") + "</ol>" : "<p>Aucun résultat.</p>";
        };
        $("wf_go").onclick = async function () {
            const r = await svc("workforce", { reports: reps, required: required, seats: parseInt($("wf_seats").value, 10), cost: parseInt($("wf_cost").value, 10) });
            $("wf_out").innerHTML = "<p>Couverture : <b>" + r.coverage + "%</b> • coût estimé : " + r.cost + "</p><ol>" + r.selected.map((s) => "<li>" + esc(s.name) + " (" + s.score + "%)</li>").join("") + "</ol>" + tags(r.uncovered, "warn");
        };
    }
    function graphSvg(g) {
        const n = g.nodes.slice(0, 26), R = 150, cx = 210, cy = 175, pos = {};
        n.forEach((x, i) => { const a = i / n.length * Math.PI * 2; pos[x.id] = [cx + R * Math.cos(a), cy + R * Math.sin(a)]; });
        const lines = g.links.filter((l) => pos[l.source] && pos[l.target]).map((l) => '<line x1="' + pos[l.source][0] + '" y1="' + pos[l.source][1] + '" x2="' + pos[l.target][0] + '" y2="' + pos[l.target][1] + '" stroke="currentColor" opacity="' + Math.min(.5, .12 + l.weight * .08) + '"/>').join("");
        const dots = n.map((x) => '<g><circle cx="' + pos[x.id][0] + '" cy="' + pos[x.id][1] + '" r="' + (4 + Math.min(8, x.weight)) + '" fill="var(--royal,#4a72ff)"/><text x="' + pos[x.id][0] + '" y="' + (pos[x.id][1] - 10) + '" font-size="9" text-anchor="middle" fill="currentColor">' + esc(x.id) + "</text></g>").join("");
        return '<svg viewBox="0 0 420 350" style="width:100%;max-height:380px">' + lines + dots + "</svg>";
    }

    /* ---------- Suivi & historique ---------- */
    async function secSuivi() {
        const b = $("intel_body");
        const [hist, camps, apps, ivs] = await Promise.all([svcGet("history"), svcGet("campaign/list"), svcGet("applications"), svcGet("interviews")]);
        let h = "";
        h += card("Historique & évolution des candidats", hist.candidates.length ? '<ul>' + hist.candidates.map((c) => "<li><b>" + esc(c.name) + "</b> - " + c.versions + " version(s), dernier score " + c.last_score + '% <button class="mini-btn evo" data-n="' + esc(c.name) + '" type="button">Évolution</button></li>').join("") + '</ul><div id="evo_out"></div>' : "<p>Aucun historique : il se remplit automatiquement à chaque audit ou correction.</p>");
        h += card("Campagnes RH enregistrées", '<div class="row2"><input type="text" id="camp_name" placeholder="Nom de la campagne" style="flex:1"><button class="mini-btn primary" id="camp_save" type="button">Enregistrer</button></div>' +
            (camps.campaigns.length ? "<ul>" + camps.campaigns.map((c) => "<li>" + esc(c.name) + ' <button class="mini-btn camp-load" data-n="' + esc(c.name) + '" type="button">Charger</button></li>').join("") + "</ul>" : "<p><small>Aucune campagne.</small></p>") +
            '<div class="row2"><button class="mini-btn" id="camp_export" type="button">Exporter (.json)</button><label class="mini-btn" style="cursor:pointer">Importer<input type="file" id="camp_import" accept=".json" hidden></label></div>');
        const st = apps.stages;
        h += card("Suivi de mes candidatures", '<div class="row2"><input type="text" id="ap_co" placeholder="Société" style="flex:1"><input type="text" id="ap_ti" placeholder="Poste" style="flex:1"><button class="mini-btn primary" id="ap_add" type="button">Ajouter</button></div>' +
            '<div class="kanban" style="margin-top:10px">' + st.map((s) => '<div class="kcol"><h4>' + esc(s) + " (" + apps.stats[s] + ")</h4>" + apps.items.filter((i) => i.stage === s).map((i) => '<div class="kitem"><b>' + esc(i.company) + "</b><br>" + esc(i.title) + '<br><select class="ap-move" data-id="' + i.id + '">' + st.map((x) => "<option" + (x === s ? " selected" : "") + ">" + esc(x) + "</option>").join("") + '</select> <button class="mini-btn ap-del" data-id="' + i.id + '" type="button"><i class=\"ion-close-round\"></i></button></div>').join("") + "</div>").join("") + "</div>", true);
        h += card("Entretiens planifiés", '<div class="row2"><input type="text" id="iv_c" placeholder="Candidat / Société" style="flex:1"><input type="text" id="iv_w" placeholder="2026-12-01 10:00" style="flex:1"><button class="mini-btn primary" id="iv_add" type="button">Planifier</button></div>' +
            (ivs.items.length ? "<ul>" + ivs.items.map((i) => "<li>" + esc(i.when) + " - <b>" + esc(i.candidate) + '</b> <button class="mini-btn iv-del" data-id="' + i.id + '" type="button"><i class=\"ion-close-round\"></i></button></li>').join("") + "</ul>" : "<p><small>Aucun entretien.</small></p>"), true);
        b.innerHTML = h;
        document.querySelectorAll(".evo").forEach((x) => { x.onclick = async function () {
            const e = await svcGet("history/evolution?name=" + encodeURIComponent(x.dataset.n));
            const mx = 100;
            $("evo_out").innerHTML = "<p><b>" + esc(e.name) + "</b> • tendance " + (e.trend >= 0 ? "+" : "") + e.trend + " pts</p>" + e.versions.map((v) => '<div class="tl-row"><span class="lab">' + new Date(v.ts * 1000).toLocaleDateString("fr-FR") + '</span><div class="tl-track"><div class="tl-seg" style="left:0;width:' + v.score / mx * 100 + '%"></div></div><small>' + v.score + "% " + esc(v.label) + "</small></div>").join("");
        }; });
        $("camp_save").onclick = async function () {
            if (typeof lastHrReport === "undefined" || !lastHrReport) { showToast("Aucune campagne RH à enregistrer."); return; }
            const slim = JSON.parse(JSON.stringify(lastHrReport)); (slim.candidates || []).forEach((c) => { delete c.pdf_url; });
            await svc("campaign/save", { name: $("camp_name").value || "campagne", payload: slim }); showToast("Campagne enregistrée localement."); secSuivi();
        };
        document.querySelectorAll(".camp-load").forEach((x) => { x.onclick = async function () {
            const r = await svc("campaign/load", { name: x.dataset.n });
            if (r.success) { lastHrReport = r.payload; refreshHrDashboardMetrics(); const a = $("hr_results_area"); if (a) a.classList.remove("hidden"); showToast("Campagne chargée."); switchTab("tab-hr"); }
        }; });
        $("camp_export").onclick = async function () {
            if (typeof lastHrReport === "undefined" || !lastHrReport) { showToast("Aucune campagne RH à exporter."); return; }
            const slim = JSON.parse(JSON.stringify(lastHrReport)); (slim.candidates || []).forEach((c) => { delete c.pdf_url; });
            const res = await fetch("/api/svc/campaign/export", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ payload: slim }) });
            const a = document.createElement("a"); a.href = URL.createObjectURL(await res.blob()); a.download = "campagne_claverats.json"; a.click();
        };
        $("camp_import").onchange = async function (e) {
            const f = e.target.files[0]; if (!f) return;
            const res = await fetch("/api/svc/campaign/import", { method: "POST", body: await f.text() }); const j = await res.json();
            if (j.success) { lastHrReport = j.payload; refreshHrDashboardMetrics(); const a = $("hr_results_area"); if (a) a.classList.remove("hidden"); showToast("Campagne importée et vérifiée."); switchTab("tab-hr"); } else showToast(j.message || "Fichier invalide.");
        };
        $("ap_add").onclick = async function () { if (!$("ap_co").value.trim()) return; await svc("applications", { company: $("ap_co").value, title: $("ap_ti").value, score: typeof lastReport !== "undefined" && lastReport ? lastReport.score : null }); secSuivi(); };
        document.querySelectorAll(".ap-move").forEach((s) => { s.onchange = async function () { await svc("applications/move", { id: s.dataset.id, stage: s.value }); secSuivi(); }; });
        document.querySelectorAll(".ap-del").forEach((s) => { s.onclick = async function () { await svc("applications/delete", { id: s.dataset.id }); secSuivi(); }; });
        $("iv_add").onclick = async function () { if (!$("iv_c").value.trim()) return; await svc("interviews", { candidate: $("iv_c").value, when: $("iv_w").value }); secSuivi(); };
        document.querySelectorAll(".iv-del").forEach((s) => { s.onclick = async function () { await svc("interviews/delete", { id: s.dataset.id }); secSuivi(); }; });
    }

    /* ---------- Centre de contrôle ---------- */
    async function secCtrl(target) {
        const b = target || $("intel_body");
        const [hl, au, bk] = await Promise.all([svcGet("health"), svcGet("audit"), svcGet("backups")]);
        CE.setPinState(hl.pin);
        const bad = hl.store.filter((s) => !s.ok);
        let h = "";
        h += card("Santé des données locales", '<p>Fichiers : <b>' + hl.store.length + "</b> • corrompus : <b>" + bad.length + "</b></p>" + tags(bad.map((x) => x.file), "warn") +
            "<p><small>OpenCV : " + (hl.opencv ? "oui" : "non (détection photo simplifiée)") + " • OCR local : " + (hl.ocr ? "oui" : "non (optionnel)") + " • journal : " + (hl.audit.ok ? "intègre" : "ALTÉRÉ") + " (" + hl.audit.count + " entrées)</small></p>");
        h += card("Sauvegarde & restauration", '<div class="row2"><button class="mini-btn primary" id="bk_go" type="button">Créer une sauvegarde</button></div>' +
            (bk.items.length ? '<div class="row2"><select id="bk_sel">' + bk.items.map((x) => "<option>" + esc(x) + "</option>").join("") + '</select><button class="mini-btn" id="bk_restore" type="button">Restaurer</button></div>' : "<p><small>Aucune sauvegarde.</small></p>") +
            '<div class="row2"><button class="mini-btn" id="purge_old" type="button">Purger données &gt; 30 jours</button></div>');
        h += card("Verrouillage par PIN", "<p>" + (hl.pin ? "PIN actif : verrouillage après 15 min d'inactivité." : "Aucun PIN défini.") + '</p><div class="row2"><input type="password" id="pin_new" placeholder="Nouveau PIN (4-12)" style="flex:1"><button class="mini-btn primary" id="pin_set" type="button">Définir</button><button class="mini-btn" id="pin_lock" type="button">Verrouiller</button></div>');
        h += card("Zone sensible", '<p><small>Efface immédiatement toutes les données locales (historique, campagnes, sauvegardes, journal, PIN) ainsi que le stockage du navigateur.</small></p><button class="mini-btn danger" id="panic" type="button">Effacement total</button>');
        h += card("Journal d'audit local (chaîné SHA-256)", '<div class="row2"><a class="mini-btn" href="/api/svc/audit/export">Exporter (.json)</a></div><ul>' + au.entries.slice(0, 12).map((e) => "<li><small>" + new Date(e.ts * 1000).toLocaleString("fr-FR") + " - " + esc(e.action) + " " + esc(e.detail) + "</small></li>").join("") + "</ul>", true);
        b.innerHTML = h;
        $("bk_go").onclick = async function () { const r = await svc("backup"); showToast("Sauvegarde créée : " + r.name); secCtrl(b); };
        const rs = $("bk_restore"); if (rs) rs.onclick = async function () { const r = await svc("restore", { name: $("bk_sel").value }); showToast(r.success ? r.restored + " fichier(s) restauré(s)." : r.message); };
        $("purge_old").onclick = async function () { const r = await svc("purge", { days: 30 }); showToast(r.removed + " fichier(s) ancien(s) supprimé(s)."); };
        $("pin_set").onclick = async function () { const r = await svc("pin/set", { pin: $("pin_new").value }); showToast(r.success ? "PIN défini." : r.message); secCtrl(b); };
        $("pin_lock").onclick = function () { CE.lockNow(); };
        $("panic").onclick = async function () {
            if (!confirm("Effacer TOUTES les données locales ? Action irréversible.")) return;
            await svc("purge", { panic: true });
            try { Object.keys(localStorage).filter((k) => k.indexOf("claverats_") === 0).forEach((k) => localStorage.removeItem(k)); sessionStorage.clear(); } catch (e) {}
            location.reload();
        };
    }
})();
