const api = {
  async state() {
    return request("/api/state");
  },
  async reset() {
    return request("/api/reset", { method: "POST" });
  },
  async createVendor(payload) {
    return request("/api/vendors", jsonPost(payload));
  },
  async submitEvidence(vendorId, evidenceId, payload) {
    return request(`/api/vendors/${vendorId}/evidence/${evidenceId}/submit`, jsonPost(payload));
  },
  async uploadEvidence(vendorId, evidenceId, formData) {
    return request(`/api/vendors/${vendorId}/evidence/${evidenceId}/upload`, {
      method: "POST",
      body: formData,
    });
  },
  async decideEvidence(vendorId, evidenceId, payload) {
    return request(`/api/vendors/${vendorId}/evidence/${evidenceId}/decision`, jsonPost(payload));
  },
  async updateIssue(vendorId, issueId, status, actor) {
    return request(`/api/vendors/${vendorId}/issues/${issueId}`, jsonPost({ status, actor }));
  },
  async updateFollowup(vendorId, followupId, status, actor) {
    return request(`/api/vendors/${vendorId}/followups/${followupId}`, jsonPost({ status, actor }));
  },
  async rejectVendor(vendorId, reason) {
    return request(`/api/vendors/${vendorId}/reject`, jsonPost({ reason }));
  },
};

let state = null;
let selectedVendorId = null;
let selectedRole = "Admin / Ops Manager";
let vendorFilter = "All";
let vendorSearch = "";

const viewMeta = {
  dashboard: ["Operations dashboard", "Evidence review command center"],
  vendors: ["Vendor reviews", "Vendor evidence workspace"],
  queue: ["Reviewer queue", "Submitted evidence sorted by risk"],
  templates: ["Reusable checklists", "Evidence requirement templates"],
  followups: ["Owner accountability", "Follow-ups and unresolved risks"],
  audit: ["Audit-ready history", "Timeline of evidence decisions"],
};

const roleHints = {
  "Admin / Ops Manager": "Create reviews, assign owners, and monitor evidence readiness.",
  "Vendor Owner": "Submit evidence and complete follow-ups assigned to your team.",
  "Reviewer": "Review submissions, flag risks, and make evidence decisions.",
  "Leadership / Auditor": "Read-only visibility into risk posture, decisions, and audit history.",
};

const rolePermissions = {
  "Admin / Ops Manager": ["createVendor", "viewAll", "viewQueue", "viewTemplates", "viewAudit"],
  "Vendor Owner": ["submitEvidence", "manageFollowups"],
  "Reviewer": ["reviewEvidence", "manageIssues", "viewQueue"],
  "Leadership / Auditor": ["readOnly", "viewAudit"],
};

document.addEventListener("DOMContentLoaded", async () => {
  bindNavigation();
  bindDialogs();
  await loadState();
});

async function request(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

function jsonPost(payload) {
  return {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  };
}

async function loadState(nextState) {
  state = nextState || await api.state();
  if (state.users?.length && !availableRoles().includes(selectedRole)) {
    selectedRole = availableRoles()[0];
  }
  if (!selectedVendorId && state.vendors.length) selectedVendorId = state.vendors[0].id;
  if (!state.vendors.some((vendor) => vendor.id === selectedVendorId)) {
    selectedVendorId = state.vendors[0]?.id || null;
  }
  renderAll();
}

function bindNavigation() {
  document.querySelectorAll(".nav-item").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll(".nav-item").forEach((item) => item.classList.remove("active"));
      document.querySelectorAll(".view").forEach((view) => view.classList.remove("active"));
      button.classList.add("active");
      document.getElementById(`${button.dataset.view}View`).classList.add("active");
      document.getElementById("viewEyebrow").textContent = viewMeta[button.dataset.view][0];
      document.getElementById("viewTitle").textContent = viewMeta[button.dataset.view][1];
    });
  });

  document.getElementById("vendorSearch").addEventListener("input", (event) => {
    vendorSearch = event.target.value.toLowerCase();
    renderVendors();
  });

  document.querySelectorAll("#vendorFilters button").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll("#vendorFilters button").forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
      vendorFilter = button.dataset.filter;
      renderVendors();
    });
  });
}

