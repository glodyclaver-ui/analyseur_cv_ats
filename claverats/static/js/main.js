let lastReport = null;
let lastHrReport = null;
let isHrMode = false;
let isAnonymousMode = false;
let hrQuickFilter = "all";
let hrCityFilter = "";
let activeHrDetailIdx = 0;
let selectedHrIndices = new Set();
let simulatedAddedSkills = new Set();

let practiceInterval = null;
let practiceSecondsLeft = 90;
let practiceQuestionIdx = 0;

let hrReadFilter = "all";
let lastMultiOfferMatrix = [];
let activeMultiOfferIdx = 0;
let hrLeafletMap = null;


(function initApp() {
    const savedTheme = localStorage.getItem("claverats_theme") || "light";
    document.documentElement.setAttribute("data-theme", savedTheme);
    const dateChip = document.getElementById("current_date_chip");
    if (dateChip) {
        dateChip.textContent = new Date().toLocaleDateString("fr-FR");
    }
    updateTopNButtonLabel();
    initHrCalendarCombo();

    if (localStorage.getItem("claverats_last_candidate")) {
        const resumeBtn = document.getElementById("btn_resume_history");
        if (resumeBtn) resumeBtn.classList.remove("hidden");
    }
})();

function restoreLastLocalSession() {
    const raw = localStorage.getItem("claverats_last_candidate");
    if (!raw) return;
    try {
        const parsed = JSON.parse(raw);
        if (parsed && parsed.success) {
            lastReport = parsed;
            document.querySelectorAll(".side-btn, .mob-tab").forEach(b => b.classList.remove("disabled"));
            renderAllViews(parsed);
            switchTab("tab-overview");
        }
    } catch (e) {}
}

function toggleTheme() {
    const current = document.documentElement.getAttribute("data-theme") || "light";
    const next = current === "light" ? "dark" : "light";
    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem("claverats_theme", next);
}

function toggleWorkspaceMode() {
    if (isHrMode) {
        switchTab(lastReport ? "tab-overview" : "tab-scan");
    } else {
        switchTab("tab-hr");
    }
}

function switchTab(tabId) {
    const btn = document.querySelector(`[data-tab="${tabId}"]`);
    if (btn && btn.classList.contains("disabled")) return;

    document.querySelectorAll(".side-btn, .mob-tab").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".tab-pane").forEach(p => p.classList.add("hidden"));

    document.querySelectorAll(`[data-tab="${tabId}"]`).forEach(b => b.classList.add("active"));
    const target = document.getElementById(tabId);
    if (target) target.classList.remove("hidden");

    isHrMode = (tabId === "tab-hr");
    const heroTitle = document.getElementById("greeting_title");
    const heroSub = document.getElementById("greeting_sub");
    const modeBtn = document.getElementById("mode_switch_btn");

    const floatBar = document.getElementById("hr_floating_action_bar");
    if (floatBar) {
        floatBar.classList.toggle("hidden", !isHrMode || selectedHrIndices.size === 0);
    }

    if (modeBtn) {
        if (isHrMode) {
            modeBtn.innerHTML = '<i class="ion-person"></i> <span>Mode Candidat</span>';
            modeBtn.className = "pill-btn-ghost";
        } else {
            modeBtn.innerHTML = '<i class="ion-speakerphone"></i> <span>Mode Équipe RH</span>';
            modeBtn.className = "pill-btn-primary";
        }
    }

    if (isHrMode) {
        if (heroTitle) heroTitle.innerHTML = 'Espace <span class="underline-blue">Équipe RH</span>';
        if (heroSub) heroSub.textContent = "Importez jusqu'à 50 CV PDF, triez en mode RGPD et pilotez vos entretiens 100 % en local.";
    } else if (!lastReport) {
        if (heroTitle) heroTitle.innerHTML = 'Organisez votre <span class="underline-blue">candidature</span>';
        if (heroSub) heroSub.textContent = "Comparez votre CV et l'offre d'emploi 100 % en local sur CLAVERATS.";
    } else {
        try {
            const _cv = lastReport.cv_details || {}, _job = lastReport.job_details || {};
            if (heroTitle) heroTitle.innerHTML = `Bilan pour <span class="underline-blue">${_cv.full_name || "Candidat"}</span>`;
            if (heroSub && _job.contract_type) heroSub.textContent = `Contrat : ${_job.contract_type} - Lieu : ${_job.location}`;
        } catch (e) {}
    }
}

function handleFileSelect(input, labelId, defaultText) {
    const label = document.getElementById(labelId);
    label.textContent = (input.files && input.files.length > 0)
        ? `Fichier : ${input.files.item(0).name}`
        : defaultText;
}

function handleMultiFiles(input) {
    const label = document.getElementById("hr-files-label");
    label.textContent = (input.files && input.files.length > 0)
        ? `${input.files.length} fichier(s) CV (.PDF) sélectionné(s)`
        : "Sélectionner ou glisser plusieurs CV (.PDF)";
}

function resetForm() {
    document.getElementById("cv_text").value = "";
    document.getElementById("job_text").value = "";
    document.getElementById("job_url").value = "";
    document.getElementById("cv_pdf").value = "";
    document.getElementById("job_pdf").value = "";
    document.getElementById("cv-file-label").textContent = "Importer votre CV (PDF, JPG ou PNG)";
    document.getElementById("job-file-label").textContent = "Importer l'offre en PDF (Optionnel)";
    document.getElementById("alert_box").classList.remove("show");
    document.getElementById("nav_username").textContent = "Candidat CLAVERATS";
    document.getElementById("nav_location").textContent = "Bonjour,";

    document.querySelectorAll(".side-btn, .mob-tab").forEach(b => {
        if (b.dataset.tab !== "tab-scan" && b.dataset.tab !== "tab-hr") {
            b.classList.add("disabled");
        }
    });
    lastReport = null;
    simulatedAddedSkills.clear();
    switchTab("tab-scan");
}

async function runMatching() {
    const alertBox = document.getElementById("alert_box");
    const btn = document.getElementById("btn-analyze");
    alertBox.classList.remove("show");

    const formData = new FormData();
    formData.append("cv_text", document.getElementById("cv_text").value);
    formData.append("job_text", document.getElementById("job_text").value);
    formData.append("job_url", document.getElementById("job_url").value);

    const cvPdf = document.getElementById("cv_pdf");
    if (cvPdf.files && cvPdf.files.length > 0) {
        formData.append("cv_pdf", cvPdf.files.item(0));
    }
    const jobPdf = document.getElementById("job_pdf");
    if (jobPdf.files && jobPdf.files.length > 0) {
        formData.append("job_pdf", jobPdf.files.item(0));
    }

    btn.disabled = true;
    btn.innerHTML = '<i class="ion-load-c"></i> Audit en cours...';

    try {
        const res = await fetch("/api/analyze", { method: "POST", body: formData });
        const data = await res.json();
        if (!data.success) {
            alertBox.textContent = data.message;
            alertBox.classList.add("show");
            return;
        }
        lastReport = data;
        simulatedAddedSkills.clear();
        try {
            localStorage.setItem("claverats_last_candidate", JSON.stringify(data));
        } catch (e) {}

        document.querySelectorAll(".side-btn, .mob-tab").forEach(b => b.classList.remove("disabled"));
        renderAllViews(data);
        switchTab("tab-overview");
    } catch (err) {
        alertBox.textContent = "Erreur de communication avec le serveur Python local.";
        alertBox.classList.add("show");
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="ion-analytics"></i> Lancer l\'audit intelligent';
    }
}

function switchCandidateSkillPill(mode, btnEl) {
    document.querySelectorAll("#cand_skill_pills .seg-pill").forEach(b => b.classList.remove("active"));
    if (btnEl) btnEl.classList.add("active");

    const bMatch = document.getElementById("cand_block_matched");
    const bMiss = document.getElementById("cand_block_missing");
    if (!bMatch || !bMiss) return;

    if (mode === "matched") {
        bMatch.classList.remove("hidden");
        bMiss.classList.add("hidden");
    } else if (mode === "missing") {
        bMatch.classList.add("hidden");
        bMiss.classList.remove("hidden");
    } else {
        bMatch.classList.remove("hidden");
        bMiss.classList.remove("hidden");
    }
}

function toggleSimulatedSkill(skill) {
    if (simulatedAddedSkills.has(skill)) {
        simulatedAddedSkills.delete(skill);
    } else {
        simulatedAddedSkills.add(skill);
    }
    updateSimulatedScoreDisplay();
}

function updateSimulatedScoreDisplay() {
    if (!lastReport) return;
    const base = lastReport.score || 0;
    const proj = lastReport.projected_score || base;
    const totalMiss = (lastReport.missing_skills || []).length;
    let sim = base;
    if (totalMiss > 0 && simulatedAddedSkills.size > 0) {
        sim = Math.round(base + (proj - base) * (simulatedAddedSkills.size / totalMiss));
    }
    document.getElementById("ov_score").textContent = `${sim}%`;
    document.getElementById("ov_projected_hint").textContent = simulatedAddedSkills.size > 0
        ? `Simulé (+${simulatedAddedSkills.size}) • Potentiel : ${proj}%`
        : `Potentiel : ${proj}%`;

    document.getElementById("missing_tags").innerHTML = (lastReport.missing_skills || []).length
        ? lastReport.missing_skills.map(s => {
            const act = simulatedAddedSkills.has(s);
            return `<button type="button" class="skill-tag ${act ? 'tag-ok' : 'tag-miss'}" style="border:none; cursor:pointer;" onclick="toggleSimulatedSkill('${s.replace(/'/g, "\\'")}')">${act ? '✓ ' : '+ '}${s}</button>`;
        }).join("")
        : `<span class="muted-small">Aucun mot-clé manquant !</span>`;
}

function renderAllViews(data) {
    const cv = data.cv_details;
    const job = data.job_details;
    const comp = data.comparison;

    const avatarBox = document.getElementById("nav_initials");
    if (avatarBox) {
        avatarBox.innerHTML = cv.photo ? `<img src="${cv.photo}" alt="Photo CV">` : (cv.initials ? String(cv.initials).slice(0, 2).toUpperCase() : '<i class="ion-person"></i>');
    }

    document.getElementById("nav_username").textContent = cv.full_name || "Candidat";
    document.getElementById("nav_location").textContent = `${cv.main_profession || "Profil"} • ${cv.location}`;
    document.getElementById("greeting_title").innerHTML = `Bilan pour <span class="underline-blue">${cv.full_name}</span>`;
    document.getElementById("greeting_sub").textContent = `Contrat : ${job.contract_type} - Lieu : ${job.location}`;

    const geoB = document.getElementById("geo_banner");
    geoB.textContent = `${comp.geo.badge} - ${comp.geo.message}`;
    geoB.className = comp.geo.status === "compatible" ? "status-banner ok" : "status-banner danger";

    const mailB = document.getElementById("email_trust_banner");
    mailB.textContent = `${job.email_audit.badge} - ${job.email_audit.details}`;
    mailB.className = job.email_audit.trust_pct >= 70 ? "status-banner ok" : "status-banner danger";

    document.getElementById("ov_skills").textContent = `${data.stats.matched_count} / ${data.stats.job_skills_count}`;
    document.getElementById("ov_missing_count").textContent = `${data.stats.missing_count} manquant(s)`;
    document.getElementById("ov_tier_chip").textContent = (data.match_tier || {}).label || "Toutes détectées";
    document.getElementById("ov_exp").textContent = `${cv.exp_years} an(s)`;
    document.getElementById("ov_exp_req").textContent = `${job.required_exp_years} an(s) requis`;
    document.getElementById("ov_posture_chip").textContent = (cv.posture_info || {}).posture || "Polyvalente";
    document.getElementById("ov_seniority_chip").textContent = cv.seniority || "Junior";

    document.getElementById("matched_tags").innerHTML = data.matched_skills.length
        ? data.matched_skills.map(s => `<span class="skill-tag tag-ok">${s}</span>`).join("")
        : `<span class="muted-small">Aucune compétence commune</span>`;

    const catBox = document.getElementById("category_bars");
    if (catBox) {
        catBox.innerHTML = (data.category_breakdown || []).map(c => `
            <div>
                <div class="cat-row-head"><span>${c.category}</span><span>${c.matched}/${c.total} (${c.percent}%)</span></div>
                <div class="cat-track"><div class="cat-fill" style="width:${c.percent}%"></div></div>
            </div>`).join("");
    }

    updateSimulatedScoreDisplay();
    renderProfileAndInterviewViews(data);
}

function openPhotoModal(src, title) {
    if (!src) return;
    const modal = document.getElementById("photo_zoom_modal");
    document.getElementById("photo_modal_title").textContent = title || "Photo du Candidat";
    document.getElementById("photo_modal_body").innerHTML = `<img src="${src}" alt="Photo" style="max-width:100%; max-height:65vh; border-radius:18px; box-shadow:0 10px 25px rgba(0,0,0,0.18);">`;
    modal.classList.remove("hidden");
}

function closePhotoModal() {
    document.getElementById("photo_zoom_modal")?.classList.add("hidden");
}

function openPdfModal(pdfUrl, title) {
    if (!pdfUrl) return;
    const modal = document.getElementById("pdf_preview_modal");
    document.getElementById("pdf_modal_title").textContent = title || "Aperçu Document PDF";
    document.getElementById("pdf_modal_iframe").src = pdfUrl;
    modal.classList.remove("hidden");
}

function closePdfModal() {
    const modal = document.getElementById("pdf_preview_modal");
    if (modal) modal.classList.add("hidden");
    const iframe = document.getElementById("pdf_modal_iframe");
    if (iframe) iframe.src = "";
}

function showNoticeBanner(boxId, msg, isWarn = true) {
    const box = document.getElementById(boxId);
    if (!box) return;
    box.classList.remove("hidden", "is-warn");
    if (isWarn) box.classList.add("is-warn");
    box.innerHTML = `<span class="info-circle-icon"><i class="ion-information"></i></span><span>${msg}</span>`;
}

