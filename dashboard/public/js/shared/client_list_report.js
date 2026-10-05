/**
 * "Client List" report tab (see dashboard.api.shared.client_list_report)
 * - franchisor-only, same table/CSV pattern as client_locations.js
 * minus the map. Columns to show/export are the user's own pick (a
 * checkbox per column, all ticked by default) - the backend always
 * returns every field for every row regardless of what's ticked here.
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
      throw new Error(data.message || "Request failed.");
    }

    return data.message || data;
  }

  function csvCell(value) {
    var text = String(value == null ? "" : value).replace(/"/g, '""');
    return '"' + text + '"';
  }

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

  // Every column this report can show - order here is the order columns
  // render in, both on screen and in the CSV.
  var COLUMNS = [
    { key: "client", label: "Client", value: function (r) { return r.client_label || r.client; } },
    { key: "coach", label: "Coach", value: function (r) { return r.coach_label || ""; } },
    { key: "billing_contact", label: "Billing Contact", value: function (r) { return r.billing_contact_label || ""; } },
    { key: "age", label: "Age", value: function (r) { return r.age || ""; } },
    { key: "client_type", label: "Client Type", value: function (r) { return r.client_type || ""; } },
    { key: "billing_contact_email", label: "Billing Contact Email", value: function (r) { return r.billing_contact_email || ""; } },
    { key: "billing_contact_phone", label: "Billing Contact Phone", value: function (r) { return r.billing_contact_phone || ""; } },
    { key: "sex", label: "Sex", value: function (r) { return r.sex || ""; } },
    { key: "gender", label: "Gender", value: function (r) { return r.gender || ""; } }
  ];

  var state = { rows: [] };

  function renderColumnPicker() {
    var container = el("clientListColumnPicker");
    if (!container) return;

    container.innerHTML = COLUMNS.map(function (col) {
      return '<label style="display:flex; align-items:center; gap:6px; font-weight:normal; font-size:13px;">'
        + '<input type="checkbox" data-client-list-column="' + escapeHtml(col.key) + '" checked>'
        + escapeHtml(col.label)
        + "</label>";
    }).join("");

    container.querySelectorAll("[data-client-list-column]").forEach(function (checkbox) {
      checkbox.addEventListener("change", function () {
        if (state.rows.length) renderTable(state.rows);
      });
    });
  }

  function selectedColumns() {
    var checked = {};
    document.querySelectorAll("#clientListColumnPicker [data-client-list-column]").forEach(function (checkbox) {
      checked[checkbox.dataset.clientListColumn] = checkbox.checked;
    });

    var columns = COLUMNS.filter(function (col) { return checked[col.key] !== false; });
    return columns.length ? columns : COLUMNS;
  }

  function renderTable(rows) {
    var head = el("clientListTableHead");
    var body = el("clientListTableBody");
    if (!head || !body) return;

    var columns = selectedColumns();

    head.innerHTML = columns.map(function (c) { return "<th>" + escapeHtml(c.label) + "</th>"; }).join("");

    body.innerHTML = rows.map(function (row) {
      return "<tr>" + columns.map(function (c) {
        return "<td>" + escapeHtml(c.value(row) || "—") + "</td>";
      }).join("") + "</tr>";
    }).join("");
  }

  async function loadCoachOptions() {
    var select = el("clientListCoachSelect");
    if (!select) return;

    try {
      var options = await callApi("dashboard.api.shared.coach_logs.get_coach_log_options", {});

      (options || []).forEach(function (opt) {
        var optionEl = document.createElement("option");
        optionEl.value = opt.value;
        optionEl.textContent = opt.label;
        select.appendChild(optionEl);
      });
    } catch (error) {
      console.error("Coach options failed:", error);
    }
  }

  async function runReport() {
    var btn = el("runClientListReportBtn");
    var select = el("clientListCoachSelect");
    var statusSelect = el("clientListStatusSelect");
    var empty = el("clientListEmpty");
    var results = el("clientListResults");
    var exportBtn = el("exportClientListReportBtn");

    if (btn) { btn.disabled = true; btn.textContent = "Running..."; }

    try {
      var payload = await callApi("dashboard.api.shared.client_list_report.get_client_list_report", {
        coach: select ? select.value : "",
        status: statusSelect ? statusSelect.value : ""
      });

      var rows = (payload && payload.rows) || [];
      state.rows = rows;

      if (!rows.length) {
        if (empty) { empty.style.display = ""; empty.textContent = "No clients found."; }
        if (results) results.style.display = "none";
        if (exportBtn) exportBtn.style.display = "none";
        return;
      }

      if (empty) empty.style.display = "none";
      if (results) results.style.display = "";
      if (exportBtn) exportBtn.style.display = "";

      renderTable(rows);
    } catch (error) {
      window.alert(error.message || "Could not run the report.");
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = "Run Report"; }
    }
  }

  function exportReport() {
    exportRowsToCsv("client-list.csv", selectedColumns(), state.rows);
  }

  function init() {
    if (!el("runClientListReportBtn")) return;

    renderColumnPicker();
    loadCoachOptions();

    el("runClientListReportBtn").addEventListener("click", runReport);

    var exportBtn = el("exportClientListReportBtn");
    if (exportBtn) exportBtn.addEventListener("click", exportReport);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
