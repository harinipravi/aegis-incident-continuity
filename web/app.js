let INCIDENT_ID = "INC-006";

const $ = (id) => document.getElementById(id);

const generateButton = $("generateRcaBtn");
const approveButton = $("approveBtn");
const rejectButton = $("rejectBtn");

/* ==========================================================================
   THEME ENGINE (Dark, Light, System Default)
   ========================================================================== */

const themeSelect = $("themeSelect");

function getSystemTheme() {
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function setTheme(mode) {
    if (!mode) mode = "system";
    
    // Store user preference
    localStorage.setItem("aegis-theme", mode);
    
    // Set html attribute
    document.documentElement.setAttribute("data-theme", mode);
    
    if (themeSelect && themeSelect.value !== mode) {
        themeSelect.value = mode;
    }
}

function initTheme() {
    const savedTheme = localStorage.getItem("aegis-theme") || "system";
    setTheme(savedTheme);

    if (themeSelect) {
        themeSelect.addEventListener("change", (e) => {
            setTheme(e.target.value);
            showToast(`Appearance changed to ${e.target.options[e.target.selectedIndex].text}`, "info");
        });
    }

    // System theme change listener
    window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
        const currentMode = localStorage.getItem("aegis-theme");
        if (currentMode === "system" || !currentMode) {
            setTheme("system");
        }
    });
}


/* ==========================================================================
   TOAST NOTIFICATION SYSTEM
   ========================================================================== */

function showToast(message, type = "info", duration = 4000) {
    const container = $("toastContainer");
    if (!container) return;

    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;

    let icon = "ℹ";
    if (type === "success") icon = "✓";
    if (type === "error") icon = "✕";

    toast.innerHTML = `
        <span class="toast-icon">${icon}</span>
        <div class="toast-content">${escapeHtml(message)}</div>
    `;

    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = "0";
        toast.style.transform = "translateY(10px)";
        setTimeout(() => toast.remove(), 200);
    }, duration);
}


/* ==========================================================================
   MODAL CONTROLS
   ========================================================================== */

function openModal(modalId) {
    const modal = typeof modalId === "string" ? $(modalId) : modalId;
    if (modal) {
        modal.hidden = false;
        modal.style.display = "grid";
    }
}

function closeModal(modalId) {
    const modal = typeof modalId === "string" ? $(modalId) : modalId;
    if (modal) {
        modal.hidden = true;
        modal.style.display = "none";
    }
}

document.addEventListener("click", (e) => {
    const closeBtn = e.target.closest("[data-modal-close]");
    if (closeBtn) {
        const modal = closeBtn.closest(".modal-overlay");
        if (modal) {
            closeModal(modal);
        }
        return;
    }

    if (e.target.classList.contains("modal-overlay")) {
        closeModal(e.target);
    }
});

document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" || e.key === "Esc") {
        document.querySelectorAll(".modal-overlay").forEach((modal) => {
            closeModal(modal);
        });
    }
});


/* ==========================================================================
   HELPERS & RENDERING
   ========================================================================== */

function setText(id, value) {
    const element = $(id);
    if (element) {
        element.textContent = value ?? "—";
    }
}

function formatConfidence(value) {
    if (typeof value !== "number") return "—";
    return `${Math.round(value * 100)}%`;
}

function renderList(items) {
    if (!Array.isArray(items) || items.length === 0) {
        return "<p>No evidence available.</p>";
    }

    return `
        <ul>
            ${items.map(item => `<li>${escapeHtml(String(item))}</li>`).join("")}
        </ul>
    `;
}

