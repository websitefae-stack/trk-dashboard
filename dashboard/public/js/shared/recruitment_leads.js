(function () {
  "use strict";

  var el = Dashboard.el;

  const SHARED_API = "dashboard.api.shared.recruitment_leads";

  // Mirrors recruitment_leads.PIPELINE_STAGES exactly - each one "this
  // step has been reached" rather than "fully complete", so a card
  // moves the moment an NDA/Intent/Intake/Contract link is generated,
  // not only once it's actually signed back.
  const STAGE_COLUMNS = ["New", "NDA Sent", "Intent Sent", "Converted", "Intake Form", "Contract Sent", "Onboarding", "Declined"];
  const CONVERTED_PREVIEW_COUNT = 3;

  function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta && meta.content ? meta.content : "";
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
      throw new Error(data.message || "There was a problem loading recruitment leads.");
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
    const detailUrl = `${baseUrl}/recruitment_lead_details?name=${encodeURIComponent(lead.name)}`;

    const metaBits = [];
    if (showCoach && lead.coach_label) metaBits.push(escapeHtml(lead.coach_label));

    return `
      <a class="dashboard-lead-card" href="${detailUrl}">
        ${lead.lead_type ? `<span class="dashboard-badge dashboard-status-active dashboard-lead-card-type">${escapeHtml(lead.lead_type)}</span>` : ""}
        <div class="dashboard-lead-card-client">${escapeHtml(lead.contact_name || "—")}</div>
        ${metaBits.length ? `<div class="dashboard-lead-card-meta">${metaBits.join(" · ")}</div>` : ""}
        <div class="dashboard-lead-card-contact-methods">
          ${lead.contact_mobile ? `<span>${escapeHtml(lead.contact_mobile)}</span>` : ""}
          ${lead.contact_email ? `<span>${escapeHtml(lead.contact_email)}</span>` : ""}
        </div>
      </a>
    `;
  }

  function renderConvertedColumnBody(rows, baseUrl, showCoach) {
    if (!rows.length) {
      return '<div class="dashboard-lead-column-empty">No leads</div>';
    }

    const visible = rows.slice(0, CONVERTED_PREVIEW_COUNT);
    const hidden = rows.slice(CONVERTED_PREVIEW_COUNT);

    let html = visible.map((lead) => renderCard(lead, baseUrl, showCoach)).join("");

    if (hidden.length) {
      html += `
        <div class="dashboard-lead-column-hidden" style="display:none;">
          ${hidden.map((lead) => renderCard(lead, baseUrl, showCoach)).join("")}
        </div>
        <button type="button" class="dashboard-lead-show-all-btn">Show all ${rows.length} converted</button>
      `;
    }

    return html;
  }

  function renderBoard(board, leads) {
    const baseUrl = board.dataset.baseUrl || "/franchisor_db";
    const showCoach = board.dataset.showCoach === "1";

    const byStage = {};
    STAGE_COLUMNS.forEach((stage) => { byStage[stage] = []; });

    leads.forEach((lead) => {
      const stage = STAGE_COLUMNS.indexOf(lead.pipeline_stage) !== -1 ? lead.pipeline_stage : "New";
      byStage[stage].push(lead);
    });

    board.innerHTML = STAGE_COLUMNS.filter((stage) => stage === "New" || byStage[stage].length).map((stage) => {
      const rows = byStage[stage];
      const body = stage === "Converted"
        ? renderConvertedColumnBody(rows, baseUrl, showCoach)
        : (rows.length ? rows.map((lead) => renderCard(lead, baseUrl, showCoach)).join("") : '<div class="dashboard-lead-column-empty">No leads</div>');

      return `
        <div class="dashboard-lead-column">
          <div class="dashboard-lead-column-head">
            <span>${escapeHtml(stage)}</span>
            <span class="dashboard-lead-column-count">${rows.length}</span>
          </div>
          <div class="dashboard-lead-column-body">
            ${body}
          </div>
        </div>
      `;
    }).join("");

    board.querySelectorAll(".dashboard-lead-show-all-btn").forEach((btn) => {
      btn.addEventListener("click", function () {
        const hidden = btn.previousElementSibling;
        if (hidden) hidden.style.display = "";
        btn.style.display = "none";
      });
    });
  }

  function setCount(count) {
    const countEl = el("recruitmentLeadsCount");
    if (countEl) countEl.textContent = `${count} lead${count === 1 ? "" : "s"}`;
  }

  async function loadLeads() {
    const board = el("recruitmentLeadsKanbanBoard");
    if (!board) return;

    try {
      const leads = await apiPost(`${SHARED_API}.get_recruitment_leads`, {
        scope: board.dataset.scope || "mine",
        lead_type: board.dataset.leadType || "",
      });

      const rows = Array.isArray(leads) ? leads : [];
      renderBoard(board, rows);
      setCount(rows.length);
    } catch (error) {
      console.error("Failed to load recruitment leads:", error);
      board.innerHTML = `<div class="dashboard-empty">${escapeHtml(error.message || "Could not load recruitment leads.")}</div>`;
      setCount(0);
    }
  }

  function initScopeToggle() {
    const board = el("recruitmentLeadsKanbanBoard");
    const toggle = el("recruitmentLeadsScopeToggle");
    if (!board || !toggle) return;

    toggle.querySelectorAll("[data-scope]").forEach((btn) => {
      btn.addEventListener("click", function () {
        if (btn.dataset.scope === board.dataset.scope) return;

        toggle.querySelectorAll("[data-scope]").forEach((b) => b.classList.toggle("is-active", b === btn));
        board.dataset.scope = btn.dataset.scope;
        loadLeads();
      });
    });
  }

  function initTypeToggle() {
    const board = el("recruitmentLeadsKanbanBoard");
    const toggle = el("recruitmentLeadsTypeToggle");
    if (!board || !toggle) return;

    toggle.querySelectorAll("[data-lead-type]").forEach((btn) => {
      btn.addEventListener("click", function () {
        if (btn.dataset.leadType === board.dataset.leadType) return;

        toggle.querySelectorAll("[data-lead-type]").forEach((b) => b.classList.toggle("is-active", b === btn));
        board.dataset.leadType = btn.dataset.leadType;
        loadLeads();
      });
    });
  }

  function init() {
    const board = el("recruitmentLeadsKanbanBoard");
    if (!board) return;

    loadLeads();
    initScopeToggle();
    initTypeToggle();

    const refreshBtn = el("refreshRecruitmentLeads");
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