function renderProfileAndInterviewViews(data) {
    const cv = data.cv_details;
    const job = data.job_details;
    const comp = data.comparison;
    const posture = cv.posture_info || {};
    const ats = cv.ats_audit || { ats_ready_pct: 100, checks: [] };

    const avatarBox = document.getElementById("nav_initials");
    if (avatarBox && cv.photo) {
        avatarBox.onclick = () => openPhotoModal(cv.photo, cv.full_name || "Photo Candidat");
    }

    const gapListEl = document.getElementById("gap_summary_list");
    if (gapListEl) {
        gapListEl.innerHTML = `
            <li><strong>Expérience</strong><span>${comp.exp_status}</span></li>
            <li><strong>Études</strong><span>${comp.edu_status}</span></li>
            <li><strong>Langues</strong><span>${comp.lang_status}</span></li>
        `;
    }

    document.getElementById("edit_name").value = cv.full_name || "";
    if (document.getElementById("edit_profession")) document.getElementById("edit_profession").value = cv.main_profession || "";
    document.getElementById("edit_cand_loc").value = cv.location || "";
    document.getElementById("edit_job_loc").value = job.location || "";
    document.getElementById("edit_cand_exp").value = cv.exp_years || 0;
    document.getElementById("edit_req_exp").value = job.required_exp_years || 0;
    if (document.getElementById("edit_cand_edu")) document.getElementById("edit_cand_edu").value = cv.education_label || "";
    document.getElementById("edit_cand_langs").value = (cv.languages || []).join(", ");
    if (document.getElementById("edit_extra_skills")) {
        document.getElementById("edit_extra_skills").value = (data.matched_skills || []).join(", ");
    }

    verifyFieldAgainstCV("edit_name", "verif_name");
    verifyFieldAgainstCV("edit_cand_loc", "verif_cand_loc");

    const atsBadge = document.getElementById("ats_ready_badge");
    if (atsBadge) atsBadge.textContent = `${ats.ats_ready_pct}% ATS-Ready`;

    const atsList = document.getElementById("ats_checks_list");
    if (atsList) {
        atsList.innerHTML = (ats.checks || []).map(ch => `
            <li><strong>${ch.ok ? '✓' : '⚠'} ${ch.label}</strong><span>${ch.detail}</span></li>
        `).join("");
    }

    const expList = document.getElementById("structured_exp_list");
    if (expList) {
        const exps = cv.structured_experiences || [];
        expList.innerHTML = exps.length
            ? exps.map(ex => `
                <li>
                    <strong>${ex.period} • ${ex.employer} - ${ex.role}</strong>
                    <span>${(ex.tasks && ex.tasks.length) ? ex.tasks.join(" • ") : "Missions générales du poste"}</span>
                </li>
            `).join("")
            : `<li><strong>Parcours</strong><span>Aucune expérience détaillée structurée détectée.</span></li>`;
    }

    const profSum = document.getElementById("profile_summary_list");
    if (profSum) {
        profSum.innerHTML = `
            <li><strong>Profession & Séniorité</strong><span>${cv.main_profession} • ${cv.seniority || ""}</span></li>
            <li><strong>Posture & Impact</strong><span>Posture ${posture.posture || "Polyvalente"} • Impact rédactionnel : ${posture.impact_score || 0}%</span></li>
            <li><strong>Coordonnées</strong><span>${(cv.phones || []).join(" | ") || "Tél N/A"} • ${(cv.emails || []).join(", ") || "Email N/A"}</span></li>
        `;
    }

    document.getElementById("interview_questions_list").innerHTML = (data.interview_questions || []).map((q, i) => `
        <li><strong>Question ${i + 1}</strong><span>${q}</span></li>
    `).join("");

    const intel = (comp.geo || {}).intel || {};
    const commuteTxt = intel.known ? ` • Distance : ${intel.distance_km} km (~${intel.commute_min} min, ${intel.co2_annual_kg} kg CO₂/an)` : "";
    const permitsTxt = (job.required_permits && job.required_permits.length) ? ` • Mobilité : ${job.required_permits.join(", ")}` : "";
    const offerElList = document.getElementById("offer_elements_list");
    if (offerElList) {
        const allReqSkills = [...(data.matched_skills || []), ...(data.missing_skills || [])];
        offerElList.innerHTML = `
            <li><strong>Organisation, Contrat & Durée</strong><span>${job.company_name} - ${job.contract_type} (${job.contract_duration || "Non précisée"}) • Début : ${job.start_date_info || "Dès que possible"}</span></li>
            <li><strong>Lieu, Trajet & Mobilité</strong><span>${job.location} (${comp.geo.badge})${commuteTxt}${permitsTxt}</span></li>
            <li><strong>Expérience & Diplôme exigés</strong><span>${job.required_exp_years} an(s) • ${job.required_edu_label}</span></li>
            <li><strong>Compétences demandées (${allReqSkills.length})</strong><span>${allReqSkills.join(", ") || "Non précisées"}</span></li>
        `;
    }

    const moBaseTitle = document.getElementById("mo_base_offer_title");
    if (moBaseTitle) {
        moBaseTitle.textContent = `${job.company_name} - ${job.contract_type} (${job.location})`;
    }

    document.getElementById("emp_company").textContent = job.company_name || "-";
    document.getElementById("emp_email").textContent = (job.apply_emails && job.apply_emails.length) ? job.apply_emails.join(", ") : "Non mentionné";
    document.getElementById("emp_apply_link").innerHTML = (job.apply_links && job.apply_links.length)
        ? `<a href="${job.apply_links.at(0)}" target="_blank">Postuler en ligne</a>`
        : "Voir annonce";
    document.getElementById("emp_deadline").textContent = `${job.deadline.deadline_date} (${job.deadline.status_label})`;

    const labelsBox = document.getElementById("emp_labels");
    if (labelsBox) {
        labelsBox.innerHTML = `
            <span class="meta-pill">${job.contract_type}</span>
            <span class="meta-pill">${job.location}</span>
            <span class="meta-pill">${job.email_audit.badge}</span>
            <span class="meta-pill">${comp.geo.badge}</span>
        `;
    }

    const cleanFileName = "CV_" + (cv.full_name || "Candidat").trim().replace(/\s+/g, "_") + ".pdf";
    const chkLabel = document.getElementById("chk_cv_filename");
    if (chkLabel) chkLabel.textContent = `CV renommé au nom du candidat (${cleanFileName})`;

    document.getElementById("cover_pitch_box").value = data.cover_pitch || "";
    initCalendar(job.deadline);
    initMiniWeekStrip(job.deadline);
}

function toggleInterviewPractice() {
    if (!lastReport || !lastReport.interview_questions?.length) return;
    const box = document.getElementById("interview_practice_box");
    box.classList.toggle("hidden");
    if (!box.classList.contains("hidden")) {
        practiceQuestionIdx = 0;
        loadPracticeQuestion();
    } else if (practiceInterval) {
        clearInterval(practiceInterval);
    }
}

function loadPracticeQuestion() {
    const qs = lastReport?.interview_questions || [];
    if (!qs.length) return;
    const q = qs[practiceQuestionIdx % qs.length];
    document.getElementById("practice_q_title").textContent = `Question ${(practiceQuestionIdx % qs.length) + 1} / ${qs.length}`;
    document.getElementById("practice_q_text").textContent = q;
    resetPracticeTimer();
}

function nextPracticeQuestion() {
    practiceQuestionIdx += 1;
    loadPracticeQuestion();
}

function resetPracticeTimer() {
    if (practiceInterval) clearInterval(practiceInterval);
    practiceSecondsLeft = 90;
    updateTimerDisplay();
    practiceInterval = setInterval(() => {
        practiceSecondsLeft -= 1;
        updateTimerDisplay();
        if (practiceSecondsLeft <= 0) {
            clearInterval(practiceInterval);
        }
    }, 1000);
}

function updateTimerDisplay() {
    const m = String(Math.floor(Math.max(0, practiceSecondsLeft) / 60)).padStart(2, "0");
    const s = String(Math.max(0, practiceSecondsLeft) % 60).padStart(2, "0");
    const el = document.getElementById("practice_timer_lbl");
    if (el) el.textContent = `${m}:${s}`;
}

function resetMultiOfferSimulator() {
    for (let i = 1; i <= 3; i++) {
        if (document.getElementById(`mo_title_${i}`)) document.getElementById(`mo_title_${i}`).value = "";
        if (document.getElementById(`mo_url_${i}`)) document.getElementById(`mo_url_${i}`).value = "";
        if (document.getElementById(`mo_text_${i}`)) document.getElementById(`mo_text_${i}`).value = "";
        if (document.getElementById(`mo_pdf_${i}`)) document.getElementById(`mo_pdf_${i}`).value = "";
        if (document.getElementById(`mo_pdf_lbl_${i}`)) document.getElementById(`mo_pdf_lbl_${i}`).textContent = "";
    }
    document.getElementById("multi_offer_alert_box")?.classList.add("hidden");
    document.getElementById("multi_offer_matrix_box")?.classList.add("hidden");
    lastMultiOfferMatrix = [];
}

async function runMultiOfferSimulation() {
    if (!lastReport) return;
    const alertBox = document.getElementById("multi_offer_alert_box");
    alertBox?.classList.add("hidden");

    const fd = new FormData();
    fd.append("raw_cv_text", lastReport.raw_cv_text || "");
    fd.append("base_job_text", (lastReport.job_details || {}).raw_job_text || "");
    fd.append("base_job_title", `${(lastReport.job_details || {}).company_name || "Offre Initiale"} (${(lastReport.job_details || {}).location || "Actuelle"})`);

    for (let i = 1; i <= 3; i++) {
        fd.append(`mo_title_${i}`, document.getElementById(`mo_title_${i}`)?.value.trim() || "");
        fd.append(`mo_url_${i}`, document.getElementById(`mo_url_${i}`)?.value.trim() || "");
        fd.append(`mo_text_${i}`, document.getElementById(`mo_text_${i}`)?.value.trim() || "");
        const pdfIn = document.getElementById(`mo_pdf_${i}`);
        if (pdfIn && pdfIn.files && pdfIn.files.length > 0) {
            fd.append(`mo_pdf_${i}`, pdfIn.files.item(0));
        }
    }

    const res = await fetch("/api/multi-offer-simulate", { method: "POST", body: fd });
    const data = await res.json();
    if (!data.success) {
        showNoticeBanner("multi_offer_alert_box", data.message, true);
        return;
    }

    lastMultiOfferMatrix = data.matrix || [];
    activeMultiOfferIdx = 0;
    renderMultiOfferTabsAndCharts();
}

function selectMultiOfferTab(idx) {
    activeMultiOfferIdx = idx;
    renderMultiOfferTabsAndCharts();
}

function renderMultiOfferTabsAndCharts() {
    const box = document.getElementById("multi_offer_matrix_box");
    if (!box || !lastMultiOfferMatrix.length) return;
    box.classList.remove("hidden");

    const tabsHtml = lastMultiOfferMatrix.map((m, idx) => `
        <button type="button" class="seg-pill ${idx === activeMultiOfferIdx ? 'active' : ''}" onclick="selectMultiOfferTab(${idx})">
            #${m.rank} ${m.title} (${m.win_chance}%)
        </button>
    `).join("");

    const cur = lastMultiOfferMatrix.at(activeMultiOfferIdx) || lastMultiOfferMatrix.at(0);
    const totalReq = Math.max(1, cur.matched_count + cur.missing_count);
    const skillPct = Math.round((cur.matched_count / totalReq) * 100);

    box.innerHTML = `
        <div class="card-top-row" style="margin-top:10px;">
            <div class="segmented-pills">${tabsHtml}</div>
            <button type="button" class="pill-btn-ghost" onclick="exportMultiOfferPdf()"><i class="ion-document"></i> Exporter Comparatif PDF</button>
        </div>

        <div class="bento-kpi-3" style="margin-top:14px;">
            <div class="donut-kpi-card">
                <div><span class="kpi-label">Chance Globale</span><div class="kpi-number" style="margin:2px 0;">${cur.win_chance}%</div><span class="trend-mint">Rang #${cur.rank}</span></div>
                <div class="ring-gauge" style="border-color:#10B981;">${cur.win_chance}%</div>
            </div>
            <div class="donut-kpi-card">
                <div><span class="kpi-label">Compétences Voulues</span><div class="kpi-number" style="margin:2px 0;">${cur.matched_count}/${cur.matched_count + cur.missing_count}</div><span class="muted-small">${cur.missing_count} manquante(s)</span></div>
                <div class="ring-gauge" style="border-color:#4A72FF;">${skillPct}%</div>
            </div>
            <div class="donut-kpi-card">
                <div><span class="kpi-label">Marché & Lieu</span><div class="kpi-number" style="font-size:1.25rem; margin:4px 0;">${cur.market_tension}</div><span class="muted-small">${cur.location}</span></div>
                <div class="ring-gauge" style="border-color:#F5A623;">${cur.tech_score}%</div>
            </div>
        </div>

        <div class="bento-grid-2">
            <div class="bento-card" style="padding:16px;">
                <strong style="display:block; margin-bottom:8px; color:#059669;">Compétences que vous avez (${cur.matched_count})</strong>
                <div class="tags-wrap">${(cur.matched_skills || []).map(s => `<span class="skill-tag tag-ok">${s}</span>`).join("") || '<span class="muted-small">Aucune</span>'}</div>
            </div>
            <div class="bento-card" style="padding:16px;">
                <strong style="display:block; margin-bottom:8px; color:#DC2626;">Compétences manquantes (${cur.missing_count})</strong>
                <div class="tags-wrap">${(cur.missing_skills || []).map(s => `<span class="skill-tag tag-miss">${s}</span>`).join("") || '<span class="muted-small">Aucune compétence manquante !</span>'}</div>
            </div>
        </div>
    `;
}