function bindDialogs() {
  const vendorDialog = document.getElementById("vendorDialog");
  const evidenceDialog = document.getElementById("evidenceDialog");

  document.getElementById("newVendorBtn").addEventListener("click", () => {
    const form = document.getElementById("vendorForm");
    form.elements.dueDate.value = addDays(12);
    vendorDialog.showModal();
  });
  document.getElementById("closeVendorDialog").addEventListener("click", () => vendorDialog.close());
  document.getElementById("cancelVendor").addEventListener("click", () => vendorDialog.close());
  document.getElementById("closeEvidenceDialog").addEventListener("click", () => evidenceDialog.close());
  document.getElementById("cancelEvidence").addEventListener("click", () => evidenceDialog.close());

  document.getElementById("vendorForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const payload = {
      name: form.elements.name.value,
      category: form.elements.category.value,
      owner: form.elements.owner.value,
      reviewer: form.elements.reviewer.value,
      stage: form.elements.stage.value,
      dueDate: form.elements.dueDate.value,
      actor: actorName(),
      riskAnswers: Object.fromEntries(["pii", "financial", "storesData", "api", "critical", "ai", "subprocessors", "unknownSubprocessors"].map((key) => [key, form.elements[key].checked])),
    };
    await loadState(await api.createVendor(payload));
    selectedVendorId = state.vendors.at(-1).id;
    vendorDialog.close();
    switchView("vendors");
  });

  document.getElementById("evidenceForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const file = form.elements.file.files[0];
    if (file) {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("validUntil", form.elements.validUntil.value || "");
      formData.append("notes", form.elements.notes.value);
      formData.append("actor", actorName());
      await loadState(await api.uploadEvidence(form.elements.vendorId.value, form.elements.evidenceId.value, formData));
    } else {
      await loadState(await api.submitEvidence(form.elements.vendorId.value, form.elements.evidenceId.value, {
        fileName: form.elements.fileName.value,
        validUntil: form.elements.validUntil.value || null,
        notes: form.elements.notes.value,
        actor: actorName(),
      }));
    }
    evidenceDialog.close();
  });
}

function renderAll() {
  renderActorSelect();
  const ids = scopedVendorIds();
  if (selectedVendorId && !ids.has(selectedVendorId)) selectedVendorId = scopedVendors()[0]?.id || null;
  renderDashboard();
  renderVendors();
  renderQueue("dashboardQueue", scopedQueue().slice(0, 4));
  renderQueue("queueList", scopedQueue(), !can("viewQueue"));
  renderTemplates();
  renderFollowups();
  renderAudit();
}

function renderActorSelect() {
  const select = document.getElementById("actorSelect");
  if (!select || !state.users) return;
  select.innerHTML = availableRoles()
    .map((role) => `<option value="${role}" ${role === selectedRole ? "selected" : ""}>${role}</option>`)
    .join("");
  select.onchange = () => {
    selectedRole = select.value;
    renderAll();
  };
  const role = currentRole();
  document.getElementById("roleHint").textContent = roleHints[role] || "High-risk vendors, evidence gaps, and next actions in one place.";
  document.getElementById("newVendorBtn").hidden = !can("createVendor");
}

function availableRoles() {
  const order = ["Admin / Ops Manager", "Vendor Owner", "Reviewer", "Leadership / Auditor"];
  const roles = [...new Set((state.users || []).map((user) => user.role))];
  return order.filter((role) => roles.includes(role));
}

function currentRole() {
  return selectedRole;
}

function actorName() {
  const preferred = {
    "Admin / Ops Manager": "Admin",
    "Vendor Owner": "Head of Support",
    "Reviewer": "Security Manager",
    "Leadership / Auditor": "Leadership",
  };
  return preferred[selectedRole] || state.users?.find((user) => user.role === selectedRole)?.name || selectedRole;
}

function can(permission) {
  return rolePermissions[currentRole()]?.includes(permission);
}

