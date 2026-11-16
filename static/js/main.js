let lastReport = null;
let lastHrReport = null;
let isHrMode = false;
let isAnonymousMode = false;
let hrQuickFilter = "all";
let selectedHrIndices = new Set();
let simulatedAddedSkills = new Set();

(function initApp() {
    const savedTheme = localStorage.getItem("claverats_theme") || "light";
    document.documentElement.setAttribute("data-theme", savedTheme);
    const dateChip = document.getElementById("current_date_chip");
    if (dateChip) {
        dateChip.textContent = new Date().toLocaleDateString("fr-FR");
    }
    updateTopNButtonLabel();
})();

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
        if (heroSub) heroSub.textContent = "Importez vos CV PDF, comparez les profils et exportez votre shortlist vers Excel.";
    } else if (!lastReport) {
        if (heroTitle) heroTitle.innerHTML = 'Organisez votre <span class="underline-blue">candidature</span>';
        if (heroSub) heroSub.textContent = "Comparez votre CV et l'offre d'emploi 100 % en local sur CLAVERATS.";
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
        : "Sélectionner plusieurs fichiers CV (.PDF)";
}

function resetForm() {
    document.getElementById("cv_text").value = "";
    document.getElementById("job_text").value = "";
    document.getElementById("job_url").value = "";
    document.getElementById("cv_pdf").value = "";
    document.getElementById("job_pdf").value = "";
    document.getElementById("cv-file-label").textContent = "Importer votre CV (.PDF)";
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
            return `<button type="button" class="skill-tag ${act ? 'tag-ok' : 'tag-miss'}" style="border:none; cursor:pointer;" onclick="toggleSimulatedSkill('${s}')">${act ? '✓ ' : '+ '}${s}</button>`;
        }).join("")
        : `<span class="muted-small">Aucun mot-clé manquant !</span>`;
}

function renderAllViews(data) {
    const cv = data.cv_details;
    const job = data.job_details;
    const comp = data.comparison;

    const avatarBox = document.getElementById("nav_initials");
    if (avatarBox) {
        avatarBox.innerHTML = cv.photo ? `<img src="${cv.photo}" alt="Photo CV">` : '<i class="ion-person"></i>';
    }

    document.getElementById("nav_username").textContent = cv.full_name || "Candidat";
    document.getElementById("nav_location").textContent = `${cv.main_profession || "Profil"} • ${cv.location}`;
    document.getElementById("greeting_title").innerHTML = `Bilan pour <span class="underline-blue">${cv.full_name}</span>`;
    document.getElementById("greeting_sub").textContent = `Contrat : ${job.contract_type} — Lieu : ${job.location}`;

    const geoB = document.getElementById("geo_banner");
    geoB.textContent = `${comp.geo.badge} — ${comp.geo.message}`;
    geoB.className = comp.geo.status === "compatible" ? "status-banner ok" : "status-banner danger";

    const mailB = document.getElementById("email_trust_banner");
    mailB.textContent = `${job.email_audit.badge} — ${job.email_audit.details}`;
    mailB.className = job.email_audit.trust_pct >= 70 ? "status-banner ok" : "status-banner danger";

    document.getElementById("ov_skills").textContent = `${data.stats.matched_count} / ${data.stats.job_skills_count}`;
    document.getElementById("ov_missing_count").textContent = `${data.stats.missing_count} manquant(s)`;
    document.getElementById("ov_exp").textContent = `${cv.exp_years} an(s)`;
    document.getElementById("ov_exp_req").textContent = `${job.required_exp_years} an(s) requis`;
    document.getElementById("ov_langs").textContent = (cv.languages && cv.languages.length) ? cv.languages.join(", ") : "Langues CV";

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

    document.getElementById("gap_summary_list").innerHTML = `
        <li><strong>Expérience</strong><span>${comp.exp_status}</span></li>
        <li><strong>Études</strong><span>${comp.edu_status}</span></li>
        <li><strong>Langues</strong><span>${comp.lang_status}</span></li>
    `;

    document.getElementById("edit_name").value = cv.full_name || "";
    document.getElementById("edit_cand_loc").value = cv.location || "";
    document.getElementById("edit_job_loc").value = job.location || "";
    document.getElementById("edit_cand_exp").value = cv.exp_years || 0;
    document.getElementById("edit_req_exp").value = job.required_exp_years || 0;
    document.getElementById("edit_cand_langs").value = (cv.languages || []).join(", ");

    verifyFieldAgainstCV("edit_name", "verif_name");
    verifyFieldAgainstCV("edit_cand_loc", "verif_cand_loc");

    const profSum = document.getElementById("profile_summary_list");
    if (profSum) {
        profSum.innerHTML = `
            <li><strong>Profession détectée</strong><span>${cv.main_profession}</span></li>
            <li><strong>Objectif / Accroche CV</strong><span>${cv.objective || "Non précisé"}</span></li>
            <li><strong>Coordonnées extraites</strong><span>${(cv.phones || []).join(" | ") || "Tél N/A"} • ${(cv.emails || []).join(", ") || "Email N/A"}</span></li>
        `;
    }

    document.getElementById("interview_questions_list").innerHTML = (data.interview_questions || []).map((q, i) => `
        <li><strong>Question ${i + 1}</strong><span>${q}</span></li>
    `).join("");

    const offerElList = document.getElementById("offer_elements_list");
    if (offerElList) {
        const allReqSkills = [...(data.matched_skills || []), ...(data.missing_skills || [])];
        offerElList.innerHTML = `
            <li><strong>Organisation & Type de contrat</strong><span>${job.company_name} — ${job.contract_type}</span></li>
            <li><strong>Lieu & Mobilité</strong><span>${job.location} (${comp.geo.badge})</span></li>
            <li><strong>Expérience & Diplôme exigés</strong><span>${job.required_exp_years} an(s) • ${job.required_edu_label}</span></li>
            <li><strong>Compétences demandées par l'offre</strong><span>${allReqSkills.join(", ") || "Non précisées"}</span></li>
            <li><strong>Clôture & Contact</strong><span>${job.deadline.deadline_date} • ${(job.apply_emails || []).join(", ") || "Voir lien"}</span></li>
        `;
    }

    document.getElementById("emp_company").textContent = job.company_name || "—";
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
    if (chkLabel) {
        chkLabel.textContent = `CV renommé au nom du candidat (${cleanFileName})`;
    }

    document.getElementById("cover_pitch_box").value = data.cover_pitch || "";
    initCalendar(job.deadline);
}