async function exportMultiOfferPdf() {
    if (!lastMultiOfferMatrix.length || !lastReport) return;
    const res = await fetch("/api/export-multi-offer-pdf", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            matrix: lastMultiOfferMatrix,
            candidate_name: (lastReport.cv_details || {}).full_name || "Candidat"
        })
    });
    if (!res.ok) return;
    const a = document.createElement("a");
    a.href = URL.createObjectURL(await res.blob());
    a.download = "Matrice_Multi_Offres_CLAVERATS.pdf";
    a.click();
}


let calViewYear = new Date().getFullYear();
let calViewMonth = new Date().getMonth();
let selectedPlanDate = new Date();
let miniWeekAnchor = new Date();
let favorableIsoSet = new Set();

function initMiniWeekStrip(dl) {
    miniWeekAnchor = new Date();
    miniWeekAnchor.setHours(0, 0, 0, 0);
    favorableIsoSet = new Set((dl && dl.favorable_dates) || []);
    drawMiniWeekStrip();
}

function shiftMiniCalWeek(daysDelta) {
    miniWeekAnchor.setDate(miniWeekAnchor.getDate() + daysDelta);
    drawMiniWeekStrip();
}

function drawMiniWeekStrip() {
    const strip = document.getElementById("mini_week_strip");
    const monthLbl = document.getElementById("mini_cal_month_label");
    if (!strip) return;

    const months = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin", "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"];
    const daysShort = ["Dim", "Lun", "Mar", "Mer", "Jeu", "Ven", "Sam"];
    if (monthLbl) monthLbl.textContent = `${months.at(miniWeekAnchor.getMonth())} ${miniWeekAnchor.getFullYear()}`;

    const today = new Date();
    today.setHours(0, 0, 0, 0);

    let html = "";
    for (let i = -2; i <= 2; i++) {
        const d = new Date(miniWeekAnchor);
        d.setDate(miniWeekAnchor.getDate() + i);
        const iso = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
        let cls = "mini-day-pill";
        if (favorableIsoSet.has(iso)) cls += " is-best";
        else if (d >= today) cls += " is-open";

        html += `
            <div class="${cls}" onclick="selectMiniWeekDay('${iso}')">
                <span>${daysShort.at(d.getDay())}</span>
                <strong style="font-size:1rem;">${d.getDate()}</strong>
            </div>
        `;
    }
    strip.innerHTML = html;
}

function selectMiniWeekDay(iso) {
    const isFav = favorableIsoSet.has(iso);
    const gauge = document.getElementById("mini_cal_gauge");
    const adv = document.getElementById("mini_cal_advice");
    if (gauge) gauge.textContent = isFav ? "92%" : "74%";
    if (adv) adv.textContent = isFav
        ? `Date optimale (${iso}) : fort taux d'ouverture RH !`
        : `Date ouverte (${iso}) : candidature possible.`;
}

function initCalendar(dl) {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    calViewYear = today.getFullYear();
    calViewMonth = today.getMonth();
    selectedPlanDate = new Date(today);
    favorableIsoSet = new Set((dl && dl.favorable_dates) || []);
    document.getElementById("cal_days_badge").textContent = dl.deadline_iso ? `${dl.days_left} j restants` : "Date libre";
    drawCalendarGrid();
}

function changeCalendarMonth(delta) {
    calViewMonth += delta;
    if (calViewMonth > 11) {
        calViewMonth = 0;
        calViewYear += 1;
    } else if (calViewMonth < 0) {
        calViewMonth = 11;
        calViewYear -= 1;
    }
    drawCalendarGrid();
}

