/**
 * "My Documents" - the coach-facing view of their own Coach Document
 * Requirement rows (assigned by dashboard.api.shared.practice_documents.
 * sync_coach_document_requirements when a Practice Document is published).
 * Mirrors client_resources.js's conventions for the sibling Client
 * Resources feature - same request helpers, same card grid.
 */
(function () {
  "use strict";

  var el = Dashboard.el;
  var qsa = Dashboard.qsa;

  var API = "dashboard.api.shared.practice_documents";

  var STATUS_LABELS = {
    "Pending": "Pending",
    "Acknowledged": "Acknowledged",
    "Completed": "Completed"
  };

  var NEXT_ACTION = {
    "Pending": { status: "Acknowledged", label: "Mark Acknowledged" },
    "Acknowledged": { status: "Completed", label: "Mark Complete" }
  };

  function getCsrfToken() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    return meta && meta.content ? meta.content : "";
  }

  async function apiGet(method, args) {
    var params = new URLSearchParams(args || {});
    var response = await fetch("/api/method/" + method + "?" + params.toString(), {
      method: "GET",
      credentials: "same-origin"
    });

    var data = await response.json();

    if (!response.ok || data.exc) {
      throw new Error(data.message || "There was a problem loading this.");
    }

    return data.message;
  }

  async function apiPost(method, args) {
    var response = await fetch("/api/method/" + method, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-Frappe-CSRF-Token": getCsrfToken()
      },
      body: JSON.stringify(args || {})
    });

    var data = await response.json();

    if (!response.ok || data.exc) {
      throw new Error(data.message || "There was a problem saving this.");
    }

    return data.message;
  }

  function setText(id, value) {
    var node = el(id);
    if (node) node.textContent = value == null ? "" : value;
  }

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function formatDate(value) {
    if (!value) return "—";
    var date = new Date(String(value).replace(" ", "T"));
    if (Number.isNaN(date.getTime())) return String(value);
    return date.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
  }

  // -------------------------------------------------------------------
  // My Documents card (coach_db home)
  // -------------------------------------------------------------------

  async function initMyDocumentsCard() {
    var card = el("dashboardMyDocumentsCard");
    if (!card) return;

    try {
      var summary = await apiGet(API + ".get_my_document_summary");

      setText("myDocumentsOutstanding", summary.outstanding || 0);

      var badge = el("myDocumentsBadge");
      if (badge) {
        if (summary.outstanding > 0) {
          badge.style.display = "inline-flex";
          badge.textContent = summary.outstanding;
        } else {
          badge.style.display = "none";
        }
      }

      var recentEl = el("myDocumentsRecent");
      if (recentEl) {
        var recent = summary.recent_outstanding || [];
        recentEl.innerHTML = recent.length
          ? recent.map(function (row) {
              return '<div class="dashboard-resources-recent-row">' + escapeHtml(row.document_title) + "</div>";
            }).join("")
          : '<div class="dashboard-resources-recent-row">Nothing outstanding.</div>';
      }
    } catch (err) {
      // Card is decorative on the home dashboard - fail quietly.
    }
  }

  // -------------------------------------------------------------------
  // /coach_db/coach-documents page
  // -------------------------------------------------------------------

  function renderDocumentCard(row) {
    var statusClass = "doc-status-" + row.status;
    var categories = (row.categories || []).map(function (label) {
      return '<span class="dashboard-badge">' + escapeHtml(label) + "</span>";
    }).join("");

    var fileUrl = row.has_file
      ? "/api/method/" + API + ".get_my_document_file?requirement_name=" + encodeURIComponent(row.name)
      : "";

    var action = NEXT_ACTION[row.status];

    return (
      '<div class="client-resource-card" data-requirement="' + escapeHtml(row.name) + '">' +
        '<div class="client-resource-card-title">' + escapeHtml(row.document_title) + "</div>" +
        '<div class="client-resource-card-meta">' +
          escapeHtml(row.document_code || "") + (row.document_version ? " · v" + escapeHtml(row.document_version) : "") +
          (row.document_type ? " · " + escapeHtml(row.document_type) : "") +
        "</div>" +
        (row.summary ? '<div class="client-resource-card-summary">' + escapeHtml(row.summary) + "</div>" : "") +
        (categories ? '<div class="client-resource-card-categories">' + categories + "</div>" : "") +
        '<div class="client-resource-card-row"><strong>Status:</strong> <span class="dashboard-badge ' + statusClass + '">' + escapeHtml(STATUS_LABELS[row.status] || row.status) + "</span>" + (row.mandatory ? ' <span class="dashboard-badge">Mandatory</span>' : "") + "</div>" +
        '<div class="client-resource-card-row"><strong>Assigned:</strong> ' + escapeHtml(formatDate(row.assigned_on)) + "</div>" +
        (row.completed_on ? '<div class="client-resource-card-row"><strong>Completed:</strong> ' + escapeHtml(formatDate(row.completed_on)) + "</div>" : "") +
        '<div class="client-resource-card-actions">' +
          (fileUrl ? '<a class="dashboard-btn dashboard-btn-light" href="' + escapeHtml(fileUrl) + '" target="_blank" rel="noopener">View</a>' : '<span class="dashboard-btn dashboard-btn-light" style="opacity:.5;pointer-events:none;">View</span>') +
          (action ? '<button type="button" class="dashboard-btn dashboard-btn-primary doc-action-btn" data-requirement="' + escapeHtml(row.name) + '" data-status="' + escapeHtml(action.status) + '">' + escapeHtml(action.label) + "</button>" : "") +
        "</div>" +
      "</div>"
    );
  }

  function renderDocuments(rows) {
    var grid = el("coachDocumentsGrid");
    if (!grid) return;

    if (!rows.length) {
      grid.innerHTML = '<div class="dashboard-empty">You do not currently have any documents to complete.</div>';
      return;
    }

    grid.innerHTML = rows.map(renderDocumentCard).join("");

    qsa(".doc-action-btn", grid).forEach(function (button) {
      button.addEventListener("click", function () {
        updateStatus(button.dataset.requirement, button.dataset.status, button);
      });
    });
  }

  async function updateStatus(requirementName, status, button) {
    if (button) {
      button.disabled = true;
      button.textContent = "Saving...";
    }

    try {
      await apiPost(API + ".update_my_document_status", {
        requirement_name: requirementName,
        status: status
      });

      loadDocuments();
      initMyDocumentsCard();
    } catch (err) {
      window.alert(err.message || "Could not update this document.");
      if (button) button.disabled = false;
    }
  }

  async function loadDocuments() {
    var grid = el("coachDocumentsGrid");
    if (!grid) return;

    grid.innerHTML = '<div class="dashboard-empty">Loading documents...</div>';

    try {
      var summary = await apiGet(API + ".get_my_document_summary");
      setText("coachDocumentsOutstanding", summary.outstanding || 0);
      setText("coachDocumentsCompleted", summary.completed || 0);
      setText("coachDocumentsTotal", summary.total || 0);

      var rows = await apiGet(API + ".get_my_document_requirements");
      renderDocuments(rows || []);
    } catch (err) {
      grid.innerHTML = '<div class="dashboard-empty">' + escapeHtml(err.message || "Could not load your documents.") + "</div>";
    }
  }

  function initCoachDocumentsPage() {
    if (!el("coachDocumentsPage")) return;
    loadDocuments();
  }

  function init() {
    initMyDocumentsCard();
    initCoachDocumentsPage();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