let calViewYear = new Date().getFullYear();
let calViewMonth = new Date().getMonth();
let selectedPlanDate = new Date();

function initCalendar(dl) {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    calViewYear = today.getFullYear();
    calViewMonth = today.getMonth();
    selectedPlanDate = new Date(today);
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
    document.getElementById("selected_date_label").textContent = `Date choisie : ${selectedPlanDate.toLocaleDateString("fr-FR")}`;
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
        let cls = "cal-day";
        if (cell >= today) cls += " open-apply";
        if (cell.getTime() === selectedPlanDate.getTime()) cls += " is-selected";
        html += `<div class="${cls}" onclick="selectCalendarDay(${calViewYear}, ${calViewMonth}, ${d})">${d}</div>`;
    }
    grid.innerHTML = html;
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

function updateTopNButtonLabel() {
    const n = document.getElementById("hr_positions_count")?.value || "3";
    const btn = document.getElementById("btn_select_top_n");
    if (btn) btn.textContent = `Sélectionner le Top ${n}`;
}

function toggleAnonymousMode() {
    isAnonymousMode = !isAnonymousMode;
    const btn = document.getElementById("btn_anon_mode");
    if (btn) btn.textContent = isAnonymousMode ? "Mode Anonyme : ACTIF" : "Mode Anonyme";
    if (lastHrReport) {
        renderHrCardsGrid();
        updateHrFaceToFace();
    }
}