function selectCalendarDay(y, m, d) {
    selectedPlanDate = new Date(y, m, d);
    const iso = `${y}-${String(m + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
    const tag = favorableIsoSet.has(iso) ? " (Date favorable recommandée)" : "";
    document.getElementById("selected_date_label").textContent = `Date choisie : ${selectedPlanDate.toLocaleDateString("fr-FR")}${tag}`;
    drawCalendarGrid();
}

function drawCalendarGrid() {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const months = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin", "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"];
    document.getElementById("cal_month_title").textContent = `${months.at(calViewMonth)} ${calViewYear}`;

    const first = new Date(calViewYear, calViewMonth, 1).getDay();
    const offset = first === 0 ? 6 : first - 1;
    const days = new Date(calViewYear, calViewMonth + 1, 0).getDate();
    const grid = document.getElementById("apply_calendar_grid");

    let html = "";
    for (let i = 0; i < offset; i++) html += `<div class="cal-day empty"></div>`;
    for (let d = 1; d <= days; d++) {
        const cell = new Date(calViewYear, calViewMonth, d);
        cell.setHours(0, 0, 0, 0);
        const iso = `${calViewYear}-${String(calViewMonth + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
        let cls = "cal-day";
        if (favorableIsoSet.has(iso)) {
            cls += " favorable-day";
        } else if (cell >= today) {
            cls += " open-apply";
        }
        if (cell.getTime() === selectedPlanDate.getTime()) cls += " is-selected";
        html += `<div class="${cls}" onclick="selectCalendarDay(${calViewYear}, ${calViewMonth}, ${d})">${d}</div>`;
    }
    grid.innerHTML = html;
}

function updateChecklistCount() {
    const boxes = document.querySelectorAll("#apply_checklist input[type='checkbox']");
    const total = boxes.length || 4;
    const checked = Array.from(boxes).filter(b => b.checked).length;
    const pct = Math.round((checked / total) * 100);

    const counter = document.getElementById("checklist_counter");
    if (counter) counter.textContent = `${checked}/${total}`;

    const bar = document.getElementById("checklist_progress_bar");
    if (bar) {
        bar.style.width = `${pct}%`;
        bar.style.background = checked === total ? "#10B981" : "#4A72FF";
    }

    const banner = document.getElementById("checklist_ready_banner");
    if (banner) {
        banner.classList.toggle("hidden", checked < total);
    }
}

function initHrCalendarCombo() {
    const combo = document.getElementById("hr_calendar_combo");
    if (!combo) return;
    const saved = JSON.parse(localStorage.getItem("claverats_hr_cal_links") || "null") || [
        { label: "Aucun lien (Entretien sur place)", url: "" },
        { label: "Entretien Découverte (15 min)", url: "https://calendly.com" },
        { label: "Entretien Technique (1h)", url: "https://calendly.com" }
    ];
    localStorage.setItem("claverats_hr_cal_links", JSON.stringify(saved));
    combo.innerHTML = saved.map((item, idx) => `<option value="${item.url}">${item.label}</option>`).join("");
}

function promptNewCalendarLink() {
    const label = prompt("Nom du créneau (ex: Visio RH 30 min) :");
    if (!label) return;
    const url = prompt("Lien de réservation (ex: https://calendly.com...) :") || "";
    const saved = JSON.parse(localStorage.getItem("claverats_hr_cal_links") || "[]");
    saved.push({ label, url });
    localStorage.setItem("claverats_hr_cal_links", JSON.stringify(saved));
    initHrCalendarCombo();
    const combo = document.getElementById("hr_calendar_combo");
    if (combo) combo.selectedIndex = saved.length - 1;
    renderHrMasterDetail();
}

function applySelectedCalendarLink() {
    renderHrMasterDetail();
}

function updateTopNButtonLabel() {
    const n = document.getElementById("hr_positions_count")?.value || "3";
    const btn = document.getElementById("btn_select_top_n");
    if (btn) btn.textContent = `Sélectionner Top ${n}`;
}

function toggleAnonymousMode() {
    isAnonymousMode = !isAnonymousMode;
    const btn = document.getElementById("btn_anon_mode");
    if (btn) {
        btn.innerHTML = isAnonymousMode
            ? '<i class="ion-eye"></i> RGPD : ACTIF'
            : '<i class="ion-eye-disabled"></i> Anonymiser (RGPD)';
    }
    if (lastHrReport) {
        renderHrTableAndMaster();
        updateHrFaceToFace();
    }
}

async function runHrBatch() {
    const noticeBox = document.getElementById("hr_form_notice_box");
    const btn = document.getElementById("btn-hr-analyze");
    noticeBox?.classList.add("hidden");

    const jobText = document.getElementById("hr_job_text")?.value.trim() || "";
    const jobUrl = document.getElementById("hr_job_url")?.value.trim() || "";
    const jobPdf = document.getElementById("hr_job_pdf");
    const filesInput = document.getElementById("hr_cv_files");

    const hasOffer = jobText.length >= 10 || jobUrl.length >= 6 || (jobPdf && jobPdf.files && jobPdf.files.length > 0);
    const hasCvs = filesInput && filesInput.files && filesInput.files.length > 0;

    if (!hasOffer && !hasCvs) {
        showNoticeBanner("hr_form_notice_box", "Veuillez importer au moins un CV (.PDF) et renseigner la description du poste (texte, lien URL ou PDF) avant d'analyser.", true);
        return;
    }
    if (!hasCvs) {
        showNoticeBanner("hr_form_notice_box", "Veuillez sélectionner ou glisser au moins un fichier CV (.PDF) dans la zone de gauche.", true);
        return;
    }
    if (!hasOffer) {
        showNoticeBanner("hr_form_notice_box", "Veuillez renseigner l'offre d'emploi à pourvoir (collez le texte, indiquez un lien URL ou importez un PDF).", true);
        return;
    }

    const formData = new FormData();
    formData.append("hr_job_text", jobText);
    formData.append("hr_job_url", jobUrl);
    formData.append("positions_count", document.getElementById("hr_positions_count").value || "3");
    formData.append("tech_weight", document.getElementById("hr_tech_weight")?.value || "60");

    if (jobPdf && jobPdf.files && jobPdf.files.length > 0) {
        formData.append("hr_job_pdf", jobPdf.files.item(0));
    }
    for (let i = 0; i < filesInput.files.length; i++) {
        formData.append("hr_cv_files", filesInput.files.item(i));
    }

    btn.disabled = true;
    btn.innerHTML = '<i class="ion-load-c"></i> Classement en cours...';

    try {
        const res = await fetch("/api/hr-batch", { method: "POST", body: formData });
        const data = await res.json();
        if (!data.success) {
            showNoticeBanner("hr_form_notice_box", data.message, true);
            return;
        }
        lastHrReport = data;
        selectedHrIndices.clear();
        activeHrDetailIdx = 0;
        hrQuickFilter = "all";
        hrReadFilter = "all";
        hrCityFilter = "";

        refreshHrDashboardMetrics();
        document.getElementById("hr_results_area").classList.remove("hidden");
    } catch (err) {
        showNoticeBanner("hr_form_notice_box", "Erreur de communication avec le serveur Python local.", true);
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="ion-speakerphone"></i> Analyser et classer tous les CV reçus';
    }
}

function refreshHrDashboardMetrics() {
    if (!lastHrReport || !lastHrReport.candidates) return;
    const cands = lastHrReport.candidates;
    const total = cands.length || 1;

    const goodCount = cands.filter(c => c.score >= 45).length;
    const goodPct = Math.round((goodCount / total) * 100);
    const avgS = Math.round(cands.reduce((acc, c) => acc + (c.score || 0), 0) / total);

    const cleanC = cands.filter(c => c.readability === "clean").length;
    const partC = cands.filter(c => c.readability === "partial").length;
    const unreadC = cands.filter(c => c.readability === "unreadable").length;

    document.getElementById("hr_total_cv").textContent = cands.length;
    document.getElementById("hr_wanted_chip").textContent = `Voulu : ${lastHrReport.positions_count || 3}`;
    document.getElementById("hr_quota_label").textContent = `Moyenne : ${avgS}%`;
    document.getElementById("hr_top_count").textContent = goodCount;
    document.getElementById("hr_top_pct_label").textContent = `${goodPct}% de la cohorte`;
    const rSum = document.getElementById("hr_readability_summary");
    if (rSum) rSum.textContent = `${cleanC} / ${partC} / ${unreadC}`;
    document.getElementById("hr_dup_count").textContent = lastHrReport.duplicates_count || 0;

    const mBanner = document.getElementById("hr_market_alert_banner");
    if (mBanner) {
        mBanner.textContent = lastHrReport.market_alert || "Cohortes analysées avec succès.";
        mBanner.className = (lastHrReport.market_alert || "").includes("Alerte") ? "status-banner danger" : "status-banner ok";
    }

    renderHrBarsChart(lastHrReport);
    renderHrLeafletMap(lastHrReport);
    renderHrTableAndMaster();
    updateHrSelectionUI();
}

function renderHrBarsChart(data) {
    const box = document.getElementById("hr_performance_chart_box");
    const badge = document.getElementById("hr_perf_badge");
    if (!box || !data.candidates) return;

    if (badge) badge.textContent = `${data.candidates.length} CV classés`;

    box.innerHTML = `<div class="hr-bars-chart">` + data.candidates.map((c, idx) => {
        const bg = c.score >= 75 ? "#10B981" : (c.score >= 45 ? "#F59E0B" : "#EF4444");
        const blurCls = isAnonymousMode ? "rgpd-blur" : "";
        const dispName = (c.name && c.name !== "Candidat") ? c.name.split(" ").at(0) : (c.filename || `CV#${idx + 1}`).slice(0, 10);
        const barH = c.score === 0 ? 6 : Math.max(12, c.score);
        return `
            <div class="hr-bar-col" onclick="selectHrDetailCandidate(${idx})" title="${c.name} (${c.filename || ''}) : ${c.score}%">
                <strong style="font-size:0.74rem; color:${c.score === 0 ? '#EF4444' : 'inherit'};">${c.score}%</strong>
                <div class="hr-bar-fill" style="height:${barH}%; background:${bg};"></div>
                <span class="muted-small ${blurCls}" style="font-size:0.7rem; max-width:58px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${dispName}</span>
            </div>
        `;
    }).join("") + `</div>`;
}

function setHrQuickFilter(mode, btnEl) {
    hrQuickFilter = mode;
    document.querySelectorAll("#hr_score_pills .seg-pill").forEach(b => b.classList.remove("active"));
    if (btnEl) btnEl.classList.add("active");
    renderHrTableAndMaster();
}

function setHrReadFilter(mode, btnEl) {
    hrReadFilter = mode;
    document.querySelectorAll("#hr_read_pills .seg-pill").forEach(b => b.classList.remove("active"));
    if (btnEl) btnEl.classList.add("active");
    renderHrTableAndMaster();
}

function getFilteredHrCandidates() {
    if (!lastHrReport || !lastHrReport.candidates) return [];
    const q = (document.getElementById("hr_search_input")?.value || "").toLowerCase();
    return lastHrReport.candidates.map((c, idx) => ({ ...c, _origIdx: idx })).filter(c => {
        const tierCode = (c.match_tier || {}).code || "mid";
        if (hrQuickFilter !== "all" && tierCode !== hrQuickFilter) return false;
        if (hrReadFilter !== "all" && (c.readability || "clean") !== hrReadFilter) return false;
        if (hrCityFilter && !(c.location || "").toLowerCase().includes(hrCityFilter.toLowerCase())) return false;
        if (q) {
            const hay = `${c.name} ${c.filename || ""} ${c.main_profession} ${c.location} ${(c.matched_skills || []).join(" ")}`.toLowerCase();
            if (!hay.includes(q)) return false;
        }
        return true;
    });
}

function selectHrDetailCandidate(origIdx) {
    activeHrDetailIdx = origIdx;
    renderHrTableAndMaster();
}

function filterHrCards() {
    renderHrTableAndMaster();
}

let editingHrCandidateIdx = null;

function renderHrTableAndMaster() {
    const tbody = document.getElementById("hr_table_body");
    if (!tbody || !lastHrReport) return;

    const list = getFilteredHrCandidates();
    const blurCls = isAnonymousMode ? "rgpd-blur" : "";

    const readLabels = {
        clean: { cls: "read-clean", txt: "100 % Lisible" },
        partial: { cls: "read-partial", txt: "Partiel / Complexe" },
        unreadable: { cls: "read-unreadable", txt: "Illisible (Image)" }
    };

    tbody.innerHTML = list.map(c => {
        const idx = c._origIdx;
        const checked = selectedHrIndices.has(idx);
        const activeRow = (idx === activeHrDetailIdx) ? "active-row" : "";
        const tier = c.match_tier || { code: "mid", label: "Moyen" };
        const rd = readLabels[c.readability || "clean"] || readLabels.clean;
        const avatarHtml = c.photo ? `<img src="${c.photo}" alt="Avatar">` : String(c.initials || "CV").slice(0, 2).toUpperCase();
        const dupTag = c.is_duplicate ? `<span class="dup-badge">Doublon</span>` : "";

        return `
            <tr class="${activeRow}" onclick="selectHrDetailCandidate(${idx})">
                <td onclick="event.stopPropagation()">
                    <input type="checkbox" ${checked ? "checked" : ""} onchange="toggleHrCandidateCheck(${idx})" style="width:17px; height:17px; accent-color:#4A72FF;">
                </td>
                <td onclick="event.stopPropagation(); ${c.photo ? `openPhotoModal('${c.photo}', '${(c.name || '').replace(/'/g, "\\'")}')` : ''}">
                    <div class="table-avatar ${blurCls}" title="${c.photo ? 'Cliquez pour agrandir la photo' : ''}">${avatarHtml}</div>
                </td>
                <td>
                    <strong class="${blurCls}">${c.name}</strong>${dupTag}
                    <div class="muted-small">${c.main_profession}</div>
                    <div class="muted-small" style="font-size:0.7rem;">${c.filename || ""}</div>
                </td>
                <td><strong>${c.exp_years} an(s)</strong><div class="muted-small">${c.seniority || ""}</div></td>
                <td class="${blurCls}">${c.location || "Non précisée"}</td>
                <td class="${blurCls}">
                    <div>${c.phone || "Tél N/A"}</div>
                    <div class="muted-small">${c.email || "Email N/A"}</div>
                </td>
                <td>
                    <span class="read-badge ${rd.cls}">${rd.txt}</span><br>
                    <span class="tier-badge tier-${tier.code}">${c.score}% • ${tier.label}</span>
                </td>
                <td onclick="event.stopPropagation()">
                    <div style="display:flex; gap:5px; flex-wrap:wrap;">
                        ${c.pdf_url ? `<button type="button" class="pill-btn-ghost" style="padding:4px 9px; font-size:0.74rem;" onclick="openPdfModal('${c.pdf_url}', '${(c.filename || c.name).replace(/'/g, "\\'")}')">Voir PDF</button>` : ""}
                        <button type="button" class="pill-btn-primary" style="padding:4px 9px; font-size:0.74rem;" onclick="openHrManualEditor(${idx})">Corriger</button>
                    </div>
                </td>
            </tr>
        `;
    }).join("");

    renderSelectedCandidateKpiStrip();
    renderHrMasterDetail();
}

function renderSelectedCandidateKpiStrip() {
    const strip = document.getElementById("hr_selected_kpi_strip");
    if (!strip || !lastHrReport || !lastHrReport.candidates?.length) return;
    const cand = lastHrReport.candidates.at(activeHrDetailIdx) || lastHrReport.candidates.at(0);
    const axes = cand.radar_axes || {};
    const jobSkillsCount = Math.max(1, (lastHrReport.job_skills || []).length);
    const matchedCount = (cand.matched_skills || []).length;

    strip.innerHTML = `
        <div class="donut-kpi-card">
            <div><span class="kpi-label">Score Global Profil</span><div class="kpi-number" style="margin:2px 0;">${cand.score}%</div><span class="trend-mint">${(cand.match_tier || {}).label || ""}</span></div>
            <div class="ring-gauge" style="border-color:#10B981;">${cand.score}%</div>
        </div>
        <div class="donut-kpi-card">
            <div><span class="kpi-label">Compétences Voulues</span><div class="kpi-number" style="margin:2px 0;">${matchedCount}/${jobSkillsCount}</div><span class="muted-small">${(cand.missing_skills || []).length} manquante(s)</span></div>
            <div class="ring-gauge" style="border-color:#4A72FF;">${axes.Technique || 0}%</div>
        </div>
        <div class="donut-kpi-card">
            <div><span class="kpi-label">Expérience & Posture</span><div class="kpi-number" style="margin:2px 0;">${cand.exp_years} an(s)</div><span class="muted-small">${cand.posture || "Polyvalente"}</span></div>
            <div class="ring-gauge" style="border-color:#F5A623;">${axes.Expérience || 0}%</div>
        </div>
        <div class="donut-kpi-card">
            <div><span class="kpi-label">Diplôme & Langues</span><div class="kpi-number" style="font-size:1.1rem; margin:4px 0;">${cand.seniority || ""}</div><span class="muted-small">${(cand.languages || []).join(", ") || "FR"}</span></div>
            <div class="ring-gauge" style="border-color:#8B5CF6;">${axes.Diplômes || 0}%</div>
        </div>
    `;
}

function renderHrMasterDetail() {
    const sideList = document.getElementById("hr_dark_sidebar_list");
    const detailPane = document.getElementById("hr_dark_detail_pane");
    if (!sideList || !detailPane || !lastHrReport) return;

    const goodList = lastHrReport.candidates
        .map((c, idx) => ({ ...c, _origIdx: idx }))
        .filter(c => c.score >= 45);

    const blurCls = isAnonymousMode ? "rgpd-blur" : "";

    if (!goodList.length) {
        sideList.innerHTML = `<p style="opacity:0.75; font-size:0.84rem; padding:12px;">Aucun profil retenu (≥ 45 %) pour le moment. Utilisez "Corriger" dans le tableau ci-dessus pour compléter un CV complexe.</p>`;
        detailPane.innerHTML = `<p style="opacity:0.75;">Sélectionnez ou corrigez un candidat dans le tableau pour afficher sa fiche d'entretien ici.</p>`;
        return;
    }

    sideList.innerHTML = goodList.map(c => {
        const idx = c._origIdx;
        const activeCls = (idx === activeHrDetailIdx) ? "is-active" : "";
        const avatarHtml = c.photo ? `<img src="${c.photo}" alt="Avatar">` : String(c.initials || "CV").slice(0, 2).toUpperCase();
        return `
            <div class="dark-cand-item ${activeCls}" onclick="selectHrDetailCandidate(${idx})">
                <div style="display:flex; align-items:center; gap:10px; min-width:0;">
                    <div class="table-avatar ${blurCls}" style="width:36px; height:36px;">${avatarHtml}</div>
                    <div style="min-width:0;">
                        <strong class="${blurCls}" style="display:block; font-size:0.86rem; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${c.name}</strong>
                        <small style="opacity:0.75; font-size:0.74rem;">#${c.rank} • ${c.posture || "Polyvalente"}</small>
                    </div>
                </div>
                <span style="font-weight:800; font-size:0.85rem;">${c.score}%</span>
            </div>
        `;
    }).join("");

    const cand = lastHrReport.candidates.at(activeHrDetailIdx);
    const displayedCand = (cand && cand.score >= 45) ? cand : goodList.at(0);
    const dispIdx = (cand && cand.score >= 45) ? activeHrDetailIdx : goodList.at(0)._origIdx;

    const calUrl = document.getElementById("hr_calendar_combo")?.value || "";
    const dtVal = document.getElementById("hr_invite_datetime")?.value.trim() || "";
    const firstName = (displayedCand.name || "Candidat").split(" ").at(0);
    const bestSkill = (displayedCand.matched_skills && displayedCand.matched_skills.length) ? displayedCand.matched_skills.at(0) : "votre parcours";

    const inviteText = `Bonjour ${firstName}, votre profil (notamment votre maîtrise de ${bestSkill}) a retenu notre attention. Nous souhaitons vous convier à un entretien.${dtVal ? " Créneau : " + dtVal + "." : ""}${calUrl ? " Réservez votre créneau ici : " + calUrl : ""}`;
    const rejectText = `Bonjour ${firstName}, merci pour l'intérêt porté à notre offre. Bien que nous ayons apprécié votre profil (en particulier ${bestSkill}), nous avons retenu d'autres candidatures pour ce poste. Nous conservons votre CV dans notre vivier.`;

    const waDigits = (displayedCand.phone || "").split("[").at(0).replace(/\D/g, "");
    const waUrl = (!isAnonymousMode && waDigits.length >= 8) ? `https://wa.me/${waDigits}?text=${encodeURIComponent(inviteText)}` : "#";
    const mailInviteUrl = (!isAnonymousMode && displayedCand.email) ? `mailto:${displayedCand.email}?subject=${encodeURIComponent("Invitation Entretien")}&body=${encodeURIComponent(inviteText)}` : "#";
    const mailRejectUrl = (!isAnonymousMode && displayedCand.email) ? `mailto:${displayedCand.email}?subject=${encodeURIComponent("Suite à votre candidature")}&body=${encodeURIComponent(rejectText)}` : "#";

    const geoTxt = displayedCand.distance_km != null ? `${displayedCand.distance_km} km (${displayedCand.commute_min} min • ${displayedCand.co2_annual_kg} kg CO₂/an)` : "Distance locale N/A";
    const expsHtml = (displayedCand.structured_experiences || []).slice(0, 2).map(e => `${e.period} : ${e.role} (${e.employer})`).join(" | ");

    detailPane.innerHTML = `
        <div>
            <div class="card-top-row" style="margin-bottom:10px;">
                <div>
                    <h3 class="${blurCls}" style="font-size:1.25rem; font-weight:800;">${displayedCand.name}</h3>
                    <p style="color:#9CA3AF; font-size:0.85rem;">${displayedCand.main_profession} • ${displayedCand.education}</p>
                </div>
                <span class="chip-mint">${displayedCand.score}% Matching</span>
            </div>
            <p style="font-size:0.84rem; color:#D1D5DB; margin-bottom:10px;">${displayedCand.objective || ""}</p>
            ${expsHtml ? `<p style="font-size:0.78rem; color:#FCD34D; margin-bottom:12px;"><b>Parcours :</b> ${expsHtml}</p>` : ""}

            <div class="dark-metrics-grid" style="margin-bottom:14px;">
                <div class="dark-metric-box"><small>Séniorité & Expérience</small><strong>${displayedCand.exp_years} an(s) • ${displayedCand.seniority || ""}</strong></div>
                <div class="dark-metric-box"><small>Posture Dominante</small><strong>${displayedCand.posture || "Polyvalente"}</strong></div>
                <div class="dark-metric-box"><small>Trajet & Empreinte CO₂</small><strong style="font-size:0.86rem;">${geoTxt}</strong></div>
            </div>

            ${skillChipsHtml(displayedCand.matched_skills, "ok", 10, "Compétences validées")}
            ${skillChipsHtml(displayedCand.missing_skills, "ko", 8, "Points à vérifier", "Aucun écart majeur")}
        </div>

        <div style="display:flex; gap:8px; flex-wrap:wrap; padding-top:14px; border-top:1px solid rgba(255,255,255,0.1);">
            ${waUrl !== "#" ? `<a href="${waUrl}" target="_blank" class="pill-btn-primary" style="background:#10B981;"><i class="ion-social-whatsapp"></i> WhatsApp</a>` : ""}
            ${mailInviteUrl !== "#" ? `<a href="${mailInviteUrl}" class="pill-btn-primary"><i class="ion-email"></i> Convoquer</a>` : ""}
            ${mailRejectUrl !== "#" ? `<a href="${mailRejectUrl}" class="pill-btn-ghost" style="background:rgba(255,255,255,0.08); color:#FFF; border-color:rgba(255,255,255,0.15);">Refus bienveillant</a>` : ""}
            <button type="button" class="pill-btn-ghost" style="background:rgba(255,255,255,0.08); color:#FFF; border-color:rgba(255,255,255,0.15);" onclick="exportPredictiveTxt(${dispIdx})">Guide Prédictif (.TXT)</button>
            <button type="button" class="pill-btn-ghost" style="background:rgba(255,255,255,0.08); color:#FFF; border-color:rgba(255,255,255,0.15);" onclick="exportScorecardPdf(${dispIdx})">Scorecard PDF</button>
        </div>
    `;
}

function openHrManualEditor(idx) {
    if (!lastHrReport || !lastHrReport.candidates) return;
    const cand = lastHrReport.candidates.at(idx);
    if (!cand) return;
    editingHrCandidateIdx = idx;
    activeHrDetailIdx = idx;

    document.getElementById("hr_editor_title").textContent = `Corriger / Compléter : ${cand.name} (${cand.filename || "CV"})`;
    document.getElementById("hr_ed_name").value = cand.name || "";
    document.getElementById("hr_ed_prof").value = cand.main_profession || "";
    document.getElementById("hr_ed_exp").value = cand.exp_years || 0;
    document.getElementById("hr_ed_loc").value = cand.location || "";
    document.getElementById("hr_ed_phone").value = cand.phone || "";
    document.getElementById("hr_ed_email").value = cand.email || "";
    document.getElementById("hr_ed_edu").value = cand.education || "";
    document.getElementById("hr_ed_posture").value = cand.posture || "Polyvalente";
    document.getElementById("hr_ed_skills").value = (cand.matched_skills || []).join(", ");

    const card = document.getElementById("hr_manual_editor_card");
    card.classList.remove("hidden");
    card.scrollIntoView({ behavior: "smooth", block: "center" });
}

function closeHrManualEditor() {
    document.getElementById("hr_manual_editor_card")?.classList.add("hidden");
    editingHrCandidateIdx = null;
}

function openActiveCandidatePdf() {
    if (!lastHrReport || editingHrCandidateIdx == null) return;
    const cand = lastHrReport.candidates.at(editingHrCandidateIdx);
    if (cand && cand.pdf_url) {
        openPdfModal(cand.pdf_url, cand.filename || cand.name);
    }
}

async function saveHrManualCandidateEdit() {
    if (!lastHrReport || editingHrCandidateIdx == null) return;
    const cand = lastHrReport.candidates.at(editingHrCandidateIdx);
    if (!cand) return;

    cand.name = document.getElementById("hr_ed_name").value.trim() || "Candidat";
    cand.main_profession = document.getElementById("hr_ed_prof").value.trim() || "Profil";
    cand.exp_years = parseFloat(document.getElementById("hr_ed_exp").value || "0");
    cand.location = document.getElementById("hr_ed_loc").value.trim() || "Non précisée";
    cand.phone = document.getElementById("hr_ed_phone").value.trim();
    cand.email = document.getElementById("hr_ed_email").value.trim();
    cand.education = document.getElementById("hr_ed_edu").value.trim() || "Non précisé";
    cand.posture = document.getElementById("hr_ed_posture").value;
    cand.matched_skills = document.getElementById("hr_ed_skills").value;

    const res = await fetch("/api/hr-recalculate-candidate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            candidate: cand,
            job_details: lastHrReport.job_details || {},
            job_skills: lastHrReport.job_skills || [],
            tech_weight: lastHrReport.tech_weight || 60
        })
    });
    const data = await res.json();
    if (data.success && data.candidate) {
        lastHrReport.candidates[editingHrCandidateIdx] = data.candidate;
        lastHrReport.candidates.sort(rankCmp);
        lastHrReport.candidates.forEach((c, i) => { c.rank = i + 1; });
        closeHrManualEditor();
        refreshHrDashboardMetrics();
    }
}

