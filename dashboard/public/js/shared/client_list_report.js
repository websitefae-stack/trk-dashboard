/**
 * "Client List" report tab (see dashboard.api.shared.client_list_report)
 * - franchisor-only, same table/CSV pattern as client_locations.js
 * minus the map.
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

  var state = { rows: [] };

  function renderTable(rows) {
    var body = el("clientListTableBody");
    if (!body) return;

    body.innerHTML = rows.map(function (row) {
      return "<tr>"
        + "<td>" + escapeHtml(row.client_label || row.client) + "</td>"
        + "<td>" + escapeHtml(row.coach_label || "—") + "</td>"
        + "<td>" + escapeHtml(row.billing_contact_label || "—") + "</td>"
        + "<td>" + escapeHtml(row.age || "—") + "</td>"
        + "<td>" + escapeHtml(row.billing_contact_email || "—") + "</td>"
        + "<td>" + escapeHtml(row.billing_contact_phone || "—") + "</td>"
        + "<td>" + escapeHtml(row.sex || "—") + "</td>"
        + "<td>" + escapeHtml(row.gender || "—") + "</td>"
        + "</tr>";
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
    var empty = el("clientListEmpty");
    var results = el("clientListResults");
    var exportBtn = el("exportClientListReportBtn");

    if (btn) { btn.disabled = true; btn.textContent = "Running..."; }

    try {
      var payload = await callApi("dashboard.api.shared.client_list_report.get_client_list_report", {
        coach: select ? select.value : ""
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
    exportRowsToCsv("client-list.csv", [
      { label: "Client", value: function (r) { return r.client_label || r.client; } },
      { label: "Coach", value: function (r) { return r.coach_label || ""; } },
      { label: "Billing Contact", value: function (r) { return r.billing_contact_label || ""; } },
      { label: "Age", value: function (r) { return r.age || ""; } },
      { label: "Billing Contact Email", value: function (r) { return r.billing_contact_email || ""; } },
      { label: "Billing Contact Phone", value: function (r) { return r.billing_contact_phone || ""; } },
      { label: "Sex", value: function (r) { return r.sex || ""; } },
      { label: "Gender", value: function (r) { return r.gender || ""; } }
    ], state.rows);
  }

  function init() {
    if (!el("runClientListReportBtn")) return;

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