function scopedVendors() {
  if (can("viewAll") || currentRole() === "Leadership / Auditor") return state.vendors;
  if (currentRole() === "Vendor Owner") {
    const actor = actorName();
    return state.vendors.filter((vendor) =>
      vendor.owner === actor ||
      vendor.followups.some((followup) => followup.owner === actor) ||
      vendor.evidence.some((item) => ["Requested", "Missing", "Needs Clarification"].includes(item.status))
    );
  }
  if (currentRole() === "Reviewer") {
    return state.vendors.filter((vendor) =>
      vendor.reviewer === actorName() ||
      vendor.evidence.some((item) => ["Submitted", "Needs Clarification", "Expired", "Rejected"].includes(item.status)) ||
      vendor.riskIssues.length
    );
  }
  return [];
}

function scopedVendorIds() {
  return new Set(scopedVendors().map((vendor) => vendor.id));
}

function scopedQueue() {
  if (!can("viewQueue")) return [];
  const ids = scopedVendorIds();
  return state.queue.filter((item) => ids.has(item.vendorId));
}

function scopedFollowups() {
  if (can("viewAll")) return state.followups;
  if (currentRole() !== "Vendor Owner") return [];
  return state.followups.filter((item) => item.owner === actorName());
}

function scopedAudit() {
  if (can("viewAll") || currentRole() === "Leadership / Auditor") return state.audit;
  const ids = scopedVendorIds();
  return state.audit.filter((entry) => ids.has(entry.vendorId));
}

function roleEmptyState(screen) {
  return empty(`${currentRole()} does not have ${screen} access in this workflow.`);
}

function renderDashboard() {
  const metricGrid = document.getElementById("metricGrid");
  const vendors = scopedVendors();
  metricGrid.innerHTML = dashboardGroups(vendors)
    .map((group) => `
      <article class="metric metric-wide">
        <span>${group.label}</span>
        <strong>${group.value}</strong>
        <p>${group.detail}</p>
      </article>
    `)
    .join("");

  const attention = vendors.filter((vendor) => ["Action Required", "Ready for Review", "Approved with Risk"].includes(vendor.status));
  document.getElementById("attentionList").innerHTML = attention.map(vendorCard).join("") || empty("No vendors need attention.");
}

function dashboardGroups(vendors) {
  const evidence = vendors.flatMap((vendor) => vendor.evidence);
  const queue = scopedQueue();
  const actionRequired = vendors.filter((vendor) => vendor.status === "Action Required").length;
  const approved = vendors.filter((vendor) => vendor.status === "Approved").length;
  const highRisk = vendors.filter((vendor) => vendor.risk.tier === "High").length;
  const pending = evidence.filter((item) => ["Requested", "Missing"].includes(item.status)).length;
  const openFollowups = scopedFollowups().filter((item) => !["Completed", "Cancelled"].includes(item.status)).length;
  if (currentRole() === "Vendor Owner") {
    return [
      { label: "My vendors", value: vendors.length, detail: `${pending} evidence items need submission` },
      { label: "Follow-ups", value: openFollowups, detail: "Assigned items waiting on owner action" },
      { label: "Blocked reviews", value: actionRequired, detail: "Vendor reviews needing evidence or clarification" },
    ];
  }
  if (currentRole() === "Reviewer") {
    return [
      { label: "Review queue", value: queue.length, detail: "Evidence items waiting for reviewer action" },
      { label: "High-risk scope", value: highRisk, detail: "Vendors with elevated review priority" },
      { label: "Action required", value: actionRequired, detail: "Blocked vendors or unresolved risk issues" },
    ];
  }
  if (currentRole() === "Leadership / Auditor") {
    return [
      { label: "Vendors tracked", value: vendors.length, detail: `${highRisk} high-risk vendors under oversight` },
      { label: "Risk posture", value: actionRequired, detail: "Vendors currently blocked or risky" },
      { label: "Approved", value: approved, detail: "Reviews with acceptable evidence posture" },
    ];
  }
  return [
    { label: "Active reviews", value: vendors.filter((vendor) => vendor.status !== "Approved").length, detail: `${highRisk} high-risk vendors in scope` },
    { label: "Evidence workload", value: pending, detail: "Requested or overdue evidence items" },
    { label: "Needs attention", value: actionRequired, detail: "Blocked vendors and unresolved risks" },
  ];
}