function renderHrLeafletMap(data) {
    const mapDiv = document.getElementById("hr_leaflet_map");
    if (!mapDiv) return;
    const clusters = (data && data.city_clusters) || [];
    const job = data && (data.job_coords || (data.job_details && data.job_details.job_coords));
    const hasJob = job && typeof job.lat === "number";
    if (!clusters.length && !hasJob) {
        if (mapDiv._gm) mapDiv._gm.destroy();
        mapDiv.innerHTML = `<p class="muted-small" style="padding:20px; text-align:center;">Aucune localisation détectée dans les CV importés.</p>`;
        return;
    }
    // Carte interactive 100 % locale (static/js/geomap.js) : pays, relief, zoom, survol, marqueurs animés
    const filt = (hrCityFilter || "").toLowerCase();
    const selected = clusters.find(c => filt && (c.city || "").toLowerCase() === filt);
    const pins = clusters.map(cl => ({
        id: cl.city, kind: "cluster", count: cl.count, priority: cl.count,
        label: (cl.city || "Ville").split(",")[0],
        sub: `${cl.count} candidat(s) • Moy. ${cl.avg_score}%` + (cl.distance_km != null ? ` • ${cl.distance_km} km` : ""),
        lat: cl.coords && cl.coords.lat, lon: cl.coords && cl.coords.lon
    }));
    if (hasJob) {
        pins.push({
            id: "__offer", kind: "offer", priority: 1e6,
            label: "OFFRE : " + ((data.job_details && data.job_details.location) || "Poste").split(",")[0],
            sub: "Lieu du poste à pourvoir", lat: job.lat, lon: job.lon
        });
    }
    GeoMap.mount(mapDiv, {
        pins, selectedId: selected ? selected.city : null,
        label: "Carte des candidatures par ville. Utilisez Tab pour parcourir les villes, Entrée pour filtrer.",
        onPinClick: id => { if (id !== "__offer") selectLocalMapCity(id); }
    });
}

function selectLocalMapCity(cityName) {
    if (!lastHrReport || !lastHrReport.city_clusters) return;
    hrCityFilter = cityName;
    const cl = lastHrReport.city_clusters.find(c => (c.city || "").toLowerCase() === cityName.toLowerCase());
    const infoBox = document.getElementById("hr_geo_city_info");
    if (infoBox && cl) {
        const distTxt = cl.distance_km != null ? ` • Trajet : ${cl.distance_km} km (${cl.commute_min} min) • ${cl.co2_annual_kg} kg CO₂/an` : "";
        infoBox.textContent = `Filtre actif : ${cl.city} - ${cl.count} candidat(s) (Moyenne ${cl.avg_score}%)${distTxt}`;
    }
    renderHrLeafletMap(lastHrReport);
    renderHrTableAndMaster();
}

function clearCityFilter() {
    hrCityFilter = "";
    const infoBox = document.getElementById("hr_geo_city_info");
    if (infoBox) infoBox.textContent = "Filtre géographique réinitialisé : affichage de toutes les villes.";
    renderHrTableAndMaster();
}

async function recalculateReport() {
    if (!lastReport) return;
    lastReport.cv_details.full_name = document.getElementById("edit_name").value.trim() || "Candidat";
    if (document.getElementById("edit_profession")) {
        lastReport.cv_details.main_profession = document.getElementById("edit_profession").value.trim() || lastReport.cv_details.main_profession;
    }
    lastReport.cv_details.location = document.getElementById("edit_cand_loc").value.trim() || "Non précisée";
    lastReport.cv_details.exp_years = parseFloat(document.getElementById("edit_cand_exp").value || "0");
    if (document.getElementById("edit_cand_edu")) {
        lastReport.cv_details.education_label = document.getElementById("edit_cand_edu").value.trim() || lastReport.cv_details.education_label;
    }
    const langsVal = document.getElementById("edit_cand_langs")?.value || "";
    if (langsVal.trim()) {
        lastReport.cv_details.languages = langsVal.split(",").map(s => s.trim()).filter(Boolean);
    }

    const extraSkillsVal = document.getElementById("edit_extra_skills")?.value || "";
    if (extraSkillsVal.trim()) {
        const userSkills = extraSkillsVal.split(",").map(s => s.trim()).filter(Boolean);
        const userLower = new Set(userSkills.map(s => s.toLowerCase()));
        const allOfferSkills = [...(lastReport.matched_skills || []), ...(lastReport.missing_skills || [])];
        lastReport.matched_skills = allOfferSkills.filter(s => userLower.has(s.toLowerCase()));
        lastReport.missing_skills = allOfferSkills.filter(s => !userLower.has(s.toLowerCase()));
    }

    lastReport.job_details.location = document.getElementById("edit_job_loc").value.trim() || "Non précisée";
    lastReport.job_details.required_exp_years = parseFloat(document.getElementById("edit_req_exp").value || "0");

    const res = await fetch("/api/recalculate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(lastReport)
    });
    const updated = await res.json();
    if (updated.success) {
        lastReport = updated;
        renderAllViews(updated);
        switchTab("tab-overview");
    }
}

function selectTopN() {
    if (!lastHrReport) return;
    const n = Math.max(1, parseInt(document.getElementById("hr_positions_count").value || "3", 10));
    selectedHrIndices.clear();
    lastHrReport.candidates.slice(0, n).forEach((_, i) => selectedHrIndices.add(i));
    renderHrTableAndMaster();
    updateHrSelectionUI();
}

function toggleSelectAllHr() {
    if (!lastHrReport) return;
    if (selectedHrIndices.size === lastHrReport.candidates.length) {
        selectedHrIndices.clear();
    } else {
        lastHrReport.candidates.forEach((_, i) => selectedHrIndices.add(i));
    }
    renderHrTableAndMaster();
    updateHrSelectionUI();
}

function toggleHrCandidateCheck(idx) {
    if (selectedHrIndices.has(idx)) {
        selectedHrIndices.delete(idx);
    } else {
        selectedHrIndices.add(idx);
    }
    renderHrTableAndMaster();
    updateHrSelectionUI();
}

function updateHrSelectionUI() {
    const count = selectedHrIndices.size;
    const bar = document.getElementById("hr_floating_action_bar");
    document.getElementById("hr_selected_count_label").textContent = `${count} candidat(s) sélectionné(s)`;
    const duelTag = document.getElementById("duel_status_tag");
    if (duelTag) duelTag.textContent = `${Math.min(count, 2)}/2`;
    if (bar) bar.classList.toggle("hidden", !isHrMode || count === 0);
    updateHrFaceToFace();
}

function buildRadarSvg(c1, c2) {
    const axes = ["Technique", "Expérience", "Diplômes", "Langues", "Adéquation"];
    const cx = 130, cy = 125, rMax = 82;
    const angles = axes.map((_, i) => (Math.PI * 2 * i) / axes.length - Math.PI / 2);

    const getPoints = (cand) => axes.map((ax, i) => {
        const val = ((cand.radar_axes && cand.radar_axes[ax]) || cand.score || 50) / 100;
        const x = cx + rMax * val * Math.cos(angles.at(i));
        const y = cy + rMax * val * Math.sin(angles.at(i));
        return `${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(" ");

    const gridPolys = [0.33, 0.66, 1].map(scale => {
        const pts = angles.map(a => `${(cx + rMax * scale * Math.cos(a)).toFixed(1)},${(cy + rMax * scale * Math.sin(a)).toFixed(1)}`).join(" ");
        return `<polygon points="${pts}" fill="none" stroke="#CBD5E1" stroke-width="1"/>`;
    }).join("");

    const labels = axes.map((ax, i) => {
        const lx = cx + (rMax + 22) * Math.cos(angles.at(i));
        const ly = cy + (rMax + 16) * Math.sin(angles.at(i));
        return `<text x="${lx.toFixed(1)}" y="${ly.toFixed(1)}" font-size="10" font-weight="700" text-anchor="middle" fill="currentColor">${ax}</text>`;
    }).join("");

    return `
        <svg width="260" height="250" viewBox="0 0 260 250">
            ${gridPolys}
            <polygon points="${getPoints(c1)}" fill="rgba(74,114,255,0.22)" stroke="#4A72FF" stroke-width="2.5"/>
            <polygon points="${getPoints(c2)}" fill="rgba(245,166,35,0.22)" stroke="#F5A623" stroke-width="2.5"/>
            ${labels}
        </svg>
    `;
}

function updateHrFaceToFace() {
    const emptyEl = document.getElementById("hr_duel_empty_state");
    const activeEl = document.getElementById("hr_duel_active_content");
    if (!lastHrReport || selectedHrIndices.size !== 2) {
        if (emptyEl) emptyEl.classList.remove("hidden");
        if (activeEl) activeEl.classList.add("hidden");
        return;
    }
    const arr = Array.from(selectedHrIndices);
    const c1 = lastHrReport.candidates.at(arr.at(0));
    const c2 = lastHrReport.candidates.at(arr.at(1));
    const n1 = isAnonymousMode ? `Candidat #${c1.rank}` : c1.name;
    const n2 = isAnonymousMode ? `Candidat #${c2.rank}` : c2.name;

    emptyEl.classList.add("hidden");
    activeEl.classList.remove("hidden");

    document.getElementById("hr_duel_cards_pair").innerHTML = [c1, c2].map((c, i) => `
        <div class="bento-card ${i === 0 && c1.score >= c2.score ? 'pastel-cream' : ''}" style="padding:14px;">
            <strong>${i === 0 ? n1 : n2} (${c.score}%)</strong>
            <p class="muted-small">${c.main_profession} • ${c.exp_years} an(s)</p>
        </div>
    `).join("");

    const radarBox = document.getElementById("hr_radar_svg_container");
    if (radarBox) radarBox.innerHTML = buildRadarSvg(c1, c2);

    document.getElementById("hr_duel_bars_box").innerHTML = `
        <div style="margin-bottom:10px;">
            <div class="cat-row-head"><span>Score (${n1} vs ${n2})</span><span>${c1.score}% vs ${c2.score}%</span></div>
            <div class="cat-track" style="margin-bottom:4px;"><div class="cat-fill" style="width:${c1.score}%; background:#4A72FF;"></div></div>
            <div class="cat-track"><div class="cat-fill" style="width:${c2.score}%; background:#F5A623;"></div></div>
        </div>
    `;
}

async function exportHrXlsx() {
    if (!lastHrReport) return;
    const selectedList = Array.from(selectedHrIndices).map(i => lastHrReport.candidates.at(i)).filter(Boolean);
    const exportList = selectedList.length ? selectedList : lastHrReport.candidates;
    const res = await fetch("/api/export-xlsx", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ candidates: exportList })
    });
    if (!res.ok) return;
    const a = document.createElement("a");
    a.href = URL.createObjectURL(await res.blob());
    a.download = `Shortlist_RH_CLAVERATS_${new Date().toISOString().slice(0, 10)}.xlsx`;
    a.click();
}

