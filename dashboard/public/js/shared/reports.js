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

  function dashboardBaseUrl() {
    var container = document.querySelector("[data-base-url]");
    return (container && container.dataset.baseUrl) || "/coach_db";
  }

  function formatDate(value) {
    if (!value) return "—";
    var datePart = String(value).split(" ")[0];
    var parts = datePart.split("-");
    if (parts.length !== 3) return datePart;
    return parts[2] + "/" + parts[1] + "/" + parts[0];
  }

  function csvCell(value) {
    var text = String(value == null ? "" : value).replace(/"/g, '""');
    return '"' + text + '"';
  }

  // Plain CSV rather than a real .xlsx - Excel (and Sheets/Numbers) all
  // open CSV directly with no extra dependency on this app's side.
  function exportRowsToCsv(filename, columns, rows) {
    if (!rows || !rows.length) {
      window.alert("Run the report first.");
      return;
    }

    var lines = [columns.map(function (c) { return csvCell(c.label); }).join(",")];

    rows.forEach(function (row) {
      lines.push(columns.map(function (c) { return csvCell(c.value(row)); }).join(","));
    });

    var blob = new Blob(["﻿" + lines.join("\r\n")], { type: "text/csv;charset=utf-8;" });
    var url = URL.createObjectURL(blob);

    var link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
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

    var resyncSection = el("resyncSection");
    if (resyncSection) {
      resyncSection.style.display = (report.duplicate_client_appointments && report.duplicate_client_appointments.length) ? "" : "none";
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

  function renderResyncResults(result) {
    var out = el("resyncResults");
    if (!out) return;

    var confirmBtn = el("confirmResyncBtn");
    var resynced = result.resynced_balances || [];
    var failed = result.failed_balances || [];

    if (!resynced.length && !failed.length) {
      out.innerHTML = '<div class="dashboard-empty">No duplicate session numbers to resync.</div>';
      if (confirmBtn) confirmBtn.style.display = "none";
      return;
    }

    var label = result.confirmed ? "Resynced" : "Would attempt";
    var html = "";

    if (resynced.length) {
      html += '<div class="dashboard-detail-section">'
        + '<h3 style="margin-bottom:8px;">' + label + " (" + resynced.length + ")</h3>"
        + '<ul style="margin:0;padding-left:20px;">'
        + resynced.map(function (name) { return "<li>" + nameLink("Client Package Balance", name) + "</li>"; }).join("")
        + '</ul>'
        + '</div>';
    }

    if (failed.length) {
      html += '<div class="dashboard-detail-section" style="margin-top:16px;">'
        + '<h3 style="margin-bottom:8px;color:#b91c1c;">Still broken - hit an error (' + failed.length + ")</h3>"
        + '<p class="dashboard-help" style="margin-bottom:8px;">Check the Error Log for these - title starts with "Recalculate Client Package Balance" or "Repair Duplicate Session Numbers".</p>'
        + '<ul style="margin:0;padding-left:20px;">'
        + failed.map(function (row) {
            var events = (row.failed_events || []).length
              ? " (failed on: " + row.failed_events.map(function (n) { return nameLink("Event", n); }).join(", ") + ")"
              : "";
            return "<li>" + nameLink("Client Package Balance", row.balance) + events + "</li>";
          }).join("")
        + '</ul>'
        + '</div>';
    }

    out.innerHTML = html;

    if (confirmBtn) {
      confirmBtn.style.display = (result.confirmed || !resynced.length) ? "none" : "";
    }
  }

  async function previewResync() {
    var btn = el("previewResyncBtn");
    if (btn) { btn.disabled = true; btn.textContent = "Checking..."; }

    try {
      var result = await callApi("dashboard.api.shared.packages.repair_duplicate_session_numbers", { confirm: 0 });
      renderResyncResults(result);
    } catch (error) {
      console.error("Resync preview failed:", error);
      window.alert(error.message || "Could not preview the resync.");
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = "Preview (no changes made)"; }
    }
  }

  async function confirmResync() {
    if (!window.confirm("This will recalculate session numbers for the packs listed above. Continue?")) {
      return;
    }

    var btn = el("confirmResyncBtn");
    if (btn) { btn.disabled = true; btn.textContent = "Resyncing..."; }

    try {
      var result = await callApi("dashboard.api.shared.packages.repair_duplicate_session_numbers", { confirm: 1 });
      renderResyncResults(result);
      window.alert("Done - " + result.resynced_balances.length + " pack(s) resynced.");
    } catch (error) {
      console.error("Resync failed:", error);
      window.alert(error.message || "Could not complete the resync.");
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = "Confirm Resync"; }
    }
  }

  var intakeFormState = {
    rows: [],
    questions: null // fetched lazily, cached once loaded
  };

  function lead_detail_url(name) {
    return dashboardBaseUrl() + "/lead_details?name=" + encodeURIComponent(name);
  }

  function renderIntakeFormReport(rows) {
    var empty = el("intakeFormReportEmpty");
    var results = el("intakeFormReportResults");
    var body = el("intakeFormReportTableBody");
    if (!empty || !results || !body) return;

    intakeFormState.rows = rows || [];

    if (!rows.length) {
      empty.textContent = "No intake forms found.";
      empty.style.display = "";
      results.style.display = "none";
      return;
    }

    empty.style.display = "none";

    fillSelect(el("intakeFormPersonSelect"), rows.map(function (row) {
      return { value: row.name, label: row.client_name || row.name };
    }), "Select a person");

    applyIntakeFormViewMode();
  }

  function fillSelect(select, options, placeholderLabel) {
    if (!select) return;
    var current = select.value;
    select.innerHTML = '<option value="">' + escapeHtml(placeholderLabel || "Select") + "</option>"
      + options.map(function (opt) {
        return '<option value="' + escapeHtml(opt.value) + '">' + escapeHtml(opt.label) + "</option>";
      }).join("");
    if (current && options.some(function (opt) { return opt.value === current; })) {
      select.value = current;
    }
  }

  function renderIntakeFormSummaryTable(rows) {
    var body = el("intakeFormReportTableBody");
    if (!body) return;

    body.innerHTML = rows.map(function (row) {
      var detailUrl = lead_detail_url(row.name);
      var statusLabel = row.is_completed
        ? '<span style="color:#1a7f37;">Completed</span>'
        : '<span style="color:#b8860b;">Sent, not yet completed</span>';

      return "<tr>"
        + '<td><a class="dashboard-inline-link" href="' + escapeHtml(detailUrl) + '">'
        + escapeHtml(row.client_name || row.name) + "</a></td>"
        + "<td>" + escapeHtml(row.contact_name || "—")
        + (row.contact_email ? "<br><small>" + escapeHtml(row.contact_email) + "</small>" : "") + "</td>"
        + "<td>" + escapeHtml(row.coach_label || "—") + "</td>"
        + "<td>" + formatDate(row.intake_sent_on) + "</td>"
        + "<td>" + statusLabel + "</td>"
        + '<td><a class="dashboard-inline-link" href="' + escapeHtml(detailUrl) + '" target="_blank" rel="noopener">Open</a></td>'
        + "</tr>";
    }).join("");
  }

  async function ensureIntakeFormQuestions() {
    if (intakeFormState.questions) return intakeFormState.questions;

    var questions = await callApi("dashboard.api.shared.form_reports.get_intake_form_questions", {});
    intakeFormState.questions = questions || [];

    fillSelect(el("intakeFormQuestionSelect"), intakeFormState.questions.map(function (q) {
      return { value: q.value, label: q.label };
    }), "Select a question");

    return intakeFormState.questions;
  }

  async function loadIntakeFormPersonAnswers(name) {
    var empty = el("intakeFormPersonEmpty");
    var results = el("intakeFormPersonResults");
    var body = el("intakeFormPersonTableBody");
    if (!empty || !results || !body) return;

    if (!name) {
      empty.textContent = "Select a person to see their answers.";
      empty.style.display = "";
      results.style.display = "none";
      return;
    }

    empty.textContent = "Loading...";
    empty.style.display = "";
    results.style.display = "none";

    try {
      var data = await callApi("dashboard.api.shared.form_reports.get_intake_form_answers_for_person", { name: name });

      empty.style.display = "none";
      results.style.display = "";

      var detailUrl = lead_detail_url(data.name);
      body.innerHTML = '<tr><td><strong>Full record</strong></td><td><a class="dashboard-inline-link" href="'
        + escapeHtml(detailUrl) + '" target="_blank" rel="noopener">Open ' + escapeHtml(data.client_name || data.name) + "</a></td></tr>"
        + (data.answers || []).map(function (answer) {
          return "<tr><td>" + escapeHtml(answer.label) + "</td><td>" + escapeHtml(answer.value == null ? "—" : answer.value) + "</td></tr>";
        }).join("");
    } catch (error) {
      console.error("Could not load person's intake answers:", error);
      empty.textContent = error.message || "Could not load this person's answers.";
      empty.style.display = "";
      results.style.display = "none";
    }
  }

  async function loadIntakeFormQuestionAnswers(question) {
    var empty = el("intakeFormQuestionEmpty");
    var results = el("intakeFormQuestionResults");
    var body = el("intakeFormQuestionTableBody");
    var columnHead = el("intakeFormQuestionColumnHead");
    if (!empty || !results || !body) return;

    if (!question) {
      empty.textContent = "Select a question to see everyone's answer.";
      empty.style.display = "";
      results.style.display = "none";
      return;
    }

    empty.textContent = "Loading...";
    empty.style.display = "";
    results.style.display = "none";

    try {
      var data = await callApi("dashboard.api.shared.form_reports.get_intake_form_answers_for_question", { question: question });

      empty.style.display = "none";
      results.style.display = "";
      if (columnHead) columnHead.textContent = data.question || "Answer";

      if (!data.rows || !data.rows.length) {
        empty.textContent = "No answers found.";
        empty.style.display = "";
        results.style.display = "none";
        return;
      }

      body.innerHTML = data.rows.map(function (row) {
        var detailUrl = lead_detail_url(row.lead);
        return "<tr>"
          + '<td><a class="dashboard-inline-link" href="' + escapeHtml(detailUrl) + '">' + escapeHtml(row.client_name || row.lead) + "</a></td>"
          + "<td>" + escapeHtml(row.coach_label || "—") + "</td>"
          + "<td>" + escapeHtml(row.value || "—") + "</td>"
          + "</tr>";
      }).join("");
    } catch (error) {
      console.error("Could not load question's intake answers:", error);
      empty.textContent = error.message || "Could not load answers for this question.";
      empty.style.display = "";
      results.style.display = "none";
    }
  }

  function applyIntakeFormViewMode() {
    var mode = (el("intakeFormViewMode") || {}).value || "summary";

    toggleDisplayEl("intakeFormControlsRow", mode !== "summary");
    toggleDisplayEl("intakeFormPersonRow", mode === "person");
    toggleDisplayEl("intakeFormQuestionRow", mode === "question");

    toggleDisplayEl("intakeFormReportResults", mode === "summary" && intakeFormState.rows.length > 0);
    toggleDisplayEl("intakeFormPersonResults", false);
    toggleDisplayEl("intakeFormQuestionResults", false);

    var personEmpty = el("intakeFormPersonEmpty");
    var questionEmpty = el("intakeFormQuestionEmpty");
    if (personEmpty) personEmpty.style.display = mode === "person" ? "" : "none";
    if (questionEmpty) questionEmpty.style.display = mode === "question" ? "" : "none";

    if (mode === "summary") {
      renderIntakeFormSummaryTable(intakeFormState.rows);
    } else if (mode === "person") {
      loadIntakeFormPersonAnswers(el("intakeFormPersonSelect") ? el("intakeFormPersonSelect").value : "");
    } else if (mode === "question") {
      ensureIntakeFormQuestions().then(function () {
        loadIntakeFormQuestionAnswers(el("intakeFormQuestionSelect") ? el("intakeFormQuestionSelect").value : "");
      });
    }
  }

  function toggleDisplayEl(id, show) {
    var node = el(id);
    if (!node) return;
    node.style.display = show ? "" : "none";
  }

  async function runIntakeFormReport() {
    var btn = el("runIntakeFormReportBtn");
    if (btn) { btn.disabled = true; btn.textContent = "Running..."; }

    try {
      var rows = await callApi("dashboard.api.shared.form_reports.get_intake_form_report", {
        from_date: (el("intakeFormFromDate") || {}).value || "",
        to_date: (el("intakeFormToDate") || {}).value || ""
      });
      renderIntakeFormReport(rows);

      var exportBtn = el("exportIntakeFormReportBtn");
      if (exportBtn) exportBtn.style.display = rows.length ? "" : "none";
    } catch (error) {
      console.error("Intake form report failed:", error);
      window.alert(error.message || "Could not run the report.");
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = "Run Report"; }
    }
  }

  function exportIntakeFormReport() {
    exportRowsToCsv("intake-forms.csv", [
      { label: "Client / Young Person", value: function (r) { return r.client_name || r.name; } },
      { label: "Contact", value: function (r) { return r.contact_name || ""; } },
      { label: "Contact Email", value: function (r) { return r.contact_email || ""; } },
      { label: "Coach", value: function (r) { return r.coach_label || ""; } },
      { label: "Sent", value: function (r) { return formatDate(r.intake_sent_on); } },
      { label: "Status", value: function (r) { return r.is_completed ? "Completed" : "Sent, not yet completed"; } }
    ], intakeFormState.rows);
  }

  function renderResyncIntakeFormsResults(result) {
    var out = el("resyncIntakeFormsResults");
    if (!out) return;

    var confirmBtn = el("confirmResyncIntakeFormsBtn");
    var resynced = result.resynced || [];
    var unmatched = result.unmatched || [];

    if (!resynced.length && !unmatched.length) {
      out.innerHTML = '<div class="dashboard-empty">No stuck intake forms found.</div>';
      if (confirmBtn) confirmBtn.style.display = "none";
      return;
    }

    var label = result.confirmed ? "Resynced" : "Would resync";
    var html = "";

    if (resynced.length) {
      html += '<div class="dashboard-detail-section">'
        + '<h3 style="margin-bottom:8px;">' + label + " (" + resynced.length + ")</h3>"
        + '<ul style="margin:0;padding-left:20px;">'
        + resynced.map(function (row) {
            return "<li>" + nameLink("Client Lead", row.lead) + " &larr; " + nameLink("Intake Doctype", row.intake) + "</li>";
          }).join("")
        + '</ul>'
        + '</div>';
    }

    if (unmatched.length) {
      html += '<div class="dashboard-detail-section" style="margin-top:16px;">'
        + '<h3 style="margin-bottom:8px;">Could not resync (' + unmatched.length + ")</h3>"
        + '<ul style="margin:0;padding-left:20px;">'
        + unmatched.map(function (row) {
            return "<li>" + nameLink("Client Lead", row.lead) + " &mdash; " + escapeHtml(row.reason || "") + "</li>";
          }).join("")
        + '</ul>'
        + '</div>';
    }

    out.innerHTML = html;

    if (confirmBtn) {
      confirmBtn.style.display = (result.confirmed || !resynced.length) ? "none" : "";
    }
  }

  async function previewResyncIntakeForms() {
    var btn = el("previewResyncIntakeFormsBtn");
    if (btn) { btn.disabled = true; btn.textContent = "Checking..."; }

    try {
      var result = await callApi("dashboard.api.shared.leads.resync_stuck_intake_forms", { confirm: 0 });
      renderResyncIntakeFormsResults(result);
    } catch (error) {
      console.error("Resync intake forms preview failed:", error);
      window.alert(error.message || "Could not preview the resync.");
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = "Preview (no changes made)"; }
    }
  }

  async function confirmResyncIntakeForms() {
    if (!window.confirm("This will update the leads listed above with their matching intake submission's answers. Continue?")) {
      return;
    }

    var btn = el("confirmResyncIntakeFormsBtn");
    if (btn) { btn.disabled = true; btn.textContent = "Resyncing..."; }

    try {
      var result = await callApi("dashboard.api.shared.leads.resync_stuck_intake_forms", { confirm: 1 });
      renderResyncIntakeFormsResults(result);
      window.alert("Done - " + (result.resynced || []).length + " lead(s) resynced.");
    } catch (error) {
      console.error("Resync intake forms failed:", error);
      window.alert(error.message || "Could not complete the resync.");
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = "Confirm Resync"; }
    }
  }

  var formModuleState = { rows: [], questionRows: [], chartQuestions: [], mode: "charts" };

  // Fixed-order categorical palette (light mode) - validated for CVD-safe
  // adjacent contrast. Assigned by slot index within each chart, never by
  // rank/sort order, so the same answer option keeps the same color across
  // re-renders.
  var FORM_CHART_COLORS = [
    "#2a78d6", "#008300", "#e87ba4", "#eda100",
    "#1baf7a", "#eb6834", "#4a3aa7", "#e34948"
  ];

  function formChartColor(index) {
    return FORM_CHART_COLORS[index % FORM_CHART_COLORS.length];
  }

  function formModuleSelectedDoctype() {
    var select = el("formModuleSelect");
    return select ? select.value : "";
  }

  async function loadFormModuleDoctypes() {
    var select = el("formModuleSelect");
    if (!select) return;

    try {
      var options = await callApi("dashboard.api.shared.form_reports.get_form_module_doctypes", {});
      fillSelect(select, options || [], "Select a form");
    } catch (error) {
      console.error("Could not load forms:", error);
    }
  }

  function resetFormModuleReport() {
    formModuleState.rows = [];
    formModuleState.questionRows = [];

    toggleDisplayEl("formModuleSummaryResults", false);
    toggleDisplayEl("formModuleChartsResults", false);
    toggleDisplayEl("formModuleQuestionResults", false);
    toggleDisplayEl("exportFormModuleReportBtn", false);

    var chartsWrap = el("formModuleChartsResults");
    if (chartsWrap) chartsWrap.innerHTML = "";

    var questionList = el("formModuleQuestionAnswerList");
    if (questionList) questionList.innerHTML = "";

    var empty = el("formModuleEmpty");
    if (empty) {
      empty.textContent = "Select a form and run the report to see results.";
      empty.style.display = "";
    }

    fillSelect(el("formModuleQuestionSelect"), [], "Select a question");
  }

  function renderFormModuleSummaryTable(rows) {
    var body = el("formModuleSummaryTableBody");
    if (!body) return;

    var doctype = formModuleSelectedDoctype();

    body.innerHTML = rows.map(function (row) {
      return "<tr>"
        + "<td>" + formatDate(row.creation) + "</td>"
        + "<td>" + escapeHtml(row.person_label || "—") + "</td>"
        + "<td>" + escapeHtml(row.coach_label || "—") + "</td>"
        + '<td><button type="button" class="dashboard-btn dashboard-btn-light" data-view-form-submission="' + escapeHtml(row.name) + '">View</button></td>'
        + "</tr>";
    }).join("");
  }

  function openFormSubmissionModal() {
    var modal = el("formSubmissionModal");
    if (!modal) return;
    modal.classList.add("is-open");
    document.body.classList.add("dashboard-modal-open");
  }

  function closeFormSubmissionModal() {
    var modal = el("formSubmissionModal");
    if (!modal) return;
    modal.classList.remove("is-open");
    document.body.classList.remove("dashboard-modal-open");
  }

  async function showFormSubmission(name) {
    var title = el("formSubmissionModalTitle");
    var body = el("formSubmissionModalBody");
    if (!body) return;

    body.innerHTML = '<tr><td colspan="2" class="dashboard-empty">Loading…</td></tr>';
    if (title) title.textContent = "Submission";
    openFormSubmissionModal();

    try {
      var data = await callApi("dashboard.api.shared.form_reports.get_form_submission", {
        doctype: formModuleSelectedDoctype(),
        name: name
      });

      if (title) title.textContent = data.person ? ("Submission - " + data.person) : ("Submission - " + formatDate(data.submitted_on));

      if (!data.answers || !data.answers.length) {
        body.innerHTML = '<tr><td colspan="2" class="dashboard-empty">No answers on this submission.</td></tr>';
        return;
      }

      body.innerHTML = data.answers.map(function (answer) {
        return "<tr><td>" + escapeHtml(answer.label) + "</td><td>" + escapeHtml(answer.value == null ? "—" : answer.value) + "</td></tr>";
      }).join("");
    } catch (error) {
      console.error("Could not load form submission:", error);
      body.innerHTML = '<tr><td colspan="2" class="dashboard-empty">' + escapeHtml(error.message || "Could not load this submission.") + '</td></tr>';
    }
  }

  // Brand colours (matches .dashboard-btn-primary / .dashboard-btn-danger)
  // for a Check (Yes/No) question's chart - a plain palette slot doesn't
  // read as "good/bad" the way these do.
  var BRAND_BLUE = "#00A19E";
  var BRAND_RED = "#C0392B";

  function colorForChartRow(question, row, index) {
    if (question && question.fieldtype === "Check") {
      if (row.label === "Yes") return BRAND_BLUE;
      if (row.label === "No") return BRAND_RED;
    }
    return formChartColor(index);
  }

  function renderFormChartPie(data, question) {
    var stops = [];
    var cursor = 0;

    data.forEach(function (row, index) {
      var start = cursor;
      cursor += row.percent;
      stops.push(colorForChartRow(question, row, index) + " " + start + "% " + cursor + "%");
    });

    var gradient = stops.length ? "conic-gradient(" + stops.join(", ") + ")" : "#F1F5F5";

    return '<div class="form-chart-pie" style="background:' + gradient + ';"></div>'
      + '<div class="form-chart-legend">'
      + data.map(function (row, index) {
        return '<div class="form-chart-legend-row">'
          + '<span class="form-chart-swatch" style="background:' + colorForChartRow(question, row, index) + ';"></span>'
          + '<span class="form-chart-legend-label">' + escapeHtml(row.label) + '</span>'
          + '<span class="form-chart-legend-value">' + row.count + ' (' + row.percent + '%)</span>'
          + '</div>';
      }).join("")
      + '</div>';
  }

  function renderFormChartBars(data, question) {
    var max = Math.max.apply(null, data.map(function (row) { return row.count; }).concat([1]));

    return '<div class="form-chart-bars">'
      + data.map(function (row, index) {
        var width = Math.max(Math.round((row.count / max) * 100), 3);

        return '<div class="form-chart-bar-row">'
          + '<div class="form-chart-bar-head">'
          + '<span class="form-chart-legend-label">' + escapeHtml(row.label) + '</span>'
          + '<span class="form-chart-legend-value">' + row.count + ' (' + row.percent + '%)</span>'
          + '</div>'
          + '<div class="form-chart-bar-track"><div class="form-chart-bar-fill" style="width:' + width + '%;background:' + colorForChartRow(question, row, index) + ';"></div></div>'
          + '</div>';
      }).join("")
      + '</div>';
  }

  function renderFormChartAnswerList(answers) {
    if (!answers || !answers.length) {
      return '<div class="form-chart-empty">No answers yet.</div>';
    }

    return '<ul class="form-chart-answer-list">'
      + answers.map(function (answer) {
        return "<li>" + escapeHtml(answer) + "</li>";
      }).join("")
      + '</ul>';
  }

  function renderFormModuleCharts(data) {
    var wrap = el("formModuleChartsResults");
    if (!wrap) return;

    var questions = data.questions || [];

    if (!questions.length) {
      wrap.innerHTML = '<div class="dashboard-empty">This form has no questions to chart.</div>';
      return;
    }

    wrap.innerHTML = questions.map(function (question) {
      var body;

      if (question.kind === "chart") {
        var chartData = question.data || [];
        // A star rating reads as an ordered scale (1 through 5) - bars
        // keep that order visible left-to-right; a pie would scatter it
        // around a circle with no meaningful order.
        var useBars = question.fieldtype === "Rating" || chartData.length > 6;
        body = useBars ? renderFormChartBars(chartData, question) : renderFormChartPie(chartData, question);
      } else {
        body = renderFormChartAnswerList(question.answers);
      }

      return '<div class="form-chart-card">'
        + '<div class="form-chart-title">' + escapeHtml(question.label) + '</div>'
        + '<div class="form-chart-subtitle">' + (question.kind === "chart" ? "Answer breakdown" : "Individual answers") + '</div>'
        + body
        + '</div>';
    }).join("");
  }

  function renderFormModuleQuestionAnswers(data) {
    var heading = el("formModuleQuestionColumnHead");
    var list = el("formModuleQuestionAnswerList");
    if (!list) return;

    if (heading) heading.textContent = data.question || "Answers";

    var answers = (data.rows || []).map(function (row) { return row.value; }).filter(function (v) { return v; });

    list.innerHTML = answers.length
      ? answers.map(function (value) { return "<li>" + escapeHtml(value) + "</li>"; }).join("")
      : '<li class="form-chart-empty">No answers yet.</li>';
  }

  async function ensureFormModuleQuestions() {
    var doctype = formModuleSelectedDoctype();
    if (!doctype) return [];

    var questions = await callApi("dashboard.api.shared.form_reports.get_form_questions", { doctype: doctype });
    fillSelect(el("formModuleQuestionSelect"), questions || [], "Select a question");
    return questions || [];
  }

  async function loadFormModuleQuestionAnswers(question) {
    var empty = el("formModuleEmpty");
    var results = el("formModuleQuestionResults");
    if (!empty || !results) return;

    if (!question) {
      empty.textContent = "Select a question to see everyone's answer.";
      empty.style.display = "";
      results.style.display = "none";
      return;
    }

    empty.textContent = "Loading...";
    empty.style.display = "";
    results.style.display = "none";

    try {
      var data = await callApi("dashboard.api.shared.form_reports.get_form_answers_for_question", {
        doctype: formModuleSelectedDoctype(),
        question: question,
        from_date: (el("formModuleFromDate") || {}).value || "",
        to_date: (el("formModuleToDate") || {}).value || ""
      });

      formModuleState.questionRows = data.rows || [];

      empty.style.display = "none";
      results.style.display = "";
      renderFormModuleQuestionAnswers(data);
      toggleDisplayEl("exportFormModuleReportBtn", (data.rows || []).length > 0);
    } catch (error) {
      console.error("Could not load question's form answers:", error);
      empty.textContent = error.message || "Could not load answers for this question.";
      empty.style.display = "";
      results.style.display = "none";
    }
  }

  async function runFormModuleReport() {
    var doctype = formModuleSelectedDoctype();
    if (!doctype) {
      window.alert("Select a form first.");
      return;
    }

    var mode = (el("formModuleViewMode") || {}).value || "summary";
    formModuleState.mode = mode;

    var btn = el("runFormModuleReportBtn");
    if (btn) { btn.disabled = true; btn.textContent = "Running..."; }

    resetFormModuleReport();

    try {
      if (mode === "summary") {
        var data = await callApi("dashboard.api.shared.form_reports.get_form_report", {
          doctype: doctype,
          from_date: (el("formModuleFromDate") || {}).value || "",
          to_date: (el("formModuleToDate") || {}).value || ""
        });

        formModuleState.rows = data.rows || [];
        var empty = el("formModuleEmpty");

        if (!formModuleState.rows.length) {
          if (empty) { empty.textContent = "No submissions found."; empty.style.display = ""; }
        } else {
          if (empty) empty.style.display = "none";
          toggleDisplayEl("formModuleSummaryResults", true);
          renderFormModuleSummaryTable(formModuleState.rows);
          toggleDisplayEl("exportFormModuleReportBtn", true);
        }
      } else if (mode === "question") {
        var questions = await callApi("dashboard.api.shared.form_reports.get_form_questions", { doctype: doctype });
        fillSelect(el("formModuleQuestionSelect"), questions || [], "Select a question");

        var questionEmpty = el("formModuleEmpty");
        if (questionEmpty) {
          questionEmpty.textContent = (questions && questions.length)
            ? "Select a question to see everyone's answer."
            : "This form has no questions to select.";
          questionEmpty.style.display = "";
        }
      } else if (mode === "charts") {
        var chartsData = await callApi("dashboard.api.shared.form_reports.get_form_charts", {
          doctype: doctype,
          from_date: (el("formModuleFromDate") || {}).value || "",
          to_date: (el("formModuleToDate") || {}).value || ""
        });

        formModuleState.chartQuestions = chartsData.questions || [];
        var chartsEmpty = el("formModuleEmpty");

        if (!chartsData.total_submissions || !formModuleState.chartQuestions.length) {
          if (chartsEmpty) { chartsEmpty.textContent = "No submissions found."; chartsEmpty.style.display = ""; }
        } else {
          if (chartsEmpty) chartsEmpty.style.display = "none";
          toggleDisplayEl("formModuleChartsResults", true);
          renderFormModuleCharts(chartsData);
        }
      }
    } catch (error) {
      console.error("Form report failed:", error);
      window.alert(error.message || "Could not run the report.");
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = "Run Report"; }
    }
  }

  function exportFormModuleReport() {
    var mode = formModuleState.mode;

    if (mode === "question") {
      exportRowsToCsv("form-results.csv", [
        { label: "Submitted", value: function (r) { return formatDate(r.creation); } },
        { label: "Person", value: function (r) { return r.person_label || ""; } },
        { label: "Coach", value: function (r) { return r.coach_label || ""; } },
        { label: "Answer", value: function (r) { return r.value || ""; } }
      ], formModuleState.questionRows);
      return;
    }

    exportRowsToCsv("form-results.csv", [
      { label: "Submitted", value: function (r) { return formatDate(r.creation); } },
      { label: "Person", value: function (r) { return r.person_label || ""; } },
      { label: "Coach", value: function (r) { return r.coach_label || ""; } }
    ], formModuleState.rows);
  }

  var openPacksState = { rows: [] };

  function renderOpenPacksReport(rows) {
    var empty = el("openPacksReportEmpty");
    var results = el("openPacksReportResults");
    var body = el("openPacksReportTableBody");
    if (!empty || !results || !body) return;

    openPacksState.rows = rows || [];

    if (!rows.length) {
      empty.textContent = "No open session packs found.";
      empty.style.display = "";
      results.style.display = "none";
      return;
    }

    empty.style.display = "none";
    results.style.display = "";

    body.innerHTML = rows.map(function (row) {
      var baseUrl = dashboardBaseUrl();
      var detailUrl = baseUrl + "/client_details?name=" + encodeURIComponent(row.client);

      return "<tr>"
        + '<td><a class="dashboard-inline-link" href="' + escapeHtml(detailUrl) + '">'
        + escapeHtml(row.client_label || row.client) + "</a></td>"
        + "<td>" + escapeHtml(row.coach_label || "—") + "</td>"
        + "<td>" + escapeHtml(row.worker_label || "—") + "</td>"
        + "<td>" + escapeHtml(row.service_item || row.client_package || "—") + "</td>"
        + "<td>" + escapeHtml(row.qty_purchased) + "</td>"
        + "<td>" + escapeHtml(row.date_issued || "—") + "</td>"
        + "<td>" + escapeHtml(row.qty_booked) + "</td>"
        + "<td><strong>" + escapeHtml(row.qty_available) + "</strong></td>"
        + "</tr>";
    }).join("");
  }

  async function runOpenPacksReport() {
    var btn = el("runOpenPacksReportBtn");
    if (btn) { btn.disabled = true; btn.textContent = "Running..."; }

    try {
      var rows = await callApi("dashboard.api.shared.packages.get_open_session_packs_report", {});
      renderOpenPacksReport(rows);

      var exportBtn = el("exportOpenPacksReportBtn");
      if (exportBtn) exportBtn.style.display = rows.length ? "" : "none";
    } catch (error) {
      console.error("Open session packs report failed:", error);
      window.alert(error.message || "Could not run the report.");
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = "Run Report"; }
    }
  }

  function exportOpenPacksReport() {
    exportRowsToCsv("open-session-packs.csv", [
      { label: "Client", value: function (r) { return r.client_label || r.client; } },
      { label: "Coach", value: function (r) { return r.coach_label || ""; } },
      { label: "Session Worker", value: function (r) { return r.worker_label || ""; } },
      { label: "Package", value: function (r) { return r.service_item || r.client_package || ""; } },
      { label: "Purchased", value: function (r) { return r.qty_purchased; } },
      { label: "Date Issued", value: function (r) { return r.date_issued || ""; } },
      { label: "Booked", value: function (r) { return r.qty_booked; } },
      { label: "Available", value: function (r) { return r.qty_available; } }
    ], openPacksState.rows);
  }

  var coachRevenueState = { client_types: [], rows: [] };

  function formatMoney(value) {
    var number = Number(value || 0);
    try {
      return new Intl.NumberFormat("en-GB", { style: "currency", currency: "GBP" }).format(number);
    } catch (e) {
      return "£" + number.toFixed(2);
    }
  }

  function renderCoachRevenueReport(data) {
    var empty = el("coachRevenueEmpty");
    var results = el("coachRevenueResults");
    var headerRow = el("coachRevenueHeaderRow");
    var body = el("coachRevenueTableBody");
    var totalsRow = el("coachRevenueTotalsRow");
    if (!empty || !results || !headerRow || !body || !totalsRow) return;

    var clientTypes = data.client_types || [];
    var rows = data.rows || [];

    coachRevenueState.client_types = clientTypes;
    coachRevenueState.rows = rows;

    if (!rows.length) {
      empty.textContent = "No invoiced revenue found for this period.";
      empty.style.display = "";
      results.style.display = "none";
      return;
    }

    empty.style.display = "none";
    results.style.display = "";

    headerRow.innerHTML = "<th>Coach</th>"
      + clientTypes.map(function (ct) { return "<th>" + escapeHtml(ct) + "</th>"; }).join("")
      + "<th>Total</th>";

    body.innerHTML = rows.map(function (row) {
      return "<tr>"
        + "<td>" + escapeHtml(row.coach_label || row.coach) + "</td>"
        + clientTypes.map(function (ct) {
            return "<td>" + formatMoney((row.by_type || {})[ct]) + "</td>";
          }).join("")
        + "<td><strong>" + formatMoney(row.total) + "</strong></td>"
        + "</tr>";
    }).join("");

    var grandTotals = data.grand_totals || {};
    totalsRow.innerHTML = "<td>All Coaches</td>"
      + clientTypes.map(function (ct) { return "<td>" + formatMoney(grandTotals[ct]) + "</td>"; }).join("")
      + "<td>" + formatMoney(data.grand_total) + "</td>";
  }

  async function runCoachRevenueReport() {
    var btn = el("runCoachRevenueReportBtn");
    if (btn) { btn.disabled = true; btn.textContent = "Running..."; }

    var fromDate = (el("coachRevenueFromDate") || {}).value || "";
    var toDate = (el("coachRevenueToDate") || {}).value || "";

    try {
      var data = await callApi("dashboard.api.shared.dashboard.get_coach_revenue_by_client_type_report", {
        from_date: fromDate,
        to_date: toDate
      });
      renderCoachRevenueReport(data);

      var exportBtn = el("exportCoachRevenueReportBtn");
      if (exportBtn) exportBtn.style.display = (data.rows || []).length ? "" : "none";
    } catch (error) {
      console.error("Coach revenue report failed:", error);
      window.alert(error.message || "Could not run the report.");
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = "Run Report"; }
    }
  }

  function exportCoachRevenueReport() {
    var columns = [
      { label: "Coach", value: function (r) { return r.coach_label || r.coach; } }
    ].concat(coachRevenueState.client_types.map(function (ct) {
      return { label: ct, value: function (r) { return (r.by_type || {})[ct] || 0; } };
    })).concat([
      { label: "Total", value: function (r) { return r.total || 0; } }
    ]);

    exportRowsToCsv("coach-revenue-by-client-type.csv", columns, coachRevenueState.rows);
  }

  var coachLogState = { mileage: [], training: [] };

  function currentCoachLogFilter() {
    var select = el("coachLogCoachSelect");
    return select ? select.value : "";
  }

  function renderMileageLog(rows) {
    var empty = el("mileageLogEmpty");
    var results = el("mileageLogResults");
    var body = el("mileageLogTableBody");
    if (!empty || !results || !body) return;

    coachLogState.mileage = rows || [];

    if (!rows.length) {
      empty.style.display = "";
      results.style.display = "none";
      return;
    }

    empty.style.display = "none";
    results.style.display = "";

    body.innerHTML = rows.map(function (row) {
      return "<tr>"
        + "<td>" + formatDate(row.log_date) + "</td>"
        + "<td>" + escapeHtml(row.coach_label || "—") + "</td>"
        + "<td>" + escapeHtml(row.purpose || "—") + "</td>"
        + "<td>" + escapeHtml(row.miles) + "</td>"
        + "<td>" + escapeHtml(row.notes || "—") + "</td>"
        + "</tr>";
    }).join("");
  }

  async function loadMileageLog() {
    try {
      var rows = await callApi("dashboard.api.shared.coach_logs.get_mileage_log", { coach: currentCoachLogFilter() });
      renderMileageLog(rows);
    } catch (error) {
      console.error("Mileage log failed:", error);
    }
  }

  async function addMileageLogEntry() {
    var btn = el("addMileageLogBtn");
    var purposeField = el("mileageLogPurpose");
    var milesField = el("mileageLogMiles");
    var dateField = el("mileageLogDate");
    var notesField = el("mileageLogNotes");

    var purpose = purposeField ? purposeField.value : "";
    var miles = milesField ? milesField.value : "";

    if (!purpose.trim()) { window.alert("Enter a purpose / journey."); return; }
    if (!miles || Number(miles) <= 0) { window.alert("Enter miles."); return; }

    if (btn) { btn.disabled = true; btn.textContent = "Adding..."; }

    try {
      await callApi("dashboard.api.shared.coach_logs.add_mileage_log", {
        log_date: dateField ? dateField.value : "",
        purpose: purpose,
        miles: miles,
        notes: notesField ? notesField.value : ""
      });

      if (purposeField) purposeField.value = "";
      if (milesField) milesField.value = "";
      if (dateField) dateField.value = "";
      if (notesField) notesField.value = "";

      await loadMileageLog();
    } catch (error) {
      window.alert(error.message || "Could not add mileage entry.");
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = "Add Entry"; }
    }
  }

  function renderTrainingLog(rows) {
    var empty = el("trainingLogEmpty");
    var results = el("trainingLogResults");
    var body = el("trainingLogTableBody");
    if (!empty || !results || !body) return;

    coachLogState.training = rows || [];

    if (!rows.length) {
      empty.style.display = "";
      results.style.display = "none";
      return;
    }

    empty.style.display = "none";
    results.style.display = "";

    body.innerHTML = rows.map(function (row) {
      return "<tr>"
        + "<td>" + formatDate(row.log_date) + "</td>"
        + "<td>" + escapeHtml(row.coach_label || "—") + "</td>"
        + "<td>" + escapeHtml(row.log_type || "—") + "</td>"
        + "<td>" + escapeHtml(row.description || "—") + "</td>"
        + "<td>" + escapeHtml(row.duration_hours || "—") + "</td>"
        + "</tr>";
    }).join("");
  }

  async function loadTrainingLog() {
    try {
      var rows = await callApi("dashboard.api.shared.coach_logs.get_training_log", { coach: currentCoachLogFilter() });
      renderTrainingLog(rows);
    } catch (error) {
      console.error("Training log failed:", error);
    }
  }

  async function addTrainingLogEntry() {
    var btn = el("addTrainingLogBtn");
    var typeField = el("trainingLogType");
    var descriptionField = el("trainingLogDescription");
    var durationField = el("trainingLogDuration");
    var dateField = el("trainingLogDate");

    var description = descriptionField ? descriptionField.value : "";

    if (!description.trim()) { window.alert("Enter a description."); return; }

    if (btn) { btn.disabled = true; btn.textContent = "Adding..."; }

    try {
      await callApi("dashboard.api.shared.coach_logs.add_training_log", {
        log_date: dateField ? dateField.value : "",
        log_type: typeField ? typeField.value : "",
        description: description,
        duration_hours: durationField ? durationField.value : ""
      });

      if (descriptionField) descriptionField.value = "";
      if (durationField) durationField.value = "";
      if (dateField) dateField.value = "";

      await loadTrainingLog();
    } catch (error) {
      window.alert(error.message || "Could not add training/supervision entry.");
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = "Add Entry"; }
    }
  }

  async function loadCoachLogCoachOptions() {
    var row = el("coachLogCoachFilterRow");
    var select = el("coachLogCoachSelect");
    if (!select) return;

    try {
      var options = await callApi("dashboard.api.shared.coach_logs.get_coach_log_options", {});

      if (options && options.length) {
        options.forEach(function (opt) {
          var optionEl = document.createElement("option");
          optionEl.value = opt.value;
          optionEl.textContent = opt.label;
          select.appendChild(optionEl);
        });

        if (row) row.style.display = "";
      }
    } catch (error) {
      console.error("Coach log options failed:", error);
    }
  }

  function initCoachLogs() {
    if (!el("mileageLogTableBody") && !el("trainingLogTableBody")) return;

    var select = el("coachLogCoachSelect");
    if (select) {
      select.addEventListener("change", function () {
        loadMileageLog();
        loadTrainingLog();
      });
    }

    var addMileageBtn = el("addMileageLogBtn");
    if (addMileageBtn) addMileageBtn.addEventListener("click", addMileageLogEntry);

    var addTrainingBtn = el("addTrainingLogBtn");
    if (addTrainingBtn) addTrainingBtn.addEventListener("click", addTrainingLogEntry);

    loadCoachLogCoachOptions();
    loadMileageLog();
    loadTrainingLog();
  }

  function initFormsReportPicker() {
    var picker = el("formsReportPicker");
    if (!picker) return;

    var buttons = picker.querySelectorAll("[data-forms-report-tab]");
    var panels = document.querySelectorAll("[data-forms-report-panel]");

    buttons.forEach(function (button) {
      button.addEventListener("click", function () {
        var tab = button.getAttribute("data-forms-report-tab");

        buttons.forEach(function (btn) { btn.classList.toggle("is-active", btn === button); });
        panels.forEach(function (panel) {
          var isActive = panel.getAttribute("data-forms-report-panel") === tab;
          panel.classList.toggle("is-active", isActive);
          panel.style.display = isActive ? "" : "none";
        });
      });
    });
  }

  function init() {
    var intakeBtn = el("runIntakeFormReportBtn");
    if (intakeBtn) intakeBtn.addEventListener("click", runIntakeFormReport);

    var exportIntakeBtn = el("exportIntakeFormReportBtn");
    if (exportIntakeBtn) exportIntakeBtn.addEventListener("click", exportIntakeFormReport);

    var previewResyncIntakeBtn = el("previewResyncIntakeFormsBtn");
    if (previewResyncIntakeBtn) previewResyncIntakeBtn.addEventListener("click", previewResyncIntakeForms);

    var confirmResyncIntakeBtn = el("confirmResyncIntakeFormsBtn");
    if (confirmResyncIntakeBtn) confirmResyncIntakeBtn.addEventListener("click", confirmResyncIntakeForms);

    var formModuleBtn = el("runFormModuleReportBtn");
    if (formModuleBtn) formModuleBtn.addEventListener("click", runFormModuleReport);

    var exportFormModuleBtn = el("exportFormModuleReportBtn");
    if (exportFormModuleBtn) exportFormModuleBtn.addEventListener("click", exportFormModuleReport);

    function loadFormModuleQuestionsIfNeeded() {
      var mode = (el("formModuleViewMode") || {}).value || "summary";
      if (mode !== "question") return;

      var doctype = formModuleSelectedDoctype();
      var empty = el("formModuleEmpty");

      if (!doctype) {
        if (empty) { empty.textContent = "Select a form first."; empty.style.display = ""; }
        return;
      }

      toggleDisplayEl("formModuleSummaryResults", false);
      toggleDisplayEl("formModuleChartsResults", false);

      ensureFormModuleQuestions().then(function (questions) {
        if (empty) {
          empty.textContent = questions.length ? "Select a question to see everyone's answer." : "This form has no questions to select.";
          empty.style.display = "";
        }
        loadFormModuleQuestionAnswers(el("formModuleQuestionSelect") ? el("formModuleQuestionSelect").value : "");
      });
    }

    var formModuleSelect = el("formModuleSelect");
    if (formModuleSelect) {
      loadFormModuleDoctypes();
      formModuleSelect.addEventListener("change", function () {
        resetFormModuleReport();
        loadFormModuleQuestionsIfNeeded();
      });
    }

    // Auto-loads the question list as soon as "One question - everyone's
    // answer" is picked, the same way the Intake Forms tab already does
    // (see applyIntakeFormViewMode) - previously the dropdown stayed empty
    // until "Run Report" was clicked too, which read as this view simply
    // not working since nothing else on the page asks for a second click.
    var formModuleViewModeSelect = el("formModuleViewMode");
    if (formModuleViewModeSelect) {
      formModuleViewModeSelect.addEventListener("change", function () {
        var mode = formModuleViewModeSelect.value;
        toggleDisplayEl("formModuleControlsRow", mode === "question");
        toggleDisplayEl("formModuleQuestionRow", mode === "question");
        loadFormModuleQuestionsIfNeeded();
      });
    }

    var formModuleQuestionSelect = el("formModuleQuestionSelect");
    if (formModuleQuestionSelect) {
      formModuleQuestionSelect.addEventListener("change", function () { loadFormModuleQuestionAnswers(formModuleQuestionSelect.value); });
    }

    var formModuleSummaryBody = el("formModuleSummaryTableBody");
    if (formModuleSummaryBody) {
      formModuleSummaryBody.addEventListener("click", function (event) {
        var button = event.target.closest("[data-view-form-submission]");
        if (!button) return;
        showFormSubmission(button.getAttribute("data-view-form-submission"));
      });
    }

    var formSubmissionModal = el("formSubmissionModal");
    if (formSubmissionModal) {
      formSubmissionModal.addEventListener("click", function (event) {
        if (event.target === formSubmissionModal) closeFormSubmissionModal();
      });
    }

    var closeFormSubmissionModalBtn = el("closeFormSubmissionModal");
    if (closeFormSubmissionModalBtn) {
      closeFormSubmissionModalBtn.addEventListener("click", closeFormSubmissionModal);
    }

    var packsBtn = el("runOpenPacksReportBtn");
    if (packsBtn) packsBtn.addEventListener("click", runOpenPacksReport);

    var exportPacksBtn = el("exportOpenPacksReportBtn");
    if (exportPacksBtn) exportPacksBtn.addEventListener("click", exportOpenPacksReport);

    var coachRevenueBtn = el("runCoachRevenueReportBtn");
    if (coachRevenueBtn) coachRevenueBtn.addEventListener("click", runCoachRevenueReport);

    var exportCoachRevenueBtn = el("exportCoachRevenueReportBtn");
    if (exportCoachRevenueBtn) exportCoachRevenueBtn.addEventListener("click", exportCoachRevenueReport);

    initFormsReportPicker();
    initCoachLogs();

    var viewModeSelect = el("intakeFormViewMode");
    if (viewModeSelect) viewModeSelect.addEventListener("change", applyIntakeFormViewMode);

    var personSelect = el("intakeFormPersonSelect");
    if (personSelect) personSelect.addEventListener("change", function () { loadIntakeFormPersonAnswers(personSelect.value); });

    var questionSelect = el("intakeFormQuestionSelect");
    if (questionSelect) questionSelect.addEventListener("change", function () { loadIntakeFormQuestionAnswers(questionSelect.value); });

    var runBtn = el("runIntegrityReportBtn");
    if (!runBtn) return; // diagnostic tools not on this page (coach reports, or a non-office franchisor)

    runBtn.addEventListener("click", runIntegrityReport);

    var previewBtn = el("previewRepairBtn");
    if (previewBtn) previewBtn.addEventListener("click", previewRepair);

    var confirmBtn = el("confirmRepairBtn");
    if (confirmBtn) confirmBtn.addEventListener("click", confirmRepair);

    var previewResyncBtn = el("previewResyncBtn");
    if (previewResyncBtn) previewResyncBtn.addEventListener("click", previewResync);

    var confirmResyncBtn = el("confirmResyncBtn");
    if (confirmResyncBtn) confirmResyncBtn.addEventListener("click", confirmResync);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
