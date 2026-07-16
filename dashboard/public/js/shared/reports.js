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

  var formModuleState = { rows: [], questionRows: [], mode: "summary" };

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
    toggleDisplayEl("formModulePersonResults", false);
    toggleDisplayEl("formModuleQuestionResults", false);
    toggleDisplayEl("exportFormModuleReportBtn", false);

    var empty = el("formModuleEmpty");
    if (empty) {
      empty.textContent = "Select a form and run the report to see results.";
      empty.style.display = "";
    }

    fillSelect(el("formModulePersonSelect"), [], "Select a person");
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
        + "<td>" + nameLink(doctype, row.name) + "</td>"
        + "</tr>";
    }).join("");
  }

  function renderFormModulePersonAnswers(data) {
    var wrap = el("formModulePersonResults");
    if (!wrap) return;

    if (!data.submissions || !data.submissions.length) {
      wrap.innerHTML = '<div class="dashboard-empty">No submissions found for ' + escapeHtml(data.person || "this person") + '.</div>';
      return;
    }

    wrap.innerHTML = data.submissions.map(function (submission) {
      return '<div class="dashboard-detail-section" style="margin-top:16px;">'
        + '<h3 style="margin-bottom:8px;">' + formatDate(submission.submitted_on) + '</h3>'
        + '<div class="dashboard-table-wrap"><table class="dashboard-table dashboard-table-compact">'
        + '<thead><tr><th>Question</th><th>Answer</th></tr></thead>'
        + '<tbody>'
        + submission.answers.map(function (answer) {
          return "<tr><td>" + escapeHtml(answer.label) + "</td><td>" + escapeHtml(answer.value == null ? "—" : answer.value) + "</td></tr>";
        }).join("")
        + '</tbody></table></div></div>';
    }).join("");
  }

  function renderFormModuleQuestionTable(data) {
    var body = el("formModuleQuestionTableBody");
    var columnHead = el("formModuleQuestionColumnHead");
    if (!body) return;

    if (columnHead) columnHead.textContent = data.question || "Answer";

    body.innerHTML = (data.rows || []).map(function (row) {
      return "<tr>"
        + "<td>" + formatDate(row.creation) + "</td>"
        + "<td>" + escapeHtml(row.person_label || "—") + "</td>"
        + "<td>" + escapeHtml(row.coach_label || "—") + "</td>"
        + "<td>" + escapeHtml(row.value || "—") + "</td>"
        + "</tr>";
    }).join("");
  }

  async function loadFormModulePersonAnswers(person) {
    var empty = el("formModuleEmpty");
    var wrap = el("formModulePersonResults");
    if (!empty || !wrap) return;

    if (!person) {
      empty.textContent = "Select a person to see their answers.";
      empty.style.display = "";
      wrap.style.display = "none";
      return;
    }

    empty.textContent = "Loading...";
    empty.style.display = "";
    wrap.style.display = "none";

    try {
      var data = await callApi("dashboard.api.shared.form_reports.get_form_answers_for_person", {
        doctype: formModuleSelectedDoctype(),
        person: person
      });

      empty.style.display = "none";
      wrap.style.display = "";
      renderFormModulePersonAnswers(data);
    } catch (error) {
      console.error("Could not load person's form answers:", error);
      empty.textContent = error.message || "Could not load this person's answers.";
      empty.style.display = "";
      wrap.style.display = "none";
    }
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

      if (!data.rows || !data.rows.length) {
        empty.textContent = "No answers found.";
        empty.style.display = "";
        results.style.display = "none";
        return;
      }

      empty.style.display = "none";
      results.style.display = "";
      renderFormModuleQuestionTable(data);
      toggleDisplayEl("exportFormModuleReportBtn", true);
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
      } else if (mode === "person") {
        var people = await callApi("dashboard.api.shared.form_reports.get_form_people", { doctype: doctype });
        fillSelect(el("formModulePersonSelect"), people || [], "Select a person");

        var personEmpty = el("formModuleEmpty");
        if (personEmpty) {
          personEmpty.textContent = (people && people.length)
            ? "Select a person to see their answers."
            : "This form has no linked person to filter by, or nobody's submitted it yet.";
          personEmpty.style.display = "";
        }
      } else if (mode === "question") {
        var questions = await callApi("dashboard.api.shared.form_reports.get_form_questions", { doctype: doctype });
        fillSelect(el("formModuleQuestionSelect"), questions || [], "Select a question");

        var questionEmpty = el("formModuleEmpty");
        if (questionEmpty) {
          questionEmpty.textContent = "Select a question to see everyone's answer.";
          questionEmpty.style.display = "";
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
        + "<td>" + escapeHtml(row.qty_used) + "</td>"
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
      { label: "Used", value: function (r) { return r.qty_used; } },
      { label: "Booked", value: function (r) { return r.qty_booked; } },
      { label: "Available", value: function (r) { return r.qty_available; } }
    ], openPacksState.rows);
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

    var formModuleBtn = el("runFormModuleReportBtn");
    if (formModuleBtn) formModuleBtn.addEventListener("click", runFormModuleReport);

    var exportFormModuleBtn = el("exportFormModuleReportBtn");
    if (exportFormModuleBtn) exportFormModuleBtn.addEventListener("click", exportFormModuleReport);

    var formModuleSelect = el("formModuleSelect");
    if (formModuleSelect) {
      loadFormModuleDoctypes();
      formModuleSelect.addEventListener("change", resetFormModuleReport);
    }

    var formModuleViewModeSelect = el("formModuleViewMode");
    if (formModuleViewModeSelect) {
      formModuleViewModeSelect.addEventListener("change", function () {
        var mode = formModuleViewModeSelect.value;
        toggleDisplayEl("formModuleControlsRow", mode !== "summary");
        toggleDisplayEl("formModulePersonRow", mode === "person");
        toggleDisplayEl("formModuleQuestionRow", mode === "question");
      });
    }

    var formModulePersonSelect = el("formModulePersonSelect");
    if (formModulePersonSelect) {
      formModulePersonSelect.addEventListener("change", function () { loadFormModulePersonAnswers(formModulePersonSelect.value); });
    }

    var formModuleQuestionSelect = el("formModuleQuestionSelect");
    if (formModuleQuestionSelect) {
      formModuleQuestionSelect.addEventListener("change", function () { loadFormModuleQuestionAnswers(formModuleQuestionSelect.value); });
    }

    var packsBtn = el("runOpenPacksReportBtn");
    if (packsBtn) packsBtn.addEventListener("click", runOpenPacksReport);

    var exportPacksBtn = el("exportOpenPacksReportBtn");
    if (exportPacksBtn) exportPacksBtn.addEventListener("click", exportOpenPacksReport);

    initFormsReportPicker();

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
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