function renderVendors() {
  const rows = filteredVendors();
  document.getElementById("vendorTable").innerHTML = rows.map((vendor) => `
    <tr class="${vendor.id === selectedVendorId ? "selected" : ""}" data-vendor-id="${vendor.id}">
      <td><strong>${vendor.name}</strong><br><span class="muted">${vendor.category}</span></td>
      <td>${pill(vendor.risk.tier, vendor.risk.tier.toLowerCase())}<br><span class="muted">Score ${vendor.risk.score}</span></td>
      <td>${pill(vendor.status, statusClass(vendor.status))}</td>
      <td><div class="progress-bar"><span style="width:${vendor.progress}%"></span></div><span class="muted">${vendor.progress}% approved</span></td>
      <td>${vendor.owner}</td>
    </tr>
  `).join("");

  document.querySelectorAll("#vendorTable tr").forEach((row) => {
    row.addEventListener("click", () => {
      selectedVendorId = row.dataset.vendorId;
      renderVendors();
    });
  });

  const selected = scopedVendors().find((vendor) => vendor.id === selectedVendorId) || rows[0];
  document.getElementById("vendorDetail").innerHTML = selected ? vendorDetail(selected) : empty("No vendor selected.");
  bindVendorDetailActions();
}

function filteredVendors() {
  return scopedVendors().filter((vendor) => {
    const matchesFilter = vendorFilter === "All" || vendor.status === vendorFilter;
    const haystack = `${vendor.name} ${vendor.category} ${vendor.owner} ${vendor.reviewer}`.toLowerCase();
    return matchesFilter && haystack.includes(vendorSearch);
  });
}

function vendorDetail(vendor) {
  return `
    <div class="detail-content">
      <div class="status-row">
        ${pill(vendor.status, statusClass(vendor.status))}
        ${pill(`${vendor.risk.tier} Risk`, vendor.risk.tier.toLowerCase())}
      </div>
      <h2>${vendor.name}</h2>
      <p class="muted">${vendor.category} - ${vendor.stage}</p>
      <div class="fact-grid">
        ${fact("Owner", vendor.owner)}
        ${fact("Reviewer", vendor.reviewer)}
        ${fact("Due Date", vendor.dueDate)}
        ${fact("Template", vendor.templateName)}
      </div>
      <div class="ai-box"><strong>Risk rationale</strong><br>${vendor.risk.signals.length ? vendor.risk.signals.join(", ") : "No sensitive data or system access selected."}</div>

      <div class="section-title"><h3>Evidence checklist</h3></div>
      ${vendor.evidence.map((item) => evidenceItem(vendor, item)).join("")}

      <div class="section-title"><h3>Risk issues</h3></div>
      ${vendor.riskIssues.map((issue) => issueItem(vendor, issue)).join("") || empty("No open risk issues.")}
    </div>
  `;
}

function evidenceItem(vendor, item) {
  const ai = item.aiReview;
  const submitAction = can("submitEvidence")
    ? `<button class="mini-button" data-action="submit" data-vendor="${vendor.id}" data-evidence="${item.id}">Submit</button>`
    : "";
  const reviewActions = can("reviewEvidence")
    ? `
        <button class="mini-button" data-action="approve" data-vendor="${vendor.id}" data-evidence="${item.id}">Approve</button>
        <button class="mini-button" data-action="clarify" data-vendor="${vendor.id}" data-evidence="${item.id}">Clarify</button>
        <button class="mini-button" data-action="reject" data-vendor="${vendor.id}" data-evidence="${item.id}">Reject</button>
      `
    : "";
  const actionEmpty = submitAction || reviewActions ? "" : `<span class="muted action-note">Read-only for ${currentRole()}</span>`;
  return `
    <article class="evidence-item">
      <div>
        <strong>${item.name}</strong>
        <div class="evidence-meta">${item.requiredType} - ${item.reviewerRole} - Validity: ${item.validityPeriod}</div>
        ${item.fileName ? `<div class="evidence-meta">File: ${item.fileName}${item.validUntil ? ` - Valid until ${item.validUntil}` : ""}</div>` : ""}
        ${item.storedPath ? `<div class="evidence-meta">Stored securely in local evidence storage</div>` : ""}
        ${item.decisionReason ? `<div class="evidence-meta">Decision note: ${item.decisionReason}</div>` : ""}
        ${ai ? `<div class="ai-box"><strong>AI review (${ai.confidence}% confidence)</strong><br>${ai.summary}<br><span class="muted">Suggested action: ${ai.suggestedAction}</span></div>` : ""}
      </div>
      <div class="row-actions">
        ${pill(item.status, statusClass(item.status))}
        ${submitAction}
        ${reviewActions}
        ${actionEmpty}
      </div>
    </article>
  `;
}