function escapeHtml(value) {
    return value
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

function updateMetricValues(data) {
    const metrics = data.metrics_analysis;

    if (!metrics || !Array.isArray(metrics.anomalies_detected)) {
        return;
    }

    const anomalies = metrics.anomalies_detected;

    let errorRate = null;
    let latency = null;
    let dbConnections = null;

    for (const anomaly of anomalies) {
        const errorMatch = anomaly.match(/error_rate=([0-9.]+)/);
        const latencyMatch = anomaly.match(/latency_ms=([0-9.]+)/);
        const dbMatch = anomaly.match(/db_connections=([0-9.]+)/);

        if (errorMatch) {
            errorRate = Number(errorMatch[1]);
        }

        if (latencyMatch) {
            latency = Number(latencyMatch[1]);
        }

        if (dbMatch) {
            dbConnections = Number(dbMatch[1]);
        }
    }

    if (errorRate !== null) {
        setText("errorRate", `${(errorRate * 100).toFixed(1)}%`);
    }

    if (latency !== null) {
        setText("latency", `${Math.round(latency)} ms`);
    }

    if (dbConnections !== null) {
        setText("dbConnections", dbConnections);
    }
}

function updateStepperBar(rcaCompleted, mitigationDecision) {
    const rcaStep = $("stepperRca");
    const mitStep = $("stepperMitigation");
    const resStep = $("stepperResolved");

    if (rcaStep) {
        if (rcaCompleted) {
            rcaStep.className = "stepper-step complete";
        } else {
            rcaStep.className = "stepper-step active";
        }
    }

    if (mitStep) {
        if (mitigationDecision === "APPROVED") {
            mitStep.className = "stepper-step complete";
        } else if (rcaCompleted) {
            mitStep.className = "stepper-step active";
        } else {
            mitStep.className = "stepper-step";
        }
    }

    if (resStep) {
        if (mitigationDecision === "APPROVED") {
            resStep.className = "stepper-step active";
        } else {
            resStep.className = "stepper-step";
        }
    }
}

function renderRca(data) {
    // Clear any previous error styling.
    const rootCauseEl = $("rootCause");
    if (rootCauseEl) rootCauseEl.classList.remove("rca-error");

    setText("serviceName", data.service_name);
    setText("rootCause", data.suspected_root_cause);
    setText("evidenceSummary", data.evidence_summary);
    setText("mitigation", data.recommended_mitigation);
    setText("confidence", formatConfidence(data.confidence_score));

    updateMetricValues(data);

    // Metrics analysis
    if (data.metrics_analysis) {
        const metrics = data.metrics_analysis;

        $("metricsAnalysis").innerHTML = `
            ${renderList(metrics.anomalies_detected)}
            <p class="analysis-note">
                ${escapeHtml(metrics.correlation_notes || "")}
            </p>
        `;
    }

    // Logs analysis
    if (data.logs_analysis) {
        const logs = data.logs_analysis;

        $("logsAnalysis").innerHTML = `
            <h4>Error Patterns</h4>
            ${renderList(logs.error_patterns)}
            <h4>Suspect Traces</h4>
            ${renderList(logs.suspect_traces)}
        `;
    }

    // Deployment analysis
    if (data.deployment_analysis) {
        const deployments = data.deployment_analysis;

        $("deploymentAnalysis").innerHTML = `
            <h4>Suspect Deployments</h4>
            ${renderList(deployments.suspect_deployments)}
            <h4>Configuration Changes</h4>
            ${renderList(deployments.configuration_changes)}
        `;
    }

    // Update RCA status
    setText("rcaStatus", "Generated");

    const timeline = $("rcaTimeline");

    if (timeline) {
        timeline.classList.remove("active");
        timeline.classList.add("complete");

        const dot = timeline.querySelector(".timeline-dot");
        if (dot) dot.textContent = "✓";

        const small = timeline.querySelector("small");
        if (small) small.textContent = "Gemini RCA completed";
    }

    updateStepperBar(true, null);

    // Evidence labels
    setText("metricsEvidence", "Metrics analyzed successfully");
    setText("logsEvidence", "Application logs analyzed successfully");
    setText("deploymentEvidence", "Deployment changes analyzed successfully");

    showToast(`RCA successfully generated for ${INCIDENT_ID}`, "success");
}

async function generateRca() {
    if (generateButton.disabled) {
        return;
    }

    generateButton.disabled = true;
    generateButton.textContent = "⟳ Analyzing...";

    setText("rcaStatus", "Analyzing");

    $("rootCause").classList.add("loading");
    $("evidenceSummary").classList.add("loading");
    $("mitigation").classList.add("loading");

    try {
        const response = await fetch(
            `/incidents/${encodeURIComponent(INCIDENT_ID)}/rca`,
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                }
            }
        );

        if (!response.ok) {
            let detail = `HTTP ${response.status}`;

            try {
                const errorBody = await response.json();

                if (errorBody.detail) {
                    detail = errorBody.detail;
                }
            } catch (_) {
                // Ignore JSON parsing errors.
            }

            throw new Error(detail);
        }

        const data = await response.json();
        renderRca(data);

    } catch (error) {
        console.error("RCA generation failed:", error);

        setText("rcaStatus", "Failed");

        $("rootCause").classList.add("rca-error");
        $("rootCause").textContent =
            `RCA generation failed: ${error.message}`;

        $("evidenceSummary").textContent =
            "The backend did not return a valid RCA response. " +
            "You may retry once the model is available.";

        $("mitigation").textContent = "No mitigation recommendation available.";

        showToast(`RCA generation failed: ${error.message}`, "error");

    } finally {
        $("rootCause").classList.remove("loading");
        $("evidenceSummary").classList.remove("loading");
        $("mitigation").classList.remove("loading");

        generateButton.disabled = false;
        generateButton.textContent = "⚡ Generate RCA";
    }
}