async function exportPredictiveTxt(idx) {
    if (!lastHrReport) return;
    const cand = lastHrReport.candidates.at(idx);
    if (!cand) return;
    const res = await fetch("/api/export-predictive-txt", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ candidate: cand })
    });
    if (!res.ok) return;
    const a = document.createElement("a");
    a.href = URL.createObjectURL(await res.blob());
    a.download = `Entretien_Predictif_${cand.name.replace(/\s+/g, "_")}.txt`;
    a.click();
}

async function exportScorecardPdf(idx) {
    if (!lastHrReport) return;
    const cand = lastHrReport.candidates.at(idx);
    if (!cand) return;
    const res = await fetch("/api/export-scorecard-pdf", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ candidate: cand })
    });
    if (!res.ok) return;
    const a = document.createElement("a");
    a.href = URL.createObjectURL(await res.blob());
    a.download = `Scorecard_RH_${cand.name.replace(/\s+/g, "_")}.pdf`;
    a.click();
}

function resetHrDashboard() {
    document.getElementById("hr_cv_files").value = "";
    document.getElementById("hr-files-label").textContent = "Sélectionner ou glisser plusieurs CV (.PDF)";
    if (document.getElementById("hr_job_pdf")) document.getElementById("hr_job_pdf").value = "";
    if (document.getElementById("hr-job-pdf-label")) document.getElementById("hr-job-pdf-label").textContent = "Importer l'offre en PDF (Optionnel)";
    if (document.getElementById("hr_job_url")) document.getElementById("hr_job_url").value = "";
    document.getElementById("hr_job_text").value = "";
    document.getElementById("hr_form_notice_box")?.classList.add("hidden");
    document.getElementById("hr_manual_editor_card")?.classList.add("hidden");
    document.getElementById("hr_results_area").classList.add("hidden");
    selectedHrIndices.clear();
    lastHrReport = null;
    updateHrSelectionUI();
}

function normalizeStr(s) {
    return (s || "").toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").trim();
}

function verifyFieldAgainstCV(inputId, badgeId) {
    if (!lastReport || !lastReport.raw_cv_text) return;
    const val = normalizeStr(document.getElementById(inputId).value);
    const badge = document.getElementById(badgeId);
    const raw = normalizeStr(lastReport.raw_cv_text);
    if (!badge) return;

    if (!val || val === "non precisee" || val === "candidat") {
        badge.textContent = "Champ à compléter";
        badge.className = "verif-badge warn";
    } else if (raw.includes(val)) {
        badge.textContent = "✓ Vérifié : présent dans votre CV";
        badge.className = "verif-badge ok";
    } else {
        badge.textContent = "⚠ Absent du CV importé";
        badge.className = "verif-badge warn";
    }
}

function downloadCalendarICS() {
    if (!lastReport) return;
    const y = selectedPlanDate.getFullYear();
    const m = String(selectedPlanDate.getMonth() + 1).padStart(2, "0");
    const d = String(selectedPlanDate.getDate()).padStart(2, "0");
    const ics = `BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\nDTSTART:${y}${m}${d}T090000\r\nSUMMARY:Postuler via CLAVERATS\r\nEND:VEVENT\r\nEND:VCALENDAR`;
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([ics], { type: "text/calendar" }));
    a.download = `rappel_claverats_${y}-${m}-${d}.ics`;
    a.click();
}

function copyPitch() {
    const box = document.getElementById("cover_pitch_box");
    navigator.clipboard.writeText(box.value).then(() => {
        document.getElementById("copy-pitch-text").textContent = "Copié !";
        setTimeout(() => { document.getElementById("copy-pitch-text").textContent = "Copier"; }, 2000);
    });
}

async function exportPDF() {
    if (!lastReport) return;
    const res = await fetch("/api/export-pdf", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(lastReport)
    });
    if (!res.ok) return;
    const a = document.createElement("a");
    a.href = URL.createObjectURL(await res.blob());
    a.download = "Bilan_CLAVERATS.pdf";
    a.click();
}

async function exportCoverLetterPDF() {
    if (!lastReport) return;
    const payload = { ...lastReport, custom_text: document.getElementById("cover_pitch_box").value };
    const res = await fetch("/api/export-cover-letter", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    });
    if (!res.ok) return;
    const a = document.createElement("a");
    a.href = URL.createObjectURL(await res.blob());
    a.download = "Lettre_Motivation_CLAVERATS.pdf";
    a.click();
}

document.addEventListener("keydown", (e) => {
    if (!isHrMode || !lastHrReport || !lastHrReport.candidates?.length) return;
    if (["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement?.tagName)) return;
    if (e.key === "ArrowDown") {
        e.preventDefault();
        activeHrDetailIdx = (activeHrDetailIdx + 1) % lastHrReport.candidates.length;
        renderHrTableAndMaster();
    } else if (e.key === "ArrowUp") {
        e.preventDefault();
        activeHrDetailIdx = (activeHrDetailIdx - 1 + lastHrReport.candidates.length) % lastHrReport.candidates.length;
        renderHrTableAndMaster();
    } else if (e.key.toLowerCase() === "r") {
        toggleAnonymousMode();
    }
});

/* =========================================================
   EXTENSIONS PRO : TOASTS, DRAG & DROP, STATUTS RH & HISTORIQUE
   ========================================================= */
function showToast(message) {
    const old = document.querySelector(".toast-notification");
    if (old) old.remove();

    const toast = document.createElement("div");
    toast.className = "toast-notification";
    toast.innerHTML = `<i class="ion-checkmark-circled"></i><span>${message}</span>`;
    document.body.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = "0";
        toast.style.transition = "opacity 0.25s ease";
        setTimeout(() => toast.remove(), 260);
    }, 3200);
}

(function setupDragAndDropZones() {
    document.querySelectorAll(".drop-zone").forEach(zone => {
        const input = zone.querySelector("input[type='file']");
        if (!input) return;

        zone.addEventListener("dragover", (e) => {
            e.preventDefault();
            zone.classList.add("drag-over");
        });
        zone.addEventListener("dragleave", () => {
            zone.classList.remove("drag-over");
        });
        zone.addEventListener("drop", (e) => {
            e.preventDefault();
            zone.classList.remove("drag-over");
            if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length > 0) {
                input.files = e.dataTransfer.files;
                input.dispatchEvent(new Event("change"));
                showToast(`${e.dataTransfer.files.length} fichier(s) PDF chargé(s) !`);
            }
        });
    });
})();

function saveCandidateToHistory5(report) {
    if (!report || !report.success) return;
    try {
        const key = "claverats_history_5";
        const list = JSON.parse(localStorage.getItem(key) || "[]");
        const entry = {
            id: Date.now(),
            date: new Date().toLocaleDateString("fr-FR"),
            name: (report.cv_details || {}).full_name || "Candidat",
            company: (report.job_details || {}).company_name || "Offre",
            score: report.score || 0,
            report: report
        };
        const updated = [entry, ...list.filter(x => !(x.name === entry.name && x.company === entry.company))].slice(0, 5);
        localStorage.setItem(key, JSON.stringify(updated));
    } catch (e) {}
}

function updateHrCandidateStatus(idx, newStatus) {
    if (!lastHrReport || !lastHrReport.candidates) return;
    const cand = lastHrReport.candidates.at(idx);
    if (!cand) return;
    cand.hr_status = newStatus;
    showToast(`Statut de ${cand.name} mis à jour : ${newStatus}`);
}

async function inspectHrCandidateFullView(idx) {
    if (!lastHrReport || !lastHrReport.candidates) return;
    const cand = lastHrReport.candidates.at(idx);
    if (!cand) return;

    const res = await fetch("/api/hr-inspect-candidate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            candidate: cand,
            job_details: lastHrReport.job_details || {},
            job_skills: lastHrReport.job_skills || [],
            tech_weight: lastHrReport.tech_weight || 60
        })
    });
    const report = await res.json();
    if (report && report.success) {
        lastReport = report;
        document.querySelectorAll(".side-btn, .mob-tab").forEach(b => b.classList.remove("disabled"));
        renderAllViews(report);
        switchTab("tab-overview");
        showToast(`Audit détaillé chargé pour ${cand.name}`);
    }
}

const _origRenderAllViews = renderAllViews;
renderAllViews = function(data) {
    _origRenderAllViews(data);
    saveCandidateToHistory5(data);
};

const _origRenderHrMasterDetail = renderHrMasterDetail;
renderHrMasterDetail = function() {
    _origRenderHrMasterDetail();
    const detailPane = document.getElementById("hr_dark_detail_pane");
    if (!detailPane || !lastHrReport || !lastHrReport.candidates?.length) return;

    const goodList = lastHrReport.candidates.map((c, idx) => ({ ...c, _origIdx: idx })).filter(c => c.score >= 45);
    if (!goodList.length) return;

    const cand = lastHrReport.candidates.at(activeHrDetailIdx);
    const displayedCand = (cand && cand.score >= 45) ? cand : goodList.at(0);
    const dispIdx = (cand && cand.score >= 45) ? activeHrDetailIdx : goodList.at(0)._origIdx;

    const actionRow = detailPane.lastElementChild;
    if (actionRow && !actionRow.querySelector(".hr-status-select")) {
        const statuses = ["À convoquer", "Entretien planifié", "Vivier", "Refusé"];
        const selHtml = `<select class="hr-status-select" onchange="updateHrCandidateStatus(${dispIdx}, this.value)">` +
            statuses.map(st => `<option value="${st}" ${(displayedCand.hr_status || "À convoquer") === st ? "selected" : ""}>${st}</option>`).join("") +
            `</select>`;
        const inspectBtn = `<button type="button" class="pill-btn-ghost" style="background:rgba(74,114,255,0.22); color:#FFF; border-color:#4A72FF;" onclick="inspectHrCandidateFullView(${dispIdx})"><i class="ion-eye"></i> Audit complet</button>`;
        actionRow.insertAdjacentHTML("afterbegin", selHtml + inspectBtn);
    }
};

/* =========================================================
   SYNCHRONISATION VÉRIFICATION (i), FLÈCHE QUOTA RH & CARTE
   ========================================================= */
function verifySkillsAgainstCV(inputId, badgeId, rawSourceText) {
    const badge = document.getElementById(badgeId);
    const input = document.getElementById(inputId);
    if (!badge || !input) return;

    const raw = normalizeStr(rawSourceText || "");
    const items = input.value.split(",").map(s => s.trim()).filter(Boolean);
    if (!items.length) {
        badge.innerHTML = `<i class="ion-information-circled"></i> Saisissez vos compétences clés séparées par une virgule.`;
        badge.className = "verif-badge warn";
        return;
    }
    if (!raw) {
        badge.innerHTML = `<i class="ion-information-circled"></i> Texte PDF non extractible : saisie manuelle enregistrée.`;
        badge.className = "verif-badge warn";
        return;
    }

    const notFound = items.filter(sk => !raw.includes(normalizeStr(sk)));
    if (notFound.length === 0) {
        badge.innerHTML = `✓ Toutes ces compétences (${items.length}) figurent dans le PDF.`;
        badge.className = "verif-badge ok";
    } else {
        badge.innerHTML = `<i class="ion-information-circled"></i> Non trouvé dans le PDF : <b>${notFound.join(", ")}</b>`;
        badge.className = "verif-badge warn";
    }
}

function verifyHrFieldAgainstPdf(inputId, badgeId) {
    if (!lastHrReport || editingHrCandidateIdx == null) return;
    const cand = lastHrReport.candidates.at(editingHrCandidateIdx);
    const badge = document.getElementById(badgeId);
    const val = normalizeStr(document.getElementById(inputId)?.value || "");
    if (!badge || !cand) return;

    const raw = normalizeStr(cand.raw_text || "");
    if (!val || val === "non precisee" || val === "candidat") {
        badge.innerHTML = `<i class="ion-information-circled"></i> Champ à compléter`;
        badge.className = "verif-badge warn";
    } else if (raw && raw.includes(val)) {
        badge.innerHTML = `✓ Présent dans le CV PDF`;
        badge.className = "verif-badge ok";
    } else {
        badge.innerHTML = `<i class="ion-information-circled"></i> Non trouvé dans le texte du PDF`;
        badge.className = "verif-badge warn";
    }
}

function verifyHrSkillsAgainstPdf() {
    if (!lastHrReport || editingHrCandidateIdx == null) return;
    const cand = lastHrReport.candidates.at(editingHrCandidateIdx);
    if (!cand) return;
    verifySkillsAgainstCV("hr_ed_skills", "hr_verif_skills", cand.raw_text || "");
}

const _origVerifyFieldAgainstCV = verifyFieldAgainstCV;
verifyFieldAgainstCV = function(inputId, badgeId) {
    _origVerifyFieldAgainstCV(inputId, badgeId);
    const badge = document.getElementById(badgeId);
    if (badge && badge.className.includes("warn")) {
        badge.innerHTML = `<i class="ion-information-circled"></i> ${badge.textContent.replace("⚠ ", "")}`;
    }
};

const _origRenderProfileAndInterviewViews = renderProfileAndInterviewViews;
renderProfileAndInterviewViews = function(data) {
    _origRenderProfileAndInterviewViews(data);
    verifyFieldAgainstCV("edit_profession", "verif_prof");
    verifyFieldAgainstCV("edit_cand_edu", "verif_edu");
    verifyFieldAgainstCV("edit_cand_langs", "verif_langs");
    verifySkillsAgainstCV("edit_extra_skills", "verif_skills", data.raw_cv_text || "");
};

const _origOpenHrManualEditor = openHrManualEditor;
openHrManualEditor = function(idx) {
    _origOpenHrManualEditor(idx);
    verifyHrFieldAgainstPdf("hr_ed_name", "hr_verif_name");
    verifyHrFieldAgainstPdf("hr_ed_prof", "hr_verif_prof");
    verifyHrFieldAgainstPdf("hr_ed_loc", "hr_verif_loc");
    verifyHrFieldAgainstPdf("hr_ed_edu", "hr_verif_edu");
    verifyHrSkillsAgainstPdf();
};

