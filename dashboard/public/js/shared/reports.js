(function () {
  "use strict";

  var el = Dashboard.el;

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
      throw new Error(data.message || "Request failed.");
    }

    return data.message || data;
  }

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function deskLink(doctype, name) {
    return "/app/" + doctype.toLowerCase().replace(/ /g, "-") + "/" + encodeURIComponent(name);
  }

  function nameLink(doctype, name) {
    return '<a href="' + escapeHtml(deskLink(doctype, name)) + '" target="_blank" rel="noopener">'
      + escapeHtml(name) + '</a>';
  }

  function renderSection(title, items, renderItem) {
    if (!items || !items.length) {
      return '<div class="dashboard-detail-section" style="margin-top:16px;">'
        + '<h3 style="margin-bottom:8px;">' + escapeHtml(title) + ' (0)</h3>'
        + '<div class="dashboard-empty">None found.</div>'
        + '</div>';
    }

    return '<div class="dashboard-detail-section" style="margin-top:16px;">'
      + '<h3 style="margin-bottom:8px;">' + escapeHtml(title) + ' (' + items.length + ')</h3>'
      + '<ul style="margin:0;padding-left:20px;">'
      + items.map(renderItem).join("")
      + '</ul>'
      + '</div>';
  }

  function renderReport(report) {
    var out = el("integrityReportResults");
    var empty = el("integrityReportEmpty");
    if (!out || !empty) return;

    empty.style.display = "none";
    out.style.display = "";

    var html = "";

    html += renderSection(
      "Orphan Client Appointments (linked Event no longer exists)",
      report.orphan_client_appointments,
      function (row) {
        return "<li>" + nameLink("Client Appointment", row.name)
          + " &mdash; was linked to " + escapeHtml(row.linked_event || "—")
          + (row.client ? " (client: " + escapeHtml(row.client) + ")" : "")
          + "</li>";
      }
    );

    html += renderSection(
      "Broken Event &rarr; Client Appointment links",
      report.broken_event_appointment_links,
      function (row) {
        return "<li>" + nameLink("Event", row.name)
          + " points at " + escapeHtml(row.custom_client_appointment || "—") + ", which no longer exists</li>";
      }
    );

    html += renderSection(
      "Orphan client-session Events (Therapy Session / Parent Check-In with no client at all)",
      report.orphan_client_session_events,
      function (row) {
        return "<li>" + nameLink("Event", row.name)
          + " &mdash; " + escapeHtml(row.subject || "") + " (" + escapeHtml(row.starts_on || "") + ")</li>";
      }
    );

    html += renderSection(
      "Duplicate Events (same client, same exact start time)",
      report.duplicate_events,
      function (group) {
        return "<li>Client " + escapeHtml(group.client) + " at " + escapeHtml(group.starts_on) + ": "
          + group.events.map(function (ev) { return nameLink("Event", ev.name); }).join(", ")
          + "</li>";
      }
    );

    html += renderSection(
      "Duplicate Client Appointments (same package balance, same session number)",
      report.duplicate_client_appointments,
      function (group) {
        return "<li>" + escapeHtml(group.client_package_balance) + " session " + escapeHtml(group.session_number) + ": "
          + group.appointments.map(function (a) { return nameLink("Client Appointment", a.name); }).join(", ")
          + "</li>";
      }
    );

    out.innerHTML = html;

    var repairSection = el("repairSection");
    if (repairSection) {
      repairSection.style.display = (report.duplicate_events && report.duplicate_events.length) ? "" : "none";
    }
  }

  async function runIntegrityReport() {
    var btn = el("runIntegrityReportBtn");
    if (btn) { btn.disabled = true; btn.textContent = "Running..."; }

    try {
      var report = await callApi("dashboard.api.shared.packages.get_appointment_integrity_report", {});
      renderReport(report);
    } catch (error) {
      console.error("Integrity report failed:", error);
      window.alert(error.message || "Could not run the report.");
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = "Run Report"; }
    }
  }

  function renderRepairResults(result) {
    var out = el("repairResults");
    if (!out) return;

    var confirmBtn = el("confirmRepairBtn");

    if (!result.duplicate_event_names || !result.duplicate_event_names.length) {
      out.innerHTML = '<div class="dashboard-empty">No duplicate Events to repair.</div>';
      if (confirmBtn) confirmBtn.style.display = "none";
      return;
    }

    var label = result.confirmed ? "Deleted" : "Would delete";
    out.innerHTML = '<div class="dashboard-detail-section">'
      + '<h3 style="margin-bottom:8px;">' + label + " (" + result.duplicate_event_names.length + ")</h3>"
      + '<ul style="margin:0;padding-left:20px;">'
      + result.duplicate_event_names.map(function (name) { return "<li>" + nameLink("Event", name) + "</li>"; }).join("")
      + '</ul>'
      + '<p class="dashboard-help" style="margin-top:8px;">Kept: '
      + result.kept.map(function (name) { return nameLink("Event", name); }).join(", ")
      + '</p>'
      + '</div>';

    if (confirmBtn) {
      confirmBtn.style.display = result.confirmed ? "none" : "";
    }
  }

  async function previewRepair() {
    var btn = el("previewRepairBtn");
    if (btn) { btn.disabled = true; btn.textContent = "Checking..."; }

    try {
      var result = await callApi("dashboard.api.shared.packages.repair_duplicate_client_session_events", { confirm: 0 });
      renderRepairResults(result);
    } catch (error) {
      console.error("Repair preview failed:", error);
      window.alert(error.message || "Could not preview repairs.");
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = "Preview (no changes made)"; }
    }
  }

  async function confirmRepair() {
    if (!window.confirm("This will permanently delete the duplicate Events listed above. This cannot be undone. Continue?")) {
      return;
    }

    var btn = el("confirmRepairBtn");
    if (btn) { btn.disabled = true; btn.textContent = "Deleting..."; }

    try {
      var result = await callApi("dashboard.api.shared.packages.repair_duplicate_client_session_events", { confirm: 1 });
      renderRepairResults(result);
      window.alert("Done - " + result.duplicate_event_names.length + " duplicate event(s) deleted.");
    } catch (error) {
      console.error("Repair failed:", error);
      window.alert(error.message || "Could not complete repairs.");
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = "Confirm Delete"; }
    }
  }

  function init() {
    var runBtn = el("runIntegrityReportBtn");
    if (!runBtn) return; // not on the reports page

    runBtn.addEventListener("click", runIntegrityReport);

    var previewBtn = el("previewRepairBtn");
    if (previewBtn) previewBtn.addEventListener("click", previewRepair);

    var confirmBtn = el("confirmRepairBtn");
    if (confirmBtn) confirmBtn.addEventListener("click", confirmRepair);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