/* ==========================================================================
   MITIGATION APPROVAL & REJECTION WORKFLOW
   ========================================================================== */

function updateMitigationTimeline(decision) {
    const timeline = $("mitigationTimeline");
    if (!timeline) return;

    const dot = timeline.querySelector(".timeline-dot");
    const small = timeline.querySelector("small");

    if (decision === "APPROVED") {
        timeline.classList.remove("active");
        timeline.classList.add("complete");

        if (dot) dot.textContent = "✓";
        if (small) small.textContent = "Mitigation approved";
        
        updateStepperBar(true, "APPROVED");
    } else if (decision === "REJECTED") {
        timeline.classList.remove("complete", "active");

        if (dot) dot.textContent = "4";
        if (small) small.textContent = "Mitigation rejected";
        
        updateStepperBar(true, "REJECTED");
    } else {
        timeline.classList.remove("complete", "active");

        if (dot) dot.textContent = "4";
        if (small) small.textContent = "Human approval required";
    }
}

async function saveMitigationDecision(decision) {
    const response = await fetch(
        `/incidents/${encodeURIComponent(INCIDENT_ID)}/mitigation`,
        {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ decision })
        }
    );

    if (!response.ok) {
        let detail = `HTTP ${response.status}`;

        try {
            const errorBody = await response.json();
            if (errorBody.detail) {
                detail = errorBody.detail;
            }
        } catch (_) {
            // Ignore JSON parsing errors.
        }

        throw new Error(detail);
    }

    return await response.json();
}

function promptApproveMitigation() {
    setText("modalApproveIncidentId", INCIDENT_ID);
    const text = $("mitigation") ? $("mitigation").textContent : "—";
    setText("modalApproveMitigationText", text);
    openModal("approveModal");
}

function promptRejectMitigation() {
    setText("modalRejectIncidentId", INCIDENT_ID);
    const text = $("mitigation") ? $("mitigation").textContent : "—";
    setText("modalRejectMitigationText", text);
    openModal("rejectModal");
}

async function executeApproveMitigation() {
    closeModal("approveModal");
    approveButton.disabled = true;
    approveButton.textContent = "⟳ Saving...";

    try {
        const result = await saveMitigationDecision("APPROVED");

        const status = $("incidentStatus");
        if (status) {
            status.textContent = "MITIGATION APPROVED";
            status.className = "badge investigating";
        }

        approveButton.textContent = "✓ Approved";

        if (rejectButton) {
            rejectButton.disabled = true;
        }

        updateMitigationTimeline("APPROVED");
        showToast(`Mitigation approval recorded for ${result.incident_id}`, "success");

    } catch (error) {
        console.error("Mitigation approval failed:", error);

        approveButton.disabled = false;
        approveButton.textContent = "✓ Approve Mitigation";
        showToast(`Unable to record mitigation approval: ${error.message}`, "error");
    }
}