function rebuildHrCityClusters() {
    if (!lastHrReport || !lastHrReport.candidates) return;
    const mapClusters = {};
    lastHrReport.candidates.forEach(c => {
        const loc = (c.city_coords && c.city_coords.label) || c.location || "Non précisée";
        if (!mapClusters[loc]) {
            mapClusters[loc] = {
                city: loc,
                count: 0,
                avg_score: 0,
                coords: c.city_coords || null,
                distance_km: c.distance_km,
                commute_min: c.commute_min,
                co2_annual_kg: c.co2_annual_kg
            };
        }
        mapClusters[loc].count += 1;
        mapClusters[loc].avg_score += (c.score || 0);
        if (c.city_coords) mapClusters[loc].coords = c.city_coords;
    });
    Object.values(mapClusters).forEach(cl => {
        cl.avg_score = Math.round(cl.avg_score / Math.max(1, cl.count));
    });
    lastHrReport.city_clusters = Object.values(mapClusters);
}

const _origRefreshHrDashboardMetrics = refreshHrDashboardMetrics;
refreshHrDashboardMetrics = function() {
    rebuildHrCityClusters();
    _origRefreshHrDashboardMetrics();
    if (!lastHrReport || !lastHrReport.candidates) return;

    const received = lastHrReport.candidates.length;
    const wanted = parseInt(lastHrReport.positions_count || 3, 10);
    const quotaLbl = document.getElementById("hr_quota_label");
    if (quotaLbl) {
        if (received < wanted) {
            quotaLbl.innerHTML = `<span style="color:#EF4444; font-weight:800;">↘ Insuffisant : ${received} / ${wanted} voulus</span>`;
        } else {
            quotaLbl.innerHTML = `<span style="color:#059669; font-weight:800;">↗ Objectif atteint : ${received} / ${wanted} voulus</span>`;
        }
    }
};

saveHrManualCandidateEdit = async function() {
    if (!lastHrReport || editingHrCandidateIdx == null) return;
    const cand = lastHrReport.candidates.at(editingHrCandidateIdx);
    if (!cand) return;

    cand.name = document.getElementById("hr_ed_name").value.trim() || "Candidat";
    cand.main_profession = document.getElementById("hr_ed_prof").value.trim() || "Profil";
    cand.exp_years = parseFloat(document.getElementById("hr_ed_exp").value || "0");
    cand.location = document.getElementById("hr_ed_loc").value.trim() || "Non précisée";
    cand.phone = document.getElementById("hr_ed_phone").value.trim();
    cand.email = document.getElementById("hr_ed_email").value.trim();
    cand.education = document.getElementById("hr_ed_edu").value.trim() || "Non précisé";
    cand.posture = document.getElementById("hr_ed_posture").value;
    cand.matched_skills = document.getElementById("hr_ed_skills").value;

    const res = await fetch("/api/hr-recalculate-candidate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            candidate: cand,
            job_details: lastHrReport.job_details || {},
            job_skills: lastHrReport.job_skills || [],
            tech_weight: lastHrReport.tech_weight || 60
        })
    });
    const data = await res.json();
    if (data.success && data.candidate) {
        const updatedCand = data.candidate;
        lastHrReport.candidates[editingHrCandidateIdx] = updatedCand;
        lastHrReport.candidates.sort(rankCmp);
        lastHrReport.candidates.forEach((c, i) => { c.rank = i + 1; });

        // Maintient la sélection sur le candidat modifié et réinitialise les filtres pour qu'il ne disparaisse pas
        activeHrDetailIdx = Math.max(0, lastHrReport.candidates.indexOf(updatedCand));
        hrQuickFilter = "all";
        hrReadFilter = "all";
        hrCityFilter = "";

        closeHrManualEditor();
        refreshHrDashboardMetrics();
        showToast(`Profil de ${updatedCand.name} recalculé (${updatedCand.score}%) et carte mise à jour !`);
    }
};

/* =========================================================
   MODULE COMPLET : RUBRIQUES SÉPARÉES, POINT ROUGE CARTE & EXPORTS
   ========================================================= */
function verifyHrCatSkills(inputId, badgeId) {
    if (!lastHrReport || editingHrCandidateIdx == null) return;
    const cand = lastHrReport.candidates.at(editingHrCandidateIdx);
    verifySkillsAgainstCV(inputId, badgeId, cand ? (cand.raw_text || "") : "");
}

function fillCategorizedInputs(catObj, prefix) {
    catObj = catObj || {};
    const prog = catObj.prog_langs || catObj["Langages de Programmation"] || [];
    const tools = catObj.software_tools || catObj["Logiciels & Outils"] || [];
    const domain = [
        ...(catObj.domain_skills || catObj["Compétences Métiers & Techniques"] || []),
        ...(catObj.certifications || catObj["Certifications & Formations"] || [])
    ];
    const soft = catObj.attitudes || catObj["Attitudes & Savoir-être"] || [];

    const setVal = (id, arr) => {
        const el = document.getElementById(id);
        if (el) el.value = Array.from(new Set(arr)).join(", ");
    };
    setVal(`${prefix}_prog`, prog);
    setVal(`${prefix}_tools`, tools);
    setVal(`${prefix}_domain`, domain);
    setVal(`${prefix}_soft`, soft);
}

function collectCategorizedSkills(prefix) {
    const readArr = (id) => (document.getElementById(id)?.value || "").split(",").map(s => s.trim()).filter(Boolean);
    return Array.from(new Set([
        ...readArr(`${prefix}_prog`),
        ...readArr(`${prefix}_tools`),
        ...readArr(`${prefix}_domain`),
        ...readArr(`${prefix}_soft`)
    ]));
}

function renderCandidateHistoryList() {
    const box = document.getElementById("cand_history_list");
    if (!box) return;
    const list = JSON.parse(localStorage.getItem("claverats_history_5") || "[]");
    if (!list.length) {
        box.innerHTML = `<li><strong>Historique</strong><span>Aucune analyse précédente sauvegardée.</span></li>`;
        return;
    }
    box.innerHTML = list.map((item, idx) => `
        <li style="cursor:pointer;" onclick="loadHistoryEntry(${idx})">
            <strong>${item.date} • ${item.company} (${item.score}%)</strong>
            <span>${item.name} - Cliquez pour recharger ce bilan</span>
        </li>
    `).join("");
}

function loadHistoryEntry(idx) {
    const list = JSON.parse(localStorage.getItem("claverats_history_5") || "[]");
    const entry = list.at(idx);
    if (entry && entry.report) {
        lastReport = entry.report;
        renderAllViews(entry.report);
        switchTab("tab-overview");
        showToast(`Bilan rechargé : ${entry.company}`);
    }
}

function renderCandidateGeoMap(data) {
    const box = document.getElementById("cand_geo_map_box");
    const cap = document.getElementById("cand_geo_map_caption");
    if (!box || !data) return;

    const intel = ((data.comparison || {}).geo || {}).intel || {};
    const cCoords = intel.cand_coords;
    const jCoords = intel.job_coords;
    const okC = cCoords && typeof cCoords.lat === "number";
    const okJ = jCoords && typeof jCoords.lat === "number";
    const pins = [];
    if (okC) pins.push({ id: "you", kind: "you", priority: 10, label: `Vous (${(data.cv_details?.location || "CV").split(",").at(0)})`, sub: "Position indiquée sur votre CV", lat: cCoords.lat, lon: cCoords.lon });
    if (okJ) pins.push({ id: "offer", kind: "offer", priority: 11, label: `Offre (${(data.job_details?.location || "Poste").split(",").at(0)})`, sub: "Lieu du poste", lat: jCoords.lat, lon: jCoords.lon });
    GeoMap.mount(box, {
        pins, refit: true,
        route: okC && okJ ? { a: cCoords, b: jCoords, km: intel.distance_km != null ? intel.distance_km : undefined } : null,
        label: "Carte : votre position et le lieu de l'offre."
    });
    if (cap) {
        cap.textContent = intel.known
            ? `Distance estimée : ${intel.distance_km} km (~${intel.commute_min} min) • Impact : ${intel.co2_annual_kg} kg CO₂/an`
            : `Vert : votre localisation (${data.cv_details?.location || "Non précisée"}) • Rouge : lieu de l'offre (${data.job_details?.location || "Non précisé"})`;
    }
}

async function exportOptimizedCvPdf() {
    if (!lastReport) return;
    const res = await fetch("/api/export-optimized-cv", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(lastReport)
    });
    if (!res.ok) return;
    const a = document.createElement("a");
    a.href = URL.createObjectURL(await res.blob());
    a.download = `CV_Optimise_ATS_${((lastReport.cv_details || {}).full_name || "Candidat").replace(/\s+/g, "_")}.pdf`;
    a.click();
    showToast("CV Optimisé ATS (.PDF) téléchargé !");
}

async function exportHrCampaignPdf() {
    if (!lastHrReport || !lastHrReport.candidates?.length) return;
    const res = await fetch("/api/export-hr-campaign-pdf", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(lastHrReport)
    });
    if (!res.ok) return;
    const a = document.createElement("a");
    a.href = URL.createObjectURL(await res.blob());
    a.download = `Rapport_Campagne_RH_${new Date().toISOString().slice(0, 10)}.pdf`;
    a.click();
    showToast("Rapport Exécutif de Campagne (.PDF) généré !");
}

function openHrNewCandidateModal() {
    if (!lastHrReport) {
        showNoticeBanner("hr_form_notice_box", "Lancez d'abord l'analyse de l'offre avec au moins un CV avant d'ajouter un profil papier/WhatsApp.", true);
        return;
    }
    const blankCand = {
        rank: (lastHrReport.candidates?.length || 0) + 1,
        filename: "Saisie_Manuelle_RH",
        raw_text: "",
        readability: "clean",
        name: "Nouveau Candidat",
        initials: "NC",
        photo: null,
        is_duplicate: false,
        main_profession: "Profil",
        objective: "Profil ajouté manuellement par l'équipe RH.",
        posture: "Polyvalente",
        seniority: "Confirmé",
        email: "",
        phone: "",
        location: (lastHrReport.job_details || {}).location || "Non précisée",
        languages: ["Français"],
        exp_years: 2,
        education: "Licence",
        score: 50,
        match_tier: { code: "mid", label: "Moyen" },
        radar_axes: { Technique: 50, Expérience: 50, Diplômes: 50, Langues: 50, Adéquation: 50 },
        matched_skills: [],
        missing_skills: [],
        categorized_skills: {},
        hr_status: "À convoquer"
    };
    lastHrReport.candidates.push(blankCand);
    const newIdx = lastHrReport.candidates.length - 1;
    openHrManualEditor(newIdx);
    showToast("Formulaire prêt : complétez le profil manuel et cliquez sur Enregistrer.");
}

// Enrichissement des fonctions existantes pour les rubriques séparées & le point rouge de l'offre
const _prevRenderProfAndInt = renderProfileAndInterviewViews;
renderProfileAndInterviewViews = function(data) {
    _prevRenderProfAndInt(data);
    fillCategorizedInputs((data.cv_details || {}).categorized_skills || {}, "edit_cat");
    ["edit_cat_prog", "edit_cat_tools", "edit_cat_domain", "edit_cat_soft"].forEach(id => {
        verifySkillsAgainstCV(id, "verif_" + id.replace("edit_", ""), data.raw_cv_text || "");
    });
    renderCandidateGeoMap(data);
    renderCandidateHistoryList();
};

recalculateReport = async function() {
    if (!lastReport) return;
    lastReport.cv_details.full_name = document.getElementById("edit_name").value.trim() || "Candidat";
    lastReport.cv_details.main_profession = document.getElementById("edit_profession")?.value.trim() || lastReport.cv_details.main_profession;
    lastReport.cv_details.location = document.getElementById("edit_cand_loc").value.trim() || "Non précisée";
    lastReport.cv_details.exp_years = parseFloat(document.getElementById("edit_cand_exp").value || "0");
    lastReport.cv_details.education_label = document.getElementById("edit_cand_edu")?.value.trim() || lastReport.cv_details.education_label;

    const langsVal = document.getElementById("edit_cand_langs")?.value || "";
    if (langsVal.trim()) {
        lastReport.cv_details.languages = langsVal.split(",").map(s => s.trim()).filter(Boolean);
    }

    const combinedUserSkills = collectCategorizedSkills("edit_cat");
    if (combinedUserSkills.length > 0) {
        const userLower = new Set(combinedUserSkills.map(s => s.toLowerCase()));
        const allOfferSkills = [...(lastReport.matched_skills || []), ...(lastReport.missing_skills || [])];
        lastReport.matched_skills = allOfferSkills.filter(s => userLower.has(s.toLowerCase()));
        lastReport.missing_skills = allOfferSkills.filter(s => !userLower.has(s.toLowerCase()));
        lastReport.bonus_skills = combinedUserSkills.filter(s => !allOfferSkills.some(o => o.toLowerCase() === s.toLowerCase()));
    }

    lastReport.job_details.location = document.getElementById("edit_job_loc").value.trim() || "Non précisée";
    lastReport.job_details.required_exp_years = parseFloat(document.getElementById("edit_req_exp").value || "0");

    const res = await fetch("/api/recalculate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(lastReport)
    });
    const updated = await res.json();
    if (updated.success) {
        lastReport = updated;
        renderAllViews(updated);
        switchTab("tab-overview");
        showToast("Profil synchronisé et score recalculé !");
    }
};

const _prevOpenHrEditor = openHrManualEditor;
openHrManualEditor = function(idx) {
    _prevOpenHrEditor(idx);
    const cand = lastHrReport?.candidates?.at(idx);
    if (!cand) return;
    const langsEl = document.getElementById("hr_ed_langs");
    if (langsEl) langsEl.value = (cand.languages || ["Français"]).join(", ");
    fillCategorizedInputs(cand.categorized_skills || {}, "hr_ed_cat");
    if (!Object.keys(cand.categorized_skills || {}).length && (cand.matched_skills || []).length) {
        const domEl = document.getElementById("hr_ed_cat_domain");
        if (domEl) domEl.value = cand.matched_skills.join(", ");
    }
    ["hr_ed_langs", "hr_ed_cat_prog", "hr_ed_cat_tools", "hr_ed_cat_domain", "hr_ed_cat_soft"].forEach(id => {
        const badgeMap = {
            hr_ed_langs: "hr_verif_langs",
            hr_ed_cat_prog: "hr_verif_prog",
            hr_ed_cat_tools: "hr_verif_tools",
            hr_ed_cat_domain: "hr_verif_domain",
            hr_ed_cat_soft: "hr_verif_soft"
        };
        verifyHrCatSkills(id, badgeMap[id]);
    });
};

