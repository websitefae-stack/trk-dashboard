/**
 * "Documents" - one section per Practice Document Type, listing the
 * current user's own Coach Document Requirement rows of that type.
 * Sections are read dynamically from the Document Type Select options,
 * so adding/renaming a type there is the only thing needed to change
 * what shows up here.
 */
(function () {
  "use strict";

  var el = Dashboard.el;
  var qsa = Dashboard.qsa;

  var API = "dashboard.api.shared.practice_documents";

  var STATUS_CLASS = {
    "Not Viewed": "doc-status-new",
    "Overdue": "doc-status-overdue",
    "Completed": "doc-status-completed",
    "Superseded": "doc-status-superseded"
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
      throw new Error(data.message || "There was a problem loading your documents.");
    }

    return data.message;
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
    if (!value) return "";
    var date = new Date(String(value).replace(" ", "T"));
    if (Number.isNaN(date.getTime())) return String(value);
    return date.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
  }

  function slugForDesk(name) {
    return "coach-document-requirement/" + encodeURIComponent(name);
  }

  function renderDocumentRow(row) {
    var statusClass = STATUS_CLASS[row.status] || "";
    var fileUrl = "/api/method/" + API + ".get_my_document_file?requirement_name=" + encodeURIComponent(row.name);

    return (
      '<div class="dashboard-doc-row">' +
        '<div class="dashboard-doc-row-main">' +
          '<div class="dashboard-doc-row-title">' + escapeHtml(row.document_title) +
            (row.mandatory ? ' <span class="dashboard-badge">Mandatory</span>' : "") +
          "</div>" +
          '<div class="dashboard-doc-row-meta">' +
            escapeHtml(row.document_code || "") +
            (row.document_version ? " &middot; v" + escapeHtml(row.document_version) : "") +
            (row.due_date ? " &middot; Due " + escapeHtml(formatDate(row.due_date)) : "") +
          "</div>" +
        "</div>" +
        '<div class="dashboard-doc-row-status">' +
          '<span class="dashboard-badge ' + statusClass + '">' + escapeHtml(row.status) + "</span>" +
        "</div>" +
        '<div class="dashboard-doc-row-actions">' +
          '<a class="dashboard-btn dashboard-btn-light" href="' + fileUrl + '" target="_blank" rel="noopener">View</a>' +
          '<a class="dashboard-btn dashboard-btn-primary" href="/app/' + slugForDesk(row.name) + '" target="_blank" rel="noopener">Open</a>' +
        "</div>" +
      "</div>"
    );
  }

  function renderTypeSection(documentType, rows) {
    var body = rows.length
      ? rows.map(renderDocumentRow).join("")
      : '<div class="dashboard-empty">No ' + escapeHtml(documentType).toLowerCase() + ' documents assigned.</div>';

    return (
      '<div class="dashboard-tab-panel" id="docType_' + escapeHtml(documentType).replace(/[^a-zA-Z0-9]/g, "") + '">' +
        '<div class="dashboard-card">' + body + "</div>" +
      "</div>"
    );
  }

  function activateTab(targetId) {
    qsa(".dashboard-tab-btn[data-tab-target]").forEach(function (button) {
      button.classList.toggle("is-active", button.dataset.tabTarget === targetId);
    });

    qsa(".dashboard-tab-panel").forEach(function (panel) {
      panel.classList.toggle("is-active", panel.id === targetId);
      panel.style.display = panel.id === targetId ? "block" : "none";
    });
  }

  function initTabs(firstTargetId) {
    var tabsWrap = el("documentTypeTabs");
    if (!tabsWrap) return;

    qsa(".dashboard-tab-btn[data-tab-target]", tabsWrap).forEach(function (button) {
      button.addEventListener("click", function () {
        activateTab(button.dataset.tabTarget);
      });
    });

    if (firstTargetId) activateTab(firstTargetId);
  }

  async function loadDocuments() {
    var tabsWrap = el("documentTypeTabs");
    var panelsWrap = el("documentTypePanels");
    if (!tabsWrap || !panelsWrap) return;

    panelsWrap.innerHTML = '<div class="dashboard-empty">Loading documents...</div>';

    var data;
    try {
      data = await apiGet(API + ".get_my_documents_by_type", {});
    } catch (error) {
      panelsWrap.innerHTML = '<div class="dashboard-empty">' + escapeHtml(error.message) + "</div>";
      return;
    }

    var types = data.types || [];
    var documents = data.documents || {};

    if (!types.length) {
      tabsWrap.innerHTML = "";
      panelsWrap.innerHTML = '<div class="dashboard-empty">No document types are configured yet.</div>';
      return;
    }

    tabsWrap.innerHTML = types.map(function (documentType, index) {
      var targetId = "docType_" + documentType.replace(/[^a-zA-Z0-9]/g, "");
      var count = (documents[documentType] || []).length;
      return (
        '<button type="button" class="dashboard-tab-btn' + (index === 0 ? " is-active" : "") + '" data-tab-target="' + targetId + '">' +
          escapeHtml(documentType) + (count ? " (" + count + ")" : "") +
        "</button>"
      );
    }).join("");

    panelsWrap.innerHTML = types.map(function (documentType) {
      return renderTypeSection(documentType, documents[documentType] || []);
    }).join("");

    var firstTargetId = "docType_" + types[0].replace(/[^a-zA-Z0-9]/g, "");
    initTabs(firstTargetId);
  }

  function init() {
    if (!el("documentsPage")) return;
    loadDocuments();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