async function executeRejectMitigation() {
    closeModal("rejectModal");
    rejectButton.disabled = true;
    rejectButton.textContent = "⟳ Saving...";

    try {
        const result = await saveMitigationDecision("REJECTED");

        const status = $("incidentStatus");
        if (status) {
            status.textContent = "MITIGATION REJECTED";
            status.className = "badge investigating";
        }

        rejectButton.textContent = "✕ Rejected";

        if (approveButton) {
            approveButton.disabled = true;
        }

        updateMitigationTimeline("REJECTED");
        showToast(`Mitigation rejection recorded for ${result.incident_id}`, "info");

    } catch (error) {
        console.error("Mitigation rejection failed:", error);

        rejectButton.disabled = false;
        rejectButton.textContent = "✕ Reject";
        showToast(`Unable to record mitigation rejection: ${error.message}`, "error");
    }
}

async function loadMitigationDecision(incidentId = INCIDENT_ID) {
    // Reset mitigation controls for the newly selected incident.
    if (approveButton) {
        approveButton.disabled = false;
        approveButton.textContent = "✓ Approve Mitigation";
    }

    if (rejectButton) {
        rejectButton.disabled = false;
        rejectButton.textContent = "✕ Reject";
    }

    updateMitigationTimeline(null);

    try {
        const response = await fetch(
            `/incidents/${encodeURIComponent(incidentId)}/mitigation`
        );

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const result = await response.json();

        if (result.decision === "APPROVED") {
            const status = $("incidentStatus");
            if (status) {
                status.textContent = "MITIGATION APPROVED";
                status.className = "badge investigating";
            }

            approveButton.textContent = "✓ Approved";
            approveButton.disabled = true;

            if (rejectButton) {
                rejectButton.disabled = true;
            }

            updateMitigationTimeline("APPROVED");
        }

        if (result.decision === "REJECTED") {
            const status = $("incidentStatus");
            if (status) {
                status.textContent = "MITIGATION REJECTED";
                status.className = "badge investigating";
            }

            rejectButton.textContent = "✕ Rejected";
            rejectButton.disabled = true;

            if (approveButton) {
                approveButton.disabled = true;
            }

            updateMitigationTimeline("REJECTED");
        }

    } catch (error) {
        console.error("Failed to load mitigation decision:", error);
    }
}


/* ==========================================================================
   EVENT LISTENERS & NAVIGATION
   ========================================================================== */

generateButton.addEventListener("click", generateRca);
approveButton.addEventListener("click", promptApproveMitigation);
rejectButton.addEventListener("click", promptRejectMitigation);

const confirmApproveBtn = $("confirmApproveBtn");
if (confirmApproveBtn) confirmApproveBtn.addEventListener("click", executeApproveMitigation);

const confirmRejectBtn = $("confirmRejectBtn");
if (confirmRejectBtn) confirmRejectBtn.addEventListener("click", executeRejectMitigation);


// ================= INCIDENTS VIEW =================

const incidentsView = $("incidentsView");
const incidentsList = $("incidentsList");
const incidentsStatus = $("incidentsStatus");
const refreshIncidentsButton = $("refreshIncidentsBtn");

const navItems = document.querySelectorAll(".nav-item");