saveHrManualCandidateEdit = async function() {
    if (!lastHrReport || editingHrCandidateIdx == null) return;
    const cand = lastHrReport.candidates.at(editingHrCandidateIdx);
    if (!cand) return;

    cand.name = document.getElementById("hr_ed_name").value.trim() || "Candidat";
    cand.main_profession = document.getElementById("hr_ed_prof").value.trim() || "Profil";
    cand.exp_years = parseFloat(document.getElementById("hr_ed_exp").value || "0");
    cand.location = document.getElementById("hr_ed_loc").value.trim() || "Non précisée";
    cand.phone = document.getElementById("hr_ed_phone").value.trim();
    cand.email = document.getElementById("hr_ed_email").value.trim();
    cand.education = document.getElementById("hr_ed_edu").value.trim() || "Non précisé";
    cand.posture = document.getElementById("hr_ed_posture").value;
    const langsStr = document.getElementById("hr_ed_langs")?.value || "";
    if (langsStr.trim()) cand.languages = langsStr.split(",").map(s => s.trim()).filter(Boolean);
    cand.matched_skills = collectCategorizedSkills("hr_ed_cat");

    const res = await fetch("/api/hr-recalculate-candidate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            candidate: cand,
            job_details: lastHrReport.job_details || {},
            job_skills: lastHrReport.job_skills || [],
            tech_weight: lastHrReport.tech_weight || 60
        })
    });
    const data = await res.json();
    if (data.success && data.candidate) {
        const updatedCand = data.candidate;
        lastHrReport.candidates[editingHrCandidateIdx] = updatedCand;
        lastHrReport.candidates.sort(rankCmp);
        lastHrReport.candidates.forEach((c, i) => { c.rank = i + 1; });

        activeHrDetailIdx = Math.max(0, lastHrReport.candidates.indexOf(updatedCand));
        hrQuickFilter = "all";
        hrReadFilter = "all";
        hrCityFilter = "";

        closeHrManualEditor();
        refreshHrDashboardMetrics();
        showToast(`Profil de ${updatedCand.name} recalculé (${updatedCand.score}%) !`);
    }
};

/* =========================================================
   VERROUILLAGE INTELLIGENT DES BOUTONS QUAND CHAMPS VIDES
   ========================================================= */
function updateActionButtonsAvailability() {
    // 1. Espace Candidat (Lancer l'audit & Réinitialiser)
    const hasCandCv = (document.getElementById("cv_text")?.value.trim().length > 0) ||
                      (document.getElementById("cv_pdf")?.files?.length > 0);
    const hasCandJob = (document.getElementById("job_text")?.value.trim().length > 0) ||
                       (document.getElementById("job_url")?.value.trim().length > 0) ||
                       (document.getElementById("job_pdf")?.files?.length > 0);

    const btnAnalyze = document.getElementById("btn-analyze");
    const btnResetCand = document.querySelector("#tab-scan .btn-soft-reset");
    if (btnAnalyze) btnAnalyze.disabled = !(hasCandCv && hasCandJob);
    if (btnResetCand) btnResetCand.disabled = !(hasCandCv || hasCandJob || lastReport !== null);

    // 2. Simulateur Multi-Offres (Comparer & Réinitialiser)
    let hasExtraOffer = false;
    for (let i = 1; i <= 3; i++) {
        if ((document.getElementById(`mo_title_${i}`)?.value.trim().length > 0) ||
            (document.getElementById(`mo_url_${i}`)?.value.trim().length > 0) ||
            (document.getElementById(`mo_text_${i}`)?.value.trim().length > 0) ||
            (document.getElementById(`mo_pdf_${i}`)?.files?.length > 0)) {
            hasExtraOffer = true;
            break;
        }
    }
    const btnCompareMo = document.querySelector("#tab-interview .pill-btn-primary[onclick*='runMultiOfferSimulation']");
    const btnResetMo = document.querySelector("#tab-interview .pill-btn-ghost[onclick*='resetMultiOfferSimulator']");
    if (btnCompareMo) btnCompareMo.disabled = !hasExtraOffer;
    if (btnResetMo) btnResetMo.disabled = !(hasExtraOffer || (lastMultiOfferMatrix && lastMultiOfferMatrix.length > 0));

    // 3. Espace Équipe RH (Analyser & Restaurer)
    const hasHrCvs = (document.getElementById("hr_cv_files")?.files?.length > 0);
    const hasHrJob = (document.getElementById("hr_job_text")?.value.trim().length > 0) ||
                     (document.getElementById("hr_job_url")?.value.trim().length > 0) ||
                     (document.getElementById("hr_job_pdf")?.files?.length > 0);

    const btnHrAnalyze = document.getElementById("btn-hr-analyze");
    const btnHrReset = document.querySelector("#tab-hr .btn-soft-reset");
    if (btnHrAnalyze) btnHrAnalyze.disabled = !(hasHrCvs && hasHrJob);
    if (btnHrReset) btnHrReset.disabled = !(hasHrCvs || hasHrJob || lastHrReport !== null);
}

(function bindDynamicButtonLocks() {
    const watchedIds = [
        "cv_text", "job_text", "job_url", "cv_pdf", "job_pdf",
        "mo_title_1", "mo_url_1", "mo_text_1", "mo_pdf_1",
        "mo_title_2", "mo_url_2", "mo_text_2", "mo_pdf_2",
        "mo_title_3", "mo_url_3", "mo_text_3", "mo_pdf_3",
        "hr_cv_files", "hr_job_text", "hr_job_url", "hr_job_pdf"
    ];
    watchedIds.forEach(id => {
        const el = document.getElementById(id);
        if (!el) return;
        el.addEventListener("input", updateActionButtonsAvailability);
        el.addEventListener("change", updateActionButtonsAvailability);
    });

    // Met aussi à jour après chaque réinitialisation ou analyse
    const _origResetForm = resetForm;
    resetForm = function() {
        _origResetForm();
        updateActionButtonsAvailability();
    };

    const _origResetHr = resetHrDashboard;
    resetHrDashboard = function() {
        _origResetHr();
        updateActionButtonsAvailability();
    };

    const _origResetMo = resetMultiOfferSimulator;
    resetMultiOfferSimulator = function() {
        _origResetMo();
        updateActionButtonsAvailability();
    };

    updateActionButtonsAvailability();
})();

/* =========================================================
   RÉPARATION ÉDITEUR RH, VERROUILLAGE, HISTORIQUE BARRE & TOP N
   ========================================================= */
let isHrEditorLocked = false;

function toggleHrEditorLock(forceState = null) {
    isHrEditorLocked = (forceState !== null) ? forceState : !isHrEditorLocked;
    const card = document.getElementById("hr_manual_editor_card");
    const lockBtn = document.getElementById("btn_hr_lock_editor");
    const saveBtn = card?.querySelector(".btn-royal");
    if (!card) return;

    card.querySelectorAll("input, select").forEach(el => {
        el.disabled = isHrEditorLocked;
    });
    if (saveBtn) saveBtn.disabled = isHrEditorLocked;

    if (lockBtn) {
        lockBtn.innerHTML = isHrEditorLocked
            ? '<i class="ion-locked"></i> <span>Verrouillé (Débloquer)</span>'
            : '<i class="ion-unlocked"></i> <span>Édition libre</span>';
        lockBtn.style.borderColor = isHrEditorLocked ? "#EF4444" : "var(--border)";
        lockBtn.style.color = isHrEditorLocked ? "#EF4444" : "var(--text)";
    }
    if (forceState === null) {
        showToast(isHrEditorLocked ? "Modification RH verrouillée." : "Modification RH déverrouillée.");
    }
}

// Réparation complète de openHrManualEditor (ne plante plus sur hr_ed_skills)
openHrManualEditor = function(idx) {
    if (!lastHrReport || !lastHrReport.candidates) return;
    const cand = lastHrReport.candidates.at(idx);
    if (!cand) return;
    editingHrCandidateIdx = idx;
    activeHrDetailIdx = idx;

    const titleEl = document.getElementById("hr_editor_title");
    if (titleEl) titleEl.textContent = `Corriger / Compléter : ${cand.name} (${cand.filename || "CV"})`;

    const setIf = (id, val) => { const el = document.getElementById(id); if (el) el.value = val; };
    setIf("hr_ed_name", cand.name || "");
    setIf("hr_ed_prof", cand.main_profession || "");
    setIf("hr_ed_exp", cand.exp_years || 0);
    setIf("hr_ed_loc", cand.location || "");
    setIf("hr_ed_phone", cand.phone || "");
    setIf("hr_ed_email", cand.email || "");
    setIf("hr_ed_edu", cand.education || "");
    setIf("hr_ed_posture", cand.posture || "Polyvalente");
    setIf("hr_ed_langs", (cand.languages || ["Français"]).join(", "));

    // Compatibilité ancien champ unique ou 4 champs séparés
    if (document.getElementById("hr_ed_skills")) {
        document.getElementById("hr_ed_skills").value = (cand.matched_skills || []).join(", ");
    }
    fillCategorizedInputs(cand.categorized_skills || {}, "hr_ed_cat");
    if (!Object.keys(cand.categorized_skills || {}).length && (cand.matched_skills || []).length) {
        setIf("hr_ed_cat_domain", cand.matched_skills.join(", "));
    }

    verifyHrFieldAgainstPdf("hr_ed_name", "hr_verif_name");
    verifyHrFieldAgainstPdf("hr_ed_prof", "hr_verif_prof");
    verifyHrFieldAgainstPdf("hr_ed_loc", "hr_verif_loc");
    verifyHrFieldAgainstPdf("hr_ed_edu", "hr_verif_edu");
    ["hr_ed_langs", "hr_ed_cat_prog", "hr_ed_cat_tools", "hr_ed_cat_domain", "hr_ed_cat_soft"].forEach(id => {
        const badgeMap = {
            hr_ed_langs: "hr_verif_langs",
            hr_ed_cat_prog: "hr_verif_prog",
            hr_ed_cat_tools: "hr_verif_tools",
            hr_ed_cat_domain: "hr_verif_domain",
            hr_ed_cat_soft: "hr_verif_soft"
        };
        verifyHrCatSkills(id, badgeMap[id]);
    });

    toggleHrEditorLock(false);
    const card = document.getElementById("hr_manual_editor_card");
    if (card) {
        card.classList.remove("hidden");
        card.scrollIntoView({ behavior: "smooth", block: "center" });
    }
};

// Synchronisation de l'historique dans la barre horizontale du haut
renderCandidateHistoryList = function() {
    const sel = document.getElementById("header_history_select");
    if (!sel) return;
    const list = JSON.parse(localStorage.getItem("claverats_history_5") || "[]");
    if (!list.length) {
        sel.classList.add("hidden");
        return;
    }
    sel.classList.remove("hidden");
    sel.innerHTML = `<option value="">Historique (${list.length})</option>` +
        list.map((item, idx) => `<option value="${idx}">${item.date} • ${item.company} (${item.score}%)</option>`).join("");
};

// Mise à jour dynamique du bouton "Sélectionner Top N" (ex: 3, 10, 15...)
(function bindDynamicQuotaButton() {
    const posInput = document.getElementById("hr_positions_count");
    if (posInput) {
        posInput.addEventListener("input", () => {
            updateTopNButtonLabel();
            if (lastHrReport) {
                lastHrReport.positions_count = parseInt(posInput.value || "3", 10);
                const wantedChip = document.getElementById("hr_wanted_chip");
                if (wantedChip) wantedChip.textContent = `Voulu : ${lastHrReport.positions_count}`;
                refreshHrDashboardMetrics();
            }
        });
    }
    renderCandidateHistoryList();
})();


/* Liste de compétences en puces ; au-delà de `max`, le reste est replié (évite les pages interminables). */
function skillChipsHtml(list, kind, max, title, emptyTxt) {
    list = Array.from(new Set(list || []));
    const esc2 = (t) => String(t).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
    const chip = (t) => `<span class="sk-chip ${kind}">${esc2(t)}</span>`;
    const head = `<div class="sk-title">${title} (${list.length})</div>`;
    if (!list.length) return `<div class="sk-block">${head}<span class="sk-empty">${emptyTxt || "Aucune"}</span></div>`;
    const rest = list.slice(max);
    return `<div class="sk-block">${head}<div class="sk-wrap">${list.slice(0, max).map(chip).join("")}</div>` +
        (rest.length ? `<details class="sk-more"><summary>Voir ${rest.length} de plus</summary><div class="sk-wrap">${rest.map(chip).join("")}</div></details>` : "") + `</div>`;
}


/* Même règle de classement que services/ranking.py : score, puis couverture des compétences, expérience, fiabilité, lisibilité, complétude, nom. */
function rankCmp(a, b) {
    const v = (c) => {
        const m = (c.matched_skills || []).length, x = (c.missing_skills || []).length;
        return [c.score || 0, (m + x) ? m / (m + x) : 0, c.exp_years || 0, ((c.doc_trust || {}).score) || 0,
            { clean: 3, partial: 2, unreadable: 0 }[c.readability] ?? 1,
            (c.emails && c.emails.length || c.email ? 1 : 0) + (c.phones && c.phones.length || c.phone ? 1 : 0) + ((c.structured_experiences || []).length ? 1 : 0)];
    };
    const A = v(a), B = v(b);
    for (let i = 0; i < A.length; i++) if (A[i] !== B[i]) return B[i] - A[i];
    return String(a.name || "").localeCompare(String(b.name || ""));
}