function issueItem(vendor, issue) {
  const issueActions = can("manageIssues")
    ? `
        <button class="mini-button" data-action="issue-accepted" data-vendor="${vendor.id}" data-issue="${issue.id}">Accept Risk</button>
        <button class="mini-button" data-action="issue-resolved" data-vendor="${vendor.id}" data-issue="${issue.id}">Resolve</button>
      `
    : `<span class="muted action-note">Reviewer action required</span>`;
  return `
    <article class="issue-item">
      <div class="status-row">${pill(issue.severity, issue.severity.toLowerCase())}${pill(issue.status, statusClass(issue.status))}</div>
      <strong>${issue.title}</strong>
      <p class="muted">${issue.recommendation}</p>
      <div class="row-actions">
        ${issueActions}
      </div>
    </article>
  `;
}

function bindVendorDetailActions() {
  document.querySelectorAll("[data-action]").forEach((button) => {
    button.addEventListener("click", async () => {
      const action = button.dataset.action;
      if (action === "submit") return openEvidenceDialog(button.dataset.vendor, button.dataset.evidence);
      if (action === "approve") return loadState(await api.decideEvidence(button.dataset.vendor, button.dataset.evidence, { decision: "Approved", reason: "Reviewer confirmed evidence is acceptable.", createIssue: false, actor: actorName() }));
      if (action === "clarify") return loadState(await api.decideEvidence(button.dataset.vendor, button.dataset.evidence, { decision: "Needs Clarification", reason: "Additional detail is required before approval.", createIssue: true, actor: actorName() }));
      if (action === "reject") return loadState(await api.decideEvidence(button.dataset.vendor, button.dataset.evidence, { decision: "Rejected", reason: "Evidence does not satisfy the requirement.", createIssue: true, actor: actorName() }));
      if (action === "issue-accepted") return loadState(await api.updateIssue(button.dataset.vendor, button.dataset.issue, "Accepted Risk", actorName()));
      if (action === "issue-resolved") return loadState(await api.updateIssue(button.dataset.vendor, button.dataset.issue, "Resolved", actorName()));
    });
  });
}

function openEvidenceDialog(vendorId, evidenceId) {
  const vendor = state.vendors.find((item) => item.id === vendorId);
  const evidence = vendor.evidence.find((item) => item.id === evidenceId);
  const form = document.getElementById("evidenceForm");
  form.elements.vendorId.value = vendorId;
  form.elements.evidenceId.value = evidenceId;
  form.elements.fileName.value = evidence.fileName || `${vendor.name.toLowerCase().replaceAll(" ", "-")}-${evidence.name.toLowerCase().replaceAll(" ", "-")}.pdf`;
  form.elements.file.value = "";
  form.elements.validUntil.value = evidence.validUntil || addDays(220);
  form.elements.notes.value = evidence.notes || "";
  document.getElementById("evidenceDialogTitle").textContent = `Submit ${evidence.name}`;
  document.getElementById("evidenceDialog").showModal();
}

function renderQueue(targetId, queue, restricted = false) {
  document.getElementById(targetId).innerHTML = restricted ? roleEmptyState("review queue") : queue.map((item) => `
    <article class="queue-item">
      <div><strong>${item.vendorName}</strong><br><span class="muted">${item.evidenceName}</span></div>
      <div>${pill(item.riskTier, item.riskTier.toLowerCase())} ${pill(item.priority, item.priority.toLowerCase())}<br><span class="muted">Due ${item.dueDate}</span></div>
      <div><span class="muted">AI flag</span><br>${item.aiFlag}</div>
    </article>
  `).join("") || empty("No evidence is waiting for review.");
}