async function loadIncidents() {
    if (!incidentsList || !incidentsStatus) {
        return;
    }

    incidentsStatus.textContent = "Loading incidents...";
    incidentsList.innerHTML = "";

    try {
        const response = await fetch("/incidents?limit=50");

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const incidents = await response.json();

        if (!Array.isArray(incidents) || incidents.length === 0) {
            incidentsStatus.textContent = "No incidents found.";
            return;
        }

        incidentsStatus.textContent =
            `${incidents.length} incident${incidents.length === 1 ? "" : "s"} found`;

        incidentsList.innerHTML = incidents.map(incident => `
            <div class="incident-row" data-incident-id="${escapeHtml(incident.incident_id)}">
                <div class="incident-id">
                    ${escapeHtml(incident.incident_id)}
                </div>

                <div class="incident-severity ${escapeHtml(
            String(incident.severity || "").toLowerCase()
        )}">
                    ${escapeHtml(incident.severity || "—")}
                </div>

                <div class="incident-summary">
                    <div class="incident-service">
                        ${escapeHtml(incident.service_name || "Unknown service")}
                    </div>
                    ${escapeHtml(incident.symptoms || "No symptoms available")}
                </div>

                <div class="incident-duration">
                    ${incident.duration_minutes ?? "—"} min
                </div>

                <div class="incident-duration">
                    ${formatIncidentDate(incident.timestamp)}
                </div>
            </div>
        `).join("");

        document.querySelectorAll(".incident-row").forEach(row => {
            row.addEventListener("click", () => {
                const incidentId = row.dataset.incidentId;
                selectIncident(incidentId);
            });
        });

    } catch (error) {
        console.error("Failed to load incidents:", error);
        incidentsStatus.textContent =
            `Unable to load incidents: ${error.message}`;
    }
}

function formatIncidentDate(timestamp) {
    if (!timestamp) {
        return "—";
    }

    const date = new Date(timestamp);

    if (Number.isNaN(date.getTime())) {
        return timestamp;
    }

    return date.toLocaleDateString();
}

async function selectIncident(incidentId) {
    console.log("Selected incident:", incidentId);

    INCIDENT_ID = incidentId;
    window.location.hash = incidentId;

    const main = document.querySelector(".main");

    if (incidentsView) {
        incidentsView.hidden = true;
    }

    if (main) {
        main.hidden = false;
    }

    // Immediately clear the previous incident while the new incident loads.
    setText("incidentId", incidentId);
    setText("workflowIncidentId", incidentId);
    setText("serviceName", "Loading...");
    setText("rootCause", "Loading incident details...");
    setText("evidenceSummary", "Loading incident evidence...");
    setText("mitigation", "—");
    setText("confidence", "—");

    setText("errorRate", "—");
    setText("latency", "—");
    setText("dbConnections", "—");

    setText("metricsAnalysis", "Loading...");
    setText("logsAnalysis", "Loading...");
    setText("deploymentAnalysis", "Loading...");
    setText("rcaStatus", "Loading");

    const severity = document.querySelector(".severity");
    if (severity) {
        severity.textContent = "—";
    }

    const status = $("incidentStatus");
    if (status) {
        status.textContent = "LOADING";
        status.className = "badge investigating";
    }

    try {
        const response = await fetch(
            `/incidents/${encodeURIComponent(incidentId)}`
        );

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const incident = await response.json();

        // Ignore stale responses from previously selected incidents.
        if (INCIDENT_ID !== incidentId) {
            return;
        }

        setText("serviceName", incident.service_name);

        setText("incidentId", incident.incident_id);
        setText("workflowIncidentId", incident.incident_id);

        const severity = document.querySelector(".severity");
        if (severity) {
            severity.textContent = incident.severity || "—";
        }

        setText("incidentStatus", "INVESTIGATING");

        // Reset RCA-specific fields for the newly selected incident.
        setText("rootCause", "Generate an RCA to analyze the incident evidence.");
        setText("evidenceSummary", "Evidence from BigQuery will appear here.");
        setText("mitigation", "—");
        setText("confidence", "—");

        setText("errorRate", "—");
        setText("latency", "—");
        setText("dbConnections", "—");

        setText("metricsAnalysis", "Waiting for RCA...");
        setText("logsAnalysis", "Waiting for RCA...");
        setText("deploymentAnalysis", "Waiting for RCA...");

        setText("rcaStatus", "Waiting");
        
        // Reset mitigation controls for the newly selected incident.
        if (approveButton) {
            approveButton.disabled = false;
            approveButton.textContent = "✓ Approve Mitigation";
        }

        if (rejectButton) {
            rejectButton.disabled = false;
            rejectButton.textContent = "✕ Reject";
        }
        
        // Reset RCA timeline.
        const timeline = $("rcaTimeline");

        if (timeline) {
            timeline.classList.remove("complete");
            timeline.classList.add("active");

            const dot = timeline.querySelector(".timeline-dot");
            if (dot) dot.textContent = "3";

            const small = timeline.querySelector("small");
            if (small) small.textContent = "Waiting for analysis";
        }

        updateStepperBar(false, null);

        // Load the mitigation decision for the selected incident.
        loadMitigationDecision(incidentId);

    } catch (error) {
        console.error("Failed to load selected incident:", error);
        showToast(`Unable to load ${incidentId}: ${error.message}`, "error");
    }
}

