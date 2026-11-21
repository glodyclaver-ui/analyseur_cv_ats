/* CLAVERATS Pro - Mobile-first : burger, accordéons, tableaux en cartes, gestion de l'historique. 100 % local. */
(function () {
    "use strict";
    const $ = (id) => document.getElementById(id);
    const isMobile = () => window.matchMedia("(max-width:767px)").matches;
    const LS_HIST = "claverats_history_5";
    const readHist = () => { try { return JSON.parse(localStorage.getItem(LS_HIST) || "[]"); } catch (e) { return []; } };
    const writeHist = (l) => { try { localStorage.setItem(LS_HIST, JSON.stringify(l)); } catch (e) {} };
    const toast = (m) => (typeof showToast === "function" ? showToast(m) : null);

    /* ---------- Accordéons de "Nouvelle analyse" ---------- */
    function mkAcc(title, nodes, stateId) {
        const d = document.createElement("details"); d.className = "acc";
        const s = document.createElement("summary");
        s.innerHTML = `<span>${title}</span>` + (stateId ? `<span class="acc-state" id="${stateId}">vide</span>` : "");
        const body = document.createElement("div"); body.className = "acc-body";
        nodes[0].parentNode.insertBefore(d, nodes[0]);
        d.appendChild(s); d.appendChild(body);
        nodes.forEach((n) => body.appendChild(n));
        return d;
    }
    function setupAccordions() {
        const scan = $("tab-scan"); if (!scan || scan.dataset.acc) return; scan.dataset.acc = "1";
        const cards = scan.querySelectorAll(":scope > .bento-card");
        const accs = [];
        if (cards[0]) {
            const div = cards[0].querySelector(".soft-divider"), ta = $("cv_text");
            if (div && ta) accs.push(mkAcc("Ou coller le texte du CV", [div, ta], "acc_cv_state"));
        }
        if (cards[1]) {
            // l'offre complète (PDF / lien / texte) est repliée ; son statut reste visible
            const kids = Array.from(cards[1].children).filter((n) => !n.classList.contains("card-top-row") && !n.classList.contains("card-title"));
            if (kids.length) accs.push(mkAcc("Offre d'emploi (PDF, lien ou texte)", kids, "acc_job_state"));
        }
        const upd = () => {
            const set = (id, ok) => { const e = $(id); if (e) { e.textContent = ok ? "renseigné" : "vide"; e.classList.toggle("ok", ok); } };
            set("acc_cv_state", ($("cv_text") || {}).value && $("cv_text").value.trim().length > 20);
            set("acc_job_state", (($("job_text") || {}).value || "").trim().length > 20 || (($("job_url") || {}).value || "").trim() || ($("job_pdf") && $("job_pdf").files && $("job_pdf").files.length));
        };
        scan.addEventListener("input", upd); scan.addEventListener("change", upd); upd();
        const apply = () => accs.forEach((a) => { a.open = !isMobile(); });
        apply();
        // bouton de téléchargement du dernier bilan
        const row = scan.querySelector(".form-actions-row");
        if (row && !$("btn_dl_last")) {
            const b = document.createElement("button"); b.type = "button"; b.id = "btn_dl_last"; b.className = "btn-soft-reset";
            b.innerHTML = '<i class="ion-android-download"></i> Télécharger le bilan PDF';
            b.onclick = () => {
                if (typeof lastReport !== "undefined" && lastReport && lastReport.success && typeof exportPDF === "function") exportPDF();
                else toast("Lancez d'abord une analyse pour pouvoir télécharger le bilan.");
            };
            row.appendChild(b);
        }
    }

    /* ---------- Tableaux -> cartes (mobile) ---------- */
    function labelTables(root) {
        (root || document).querySelectorAll("table").forEach((t) => {
            const heads = Array.from(t.querySelectorAll("thead th")).map((th) => th.textContent.trim());
            if (!heads.length) return;
            t.classList.add("cards-mobile");
            t.querySelectorAll("tbody tr").forEach((tr) => {
                Array.from(tr.children).forEach((td, i) => { if (!td.hasAttribute("data-label") && heads[i]) td.setAttribute("data-label", heads[i]); });
            });
        });
    }
    function observeTables() {
        labelTables();
        let tm; new MutationObserver(() => { clearTimeout(tm); tm = setTimeout(() => labelTables(), 120); })
            .observe(document.body, { childList: true, subtree: true });
    }

    /* ---------- Gestion de l'historique (supprimer 1 analyse / tout) ---------- */
    function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); }
    function csrfPost(url, body) {
        return fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) }).catch(() => null);
    }
    function renderPanel() {
        const p = $("hist_panel"); if (!p) return;
        const l = readHist();
        p.innerHTML = `<div class="card-top-row" style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
            <strong>Historique des analyses (${l.length})</strong>
            <button type="button" class="pill-btn-ghost" id="hist_close" aria-label="Fermer"><i class="ion-close-round"></i></button></div>` +
            (l.length ? l.map((it, i) => `<div class="hist-row">
                <div class="hist-main" data-load="${i}"><strong>${esc(it.company)} - ${esc(it.score)} %</strong><span>${esc(it.date)} • ${esc(it.name)}</span></div>
                <button type="button" class="btn-danger" data-del="${i}" aria-label="Supprimer cette analyse">Supprimer</button></div>`).join("")
                : `<p class="muted-small">Aucune analyse sauvegardée.</p>`) +
            (l.length ? `<div style="margin-top:12px;display:flex;justify-content:flex-end"><button type="button" class="btn-danger solid" id="hist_clear">Tout supprimer</button></div>` : "");
        p.querySelector("#hist_close").onclick = () => p.classList.add("hidden");
        p.querySelectorAll("[data-load]").forEach((el) => el.onclick = () => { p.classList.add("hidden"); if (typeof loadHistoryEntry === "function") loadHistoryEntry(parseInt(el.dataset.load, 10)); });
        p.querySelectorAll("[data-del]").forEach((el) => el.onclick = () => {
            const i = parseInt(el.dataset.del, 10), cur = readHist(), it = cur[i];
            if (!it || !confirm(`Supprimer l'analyse « ${it.company} » (${it.name}) ?\nCette action est définitive.`)) return;
            cur.splice(i, 1); writeHist(cur);
            if (it.name) csrfPost("/api/svc/history/delete", { name: it.name });
            refreshHistoryViews(); renderPanel(); toast("Analyse supprimée de l'historique.");
        });
        const clr = p.querySelector("#hist_clear");
        if (clr) clr.onclick = () => {
            if (!confirm("Supprimer TOUT l'historique des analyses ? Cette action est définitive.")) return;
            writeHist([]);
            try { localStorage.removeItem("claverats_last_candidate"); } catch (e) {}
            csrfPost("/api/svc/history/clear", {});
            refreshHistoryViews(); renderPanel(); toast("Historique entièrement supprimé.");
        };
    }
    function refreshHistoryViews() {
        if (typeof renderCandidateHistoryList === "function") renderCandidateHistoryList();
        const rb = $("btn_resume_history"); if (rb && !localStorage.getItem("claverats_last_candidate")) rb.classList.add("hidden");
    }
    function setupHistoryButton() {
        const hr = document.querySelector(".header-right"); if (!hr || $("btn_hist_manage")) return;
        const b = document.createElement("button"); b.type = "button"; b.id = "btn_hist_manage"; b.className = "pill-btn-ghost";
        b.innerHTML = '<i class="ion-trash"></i> <span>Historique</span>'; b.title = "Gérer / supprimer l'historique";
        b.onclick = () => { renderPanel(); $("hist_panel").classList.toggle("hidden"); };
        hr.insertBefore(b, hr.firstChild);
        const p = document.createElement("div"); p.id = "hist_panel"; p.className = "hist-panel hidden"; document.body.appendChild(p);
    }


    /* ---------- Barre d'onglets défilante (mobile) : icône + nom, tous les onglets ---------- */
    const SHORT = { "tab-scan": "Analyse", "tab-overview": "Ensemble", "tab-profile": "Profil", "tab-interview": "Entretien", "tab-apply": "Candidature", "tab-hr": "Équipe RH", "tab-intel": "Intelligence", "tab-me": "Mon espace", "tab-ref": "Paramètres" };
    function setupScrollTabs() {
        if ($("tabs_scroll")) return;
        const src = Array.from(document.querySelectorAll(".left-sidebar .side-btn[data-tab]")); if (!src.length) return;
        const bar = document.createElement("nav"); bar.id = "tabs_scroll"; bar.className = "tabs-scroll"; bar.setAttribute("aria-label", "Navigation");
        src.forEach((b) => {
            const t = b.getAttribute("data-tab"), ico = b.querySelector("i"), btn = document.createElement("button");
            btn.type = "button"; btn.className = "ts-item"; btn.dataset.tab = t;
            btn.innerHTML = (ico ? `<i class="${ico.className}"></i>` : "") + `<span>${SHORT[t] || b.getAttribute("data-tooltip") || t}</span>`;
            btn.onclick = () => { if (!btn.classList.contains("disabled") && typeof switchTab === "function") switchTab(t); };
            bar.appendChild(btn);
        });
        document.body.appendChild(bar);
        const sync = () => src.forEach((b, i) => {
            const it = bar.children[i]; if (!it) return;
            it.classList.toggle("active", b.classList.contains("active")); it.classList.toggle("disabled", b.classList.contains("disabled"));
            if (b.classList.contains("active")) { const l = it.offsetLeft - (bar.clientWidth - it.clientWidth) / 2; bar.scrollTo({ left: l, behavior: "smooth" }); }
        });
        src.forEach((b) => new MutationObserver(sync).observe(b, { attributes: true, attributeFilter: ["class"] }));
        sync();
    }

    function init() { setupScrollTabs(); setupAccordions(); observeTables(); setupHistoryButton(); }
    if (document.readyState !== "loading") init(); else document.addEventListener("DOMContentLoaded", init);
    window.ClaveratsMobile = { renderPanel, labelTables };
})();
