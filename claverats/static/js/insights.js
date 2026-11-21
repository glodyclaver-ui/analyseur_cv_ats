/* CLAVERATS Pro - Transparence du score, édition de l'offre, progression de carrière, éditeur de référentiels. 100 % local. */
(function () {
    "use strict";
    const $ = (id) => document.getElementById(id);
    const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
    const toast = (m) => (typeof showToast === "function" ? showToast(m) : alert(m));
    const post = async (url, body) => {
        const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) });
        const d = await r.json().catch(() => ({ success: false, message: "Réponse invalide" }));
        if (!r.ok && d.success !== true) d.success = false;
        return d;
    };
    const bar = (p, col) => `<div class="ins-bar"><i style="width:${Math.max(0, Math.min(100, p))}%;background:${col || "var(--royal,#4a72ff)"}"></i></div>`;
    const pane = (id, rootId) => { const t = $(id); if (!t) return null; let r = $(rootId); if (!r) { r = document.createElement("div"); r.id = rootId; r.className = "ins-root"; t.appendChild(r); } return r; };

    /* ---------- 1. Transparence du score (vue d'ensemble) ---------- */
    function renderScoreInsights(rep) {
        const root = pane("tab-overview", "ins_overview"); if (!root || !rep) return;
        const jd = rep.job_details || {}, conf = rep.score_confidence || {}, fq = rep.format_quality, role = jd.detected_role || {};
        const confCol = { "élevée": "#10b981", "moyenne": "#f59e0b", "faible": "#ef4444", "insuffisante": "#ef4444" }[conf.level] || "#6b7280";
        let h = `<div class="bento-card ins-card"><div class="card-top-row"><span class="chip-blue">TRANSPARENCE</span>` +
            (conf.level ? `<span class="ins-badge" style="background:${confCol}1a;color:${confCol}">Fiabilité : ${esc(conf.level)}</span>` : "") + `</div>
            <h3 class="card-title">Comment ce score est calculé</h3>`;
        if (role.label) h += `<p class="muted-small">Métier détecté dans l'offre : <b>${esc(role.label)}</b>${role.confidence != null ? " (confiance " + Math.round(role.confidence * 100) + " %)" : ""}. Les compétences attendues sont adaptées à ce métier.</p>`;
        (rep.score_explanation || []).forEach((e) => { h += `<div class="ins-row"><span>${esc(e.label)} <small>${esc(e.detail || "")}</small></span><b>${e.points} / ${e.weight}</b></div>${bar(e.ratio)}`; });
        (conf.reasons || []).forEach((r) => { h += `<p class="muted-small">• ${esc(r)}</p>`; });
        const reqs = jd.requirements || [], matched = new Set((rep.matched_skills || []).map((x) => x.toLowerCase()));
        if (reqs.length) {
            h += `<h4 class="ins-h">Compétences réellement attendues par l'employeur</h4><div class="ins-chips">` + reqs.map((r) => {
                const ok = matched.has(String(r.name).toLowerCase()), est = String(r.source).startsWith("estim");
                return `<span class="ins-chip ${ok ? "ok" : "ko"}" title="${est ? "Estimée d'après le métier (référentiel)" : "Écrite dans l'offre"} • coefficient ${r.weight}">${ok ? '<i class="ion-checkmark-round"></i>' : '<i class="ion-close-round"></i>'} ${esc(r.name)}${est ? " <em>estimée</em>" : ""} <small>×${r.weight}</small></span>`;
            }).join("") + `</div><p class="muted-small">« estimée » = déduite du métier, non écrite dans l'offre. Les coefficients se modifient dans l'onglet Référentiels.</p>`;
        }
        if (fq) {
            h += `<h4 class="ins-h">Lisibilité / mise en forme du CV : ${fq.score} % <small>(${esc(fq.level)})</small></h4>` + bar(fq.score, fq.score >= 75 ? "#10b981" : fq.score >= 50 ? "#f59e0b" : "#ef4444");
            const tips = (fq.criteria || []).filter((c) => !c.ok && c.tip);
            if (tips.length) h += "<ul class='ins-list'>" + tips.map((c) => `<li><b>${esc(c.label)}</b> - ${esc(c.tip)}</li>`).join("") + "</ul>";
        }
        root.innerHTML = h + "</div>";
    }

    /* ---------- 2. Informations de l'employeur (modifiables) + progression ---------- */
    function renderProfileExtras(rep) {
        const root = pane("tab-profile", "ins_profile"); if (!root || !rep) return;
        const jd = rep.job_details || {};
        root.innerHTML = `<div class="bento-card ins-card"><div class="card-top-row"><span class="chip-amber">EMPLOYEUR</span><span class="muted-small">Modifiable manuellement</span></div>
          <h3 class="card-title">Informations de l'employeur et de l'offre</h3>
          <div class="ins-grid">
            <label>Entreprise / ONG<input id="ofr_company" type="text" value="${esc(jd.company_name)}"></label>
            <label>E-mail de candidature<input id="ofr_email" type="email" value="${esc((jd.apply_emails || [])[0] || "")}"></label>
            <label class="wide">Lien de l'offre<input id="ofr_url" type="url" value="${esc((jd.apply_links || [])[0] || "")}"></label>
            <label class="wide">Description de l'offre<textarea id="ofr_desc" rows="6">${esc(jd.raw_job_text)}</textarea></label>
          </div>
          <div class="ins-actions"><button type="button" class="btn-royal" id="ofr_save">Enregistrer et relancer l'analyse</button></div>
          <p class="muted-small" id="ofr_msg">Si vous modifiez la description, les compétences attendues et le score sont recalculés.</p></div>
          <div class="bento-card ins-card"><div class="card-top-row"><span class="chip-blue">CARRIÈRE</span><span class="muted-small">Indicatif</span></div>
          <h3 class="card-title">Progression de carrière (1 / 3 / 5 ans)</h3>
          <div class="ins-actions"><button type="button" class="btn-soft-reset" id="car_go">Calculer ma progression</button></div><div id="car_out"></div></div>`;
        $("ofr_save").onclick = saveOffer; $("car_go").onclick = careerGo;
    }
    async function saveOffer() {
        if (typeof lastReport === "undefined" || !lastReport) return;
        const msg = $("ofr_msg"); msg.textContent = "Recalcul en cours…";
        const body = Object.assign({}, lastReport, { offer: { company_name: $("ofr_company").value, contact_email: $("ofr_email").value, offer_url: $("ofr_url").value, description: $("ofr_desc").value } });
        const d = await post("/api/reanalyze-offer", body);
        if (!d.success) { msg.textContent = "Erreur : " + (d.message || "Échec"); return; }
        d.pdf_original = lastReport.pdf_original; d.manual_edits = lastReport.manual_edits || {};
        lastReport = d; renderAllViews(d); if (window.CE && CE.persistCandidate) CE.persistCandidate();
        toast("Offre mise à jour - nouveau score : " + d.score + " %");
    }
    async function careerGo() {
        const out = $("car_out"); out.innerHTML = "<p class='muted-small'>Calcul…</p>";
        const d = await post("/api/svc/career/progression", { report: lastReport });
        if (!d.success) { out.innerHTML = "<p>Calcul impossible.</p>"; return; }
        const L = d.ladder || [], idx = (lv) => Math.max(0, L.indexOf(lv)), pts = [{ t: "Aujourd'hui", lv: d.current_level }].concat(d.projections.map((p) => ({ t: "+" + p.years + " an" + (p.years > 1 ? "s" : ""), lv: p.level })));
        const chart = `<div class="vz"><div class="vz-title">Trajectoire estimée (échelon atteint)</div><div class="vz-cols">` + pts.map((q, i) => {
            const h = Math.round(((idx(q.lv) + 1) / Math.max(1, L.length)) * 100);
            return `<div class="vz-col"><div class="vz-bar-wrap"><div class="vz-bar ${i === 0 ? "now" : ""}" style="height:${h}%"><b>${idx(q.lv) + 1}/${L.length}</b></div></div><span class="vz-x">${esc(q.t)}</span><small>${esc(q.lv)}</small></div>`;
        }).join("") + `</div></div>`;
        const mt = (lastReport.matched_skills || []).length, ms = (lastReport.missing_skills || []).length, cov = (mt + ms) ? Math.round(100 * mt / (mt + ms)) : 0;
        const donut = `<div class="vz vz-row"><div class="vz-donut" style="--p:${cov}"><b>${cov}%</b></div><div><div class="vz-title">Couverture des compétences exigées</div><small>${mt} validée(s) sur ${mt + ms}. Plus elle est élevée, plus la progression est rapide (${d.pace_years_per_step} an(s) par échelon).</small></div></div>`;
        out.innerHTML = chart + donut + `<p class="muted-small">${esc(d.explanation)}</p><div class="ins-timeline">` + d.projections.map((p) =>
            `<div class="ins-step"><b>Dans ${p.years} an${p.years > 1 ? "s" : ""}</b><span>${esc(p.level)}</span><small>${esc(p.reading)}</small>` +
            (p.to_acquire.length ? `<small>À acquérir : ${esc(p.to_acquire.join(", "))}</small>` : "") + `</div>`).join("") + `</div><p class="muted-small"><i class="ion-information-circled"></i> ${esc(d.disclaimer)}</p>`;
    }

    /* ---------- hook sur renderAllViews ---------- */
    const _orig = window.renderAllViews;
    window.renderAllViews = renderAllViews = function (data) {
        const r = _orig.apply(this, arguments);
        try { renderScoreInsights(data); renderProfileExtras(data); } catch (e) { console.error(e); }
        return r;
    };

    /* ---------- 3. Éditeur de référentiels (onglet Référentiels) ---------- */
    let REF = [], curSector = "", curRole = "";
    async function loadRef() {
        const r = await fetch("/api/svc/referentials"); const d = await r.json(); REF = d.sectors || [];
        if (!curSector || !REF.find((s) => s.sector === curSector)) curSector = (REF[0] || {}).sector || "";
        renderRef();
    }
    function renderRef() {
        const root = $("ref_body"); if (!root) return;
        const sec = REF.find((s) => s.sector === curSector) || { roles: [] };
        if (!sec.roles.find((r) => r.role === curRole)) curRole = (sec.roles[0] || {}).role || "";
        const role = sec.roles.find((r) => r.role === curRole) || { skills: [], keywords: [] };
        root.innerHTML = `<div class="bento-card ins-card"><h3 class="card-title">Référentiels de compétences par métier</h3>
          <p class="muted-small">Chaque métier a des compétences attendues avec un coefficient (3 = essentielle, 2 = importante, 1 = un plus) et des mots-clés (synonymes). Tout est modifiable ; enregistré localement dans <code>data/config/skills_referentials.json</code>.</p>
          <div class="ins-grid"><label>Secteur<select id="ref_sec">${REF.map((s) => `<option value="${esc(s.sector)}" ${s.sector === curSector ? "selected" : ""}>${esc(s.label)}</option>`).join("")}</select></label>
          <label>Métier<select id="ref_role">${sec.roles.map((r) => `<option value="${esc(r.role)}" ${r.role === curRole ? "selected" : ""}>${esc(r.label)}</option>`).join("")}</select></label></div>
          <p class="muted-small">Mots-clés de détection du métier : ${esc((role.keywords || []).join(", "))}</p>
          <div id="ref_skills">${(role.skills || []).map((s, i) => `<div class="ref-skill"><div><b>${esc(s.name)}</b><br><small>${esc((s.aliases || []).join(", "))}</small></div>
              <select data-i="${i}" class="ref-w"><option value="3" ${s.weight == 3 ? "selected" : ""}>Essentielle ×3</option><option value="2" ${s.weight == 2 ? "selected" : ""}>Importante ×2</option><option value="1" ${s.weight == 1 ? "selected" : ""}>Un plus ×1</option></select>
              <button type="button" class="btn-danger" data-i="${i}">Supprimer</button></div>`).join("") || "<p class='muted-small'>Aucune compétence.</p>"}</div>
          <h4 class="ins-h">Ajouter une compétence</h4><div class="ins-grid">
            <label>Nom<input id="ref_new_name" type="text" placeholder="ex : Soins de plaies"></label>
            <label>Coefficient<select id="ref_new_w"><option value="3">Essentielle ×3</option><option value="2" selected>Importante ×2</option><option value="1">Un plus ×1</option></select></label>
            <label class="wide">Mots-clés / synonymes (séparés par des virgules)<input id="ref_new_alias" type="text" placeholder="ex : pansement, soin des plaies"></label></div>
          <div class="ins-actions"><button type="button" class="btn-royal" id="ref_add">Ajouter</button>
            <button type="button" class="btn-soft-reset" id="ref_addrole">Nouveau métier</button>
            <button type="button" class="btn-danger" id="ref_reset">Rétablir les valeurs par défaut</button></div></div>`;
        $("ref_sec").onchange = (e) => { curSector = e.target.value; curRole = ""; renderRef(); };
        $("ref_role").onchange = (e) => { curRole = e.target.value; renderRef(); };
        root.querySelectorAll(".ref-w").forEach((el) => el.onchange = async () => {
            const s = role.skills[+el.dataset.i]; const d = await post("/api/svc/referentials/skill", { sector: curSector, role: curRole, name: s.name, weight: +el.value, aliases: s.aliases, old_name: s.name });
            toast(d.success ? "Coefficient enregistré." : d.message); loadRef();
        });
        root.querySelectorAll(".btn-danger[data-i]").forEach((el) => el.onclick = async () => {
            const s = role.skills[+el.dataset.i]; if (!confirm("Supprimer « " + s.name + " » de ce métier ?")) return;
            const d = await post("/api/svc/referentials/skill/delete", { sector: curSector, role: curRole, name: s.name }); toast(d.success ? "Compétence supprimée." : d.message); loadRef();
        });
        $("ref_add").onclick = async () => {
            const d = await post("/api/svc/referentials/skill", { sector: curSector, role: curRole, name: $("ref_new_name").value, weight: +$("ref_new_w").value, aliases: $("ref_new_alias").value.split(",").map((x) => x.trim()).filter(Boolean) });
            toast(d.success ? "Compétence ajoutée." : d.message); if (d.success) loadRef();
        };
        $("ref_addrole").onclick = async () => {
            const label = prompt("Nom du nouveau métier (ex : Technicien de maintenance) :"); if (!label) return;
            const kw = prompt("Mots-clés de détection, séparés par des virgules :", label.toLowerCase()) || "";
            const d = await post("/api/svc/referentials/role", { sector: curSector, key: label.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, ""), label: label, keywords: kw.split(",").map((x) => x.trim()).filter(Boolean) });
            toast(d.success ? "Métier ajouté." : d.message); if (d.success) { curRole = d.role; loadRef(); }
        };
        $("ref_reset").onclick = async () => { if (!confirm("Rétablir TOUS les référentiels par défaut ? Vos modifications seront perdues.")) return; await post("/api/svc/referentials/reset", {}); toast("Référentiels rétablis."); loadRef(); };
    }

    /* ---------- 4. Centre d'alertes RH ---------- */
    function setupAlerts() {
        const root = pane("tab-hr", "ins_alerts"); if (!root || $("al_go")) return;
        root.innerHTML = `<div class="bento-card ins-card"><div class="card-top-row"><span class="chip-amber">ALERTES RH</span><span class="muted-small">Signaux à vérifier</span></div>
          <h3 class="card-title">Centre d'alertes</h3><div class="ins-actions"><button type="button" class="btn-soft-reset" id="al_go">Analyser les alertes de la campagne</button></div><div id="al_out"></div></div>`;
        $("al_go").onclick = async () => {
            const out = $("al_out");
            if (typeof lastHrReport === "undefined" || !lastHrReport) { out.innerHTML = "<p class='muted-small'>Lancez d'abord une analyse RH.</p>"; return; }
            const d = await post("/api/svc/hr/alerts", { report: lastHrReport });
            const col = { high: "#ef4444", medium: "#f59e0b", info: "#6b7280" };
            const cn = d.counts || {}, tot = (cn.high || 0) + (cn.medium || 0) + (cn.info || 0);
            const a1 = tot ? 100 * (cn.high || 0) / tot : 0, a2 = a1 + (tot ? 100 * (cn.medium || 0) / tot : 0);
            const kinds = {}; (d.alerts || []).forEach((a) => { kinds[a.kind] = (kinds[a.kind] || 0) + 1; });
            const KL = { duplicate: "Doublons", incomplete_document: "Dossiers incomplets", offer_without_match: "Aucun match", backup_needed: "Vivier de secours", close_scores: "Scores proches", low_confidence: "Score peu fiable" };
            const mx = Math.max(1, ...Object.values(kinds));
            out.innerHTML = tot ? `<div class="vz vz-row"><div class="vz-donut" style="background:conic-gradient(#ef4444 0 ${a1}%,#f59e0b ${a1}% ${a2}%,#9ca3af ${a2}% 100%)"><b>${tot}</b></div>
                <div class="vz-legend"><span><i style="background:#ef4444"></i>Critiques ${cn.high || 0}</span><span><i style="background:#f59e0b"></i>À surveiller ${cn.medium || 0}</span><span><i style="background:#9ca3af"></i>Infos ${cn.info || 0}</span></div></div>
                <div class="vz"><div class="vz-title">Alertes par type</div>` + Object.keys(kinds).map((k) => `<div class="vz-hbar"><span>${esc(KL[k] || k)}</span><div><i style="width:${100 * kinds[k] / mx}%"></i></div><b>${kinds[k]}</b></div>`).join("") + `</div>` : "";
            out.innerHTML += (d.alerts || []).map((a) => `<div class="ref-skill" style="grid-template-columns:1fr"><div><b style="color:${col[a.severity]}"><i class="ion-information-circled"></i> ${esc(a.title)}</b>${a.candidate ? " - " + esc(a.candidate) : ""}<br><small>${esc(a.why)}</small></div></div>`).join("") || "<p>Aucune alerte.</p>";
            out.innerHTML += `<p class="muted-small">${esc(d.note || "")}</p>`;
        };
    }
    if (document.readyState !== "loading") setupAlerts(); else document.addEventListener("DOMContentLoaded", setupAlerts);

    /* ---------- 5. Diagnostic de lecture des images (OCR / photo) ---------- */
    async function setupVisionNote() {
        const dz = document.querySelector("#tab-scan label.drop-zone"); if (!dz || $("vision_note")) return;
        let d; try { d = await (await fetch("/api/svc/vision/status")).json(); } catch (e) { return; }
        const n = document.createElement("div"); n.id = "vision_note"; n.className = "vision-note " + (d.ok ? "ok" : "warn");
        n.innerHTML = d.ok ? `<i class="ion-checkmark-circled"></i> Lecture des images et PDF scannés : activée (OCR local, aucune connexion requise).`
            : `<i class="ion-information-circled"></i> <div><b>Lecture des images/PDF scannés non disponible sur ce poste.</b> ${(d.tips || []).map(esc).join(" ")}</div>`;
        dz.after(n);
    }
    if (document.readyState !== "loading") setupVisionNote(); else document.addEventListener("DOMContentLoaded", setupVisionNote);

    /* ---------- Paramètres : référentiels, centre de contrôle, diagnostic, à propos (accordéons) ---------- */
    const LOGO = '<svg viewBox="0 0 24 24" width="30" height="30" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M8 12l3 3 5-6"/></svg>';
    function renderSettings() {
        const root = $("ref_root"); if (!root) return;
        if (!$("set_shell")) {
            root.innerHTML = `<div id="set_shell"><div class="set-head"><div class="set-logo">${LOGO}</div><div><h1 style="margin:0">Paramètres <span class="underline-blue">CLAVERATS Pro</span></h1>
              <p class="muted-small" style="margin:4px 0 0">Tout est stocké sur cet appareil. Ouvrez une section pour la modifier.</p></div>
              <div class="set-tools"><button type="button" class="mini-btn" id="set_open">Tout ouvrir</button><button type="button" class="mini-btn" id="set_close">Tout réduire</button></div></div>
              <details class="set-acc" id="set_ref" open><summary><i class="ion-gear-b"></i><span>Référentiels de compétences</span></summary><div id="ref_body"></div></details>
              <details class="set-acc" id="set_ctrl"><summary><i class="ion-locked"></i><span>Centre de contrôle (données, sauvegarde, PIN, journal)</span></summary><div class="intel-grid" id="ctrl_body"><p class="muted-small">Chargement…</p></div></details>
              <details class="set-acc" id="set_ocr"><summary><i class="ion-eye"></i><span>Lecture des images et PDF scannés (OCR)</span></summary><div id="ocr_body" class="set-pad"></div></details>
              <details class="set-acc" id="set_about"><summary><i class="ion-information-circled"></i><span>À propos</span></summary><div class="set-pad"><p><b>CLAVERATS Pro</b> v2.2 - analyse de CV et espace RH, 100 % local. Données dans le dossier <code>data/</code> ; aucun CV n'est envoyé à l'extérieur.</p></div></details></div>`;
            $("set_open").onclick = () => root.querySelectorAll("details.set-acc").forEach((d) => (d.open = true));
            $("set_close").onclick = () => root.querySelectorAll("details.set-acc").forEach((d) => (d.open = false));
            $("set_ctrl").addEventListener("toggle", () => { if ($("set_ctrl").open && window.renderControlCenter) window.renderControlCenter($("ctrl_body")); });
            $("set_ocr").addEventListener("toggle", async () => {
                if (!$("set_ocr").open) return; const d = await (await fetch("/api/svc/vision/status")).json();
                $("ocr_body").innerHTML = `<p><b>OCR (Tesseract)</b> : ${d.tesseract ? "installé " + esc(d.tesseract_version) : "non installé"} - français : ${d.french ? "oui" : "non"}</p>
                  <p><b>OpenCV</b> : ${d.opencv ? esc(d.opencv_version) : "absent"} - modèles de visage : ${d.face_models ? "oui" : "non (méthode de secours)"}</p>` + (d.tips || []).map((t) => `<p class="muted-small">${esc(t)}</p>`).join("") + `<p class="muted-small">Aucune connexion Internet n'est nécessaire une fois ces composants installés.</p>`;
            });
        }
        loadRef();
    }
    const _sw = window.switchTab;
    window.switchTab = switchTab = function (id) { const r = _sw.apply(this, arguments); if (id === "tab-ref") renderSettings(); return r; };
})();
