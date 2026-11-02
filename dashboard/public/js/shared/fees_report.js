/**
 * "Fees Paid" page (franchisor_db/fees_report) - franchise + marketing
 * fees actually paid, combining Ashley's own hand-entered historical
 * totals (before 1 November 2026) with figures pulled automatically
 * from real payment data from that date on
 * (dashboard.api.shared.fees_report.get_fees_report). The add/edit form
 * only ever touches the manual (pre-cutoff) rows - an automatic row has
 * no Edit/Delete, since it's a live reflection of actual payments, not
 * something to hand-adjust here. "Run a Report" is the one place that
 * shows the actual data (totals + transaction list, both filterable by
 * coach and date range) - Edit/Delete for a Manual entry lives in its
 * Transactions table.
 */
(function () {
  "use strict";

  var el = Dashboard.el;
  var SHARED_API = "dashboard.api.shared.fees_report";

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
    return meta && meta.content ? meta.content : "";
  }

  async function apiPost(method, args) {
    var response = await fetch("/api/method/" + method, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-Frappe-CSRF-Token": getCsrfToken(),
      },
      body: JSON.stringify(args || {}),
    });

    var data = await response.json();

    if (!response.ok || data.exc) {
      throw new Error(Dashboard.extractErrorMessage(data, "There was a problem loading the fees report."));
    }

    return data.message || {};
  }

  function formatCurrency(amount) {
    return "£" + Number(amount || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  function formatMonth(monthIso) {
    var parts = String(monthIso).split("-");
    if (parts.length < 2) return monthIso;
    var date = new Date(Number(parts[0]), Number(parts[1]) - 1, 1);
    return date.toLocaleDateString(undefined, { month: "long", year: "numeric" });
  }

  async function loadRowIntoForm(name) {
    try {
      // Fetched by name (not read off the already-loaded rows) because a
      // month with only one of the two amounts set shows as a single
      // row here - Edit still needs to load BOTH fields into the form,
      // which the row-level data alone can't give us.
      var row = await apiPost(SHARED_API + ".get_manual_fee_total", { name: name });

      el("manualFeeName").value = row.name;
      el("manualFeeCoach").value = row.coach || "";
      el("manualFeeMonth").value = String(row.period).slice(0, 7);
      el("manualFeeFranchiseAmount").value = row.franchise_fee_amount || "";
      el("manualFeeMarketingAmount").value = row.marketing_fee_amount || "";
      el("manualFeeNote").value = row.note || "";

      var heading = el("manualFeeFormHeading");
      if (heading) heading.textContent = "Edit " + formatMonth(row.period);
      var saveBtn = el("saveManualFeeBtn");
      if (saveBtn) saveBtn.textContent = "Update Month";
      var cancelBtn = el("cancelEditManualFeeBtn");
      if (cancelBtn) cancelBtn.style.display = "";

      var form = el("manualFeeForm");
      if (form) form.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (error) {
      window.alert(error.message || "Could not load this month.");
    }
  }

  // Ashley raises the invoice on the 1st of the month for the month
  // that just ended, so the month she's about to enter a figure for is
  // almost always last month, not the current one.
  function lastMonthValue() {
    var now = new Date();
    var date = new Date(now.getFullYear(), now.getMonth() - 1, 1);
    return date.getFullYear() + "-" + String(date.getMonth() + 1).padStart(2, "0");
  }

  function resetForm() {
    el("manualFeeName").value = "";
    el("manualFeeCoach").value = "";
    el("manualFeeMonth").value = lastMonthValue();
    el("manualFeeFranchiseAmount").value = "";
    el("manualFeeMarketingAmount").value = "";
    el("manualFeeNote").value = "";

    var heading = el("manualFeeFormHeading");
    if (heading) heading.textContent = "Add a Historical Month";
    var saveBtn = el("saveManualFeeBtn");
    if (saveBtn) saveBtn.textContent = "Save Month";
    var cancelBtn = el("cancelEditManualFeeBtn");
    if (cancelBtn) cancelBtn.style.display = "none";
  }

  async function loadReport() {
    var totalEl = el("feesGrandTotal");
    if (!totalEl) return;

    try {
      var data = await apiPost(SHARED_API + ".get_fees_report", {});
      totalEl.textContent = formatCurrency(data.grand_total);

      var monthInput = el("manualFeeMonth");
      if (monthInput && data.auto_cutoff_date) {
        var cutoffParts = String(data.auto_cutoff_date).split("-");
        var lastManualMonth = new Date(Number(cutoffParts[0]), Number(cutoffParts[1]) - 1, 1);
        lastManualMonth.setMonth(lastManualMonth.getMonth() - 1);
        monthInput.max = lastManualMonth.getFullYear() + "-" + String(lastManualMonth.getMonth() + 1).padStart(2, "0");
      }
    } catch (error) {
      totalEl.textContent = "-";
    }
  }

  async function loadManualCoachOptions() {
    var select = el("manualFeeCoach");
    if (!select) return;

    try {
      var coaches = await apiPost(SHARED_API + ".get_coach_options_for_fees", {});
      select.innerHTML = '<option value="">Choose a coach...</option>' + (Array.isArray(coaches) ? coaches : []).map(function (c) {
        return '<option value="' + escapeHtml(c.name) + '">' + escapeHtml(c.coach_name || c.name) + "</option>";
      }).join("");
    } catch (error) {
      select.innerHTML = '<option value="">Could not load coaches</option>';
    }
  }

  function initForm() {
    var saveBtn = el("saveManualFeeBtn");
    if (!saveBtn) return;

    saveBtn.addEventListener("click", async function () {
      var coach = el("manualFeeCoach").value;
      var month = el("manualFeeMonth").value;
      var franchiseAmount = el("manualFeeFranchiseAmount").value;
      var marketingAmount = el("manualFeeMarketingAmount").value;

      if (!coach) {
        window.alert("Please choose a coach.");
        return;
      }
      if (!month) {
        window.alert("Please choose a month.");
        return;
      }
      if ((franchiseAmount === "" || Number(franchiseAmount) < 0) || (marketingAmount === "" || Number(marketingAmount) < 0)) {
        window.alert("Please enter a valid amount for both Franchise Fee and Marketing Fee (0 if there isn't one).");
        return;
      }

      saveBtn.disabled = true;

      try {
        await apiPost(SHARED_API + ".save_manual_fee_total", {
          name: el("manualFeeName").value || null,
          coach: coach,
          period: month + "-01",
          franchise_fee_amount: franchiseAmount,
          marketing_fee_amount: marketingAmount,
          note: el("manualFeeNote").value,
        });

        resetForm();
        await loadReport();
        await runReport();
      } catch (error) {
        window.alert(error.message || "Could not save this month.");
      } finally {
        saveBtn.disabled = false;
      }
    });

    var cancelBtn = el("cancelEditManualFeeBtn");
    if (cancelBtn) cancelBtn.addEventListener("click", resetForm);
  }

  function statTile(label, amount) {
    return (
      '<div>' +
        '<div style="font-size:12px; text-transform:uppercase; letter-spacing:0.04em; color:#839898;">' + escapeHtml(label) + "</div>" +
        '<div style="font-size:24px; font-weight:700;">' + formatCurrency(amount) + "</div>" +
      "</div>"
    );
  }

  function renderReportSummary(selectedCoach, totals) {
    var container = el("feesReportSummary");
    if (!container) return;

    if (!selectedCoach) {
      if (!totals.length) {
        container.innerHTML = '<div class="dashboard-empty">No fees recorded for this period.</div>';
        return;
      }

      container.innerHTML =
        '<table class="dashboard-table"><thead><tr>' +
          "<th>Coach</th><th>Franchise Fee</th><th>Marketing Fee</th><th>Total</th>" +
        "</tr></thead><tbody>" +
        totals.map(function (row) {
          return (
            "<tr>" +
              "<td>" + escapeHtml(row.coach_label) + "</td>" +
              "<td>" + formatCurrency(row.franchise_fee_total) + "</td>" +
              "<td>" + formatCurrency(row.marketing_fee_total) + "</td>" +
              "<td style=\"font-weight:700;\">" + formatCurrency(row.total) + "</td>" +
            "</tr>"
          );
        }).join("") +
        "</tbody></table>";
      return;
    }

    var row = totals[0] || { franchise_fee_total: 0, marketing_fee_total: 0, total: 0 };
    container.innerHTML =
      '<div style="display:flex; gap:28px; flex-wrap:wrap;">' +
        statTile("Franchise Fee", row.franchise_fee_total) +
        statTile("Marketing Fee", row.marketing_fee_total) +
        statTile("Total", row.total) +
      "</div>";
  }

  var latestTransactionRows = [];

  // One line per (coach, month) with Franchise Fee and Marketing Fee as
  // their own columns, instead of two separate rows (one per fee type)
  // - the raw get_fees_report() rows are split that way internally, but
  // shown side by side like this a Manual entry's two amounts are just
  // one line again, same as the Add a Historical Month form that
  // created them. Anything that's neither (an automatic payment before
  // the Fee Items are configured) folds into Total only.
  function buildTransactionRows(rows) {
    var byKey = {};
    var order = [];

    rows.forEach(function (row) {
      var key = row.name ? "manual:" + row.name : row.source + "|" + row.month + "|" + (row.coach || "");
      if (!byKey[key]) {
        byKey[key] = {
          month: row.month,
          coach_label: row.coach_label,
          source: row.source,
          name: row.name || "",
          franchise_fee_total: 0,
          marketing_fee_total: 0,
          other_total: 0,
        };
        order.push(key);
      }
      var bucket = byKey[key];
      if (row.fee_type === "Franchise Fee") {
        bucket.franchise_fee_total += row.amount;
      } else if (row.fee_type === "Marketing Fee") {
        bucket.marketing_fee_total += row.amount;
      } else {
        bucket.other_total += row.amount;
      }
    });

    return order.map(function (key) {
      var row = byKey[key];
      row.total = row.franchise_fee_total + row.marketing_fee_total + row.other_total;
      return row;
    });
  }

  function renderTransactions(rows, coachLabel) {
    var wrap = el("feesReportTransactionsWrap");
    var container = el("feesReportTransactions");
    if (!wrap || !container) return;

    var withLabels = rows.map(function (row) {
      return {
        month: row.month,
        coach_label: row.coach_label || coachLabel || "",
        fee_type: row.fee_type,
        source: row.source,
        amount: row.amount,
        name: row.name,
      };
    });

    latestTransactionRows = buildTransactionRows(withLabels);

    wrap.style.display = latestTransactionRows.length ? "" : "none";

    if (!latestTransactionRows.length) {
      container.innerHTML = '<div class="dashboard-empty">No transactions for this period.</div>';
      return;
    }

    container.innerHTML =
      '<table class="dashboard-table"><thead><tr>' +
        "<th>Month</th><th>Coach</th><th>Franchise Fee</th><th>Marketing Fee</th><th>Total</th><th>Source</th><th></th>" +
      "</tr></thead><tbody>" +
      latestTransactionRows.map(function (row) {
        return (
          '<tr data-txn-name="' + escapeHtml(row.name) + '">' +
            "<td>" + escapeHtml(formatMonth(row.month)) + "</td>" +
            "<td>" + escapeHtml(row.coach_label) + "</td>" +
            "<td>" + formatCurrency(row.franchise_fee_total) + "</td>" +
            "<td>" + formatCurrency(row.marketing_fee_total) + "</td>" +
            "<td style=\"font-weight:700;\">" + formatCurrency(row.total) + "</td>" +
            "<td>" + escapeHtml(row.source) + "</td>" +
            "<td style=\"white-space:nowrap;\">" +
              (row.source === "Manual"
                ? '<button type="button" class="dashboard-btn dashboard-btn-grey dashboard-txn-edit">Edit</button> ' +
                  '<button type="button" class="dashboard-btn dashboard-btn-grey dashboard-txn-delete">Delete</button>'
                : "") +
            "</td>" +
          "</tr>"
        );
      }).join("") +
      "</tbody></table>";

    container.querySelectorAll(".dashboard-txn-edit").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var row = btn.closest("[data-txn-name]");
        if (row && row.dataset.txnName) loadRowIntoForm(row.dataset.txnName);
      });
    });

    container.querySelectorAll(".dashboard-txn-delete").forEach(function (btn) {
      btn.addEventListener("click", async function () {
        var row = btn.closest("[data-txn-name]");
        var name = row && row.dataset.txnName;
        if (!name) return;
        if (!window.confirm("Delete this entry?")) return;

        btn.disabled = true;
        try {
          await apiPost(SHARED_API + ".delete_manual_fee_total", { name: name });
          await loadReport();
          await runReport();
        } catch (error) {
          window.alert(error.message || "Could not delete this entry.");
          btn.disabled = false;
        }
      });
    });
  }

  function csvCell(value) {
    var str = String(value == null ? "" : value);
    return /[",\n]/.test(str) ? '"' + str.replace(/"/g, '""') + '"' : str;
  }

  function downloadTransactionsCsv() {
    if (!latestTransactionRows.length) return;

    var lines = [["Month", "Coach", "Franchise Fee", "Marketing Fee", "Total", "Source"].join(",")];
    latestTransactionRows.forEach(function (row) {
      lines.push([
        csvCell(formatMonth(row.month)),
        csvCell(row.coach_label),
        csvCell(Number(row.franchise_fee_total || 0).toFixed(2)),
        csvCell(Number(row.marketing_fee_total || 0).toFixed(2)),
        csvCell(Number(row.total || 0).toFixed(2)),
        csvCell(row.source),
      ].join(","));
    });

    var blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8;" });
    var url = URL.createObjectURL(blob);
    var link = document.createElement("a");
    link.href = url;
    link.download = "fees-report.csv";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }

  async function loadRunReportCoachOptions() {
    var select = el("feesRunReportCoach");
    if (!select) return;

    try {
      var coaches = await apiPost(SHARED_API + ".get_coach_options_for_fees", {});
      select.innerHTML = '<option value="">All Coaches</option>' + (Array.isArray(coaches) ? coaches : []).map(function (c) {
        return '<option value="' + escapeHtml(c.name) + '">' + escapeHtml(c.coach_name || c.name) + "</option>";
      }).join("");
    } catch (error) {
      select.innerHTML = '<option value="">All Coaches</option>';
    }
  }

  // Last-run report args/coach label, kept so an Edit or Delete made
  // from the Transactions table below can silently re-run the same
  // report afterward - a no-op if nothing's been run yet.
  var lastRunArgs = null;
  var lastRunCoachLabel = "";

  async function runReport() {
    if (!lastRunArgs) return;

    try {
      var totals = await apiPost(SHARED_API + ".get_fee_totals_by_coach", lastRunArgs);
      renderReportSummary(lastRunArgs.coach, Array.isArray(totals) ? totals : []);

      var reportData = await apiPost(SHARED_API + ".get_fees_report", lastRunArgs);
      renderTransactions(Array.isArray(reportData.rows) ? reportData.rows : [], lastRunArgs.coach ? lastRunCoachLabel : "");
    } catch (error) {
      var summary = el("feesReportSummary");
      if (summary) summary.innerHTML = '<div class="dashboard-empty">' + escapeHtml(error.message || "Could not run this report.") + "</div>";
    }
  }

  function initRunReport() {
    var runBtn = el("runFeesReportBtn");
    if (!runBtn) return;

    runBtn.addEventListener("click", async function () {
      var coachSelect = el("feesRunReportCoach");
      lastRunCoachLabel = coachSelect.options[coachSelect.selectedIndex] ? coachSelect.options[coachSelect.selectedIndex].text : "";
      var fromMonth = el("feesRunReportFrom").value;
      var toMonth = el("feesRunReportTo").value;

      lastRunArgs = {
        coach: coachSelect.value,
        from_month: fromMonth ? fromMonth + "-01" : null,
        to_month: toMonth ? toMonth + "-01" : null,
      };

      runBtn.disabled = true;
      try {
        await runReport();
      } finally {
        runBtn.disabled = false;
      }
    });

    var downloadBtn = el("downloadFeesReportBtn");
    if (downloadBtn) downloadBtn.addEventListener("click", downloadTransactionsCsv);
  }

  async function init() {
    if (!el("feesGrandTotal")) return;

    resetForm();
    loadManualCoachOptions();
    loadRunReportCoachOptions();
    loadReport();
    initForm();
    initRunReport();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
