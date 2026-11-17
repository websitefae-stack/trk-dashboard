/**
 * "Client Portal Access" report tab (see
 * dashboard.api.shared.client_portal_access_report) - every client the
 * current user can see, whether anyone on it has client portal access
 * yet, and when it was granted. Clicking a row expands to the full
 * per-contact breakdown (reuses dashboard.api.shared.portal_access.
 * get_portal_access_rows directly - no separate read endpoint for
 * that). Only the franchisor and a client's own primary coach can
 * actually grant/revoke access - everyone else sees the same status
 * read-only, with a note on who to ask.
 */
(function () {
  "use strict";

  function el(id) {
    return document.getElementById(id);
  }

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function getCsrfToken() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    if (meta && meta.content) return meta.content;
    if (window.frappe && window.frappe.csrf_token) return window.frappe.csrf_token;
    var match = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  async function callApi(method, payload) {
    var response = await fetch("/api/method/" + method, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-Frappe-CSRF-Token": getCsrfToken()
      },
      body: JSON.stringify(payload || {})
    });

    var data = await response.json();

    if (!response.ok || data.exc) {
      console.error(data);
      throw new Error(Dashboard.extractErrorMessage(data, "Request failed."));
    }

    return data.message || data;
  }

  function formatDate(value) {
    if (!value) return "—";
    var date = new Date(value);
    if (isNaN(date.getTime())) return value;
    return date.toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });
  }

  var PERMISSION_FIELDS = [
    "view_profile",
    "can_edit_profile",
    "can_view_appointments",
    "can_book_appointments",
    "can_view_invoices",
    "can_pay_invoices",
    "can_view_courses_and_products",
    "can_view_downloads",
    "view_reports",
    "can_view_admin_details",
    "can_monitor_courses",
    "can_manage_staff_access",
    "can_view_sensitive_details"
  ];

  var PERMISSION_LABELS = {
    view_profile: "View Profile",
    can_edit_profile: "Edit Profile",
    can_view_appointments: "View Appointments",
    can_book_appointments: "Book Appointments",
    can_view_invoices: "View Invoices",
    can_pay_invoices: "Pay Invoices",
    can_view_courses_and_products: "View Courses & Products",
    can_view_downloads: "View Downloads",
    view_reports: "View Reports",
    can_view_admin_details: "View Admin Details",
    can_monitor_courses: "Monitor Courses",
    can_manage_staff_access: "Manage Staff Access",
    can_view_sensitive_details: "View Sensitive Details"
  };

  var state = { rows: [], openClient: "" };

  function renderTable() {
    var body = el("clientPortalAccessTableBody");
    if (!body) return;

    body.innerHTML = state.rows.map(function (row) {
      var mainRow =
        '<tr class="client-portal-access-row" data-client="' + escapeHtml(row.client) + '" style="cursor:pointer;">' +
          "<td>" + escapeHtml(row.client_label || row.client) + "</td>" +
          '<td>' + (row.has_access
            ? '<span class="dashboard-badge dashboard-status-active">Yes</span>'
            : '<span class="dashboard-badge dashboard-status-onhold">No</span>') + "</td>" +
          "<td>" + escapeHtml(formatDate(row.granted_on)) + "</td>" +
        "</tr>";

      var detailRow = row.client === state.openClient
        ? '<tr><td colspan="3"><div id="clientPortalAccessDetail_' + escapeHtml(row.client) + '" class="client-portal-access-detail">Loading…</div></td></tr>'
        : "";

      return mainRow + detailRow;
    }).join("");

    body.querySelectorAll(".client-portal-access-row").forEach(function (tr) {
      tr.addEventListener("click", function () {
        var client = tr.getAttribute("data-client");
        state.openClient = state.openClient === client ? "" : client;
        renderTable();
        if (state.openClient === client) loadDetail(client);
      });
    });
  }

  function permissionGridHtml(row, canManage) {
    var boxes = PERMISSION_FIELDS.map(function (field) {
      return (
        '<label>' +
          '<input type="checkbox" data-perm-row="' + escapeHtml(row.name || "") + '" ' +
          'data-perm-field="' + field + '" ' +
          (row[field] ? "checked " : "") +
          (canManage ? "" : "disabled ") +
          '> ' + escapeHtml(PERMISSION_LABELS[field]) +
        '</label>'
      );
    }).join("");

    var saveBtn = canManage
      ? '<button type="button" class="dashboard-btn dashboard-btn-compact dashboard-btn-light client-portal-access-save-permissions" ' +
        'data-save-permissions-row="' + escapeHtml(row.name || "") + '">Save Permissions</button>'
      : "";

    return '<div class="client-portal-access-permission-grid">' + boxes + "</div>" + saveBtn;
  }

  function contactDetailRowHtml(row, canManage) {
    var hasAccess = !!row.portal_access_enabled;
    var actionCell = "—";

    if (canManage) {
      actionCell =
        '<button type="button" class="dashboard-btn dashboard-btn-compact ' +
        (hasAccess ? "dashboard-btn-light" : "dashboard-btn-primary") + '" ' +
        'data-portal-toggle-row="' + escapeHtml(row.name || "") + '" ' +
        'data-portal-toggle-contact="' + escapeHtml(row.contact || "") + '">' +
        (hasAccess ? "Revoke Access" : "Grant Access") +
        "</button>";

      if (!hasAccess) {
        actionCell +=
          '<label style="display:block; margin-top:4px; font-weight:normal; font-size:12px;">' +
          '<input type="checkbox" data-portal-toggle-notify="' + escapeHtml(row.name || "") + '" checked> ' +
          "Email them their login details" +
          "</label>";
      }
    }

    return (
      "<tr>" +
        "<td>" + escapeHtml(row.contact_name || "—") + "</td>" +
        "<td>" + escapeHtml(row.email_id || "—") + "</td>" +
        "<td>" + escapeHtml(row.relationship_type || "—") + "</td>" +
        "<td>" + permissionGridHtml(row, canManage) + "</td>" +
        "<td>" + (hasAccess ? "Yes" : "No") + "</td>" +
        "<td>" + escapeHtml(formatDate(row.portal_access_granted_on)) + "</td>" +
        "<td>" + escapeHtml(formatDate(row.portal_access_notified_on)) + "</td>" +
        "<td>" + actionCell + "</td>" +
      "</tr>"
    );
  }

  async function loadDetail(client) {
    var container = el("clientPortalAccessDetail_" + client);
    if (!container) return;

    var summaryRow = state.rows.filter(function (r) { return r.client === client; })[0] || {};

    try {
      var payload = await callApi("dashboard.api.shared.portal_access.get_portal_access_rows", { client_name: client });
      var rows = (payload && payload.rows) || [];
      var canManage = !!(payload && payload.can_manage);

      container = el("clientPortalAccessDetail_" + client);
      if (!container) return;

      var askNote = "";
      if (!canManage && !summaryRow.has_access) {
        askNote = '<p class="dashboard-help" style="margin-bottom:10px;">'
          + (summaryRow.primary_coach_label
            ? "Ask " + escapeHtml(summaryRow.primary_coach_label) + " to grant access for this client."
            : "Only the franchisor or this client's primary coach can grant access.")
          + "</p>";
      }

      if (!rows.length) {
        container.innerHTML = askNote + '<p class="dashboard-help">No contacts have portal access set up for this client yet'
          + (canManage ? " - add a contact and grant access from the client's own page." : ".")
          + "</p>";
        return;
      }

      container.innerHTML = askNote +
        '<div class="dashboard-table-wrap">' +
          '<table class="dashboard-table dashboard-table-compact client-portal-access-table">' +
            "<thead><tr>" +
              "<th>Contact</th><th>Email</th><th>Relationship</th><th>Permissions</th><th>Access</th><th>Granted On</th><th>Notified On</th><th></th>" +
            "</tr></thead>" +
            "<tbody>" + rows.map(function (row) { return contactDetailRowHtml(row, canManage); }).join("") + "</tbody>" +
          "</table>" +
        "</div>";

      container.querySelectorAll("[data-portal-toggle-row]").forEach(function (button) {
        button.addEventListener("click", function (event) {
          event.stopPropagation();
          toggleAccess(client, button, rows);
        });
      });

      container.querySelectorAll("[data-save-permissions-row]").forEach(function (button) {
        button.addEventListener("click", function (event) {
          event.stopPropagation();
          savePermissions(client, button, rows);
        });
      });
    } catch (error) {
      if (container) container.innerHTML = '<p class="dashboard-help">' + escapeHtml(error.message || "Could not load contacts.") + "</p>";
    }
  }

  async function toggleAccess(client, button, rows) {
    var rowName = button.getAttribute("data-portal-toggle-row");
    var contact = button.getAttribute("data-portal-toggle-contact");
    var row = rows.filter(function (r) { return r.name === rowName; })[0];
    if (!row) return;

    var willEnable = !row.portal_access_enabled;
    var notifyCheckbox = button.parentElement.querySelector('[data-portal-toggle-notify="' + rowName + '"]');

    button.disabled = true;
    button.textContent = willEnable ? "Granting…" : "Revoking…";

    var otherRowNames = (row.row_names || [row.name]).filter(function (name) { return name !== row.name; });

    try {
      await callApi("dashboard.api.shared.portal_access.save_portal_access_row", {
        client_name: client,
        contact: contact || "",
        also_row_names: JSON.stringify(otherRowNames),
        data: JSON.stringify({
          contact_name: row.contact_name,
          email_id: row.email_id,
          phone: row.phone,
          relationship_type: row.relationship_type,
          is_primary_contact: row.is_primary_contact,
          is_billing_contact: row.is_billing_contact,
          portal_access_enabled: willEnable ? 1 : 0,
          notify_by_email: willEnable && notifyCheckbox && notifyCheckbox.checked ? 1 : 0,
          view_profile: row.view_profile,
          can_edit_profile: row.can_edit_profile,
          can_view_appointments: row.can_view_appointments,
          can_book_appointments: row.can_book_appointments,
          can_view_invoices: row.can_view_invoices,
          can_pay_invoices: row.can_pay_invoices,
          can_view_courses_and_products: row.can_view_courses_and_products,
          can_view_downloads: row.can_view_downloads,
          view_reports: row.view_reports,
          can_view_admin_details: row.can_view_admin_details,
          can_monitor_courses: row.can_monitor_courses,
          can_manage_staff_access: row.can_manage_staff_access,
          can_view_sensitive_details: row.can_view_sensitive_details
        })
      });

      await runReport();
      state.openClient = client;
      renderTable();
      loadDetail(client);
    } catch (error) {
      window.alert(error.message || "Could not update portal access.");
      button.disabled = false;
      button.textContent = willEnable ? "Grant Access" : "Revoke Access";
    }
  }

  async function savePermissions(client, button, rows) {
    var rowName = button.getAttribute("data-save-permissions-row");
    var row = rows.filter(function (r) { return r.name === rowName; })[0];
    if (!row) return;

    var cell = button.closest("td");
    var permissions = {};
    cell.querySelectorAll("[data-perm-field]").forEach(function (checkbox) {
      permissions[checkbox.getAttribute("data-perm-field")] = checkbox.checked ? 1 : 0;
    });

    var otherRowNames = (row.row_names || [row.name]).filter(function (name) { return name !== row.name; });

    button.disabled = true;
    button.textContent = "Saving…";

    try {
      await callApi("dashboard.api.shared.portal_access.save_portal_access_row", {
        client_name: client,
        contact: row.contact || "",
        also_row_names: JSON.stringify(otherRowNames),
        data: JSON.stringify(Object.assign({
          contact_name: row.contact_name,
          email_id: row.email_id,
          phone: row.phone,
          relationship_type: row.relationship_type,
          is_primary_contact: row.is_primary_contact,
          is_billing_contact: row.is_billing_contact,
          portal_access_enabled: row.portal_access_enabled,
          notify_by_email: 0
        }, permissions))
      });

      button.textContent = "Saved";
      setTimeout(function () {
        button.disabled = false;
        button.textContent = "Save Permissions";
      }, 1500);
    } catch (error) {
      window.alert(error.message || "Could not save permissions.");
      button.disabled = false;
      button.textContent = "Save Permissions";
    }
  }

  async function runReport() {
    var btn = el("runClientPortalAccessReportBtn");
    var empty = el("clientPortalAccessEmpty");
    var results = el("clientPortalAccessResults");

    if (btn) { btn.disabled = true; btn.textContent = "Running..."; }

    try {
      var payload = await callApi("dashboard.api.shared.client_portal_access_report.get_client_portal_access_report", {});
      var rows = (payload && payload.rows) || [];
      state.rows = rows;

      if (!rows.length) {
        if (empty) { empty.style.display = ""; empty.textContent = "No clients found."; }
        if (results) results.style.display = "none";
        return;
      }

      if (empty) empty.style.display = "none";
      if (results) results.style.display = "";

      renderTable();
    } catch (error) {
      window.alert(error.message || "Could not run the report.");
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = "Run Report"; }
    }
  }

  function init() {
    if (!el("runClientPortalAccessReportBtn")) return;

    el("runClientPortalAccessReportBtn").addEventListener("click", runReport);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
