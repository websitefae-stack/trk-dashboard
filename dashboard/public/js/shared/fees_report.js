/**
 * "Fees Paid" page (franchisor_db/fees_report) - a month-by-month
 * history of franchise + marketing fees actually paid, combining
 * Ashley's own hand-entered historical totals (before 1 November 2026)
 * with figures pulled automatically from real payment data from that
 * date on (dashboard.api.shared.fees_report.get_fees_report). The add/
 * edit form only ever touches the manual (pre-cutoff) rows - an
 * automatic row has no Edit/Delete, since it's a live reflection of
 * actual payments, not something to hand-adjust here.
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

  function renderRow(row, showCoach) {
    var isManual = row.source === "Manual";
    var badgeClass = isManual ? "dashboard-badge" : "dashboard-badge dashboard-status-active";

    return (
      '<div class="dashboard-card" data-fee-name="' + escapeHtml(row.name) + '" data-fee-month="' + escapeHtml(row.month) + '" style="margin-bottom:10px; display:flex; justify-content:space-between; align-items:center; gap:12px; flex-wrap:wrap;">' +
        '<div>' +
          '<div style="font-weight:600;">' + escapeHtml(formatMonth(row.month)) + "</div>" +
          (showCoach && row.coach_label ? '<div style="color:#536666; font-size:13px; margin-top:2px;">' + escapeHtml(row.coach_label) + "</div>" : "") +
          (row.note ? '<div style="color:#839898; font-size:13px; margin-top:2px;">' + escapeHtml(row.note) + "</div>" : "") +
        "</div>" +
        '<div style="display:flex; align-items:center; gap:10px;">' +
          '<span class="' + badgeClass + '">' + escapeHtml(row.source) + "</span>" +
          '<div style="font-weight:700; font-size:16px; min-width:110px; text-align:right;">' + formatCurrency(row.amount) + "</div>" +
          (isManual
            ? '<button type="button" class="dashboard-btn dashboard-btn-grey dashboard-fee-edit">Edit</button>' +
              '<button type="button" class="dashboard-btn dashboard-btn-grey dashboard-fee-delete">Delete</button>'
            : "") +
        "</div>" +
      "</div>"
    );
  }

  // Which of the 3 tabs above the main list is active - Franchise Fee/
  // Marketing Fee just filter the already-loaded rows by fee_type;
  // Total Fee merges a (coach, month) pair's Franchise + Marketing rows
  // back into one combined amount (for a Manual entry that's literally
  // the same underlying record - see buildTotalRows()).
  var activeFeeTab = "Franchise Fee";
  var latestRows = [];

  function buildTotalRows(rows) {
    var byKey = {};
    var order = [];

    rows.forEach(function (row) {
      var key = row.name ? "manual:" + row.name : row.source + "|" + row.month + "|" + (row.coach || "");
      if (!byKey[key]) {
        byKey[key] = {
          month: row.month,
          amount: 0,
          source: row.source,
          fee_type: "Total Fee",
          coach: row.coach,
          coach_label: row.coach_label,
          name: row.name,
          note: row.note,
        };
        order.push(key);
      }
      byKey[key].amount += row.amount;
    });

    return order.map(function (key) { return byKey[key]; });
  }

  function renderActiveTab() {
    var coachFilter = el("feesCoachFilter");
    var selectedCoach = coachFilter ? coachFilter.value : "";

    var rows;
    if (activeFeeTab === "Total Fee") {
      rows = buildTotalRows(latestRows);
    } else {
      rows = latestRows.filter(function (row) { return row.fee_type === activeFeeTab; });
    }

    renderList(rows, !selectedCoach);
  }

  function initFeeTabs() {
    var tabsWrap = el("feesListTabs");
    if (!tabsWrap) return;

    tabsWrap.querySelectorAll(".dashboard-tab-btn[data-fee-tab]").forEach(function (button) {
      button.addEventListener("click", function () {
        tabsWrap.querySelectorAll(".dashboard-tab-btn").forEach(function (btn) {
          btn.classList.toggle("is-active", btn === button);
        });
        activeFeeTab = button.dataset.feeTab;
        renderActiveTab();
      });
    });
  }

  function renderList(rows, showCoach) {
    var list = el("feesReportList");
    if (!list) return;

    if (!rows.length) {
      list.innerHTML = '<div class="dashboard-card"><div class="dashboard-empty">No fees recorded yet.</div></div>';
      return;
    }

    list.innerHTML = rows.map(function (row) { return renderRow(row, showCoach); }).join("");

    list.querySelectorAll(".dashboard-fee-edit").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var card = btn.closest("[data-fee-name]");
        if (!card) return;
        loadRowIntoForm(card.dataset.feeName);
      });
    });

    list.querySelectorAll(".dashboard-fee-delete").forEach(function (btn) {
      btn.addEventListener("click", async function () {
        var card = btn.closest("[data-fee-name]");
        var name = card && card.dataset.feeName;
        if (!name) return;
        if (!window.confirm("Delete this month's entry?")) return;

        btn.disabled = true;
        try {
          await apiPost(SHARED_API + ".delete_manual_fee_total", { name: name });
          await loadReport();
        } catch (error) {
          window.alert(error.message || "Could not delete this entry.");
          btn.disabled = false;
        }
      });
    });
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

  function resetForm() {
    el("manualFeeName").value = "";
    el("manualFeeCoach").value = "";
    el("manualFeeMonth").value = "";
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
    var list = el("feesReportList");
    if (!list) return;

    var coachFilter = el("feesCoachFilter");
    var selectedCoach = coachFilter ? coachFilter.value : "";

    try {
      var data = await apiPost(SHARED_API + ".get_fees_report", { coach: selectedCoach });
      latestRows = Array.isArray(data.rows) ? data.rows : [];

      var totalEl = el("feesGrandTotal");
      if (totalEl) totalEl.textContent = formatCurrency(data.grand_total);

      renderActiveTab();

      var monthInput = el("manualFeeMonth");
      if (monthInput && data.auto_cutoff_date) {
        var cutoffParts = String(data.auto_cutoff_date).split("-");
        var lastManualMonth = new Date(Number(cutoffParts[0]), Number(cutoffParts[1]) - 1, 1);
        lastManualMonth.setMonth(lastManualMonth.getMonth() - 1);
        monthInput.max = lastManualMonth.getFullYear() + "-" + String(lastManualMonth.getMonth() + 1).padStart(2, "0");
      }
    } catch (error) {
      list.innerHTML = '<div class="dashboard-card"><div class="dashboard-empty">' + escapeHtml(error.message || "Could not load the fees report.") + "</div></div>";
    }
  }

  async function loadCoachFilter() {
    var select = el("feesCoachFilter");
    if (!select) return;

    try {
      var coaches = await apiPost(SHARED_API + ".get_coach_options_for_fees", {});
      select.innerHTML = '<option value="">All Coaches</option>' + (Array.isArray(coaches) ? coaches : []).map(function (c) {
        return '<option value="' + escapeHtml(c.name) + '">' + escapeHtml(c.coach_name || c.name) + "</option>";
      }).join("");
    } catch (error) {
      select.innerHTML = '<option value="">All Coaches</option>';
    }

    select.addEventListener("change", loadReport);
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

  async function loadItemOptions(selectEl, selectedValue) {
    try {
      var items = await apiPost("dashboard.api.shared.invoices.get_link_options", { doctype: "Item" });
      items = Array.isArray(items) ? items : [];
      selectEl.innerHTML = '<option value="">Not set</option>' + items.map(function (item) {
        return '<option value="' + escapeHtml(item.name) + '">' + escapeHtml(item.label || item.name) + "</option>";
      }).join("");
      selectEl.value = selectedValue || "";
    } catch (error) {
      selectEl.innerHTML = '<option value="">Could not load items</option>';
    }
  }

  async function loadFeesSettings() {
    var franchiseSelect = el("feesFranchiseItem");
    var marketingSelect = el("feesMarketingItem");
    if (!franchiseSelect || !marketingSelect) return;

    try {
      var settings = await apiPost(SHARED_API + ".get_fees_report_settings", {});
      await Promise.all([
        loadItemOptions(franchiseSelect, settings.franchise_fee_item),
        loadItemOptions(marketingSelect, settings.marketing_fee_item),
      ]);
    } catch (error) {
      window.alert(error.message || "Could not load fee item settings.");
    }
  }

  function initSettingsForm() {
    var saveBtn = el("saveFeesSettingsBtn");
    if (!saveBtn) return;

    saveBtn.addEventListener("click", async function () {
      saveBtn.disabled = true;
      try {
        await apiPost(SHARED_API + ".save_fees_report_settings", {
          franchise_fee_item: el("feesFranchiseItem").value,
          marketing_fee_item: el("feesMarketingItem").value,
        });
        await loadReport();
        window.alert("Settings saved.");
      } catch (error) {
        window.alert(error.message || "Could not save settings.");
      } finally {
        saveBtn.disabled = false;
      }
    });
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

  function renderTransactions(rows, coachLabel) {
    var wrap = el("feesReportTransactionsWrap");
    var container = el("feesReportTransactions");
    if (!wrap || !container) return;

    latestTransactionRows = rows.map(function (row) {
      return {
        month: row.month,
        coach_label: row.coach_label || coachLabel || "",
        fee_type: row.fee_type,
        source: row.source,
        amount: row.amount,
      };
    });

    wrap.style.display = latestTransactionRows.length ? "" : "none";

    if (!latestTransactionRows.length) {
      container.innerHTML = '<div class="dashboard-empty">No transactions for this period.</div>';
      return;
    }

    container.innerHTML =
      '<table class="dashboard-table"><thead><tr>' +
        "<th>Month</th><th>Coach</th><th>Fee Type</th><th>Source</th><th>Amount</th>" +
      "</tr></thead><tbody>" +
      latestTransactionRows.map(function (row) {
        return (
          "<tr>" +
            "<td>" + escapeHtml(formatMonth(row.month)) + "</td>" +
            "<td>" + escapeHtml(row.coach_label) + "</td>" +
            "<td>" + escapeHtml(row.fee_type) + "</td>" +
            "<td>" + escapeHtml(row.source) + "</td>" +
            "<td>" + formatCurrency(row.amount) + "</td>" +
          "</tr>"
        );
      }).join("") +
      "</tbody></table>";
  }

  function csvCell(value) {
    var str = String(value == null ? "" : value);
    return /[",\n]/.test(str) ? '"' + str.replace(/"/g, '""') + '"' : str;
  }

  function downloadTransactionsCsv() {
    if (!latestTransactionRows.length) return;

    var lines = [["Month", "Coach", "Fee Type", "Source", "Amount"].join(",")];
    latestTransactionRows.forEach(function (row) {
      lines.push([
        csvCell(formatMonth(row.month)),
        csvCell(row.coach_label),
        csvCell(row.fee_type),
        csvCell(row.source),
        csvCell(Number(row.amount || 0).toFixed(2)),
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

  function initRunReport() {
    var runBtn = el("runFeesReportBtn");
    if (!runBtn) return;

    runBtn.addEventListener("click", async function () {
      var coachSelect = el("feesRunReportCoach");
      var coach = coachSelect.value;
      var coachLabel = coachSelect.options[coachSelect.selectedIndex] ? coachSelect.options[coachSelect.selectedIndex].text : "";
      var fromMonth = el("feesRunReportFrom").value;
      var toMonth = el("feesRunReportTo").value;

      var args = {
        coach: coach,
        from_month: fromMonth ? fromMonth + "-01" : null,
        to_month: toMonth ? toMonth + "-01" : null,
      };

      runBtn.disabled = true;
      try {
        var totals = await apiPost(SHARED_API + ".get_fee_totals_by_coach", args);
        renderReportSummary(coach, Array.isArray(totals) ? totals : []);

        var reportData = await apiPost(SHARED_API + ".get_fees_report", args);
        renderTransactions(Array.isArray(reportData.rows) ? reportData.rows : [], coach ? coachLabel : "");
      } catch (error) {
        var summary = el("feesReportSummary");
        if (summary) summary.innerHTML = '<div class="dashboard-empty">' + escapeHtml(error.message || "Could not run this report.") + "</div>";
      } finally {
        runBtn.disabled = false;
      }
    });

    var downloadBtn = el("downloadFeesReportBtn");
    if (downloadBtn) downloadBtn.addEventListener("click", downloadTransactionsCsv);
  }

  async function init() {
    if (!el("feesReportList")) return;

    await loadCoachFilter();
    loadManualCoachOptions();
    loadRunReportCoachOptions();
    loadFeesSettings();
    initFeeTabs();
    loadReport();
    initForm();
    initSettingsForm();
    initRunReport();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
