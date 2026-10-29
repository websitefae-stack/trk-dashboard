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

  function renderRow(row) {
    var isManual = row.source === "Manual";
    var badgeClass = isManual ? "dashboard-badge" : "dashboard-badge dashboard-status-active";

    return (
      '<div class="dashboard-card" data-fee-name="' + escapeHtml(row.name) + '" data-fee-month="' + escapeHtml(row.month) + '" style="margin-bottom:10px; display:flex; justify-content:space-between; align-items:center; gap:12px; flex-wrap:wrap;">' +
        '<div>' +
          '<div style="font-weight:600;">' + escapeHtml(formatMonth(row.month)) + (row.fee_type && row.fee_type !== "Fees Paid" ? " - " + escapeHtml(row.fee_type) : "") + "</div>" +
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

  function renderList(rows) {
    var list = el("feesReportList");
    if (!list) return;

    if (!rows.length) {
      list.innerHTML = '<div class="dashboard-card"><div class="dashboard-empty">No fees recorded yet.</div></div>';
      return;
    }

    list.innerHTML = rows.map(renderRow).join("");

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

    // Manual historical totals are business-wide, not per-coach - the
    // add form only makes sense on the unfiltered "All Coaches" view.
    var manualForm = el("manualFeeForm");
    if (manualForm) manualForm.style.display = selectedCoach ? "none" : "";

    try {
      var data = await apiPost(SHARED_API + ".get_fees_report", { coach: selectedCoach });
      var rows = Array.isArray(data.rows) ? data.rows : [];

      var totalEl = el("feesGrandTotal");
      if (totalEl) totalEl.textContent = formatCurrency(data.grand_total);

      renderList(rows);

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
      var coaches = await apiPost(SHARED_API + ".get_fee_paying_coaches", {});
      select.innerHTML = '<option value="">All Coaches</option>' + (Array.isArray(coaches) ? coaches : []).map(function (c) {
        return '<option value="' + escapeHtml(c.name) + '">' + escapeHtml(c.coach_name || c.name) + "</option>";
      }).join("");
    } catch (error) {
      select.innerHTML = '<option value="">All Coaches</option>';
    }

    select.addEventListener("change", loadReport);
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
      var month = el("manualFeeMonth").value;
      var franchiseAmount = el("manualFeeFranchiseAmount").value;
      var marketingAmount = el("manualFeeMarketingAmount").value;

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

  async function init() {
    if (!el("feesReportList")) return;

    await loadCoachFilter();
    loadFeesSettings();
    loadReport();
    initForm();
    initSettingsForm();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