async function runHrBatch() {
    const alertBox = document.getElementById("alert_box");
    const btn = document.getElementById("btn-hr-analyze");
    alertBox.classList.remove("show");

    const filesInput = document.getElementById("hr_cv_files");
    const formData = new FormData();
    formData.append("hr_job_text", document.getElementById("hr_job_text").value);
    formData.append("positions_count", document.getElementById("hr_positions_count").value || "3");

    const techWeightEl = document.getElementById("hr_tech_weight");
    if (techWeightEl) formData.append("tech_weight", techWeightEl.value || "60");

    if (filesInput.files) {
        for (let i = 0; i < filesInput.files.length; i++) {
            formData.append("hr_cv_files", filesInput.files.item(i));
        }
    }

    btn.disabled = true;
    btn.innerHTML = '<i class="ion-load-c"></i> Classement en cours...';

    try {
        const res = await fetch("/api/hr-batch", { method: "POST", body: formData });
        const data = await res.json();
        if (!data.success) {
            alertBox.textContent = data.message;
            alertBox.classList.add("show");
            return;
        }
        lastHrReport = data;
        selectedHrIndices.clear();
        hrQuickFilter = "all";

        const total = data.total_received || 1;
        const wanted = data.positions_count || 1;
        const topPct = Math.round((data.summary.top / total) * 100);
        const midPct = Math.round((data.summary.mid / total) * 100);
        const lowPct = Math.max(0, 100 - topPct - midPct);

        document.getElementById("hr_total_cv").textContent = data.total_received;
        document.getElementById("hr_wanted_chip").textContent = `Voulu : ${wanted}`;
        document.getElementById("hr_quota_label").textContent = `Moyenne : ${data.avg_score}%`;
        document.getElementById("hr_top_count").textContent = data.summary.top;
        document.getElementById("hr_top_pct_label").textContent = `${topPct}% de la cohorte`;
        document.getElementById("hr_mid_low_count").textContent = `${data.summary.mid} / ${data.summary.low}`;

        document.getElementById("hr_seg_top").style.width = `${topPct}%`;
        document.getElementById("hr_seg_mid").style.width = `${midPct}%`;
        document.getElementById("hr_seg_low").style.width = `${lowPct}%`;

        renderHrQuotaChart(data);
        renderHrPerformanceChart(data);
        renderHrCardsGrid();
        updateHrSelectionUI();
        document.getElementById("hr_results_area").classList.remove("hidden");
    } catch (err) {
        alertBox.textContent = "Erreur de communication avec le serveur Python local.";
        alertBox.classList.add("show");
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="ion-speakerphone"></i> Analyser et classer tous les CV reçus';
    }
}

function renderHrQuotaChart(data) {
    const box = document.getElementById("hr_quota_bars_container");
    const badge = document.getElementById("hr_quota_status_badge");
    const desc = document.getElementById("hr_quota_chart_desc");
    if (!box) return;

    const received = data.total_received || 0;
    const wanted = data.positions_count || 1;
    const topCount = data.summary.top || 0;

    const maxRef = Math.max(received, wanted, 1);
    const recPct = Math.round((received / maxRef) * 100);
    const wantPct = Math.round((wanted / maxRef) * 100);
    const topPct = Math.round((topCount / maxRef) * 100);

    if (received >= wanted && topCount >= wanted) {
        badge.textContent = `✓ Quota atteint (${received} reçus / ${wanted} voulus • ${topCount} Top)`;
        badge.className = "chip-mint";
        desc.textContent = "Objectif atteint : vous avez suffisamment de profils performants pour pourvoir tous les postes.";
    } else if (received >= wanted) {
        badge.textContent = `⚠ Volume atteint (${received}/${wanted}), mais seulement ${topCount} Top profil(s)`;
        badge.className = "chip-amber";
        desc.textContent = "Le nombre total de CV atteint le quota, mais les profils ≥ 70 % sont en dessous du nombre voulu.";
    } else {
        const manquant = wanted - received;
        badge.textContent = `↓ En dessous du quota (${received} reçus / ${wanted} voulus — manque ${manquant})`;
        badge.className = "chip-amber";
        desc.textContent = `Il manque encore ${manquant} candidature(s) pour atteindre le nombre de personnes à recruter.`;
    }

    box.innerHTML = `
        <div style="display:flex; flex-direction:column; gap:12px;">
            <div>
                <div class="cat-row-head"><span>Total CV Reçus</span><span>${received} dossier(s)</span></div>
                <div class="cat-track" style="height:10px;"><div class="cat-fill" style="width:${recPct}%; background:#4A72FF;"></div></div>
            </div>
            <div>
                <div class="cat-row-head"><span>Total Personnes à Recruter (Quota voulu)</span><span>${wanted} poste(s)</span></div>
                <div class="cat-track" style="height:10px;"><div class="cat-fill" style="width:${wantPct}%; background:#F5A623;"></div></div>
            </div>
            <div>
                <div class="cat-row-head"><span>Profils Qualifiés (≥ 70 %)</span><span>${topCount} candidat(s)</span></div>
                <div class="cat-track" style="height:10px;"><div class="cat-fill" style="width:${topPct}%; background:#059669;"></div></div>
            </div>
        </div>
    `;
}

