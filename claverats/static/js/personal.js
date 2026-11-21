/* CLAVERATS Pro - Mon espace (objectifs, plan de formation), fiche candidat 360° / comparaison (RH), export-import des données. 100 % local. */
(function () {
    "use strict";
    const $ = (id) => document.getElementById(id);
    const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
    const toast = (m) => (typeof showToast === "function" ? showToast(m) : alert(m));
    const post = async (u, b) => { const r = await fetch(u, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(b || {}) }); const d = await r.json().catch(() => ({ success: false })); if (!r.ok) d.success = false; return d; };

    /* ---------- Mon espace ---------- */
    async function renderMe() {
        const root = $("me_root"); if (!root) return;
        const g = await (await fetch("/api/svc/personal/goals")).json();
        const rows = (g.goals || []).map((x) => `<div class="goal ${x.status === "terminé" ? "done" : ""}"><div class="goal-main"><b>${esc(x.title)}</b><small>${x.due ? "Échéance : " + esc(x.due) : "Sans échéance"} • ${esc(x.status)}</small>
            <div class="ins-bar"><i style="width:${x.progress}%"></i></div></div>
            <select data-id="${x.id}" class="goal-st"><option ${x.status === "à faire" ? "selected" : ""}>à faire</option><option ${x.status === "en cours" ? "selected" : ""}>en cours</option><option ${x.status === "terminé" ? "selected" : ""}>terminé</option></select>
            <input type="range" min="0" max="100" step="10" value="${x.progress}" data-id="${x.id}" class="goal-pg" aria-label="Progression">
            <button type="button" class="btn-danger" data-del="${x.id}">Supprimer</button></div>`).join("") || "<p class='muted-small'>Aucun objectif pour l'instant.</p>";
        root.innerHTML = `<div class="set-head"><div class="set-logo"><i class="ion-target" style="font-size:1.6rem"></i></div><div><h1 style="margin:0">Mon <span class="underline-blue">espace</span></h1>
            <p class="muted-small" style="margin:4px 0 0">Objectifs et plan de formation. Données privées, stockées sur cet appareil, jamais transmises à l'espace RH.</p></div></div>
          <div class="bento-card ins-card"><h3 class="card-title">Mes objectifs de carrière</h3><div id="goal_list">${rows}</div>
            <h4 class="ins-h">Nouvel objectif</h4><div class="ins-grid"><label class="wide">Objectif<input id="goal_title" type="text" placeholder="ex : Obtenir la certification Excel avancé"></label>
            <label>Échéance<input id="goal_due" type="date"></label><label>Statut<select id="goal_status"><option>à faire</option><option>en cours</option></select></label></div>
            <div class="ins-actions"><button type="button" class="btn-royal" id="goal_add">Ajouter l'objectif</button></div></div>
          <div class="bento-card ins-card"><h3 class="card-title">Plan de formation (depuis mon dernier audit)</h3>
            <div class="ins-grid"><label>Temps disponible par semaine (heures)<input id="plan_h" type="number" min="1" max="40" value="5"></label></div>
            <div class="ins-actions"><button type="button" class="btn-soft-reset" id="plan_go">Générer mon plan</button></div><div id="plan_out"></div></div>`;
        $("goal_add").onclick = async () => { const d = await post("/api/svc/personal/goals", { title: $("goal_title").value, due: $("goal_due").value, status: $("goal_status").value }); if (!d.success) return toast(d.message || "Erreur"); renderMe(); };
        root.querySelectorAll(".goal-st").forEach((s) => s.onchange = async () => { await post("/api/svc/personal/goals/update", { id: s.dataset.id, status: s.value }); renderMe(); });
        root.querySelectorAll(".goal-pg").forEach((s) => s.onchange = async () => { await post("/api/svc/personal/goals/update", { id: s.dataset.id, progress: +s.value, status: +s.value >= 100 ? "terminé" : "en cours" }); renderMe(); });
        root.querySelectorAll("[data-del]").forEach((b) => b.onclick = async () => { if (!confirm("Supprimer cet objectif ?")) return; await post("/api/svc/personal/goals/delete", { id: b.dataset.del }); renderMe(); });
        $("plan_go").onclick = async () => {
            const out = $("plan_out");
            if (typeof lastReport === "undefined" || !lastReport) { out.innerHTML = "<p class='muted-small'>Lancez d'abord un audit (onglet Nouvelle analyse).</p>"; return; }
            const d = await post("/api/svc/personal/learning-plan", { report: lastReport, hours_per_week: +$("plan_h").value });
            if (!d.items.length) { out.innerHTML = "<p>Aucune compétence manquante : bravo.</p>"; return; }
            const tw = Math.max(1, d.total_weeks);
            out.innerHTML = `<p class="muted-small">Durée totale estimée : <b>${d.total_weeks} semaine(s)</b> à ${d.hours_per_week} h/semaine. ${esc(d.note)}</p><div class="vz">` +
                d.items.map((i) => `<div class="gantt"><span>${esc(i.skill)} <small>${esc(i.priority)}</small></span><div class="gantt-track"><i style="left:${100 * (i.start_week - 1) / tw}%;width:${Math.max(4, 100 * i.weeks / tw)}%"></i></div><b>S${i.start_week}${i.weeks > 1 ? "–" + (i.start_week + i.weeks - 1) : ""}</b></div><small class="gantt-hint">${esc(i.hint)}</small>`).join("") + "</div>";
        };
    }

    /* ---------- Fiche 360° + comparaison (onglet RH) ---------- */
    function setup360() {
        const t = $("tab-hr"); if (!t || $("c360_card")) return;
        const d = document.createElement("div"); d.id = "c360_card"; d.className = "bento-card ins-card";
        d.innerHTML = `<div class="card-top-row"><span class="chip-blue">FICHE 360°</span><span class="muted-small">Aide à la décision</span></div><h3 class="card-title">Fiche candidat 360° et comparaison</h3>
          <div class="ins-grid"><label>Candidat<select id="c360_a"></select></label><label>Comparer avec (optionnel)<select id="c360_b"><option value="">-</option></select></label></div>
          <div class="ins-actions"><button type="button" class="btn-soft-reset" id="c360_go">Afficher</button></div><div id="c360_out"></div>`;
        t.appendChild(d);
        const fill = () => {
            const L = (typeof lastHrReport !== "undefined" && lastHrReport && lastHrReport.candidates) || [];
            const opts = L.map((c, i) => `<option value="${i}">#${c.rank || i + 1} ${esc(c.name)} - ${c.score}%</option>`).join("");
            const ka = $("c360_a").value, kb = $("c360_b").value;
            $("c360_a").innerHTML = opts || "<option value=''>Aucun candidat analysé</option>"; $("c360_b").innerHTML = "<option value=''>-</option>" + opts;
            if (ka !== "") $("c360_a").value = ka; if (kb !== "") $("c360_b").value = kb;
        };
        const _rf = window.refreshHrDashboardMetrics;
        if (typeof _rf === "function" && !_rf.__c360) { const w = function () { const r = _rf.apply(this, arguments); try { fill(); } catch (e) {} return r; }; w.__c360 = true; refreshHrDashboardMetrics = w; }
        $("c360_a").addEventListener("focus", fill); $("c360_b").addEventListener("focus", fill); fill();
        $("c360_go").onclick = async () => {
            fill(); const out = $("c360_out"), a = $("c360_a").value, b = $("c360_b").value;
            if (a === "") { out.innerHTML = "<p class='muted-small'>Lancez d'abord une analyse RH.</p>"; return; }
            if (b !== "" && a !== b) {
                const r = await post("/api/svc/hr/compare", { report: lastHrReport, a: +a, b: +b });
                if (!r.success) { out.innerHTML = `<p>${esc(r.message)}</p>`; return; }
                const col = (x) => `<div class="vz"><b>${esc(x.name)}</b><div class="vz-donut" style="--p:${x.score};margin:8px 0"><b>${x.score}%</b></div><small>${x.exp} an(s) • couverture ${x.coverage_pct}%</small></div>`;
                out.innerHTML = `<div class="ins-grid">${col(r.a)}${col(r.b)}</div><p><b>${esc(r.verdict)}</b></p>
                  <p class="muted-small">Communes : ${esc(r.common.join(", ") || "-")}</p><p class="muted-small">Seulement ${esc(r.a.name)} : ${esc(r.only_a.join(", ") || "-")}</p><p class="muted-small">Seulement ${esc(r.b.name)} : ${esc(r.only_b.join(", ") || "-")}</p>`;
                return;
            }
            const r = await post("/api/svc/hr/candidate360", { report: lastHrReport, index: +a });
            if (!r.success) { out.innerHTML = `<p>${esc(r.message)}</p>`; return; }
            const s = r.sheet, chips = (l, k) => (l || []).map((x) => `<span class="sk-chip ${k}">${esc(x)}</span>`).join("") || "<small>-</small>";
            out.innerHTML = `<div class="vz vz-row"><div class="vz-donut" style="--p:${s.score}"><b>${s.score}%</b></div><div><b>${esc(s.name)}</b><br><small>${esc(s.profession || "")} • ${esc(s.seniority || "")} • ${esc(s.location || "")}</small><br>
              <small>Rang ${s.rank}/${s.of}${s.rank_reason ? " - " + esc(s.rank_reason) : ""}</small></div></div>
              <h4 class="ins-h">Points forts</h4><ul class="ins-list">${(s.strengths.map((x) => `<li>${esc(x)}</li>`).join("")) || "<li>-</li>"}</ul>
              <h4 class="ins-h">Points de vigilance</h4><ul class="ins-list">${(s.watch.map((x) => `<li>${esc(x)}</li>`).join("")) || "<li>Aucun</li>"}</ul>
              <h4 class="ins-h">Compétences validées (${s.matched.length})</h4><div class="sk-wrap">${chips(s.matched, "ok")}</div>
              <h4 class="ins-h">À vérifier (${s.missing.length})</h4><div class="sk-wrap">${chips(s.missing, "ko")}</div>
              <h4 class="ins-h">Parcours</h4><ul class="ins-list">${s.experiences.map((e) => `<li><b>${esc(e.company || "")}</b> - ${esc(e.role || "")} <small>${esc(e.period || "")}</small></li>`).join("") || "<li>Non détecté</li>"}</ul>
              <p class="muted-small">${esc(s.disclaimer)}</p>`;
        };
    }

    /* ---------- Export / import des données (Paramètres) ---------- */
    function setupBackupUi() {
        const shell = $("set_shell"); if (!shell || $("set_data")) return;
        const d = document.createElement("details"); d.className = "set-acc"; d.id = "set_data";
        d.innerHTML = `<summary><i class="ion-android-download"></i><span>Exporter / importer mes données</span></summary><div class="set-pad"><p>Une archive .zip contient vos historiques, objectifs et référentiels. Utile pour changer de PC ou garder une copie.</p>
          <div class="ins-actions"><a class="btn-soft-reset" href="/api/svc/data/export" download>Exporter mes données</a><label class="btn-soft-reset" style="cursor:pointer">Importer une archive<input id="imp_file" type="file" accept=".zip" style="display:none"></label></div>
          <p class="muted-small">Avant tout import, une sauvegarde automatique est créée.</p></div>`;
        shell.appendChild(d);
        $("imp_file").onchange = async (e) => {
            const f = e.target.files[0]; if (!f) return; if (!confirm("Importer « " + f.name + " » ? Vos données actuelles seront sauvegardées puis remplacées.")) return;
            const fd = new FormData(); fd.append("archive", f);
            const r = await fetch("/api/svc/data/import", { method: "POST", body: fd }); const j = await r.json().catch(() => ({}));
            toast(j.success ? j.restored + " fichier(s) importé(s)." : (j.message || "Échec de l'import"));
        };
    }

    const _sw = window.switchTab;
    window.switchTab = switchTab = function (id) { const r = _sw.apply(this, arguments); if (id === "tab-me") renderMe(); if (id === "tab-hr") setup360(); if (id === "tab-ref") setTimeout(setupBackupUi, 50); return r; };
    if (document.readyState !== "loading") setup360(); else document.addEventListener("DOMContentLoaded", setup360);
})();