function renderTemplates() {
  document.getElementById("templateGrid").innerHTML = can("viewTemplates") ? state.templates.map((template) => `
    <article class="template-card">
      <div class="status-row">${pill(template.riskTier, template.riskTier.toLowerCase())}</div>
      <h2>${template.name}</h2>
      <p class="muted">${template.description}</p>
      <ul>${template.requirements.map((item) => `<li>${item.name} - ${item.requiredType}</li>`).join("")}</ul>
    </article>
  `).join("") : roleEmptyState("template management");
}

function renderFollowups() {
  const canManage = can("manageFollowups");
  const followups = scopedFollowups();
  document.getElementById("followupList").innerHTML = currentRole() === "Reviewer" || currentRole() === "Leadership / Auditor"
    ? roleEmptyState("follow-up management")
    : followups.map((item) => `
    <article class="followup-item">
      <div class="status-row">${pill(item.status, statusClass(item.status))}<span class="muted">Due ${item.dueDate}</span></div>
      <strong>${item.vendorName}</strong>
      <p>${item.message}</p>
      <div class="row-actions">
        ${canManage
          ? `<button class="mini-button" data-followup="${item.id}" data-vendor="${item.vendorId}" data-status="Sent">Mark Sent</button>
             <button class="mini-button" data-followup="${item.id}" data-vendor="${item.vendorId}" data-status="Completed">Complete</button>`
          : `<span class="muted action-note">Owner action required</span>`}
      </div>
    </article>
  `).join("") || empty("No follow-ups are open.");

  document.querySelectorAll("[data-followup]").forEach((button) => {
    button.addEventListener("click", async () => {
      await loadState(await api.updateFollowup(button.dataset.vendor, button.dataset.followup, button.dataset.status, actorName()));
    });
  });
}

function renderAudit() {
  const audit = scopedAudit();
  document.getElementById("auditTimeline").innerHTML = currentRole() === "Vendor Owner"
    ? roleEmptyState("full audit trail")
    : audit.map((entry) => `
    <article class="timeline-item">
      <span>${entry.time}</span>
      <strong>${entry.actor}</strong>
      <div>${entry.action}${entry.target ? `<br><span>${entry.target}</span>` : ""}</div>
    </article>
  `).join("");
}

function vendorCard(vendor) {
  return `
    <article class="vendor-card">
      <div class="status-row">${pill(vendor.status, statusClass(vendor.status))}${pill(`${vendor.risk.tier} Risk`, vendor.risk.tier.toLowerCase())}</div>
      <strong>${vendor.name}</strong>
      <span class="muted">${vendor.category} - Owner: ${vendor.owner}</span>
    </article>
  `;
}

function fact(label, value) {
  return `<div class="fact"><span>${label}</span><strong>${value}</strong></div>`;
}

function pill(label, className) {
  return `<span class="pill ${className}">${label}</span>`;
}

function statusClass(status) {
  const normalized = status.toLowerCase();
  if (normalized.includes("approved")) return normalized.includes("risk") ? "risk" : "approved";
  if (normalized.includes("reject")) return "rejected";
  if (normalized.includes("action") || normalized.includes("missing") || normalized.includes("expired")) return "action";
  if (normalized.includes("clarification") || normalized.includes("waiting") || normalized.includes("partial")) return "needs";
  if (normalized.includes("submitted") || normalized.includes("ready") || normalized.includes("review")) return "ready";
  if (normalized.includes("resolved") || normalized.includes("completed")) return "resolved";
  return "draft";
}

function empty(text) {
  return `<div class="vendor-card"><span class="muted">${text}</span></div>`;
}

function addDays(days) {
  const date = new Date();
  date.setDate(date.getDate() + days);
  return date.toISOString().slice(0, 10);
}

function switchView(view) {
  document.querySelector(`.nav-item[data-view="${view}"]`).click();
}