function renderHrPerformanceChart(data) {
    const box = document.getElementById("hr_performance_chart_box");
    const badge = document.getElementById("hr_perf_badge");
    const sub = document.getElementById("hr_perf_subtitle");
    if (!box || !data.candidates) return;

    const total = data.total_received || 0;
    const wanted = data.positions_count || 1;
    const topCount = data.summary.top || 0;

    const sortedAsc = [...data.candidates].sort((a, b) => a.score - b.score);
    const w = 640, h = 135, pad = 24;

    const pts = sortedAsc.map((c, idx) => {
        const x = sortedAsc.length === 1 ? w / 2 : pad + (idx / (sortedAsc.length - 1)) * (w - pad * 2);
        const y = (h - pad) - (c.score / 100) * (h - pad * 2);
        return `${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(" ");

    const circles = sortedAsc.map((c, idx) => {
        const x = sortedAsc.length === 1 ? w / 2 : pad + (idx / (sortedAsc.length - 1)) * (w - pad * 2);
        const y = (h - pad) - (c.score / 100) * (h - pad * 2);
        const color = c.score >= 70 ? "#059669" : (c.score >= 45 ? "#F5A623" : "#EF4444");
        return `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="5" fill="${color}" />`;
    }).join("");

    const ratioPerf = total > 0 ? Math.round((topCount / total) * 100) : 0;
    if (badge) badge.textContent = `Performance Cohorte : ${ratioPerf}% (${topCount}/${wanted} postes couverts)`;
    if (sub) {
        sub.textContent = `${total} CV reçus pour ${wanted} poste(s) voulu(s) — ${topCount} candidat(s) performants (≥ 70 %).`;
    }

    box.innerHTML = `
        <svg viewBox="0 0 ${w} ${h}" style="width:100%; height:135px; display:block;">
            <line x1="${pad}" y1="${h - pad}" x2="${w - pad}" y2="${h - pad}" stroke="#CBD5E1" stroke-width="1"/>
            <line x1="${pad}" y1="${pad}" x2="${w - pad}" y2="${pad}" stroke="#CBD5E1" stroke-dasharray="4" stroke-width="1"/>
            <polyline fill="none" stroke="#4A72FF" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" points="${pts}" />
            ${circles}
        </svg>
    `;
}

function selectTopN() {
    if (!lastHrReport) return;
    const n = Math.max(1, parseInt(document.getElementById("hr_positions_count").value || "3", 10));
    selectedHrIndices.clear();
    lastHrReport.candidates.slice(0, n).forEach((_, i) => selectedHrIndices.add(i));
    renderHrCardsGrid();
    updateHrSelectionUI();
}

function toggleSelectAllHr() {
    if (!lastHrReport) return;
    if (selectedHrIndices.size === lastHrReport.candidates.length) {
        selectedHrIndices.clear();
    } else {
        lastHrReport.candidates.forEach((_, i) => selectedHrIndices.add(i));
    }
    renderHrCardsGrid();
    updateHrSelectionUI();
}

function toggleHrCandidateCheck(idx) {
    if (selectedHrIndices.has(idx)) {
        selectedHrIndices.delete(idx);
    } else {
        selectedHrIndices.add(idx);
    }
    updateHrSelectionUI();
}

function setHrQuickFilter(mode) {
    hrQuickFilter = mode;
    filterHrCards();
}

function renderHrCardsGrid() {
    const grid = document.getElementById("hr_candidates_cards_grid");
    if (!grid || !lastHrReport) return;

    const dtVal = document.getElementById("hr_invite_datetime")?.value.trim();
    const locVal = document.getElementById("hr_invite_location")?.value.trim();
    const extraInfo = [
        dtVal ? `Date & Heure : ${dtVal}` : "",
        locVal ? `Lieu : ${locVal}` : ""
    ].filter(Boolean).join(" | ");

    grid.innerHTML = (lastHrReport.candidates || []).map((c, idx) => {
        const checked = selectedHrIndices.has(idx);
        const nameDisp = isAnonymousMode ? `Candidat #${c.rank} (Anonyme)` : c.name;
        const contactDisp = isAnonymousMode ? "Masqué" : `${c.phone || "Tél N/A"} • ${c.email || "Email N/A"}`;

        const waDigits = (c.phone || "").split("[").at(0).replace(/\D/g, "");
        const rawMsg = `Bonjour ${c.name.split(" ").at(0)}, suite à votre candidature, nous souhaitons vous proposer un entretien.${extraInfo ? " (" + extraInfo + ")" : ""}`;
        const msg = encodeURIComponent(rawMsg);
        const waUrl = (!isAnonymousMode && waDigits.length >= 8) ? `https://wa.me{waDigits}?text=${msg}` : "#";
        const mailUrl = (!isAnonymousMode && c.email) ? `mailto:${c.email}?subject=Invitation%20Entretien&body=${msg}` : "#";

        const secRoles = (c.secondary_professions && c.secondary_professions.length)
            ? c.secondary_professions.map(r => `<span class="chip-gray">+ ${r}</span>`).join(" ")
            : "";

        return `
            <div class="bento-card hr-cand-card ${checked ? 'selected-card' : ''}"
                 data-score="${c.score}"
                 data-exp="${c.exp_years}"
                 data-search="${(c.name + ' ' + c.main_profession + ' ' + c.matched_skills.join(' ') + ' ' + (c.bonus_skills || []).join(' ')).toLowerCase()}">
                <div class="card-top-row">
                    <label style="display:flex; align-items:center; gap:8px; cursor:pointer; font-weight:800;">
                        <input type="checkbox" ${checked ? "checked" : ""} onchange="toggleHrCandidateCheck(${idx})" style="width:18px; height:18px; accent-color:#4A72FF;">
                        <span>#${c.rank} • ${nameDisp}</span>
                    </label>
                    <span class="${c.score >= 70 ? 'chip-mint' : 'chip-blue'}">${c.score}% Match</span>
                </div>
                <p style="font-weight:700; font-size:0.9rem; margin-bottom:4px;">${c.main_profession} • <span style="color:#4A72FF;">${c.exp_years} an(s)</span></p>
                <div class="tags-wrap" style="margin-bottom:8px;">${secRoles}</div>
                <p class="muted-small" style="margin-bottom:6px;"><b>Demandées :</b> ${c.matched_skills.join(", ") || "Aucune"}</p>
                <p class="muted-small" style="margin-bottom:8px; color:#2563EB;"><b>Bonus :</b> ${(c.bonus_skills || []).join(", ") || "Aucun"}</p>
                <div style="display:flex; justify-content:space-between; align-items:center; gap:6px; font-size:0.78rem; padding-top:8px; border-top:1px solid var(--border); flex-wrap:wrap;">
                    <span class="muted-small">${contactDisp}</span>
                    <div style="display:flex; gap:6px;">
                        ${waUrl !== "#" ? `<a href="${waUrl}" target="_blank" class="pill-btn-ghost" style="padding:3px 10px; font-size:0.75rem;">WhatsApp</a>` : ""}
                        ${mailUrl !== "#" ? `<a href="${mailUrl}" class="pill-btn-primary" style="padding:3px 10px; font-size:0.75rem;">E-mail</a>` : ""}
                    </div>
                </div>
            </div>
        `;
    }).join("");
    filterHrCards();
}