function showIncidentsView() {
    hideAllViews();
    if (incidentsView) incidentsView.hidden = false;
    loadIncidents();
}

function showOverviewView() {
    hideAllViews();
    const main = document.querySelector(".main");
    if (main) main.hidden = false;
}

// ================= ALL VIEWS HELPER =================

const rcaHistoryView = $("rcaHistoryView");
const placeholderView = $("placeholderView");

function hideAllViews() {
    const main = document.querySelector(".main");
    if (incidentsView)  incidentsView.hidden  = true;
    if (rcaHistoryView) rcaHistoryView.hidden = true;
    if (placeholderView) placeholderView.hidden = true;
    if (main) main.hidden = true;
}

// ================= RCA HISTORY VIEW =================

const rcaHistoryBody   = $("rcaHistoryBody");
const rcaHistoryStatus = $("rcaHistoryStatus");
const refreshHistoryBtn = $("refreshHistoryBtn");

async function loadRcaHistory() {
    if (!rcaHistoryBody) return;

    rcaHistoryBody.innerHTML = `<tr><td colspan="5" class="history-empty">Loading…</td></tr>`;
    if (rcaHistoryStatus) rcaHistoryStatus.textContent = "Fetching RCA history...";

    try {
        const response = await fetch("/incidents/rca-history?limit=20");

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const rows = await response.json();

        if (!Array.isArray(rows) || rows.length === 0) {
            rcaHistoryBody.innerHTML =
                `<tr><td colspan="5" class="history-empty">` +
                `No RCA results yet. Generate an RCA to populate history.</td></tr>`;
            if (rcaHistoryStatus) rcaHistoryStatus.textContent = "No history found.";
            return;
        }

        if (rcaHistoryStatus) {
            rcaHistoryStatus.textContent =
                `${rows.length} result${rows.length === 1 ? "" : "s"} found`;
        }

        rcaHistoryBody.innerHTML = rows.map(row => `
            <tr>
                <td class="col-id">${escapeHtml(row.incident_id || "—")}</td>
                <td>${escapeHtml(row.service_name || "—")}</td>
                <td class="col-score">
                    ${typeof row.confidence_score === "number"
                        ? Math.round(row.confidence_score * 100) + "%"
                        : "—"}
                </td>
                <td class="col-cause">${escapeHtml(
                    (row.suspected_root_cause || "—").slice(0, 160) +
                    (row.suspected_root_cause && row.suspected_root_cause.length > 160 ? "…" : "")
                )}</td>
                <td class="col-date">${formatIncidentDate(row.generated_at)}</td>
            </tr>
        `).join("");

    } catch (error) {
        console.error("Failed to load RCA history:", error);
        rcaHistoryBody.innerHTML =
            `<tr><td colspan="5" class="history-empty">` +
            `Unable to load history: ${escapeHtml(error.message)}</td></tr>`;
        if (rcaHistoryStatus) rcaHistoryStatus.textContent = "Error loading history.";
    }
}

