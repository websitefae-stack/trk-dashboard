(function () {
  "use strict";

  var el = Dashboard.el;

  const SHARED_API = "dashboard.api.shared.leads";

  const STATUS_COLUMNS = [
    "New", "Assessing", "Can Help", "Can't Help",
    "Intake Sent", "Intake Completed", "Converted", "Declined",
  ];

  function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta && meta.content ? meta.content : "";
  }

  function getDashboardType() {
    const path = window.location.pathname || "";
    if (path.indexOf("/franchisor_db") !== -1) return "franchisor";
    return "coach";
  }

  async function apiPost(method, args) {
    const response = await fetch(`/api/method/${method}`, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-Frappe-CSRF-Token": getCsrfToken(),
      },
      body: JSON.stringify(args || {}),
    });

    const data = await response.json();

    if (!response.ok || data.exc) {
      throw new Error(data.message || "There was a problem loading leads.");
    }

    return data.message || {};
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function renderCard(lead, baseUrl, showCoach) {
    const detailUrl = `${baseUrl}/lead_details?name=${encodeURIComponent(lead.name)}`;

    const metaBits = [];
    if (lead.client_age) metaBits.push(`Age ${escapeHtml(lead.client_age)}`);
    if (showCoach && lead.coach_label) metaBits.push(escapeHtml(lead.coach_label));

    return `
      <a class="dashboard-lead-card" href="${detailUrl}">
        <div class="dashboard-lead-card-client">${escapeHtml(lead.client_name || "—")}</div>
        <div class="dashboard-lead-card-contact">${escapeHtml(lead.contact_name || "—")}</div>
        ${metaBits.length ? `<div class="dashboard-lead-card-meta">${metaBits.join(" · ")}</div>` : ""}
        <div class="dashboard-lead-card-contact-methods">
          ${lead.contact_mobile ? `<span>${escapeHtml(lead.contact_mobile)}</span>` : ""}
          ${lead.contact_email ? `<span>${escapeHtml(lead.contact_email)}</span>` : ""}
        </div>
      </a>
    `;
  }

  function renderBoard(board, leads) {
    const baseUrl = board.dataset.baseUrl || "/coach_db";
    const showCoach = board.dataset.showCoach === "1";

    const byStatus = {};
    STATUS_COLUMNS.forEach((status) => { byStatus[status] = []; });

    leads.forEach((lead) => {
      const status = STATUS_COLUMNS.indexOf(lead.status) !== -1 ? lead.status : "New";
      byStatus[status].push(lead);
    });

    board.innerHTML = STATUS_COLUMNS.map((status) => {
      const rows = byStatus[status];

      return `
        <div class="dashboard-lead-column">
          <div class="dashboard-lead-column-head">
            <span>${escapeHtml(status)}</span>
            <span class="dashboard-lead-column-count">${rows.length}</span>
          </div>
          <div class="dashboard-lead-column-body">
            ${rows.length ? rows.map((lead) => renderCard(lead, baseUrl, showCoach)).join("") : '<div class="dashboard-lead-column-empty">No leads</div>'}
          </div>
        </div>
      `;
    }).join("");
  }

  function setCount(count) {
    const countEl = el("leadsCount");
    if (countEl) countEl.textContent = `${count} lead${count === 1 ? "" : "s"}`;
  }

  async function loadLeads() {
    const board = el("leadsKanbanBoard");
    if (!board) return;

    try {
      const leads = await apiPost(`${SHARED_API}.get_leads`, {
        dashboard_type: getDashboardType(),
      });

      const rows = Array.isArray(leads) ? leads : [];
      renderBoard(board, rows);
      setCount(rows.length);
    } catch (error) {
      console.error("Failed to load leads:", error);
      board.innerHTML = `<div class="dashboard-empty">${escapeHtml(error.message || "Could not load leads.")}</div>`;
      setCount(0);
    }
  }

  function init() {
    const board = el("leadsKanbanBoard");
    if (!board) return;

    loadLeads();

    const refreshBtn = el("refreshLeads");
    if (refreshBtn) {
      refreshBtn.addEventListener("click", loadLeads);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