function filterHrCards() {
    const q = (document.getElementById("hr_search_input")?.value || "").toLowerCase();
    document.querySelectorAll(".hr-cand-card").forEach(card => {
        const hay = card.dataset.search || "";
        const score = parseFloat(card.dataset.score || "0");
        const exp = parseFloat(card.dataset.exp || "0");

        let passQuick = true;
        if (hrQuickFilter === "top") passQuick = (score >= 70);
        else if (hrQuickFilter === "exp2") passQuick = (exp >= 2);

        card.style.display = (hay.includes(q) && passQuick) ? "" : "none";
    });
}

function updateHrSelectionUI() {
    const count = selectedHrIndices.size;
    const bar = document.getElementById("hr_floating_action_bar");
    document.getElementById("hr_selected_count_label").textContent = `${count} candidat(s) sélectionné(s)`;
    document.getElementById("hr_duel_counter_badge").textContent = `${Math.min(count, 2)}/2 pour duel`;
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
        const tag = document.getElementById("duel_status_tag");
        if (tag) tag.textContent = `En attente (${Math.min(selectedHrIndices.size, 2)}/2)`;
        return;
    }
    const arr = Array.from(selectedHrIndices);
    const c1 = lastHrReport.candidates.at(arr.at(0));
    const c2 = lastHrReport.candidates.at(arr.at(1));
    const n1 = isAnonymousMode ? `Candidat #${c1.rank}` : c1.name;
    const n2 = isAnonymousMode ? `Candidat #${c2.rank}` : c2.name;

    document.getElementById("duel_status_tag").textContent = "Duel Actif (2/2)";
    emptyEl.classList.add("hidden");
    activeEl.classList.remove("hidden");

    document.getElementById("hr_duel_cards_pair").innerHTML = [c1, c2].map((c, i) => `
        <div class="bento-card ${i === 0 && c1.score >= c2.score ? 'pastel-cream' : ''}">
            <strong>${i === 0 ? n1 : n2} (${c.score}%)</strong>
            <p class="muted-small">${c.main_profession} • ${c.exp_years} an(s)</p>
        </div>
    `).join("");

    const radarBox = document.getElementById("hr_radar_svg_container");
    if (radarBox) {
        radarBox.innerHTML = buildRadarSvg(c1, c2);
        document.getElementById("radar_legend_1").textContent = `● ${n1}`;
        document.getElementById("radar_legend_2").textContent = `● ${n2}`;
    }

    document.getElementById("hr_duel_bars_box").innerHTML = `
        <div style="margin-bottom:12px;">
            <div class="cat-row-head"><span>Score Global (${n1} vs ${n2})</span><span>${c1.score}% vs ${c2.score}%</span></div>
            <div class="cat-track" style="margin-bottom:4px;"><div class="cat-fill" style="width:${c1.score}%; background:#4A72FF;"></div></div>
            <div class="cat-track"><div class="cat-fill" style="width:${c2.score}%; background:#F5A623;"></div></div>
        </div>
        <div>
            <div class="cat-row-head"><span>Années d'expérience</span><span>${c1.exp_years} an(s) vs ${c2.exp_years} an(s)</span></div>
            <div class="cat-track" style="margin-bottom:4px;"><div class="cat-fill" style="width:${Math.min(100, c1.exp_years * 12)}%; background:#4A72FF;"></div></div>
            <div class="cat-track"><div class="cat-fill" style="width:${Math.min(100, c2.exp_years * 12)}%; background:#F5A623;"></div></div>
        </div>
    `;
}