function showRcaHistoryView() {
    hideAllViews();
    if (rcaHistoryView) rcaHistoryView.hidden = false;
    loadRcaHistory();
}

if (refreshHistoryBtn) {
    refreshHistoryBtn.addEventListener("click", loadRcaHistory);
}

// ================= PLACEHOLDER VIEW =================

const PLACEHOLDER_CONFIG = {
    Services: {
        eyebrow: "INFRASTRUCTURE",
        title: "Services Map",
        subtitle: "Service dependency topology and operational health overview.",
        icon: "◈",
        heading: "Service Map & Dependency Graph",
        description:
            "An interactive service topology map is planned for a future release. " +
            "Service health signals are currently aggregated through the BigQuery RCA evidence engine.",
    },
    Alerts: {
        eyebrow: "MONITORING",
        title: "Alert Rules",
        subtitle: "Active incident alert thresholds and automated page routing.",
        icon: "⚠",
        heading: "Alert Management Center",
        description:
            "Real-time alert threshold configuration is planned for a future release. " +
            "Incidents are currently ingested via the BigQuery incident table pipeline.",
    },
    Runbooks: {
        eyebrow: "OPERATIONS",
        title: "Runbooks Library",
        subtitle: "Standard operating procedures and automated mitigation playbooks.",
        icon: "▣",
        heading: "Automated Runbook Engine",
        description:
            "Runbook automation and executable playbooks are planned for a future release. " +
            "Mitigation actions are currently synthesized dynamically by the Gemini RCA engine.",
    },
    Reports: {
        eyebrow: "REPORTING",
        title: "Incident Reports",
        subtitle: "MTTR analytics, availability SLA tracking, and incident trend analysis.",
        icon: "▤",
        heading: "Analytics & SLA Reports",
        description:
            "Automated reporting and SLA trend analysis is planned for a future release. " +
            "Historical RCA audit records are available in the RCA History view.",
    },
};

function showPlaceholderView(key) {
    const cfg = PLACEHOLDER_CONFIG[key];
    if (!cfg || !placeholderView) return;

    hideAllViews();
    placeholderView.hidden = false;

    const set = (id, val) => { const el = $(id); if (el) el.textContent = val; };
    set("placeholderEyebrow",     cfg.eyebrow);
    set("placeholderTitle",       cfg.title);
    set("placeholderSubtitle",    cfg.subtitle);
    set("placeholderIcon",        cfg.icon);
    set("placeholderHeading",     cfg.heading);
    set("placeholderDescription", cfg.description);
}

// ================= NAV WIRING =================

navItems.forEach((item) => {
    item.addEventListener("click", () => {
        navItems.forEach(nav => nav.classList.remove("active"));
        item.classList.add("active");

        const label = item.textContent.trim();

        if (label.includes("Overview")) {
            showOverviewView();
        } else if (label.includes("Incidents")) {
            showIncidentsView();
        } else if (label.includes("RCA History")) {
            showRcaHistoryView();
        } else if (label.includes("Services")) {
            showPlaceholderView("Services");
        } else if (label.includes("Alerts")) {
            showPlaceholderView("Alerts");
        } else if (label.includes("Runbooks")) {
            showPlaceholderView("Runbooks");
        } else if (label.includes("Reports")) {
            showPlaceholderView("Reports");
        }
    });
});

if (refreshIncidentsButton) {
    refreshIncidentsButton.addEventListener("click", loadIncidents);
}

function initializeIncidentFromUrl() {
    const hashIncidentId = window.location.hash.replace("#", "").trim();

    if (hashIncidentId) {
        selectIncident(hashIncidentId);
    } else {
        selectIncident(INCIDENT_ID);
    }
}

window.addEventListener("hashchange", () => {
    const incidentId = window.location.hash.replace("#", "").trim();

    if (incidentId && incidentId !== INCIDENT_ID) {
        selectIncident(incidentId);
    }
});

// Initialize Theme & Incident State on Load
initTheme();
initializeIncidentFromUrl();
