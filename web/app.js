const INCIDENT_ID = "INC-006";

const $ = (id) => document.getElementById(id);

const generateButton = $("generateRcaBtn");
const approveButton = $("approveBtn");
const rejectButton = $("rejectBtn");

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

function renderRca(data) {
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

        if (dot) {
            dot.textContent = "✓";
        }

        const small = timeline.querySelector("small");

        if (small) {
            small.textContent = "Gemini RCA completed";
        }
    }

    // Evidence labels
    setText("metricsEvidence", "Metrics analyzed successfully");
    setText("logsEvidence", "Application logs analyzed successfully");
    setText("deploymentEvidence", "Deployment changes analyzed successfully");
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

        $("rootCause").textContent =
            `Unable to generate RCA: ${error.message}`;

        $("evidenceSummary").textContent =
            "The backend did not return a valid RCA response.";

        $("mitigation").textContent = "No mitigation available.";

    } finally {
        $("rootCause").classList.remove("loading");
        $("evidenceSummary").classList.remove("loading");
        $("mitigation").classList.remove("loading");

        generateButton.disabled = false;
        generateButton.textContent = "✦ Generate RCA";
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


async function approveMitigation() {
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

        alert(
            "Mitigation approval recorded for " +
            result.incident_id +
            ".\n\nExecution remains human-controlled."
        );

    } catch (error) {
        console.error("Mitigation approval failed:", error);

        approveButton.disabled = false;
        approveButton.textContent = "✓ Approve Mitigation";

        alert(
            "Unable to record mitigation approval.\n\n" +
            error.message
        );
    }
}


async function rejectMitigation() {
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

        alert(
            "Mitigation rejection recorded for " +
            result.incident_id +
            ".\n\nNo automated action was executed."
        );

    } catch (error) {
        console.error("Mitigation rejection failed:", error);

        rejectButton.disabled = false;
        rejectButton.textContent = "✕ Reject";

        alert(
            "Unable to record mitigation rejection.\n\n" +
            error.message
        );
    }
}


async function loadMitigationDecision() {
    try {
        const response = await fetch(
            `/incidents/${encodeURIComponent(INCIDENT_ID)}/mitigation`
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
        }

    } catch (error) {
        console.error("Failed to load mitigation decision:", error);
    }
}

loadMitigationDecision();

generateButton.addEventListener("click", generateRca);
approveButton.addEventListener("click", approveMitigation);
rejectButton.addEventListener("click", rejectMitigation);