async function exportHrXlsx() {
    if (!lastHrReport) return;
    const selectedList = Array.from(selectedHrIndices).map(i => lastHrReport.candidates.at(i)).filter(Boolean);
    if (!selectedList.length) return;
    const res = await fetch("/api/export-xlsx", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ candidates: selectedList })
    });
    if (!res.ok) return;
    const blob = await res.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `Shortlist_RH_CLAVERATS_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
}

function resetHrDashboard() {
    document.getElementById("hr_cv_files").value = "";
    document.getElementById("hr-files-label").textContent = "Sélectionner plusieurs fichiers CV (.PDF)";
    document.getElementById("hr_job_text").value = "";
    document.getElementById("hr_results_area").classList.add("hidden");
    selectedHrIndices.clear();
    lastHrReport = null;
    updateHrSelectionUI();
}

function updateChecklistCount() {
    const boxes = document.querySelectorAll("#apply_checklist input[type='checkbox']");
    const checked = Array.from(boxes).filter(b => b.checked).length;
    const counter = document.getElementById("checklist_counter");
    if (counter) counter.textContent = `${checked}/${boxes.length}`;
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

async function recalculateReport() {
    if (!lastReport) return;
    lastReport.cv_details.full_name = document.getElementById("edit_name").value.trim() || "Candidat";
    lastReport.cv_details.location = document.getElementById("edit_cand_loc").value.trim() || "Non précisée";
    lastReport.cv_details.exp_years = parseFloat(document.getElementById("edit_cand_exp").value || "0");
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
