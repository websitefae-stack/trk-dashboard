/**
 * Franchisor "Affiliates" page (franchisor_db/affiliates) -
 * dashboard.api.shared.affiliate. Two independent sections: which
 * Items/Courses earn a commission and how much (Affiliate Product
 * Setting), and the resulting per-sale commission ledger (Affiliate
 * Commission) with a bulk "mark paid" action.
 */
(function () {
  "use strict";

  var el = Dashboard.el;
  var API = "dashboard.api.shared.affiliate";

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
      throw new Error(Dashboard.extractErrorMessage(data, "There was a problem."));
    }

    return data.message || {};
  }

  function formatCurrency(amount) {
    return "£" + Number(amount || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  function showCatalogError(message) {
    var box = el("affiliateCatalogError");
    if (!box) return;
    box.textContent = message || "";
    box.style.display = message ? "" : "none";
  }

  // =====================================================
  // SETTINGS (full catalog - every item/course listed, tick to enable)
  // =====================================================

  function renderCatalogRow(row) {
    var isPercent = row.commission_type !== "Flat Amount";
    var rowId = row.type + ":" + row.code;

    return (
      '<tr data-row-id="' + escapeHtml(rowId) + '" data-type="' + row.type + '" data-code="' + escapeHtml(row.code) + '">' +
        "<td>" + escapeHtml(row.label) + "</td>" +
        '<td><input type="checkbox" class="js-affiliate-catalog-enabled" ' + (row.enabled ? "checked" : "") + "></td>" +
        '<td><select class="dashboard-select js-affiliate-catalog-type">' +
          '<option value="Percentage"' + (isPercent ? " selected" : "") + ">Percentage</option>" +
          '<option value="Flat Amount"' + (!isPercent ? " selected" : "") + ">Flat Amount</option>" +
        "</select></td>" +
        '<td><input type="number" min="0" max="100" step="0.1" class="dashboard-input js-affiliate-catalog-percent" ' +
          'style="width:90px;' + (isPercent ? "" : "display:none;") + '" value="' + (row.commission_percent || "") + '"></td>' +
        '<td><input type="number" min="0" step="0.01" class="dashboard-input js-affiliate-catalog-flat" ' +
          'style="width:90px;' + (isPercent ? "display:none;" : "") + '" value="' + (row.commission_flat_amount || "") + '"></td>' +
      "</tr>"
    );
  }

  function renderCatalogSection(title, rows) {
    if (!rows.length) return "";

    return (
      '<div style="margin-top:16px;"><h3 style="margin:0 0 8px;">' + escapeHtml(title) + "</h3>" +
      '<table class="dashboard-table"><thead><tr>' +
        "<th>Name</th><th>Enabled</th><th>Commission Type</th><th>Percent (%)</th><th>Flat Amount (&pound;)</th>" +
      "</tr></thead><tbody>" +
      rows.map(renderCatalogRow).join("") +
      "</tbody></table></div>"
    );
  }

  async function loadCatalogTable() {
    var container = el("affiliateCatalogTable");
    showCatalogError("");

    var catalog;
    try {
      catalog = await apiPost(API + ".get_affiliate_commission_catalog", {});
    } catch (error) {
      container.innerHTML = '<div class="dashboard-empty">Could not load the catalog.</div>';
      return;
    }

    if (!catalog.items.length && !catalog.courses.length) {
      container.innerHTML = '<div class="dashboard-empty">No store items or courses found.</div>';
      return;
    }

    container.innerHTML =
      renderCatalogSection("Store Items", catalog.items) +
      renderCatalogSection("Courses", catalog.courses);

    Array.prototype.slice.call(container.querySelectorAll(".js-affiliate-catalog-type")).forEach(function (select) {
      select.addEventListener("change", function () {
        var row = select.closest("tr");
        var isPercent = select.value === "Percentage";
        row.querySelector(".js-affiliate-catalog-percent").style.display = isPercent ? "" : "none";
        row.querySelector(".js-affiliate-catalog-flat").style.display = isPercent ? "none" : "";
      });
    });
  }

  function initCatalogSave() {
    var saveBtn = el("saveAffiliateCatalogBtn");
    if (!saveBtn) return;

    saveBtn.addEventListener("click", async function () {
      showCatalogError("");

      var rows = Array.prototype.slice.call(document.querySelectorAll("#affiliateCatalogTable tr[data-row-id]")).map(function (tr) {
        return {
          type: tr.dataset.type,
          code: tr.dataset.code,
          enabled: tr.querySelector(".js-affiliate-catalog-enabled").checked ? 1 : 0,
          commission_type: tr.querySelector(".js-affiliate-catalog-type").value,
          commission_percent: tr.querySelector(".js-affiliate-catalog-percent").value || 0,
          commission_flat_amount: tr.querySelector(".js-affiliate-catalog-flat").value || 0,
        };
      });

      try {
        saveBtn.disabled = true;
        saveBtn.textContent = "Saving...";
        await apiPost(API + ".save_affiliate_commission_catalog", { rows: JSON.stringify(rows) });
        await loadCatalogTable();
        await loadCoachPerformanceTable();
      } catch (error) {
        showCatalogError(error.message || "Could not save these changes.");
      } finally {
        saveBtn.disabled = false;
        saveBtn.textContent = "Save Changes";
      }
    });
  }

  // =====================================================
  // SHARED: expandable "what did they actually buy" row
  // =====================================================

  var expandedSaleRows = {};

  function renderSaleDetailRow(colspan, items, grandTotal) {
    if (!items || !items.length) {
      return '<tr class="js-affiliate-sale-detail-row"><td colspan="' + colspan + '" style="background:#F2F8F8; padding:12px 16px;">Could not find this order\'s items.</td></tr>';
    }

    var lines = items.map(function (item) {
      return (
        '<div style="display:flex; justify-content:space-between; gap:12px;">' +
          "<span>" + escapeHtml(item.item_name) + " &times; " + Number(item.qty) + "</span>" +
          "<span>" + formatCurrency(item.amount) + "</span>" +
        "</div>"
      );
    }).join("");

    return (
      '<tr class="js-affiliate-sale-detail-row"><td colspan="' + colspan + '" style="background:#F2F8F8; padding:12px 16px;">' +
        '<div style="font-size:13px; color:#839898; text-transform:uppercase; letter-spacing:0.04em; margin-bottom:6px;">Whole Order</div>' +
        lines +
        '<div style="display:flex; justify-content:space-between; gap:12px; font-weight:700; margin-top:6px; padding-top:6px; border-top:1px solid #D9E6E6;">' +
          "<span>Order Total</span><span>" + formatCurrency(grandTotal) + "</span>" +
        "</div>" +
      "</td></tr>"
    );
  }

  // isMine: use the coach's own restricted endpoint (coach_db/affiliate)
  // rather than the franchisor one (franchisor_db/affiliates) - same
  // shape, different permission check server-side.
  async function toggleSaleDetail(row, commissionName, colspan, isMine) {
    var existing = row.nextElementSibling;
    if (existing && existing.classList && existing.classList.contains("js-affiliate-sale-detail-row")) {
      existing.remove();
      delete expandedSaleRows[commissionName];
      return;
    }

    Object.keys(expandedSaleRows).forEach(function (name) {
      var openRow = document.querySelector('[data-sale-detail-for="' + name + '"]');
      if (openRow) openRow.remove();
    });
    expandedSaleRows = {};

    var method = isMine ? ".get_my_affiliate_sale_items" : ".get_affiliate_sale_items";
    var payload = isMine ? { commission: commissionName } : { commission: commissionName };

    try {
      var result = await apiPost(API + method, payload);
      var detailHtml = renderSaleDetailRow(colspan, result.items, result.grand_total);
      row.insertAdjacentHTML("afterend", detailHtml);
      var inserted = row.nextElementSibling;
      if (inserted) inserted.setAttribute("data-sale-detail-for", commissionName);
      expandedSaleRows[commissionName] = true;
    } catch (error) {
      window.alert(error.message || "Could not load this order's items.");
    }
  }

  // =====================================================
  // COMMISSIONS
  // =====================================================

  function currentDateFilters() {
    var fromEl = el("affiliateFromDate");
    var toEl = el("affiliateToDate");
    return {
      from_date: fromEl ? fromEl.value : "",
      to_date: toEl ? toEl.value : "",
    };
  }

  async function loadCoachPerformanceTable() {
    var container = el("affiliateCoachPerformanceTable");
    if (!container) return;

    var rows;
    try {
      rows = await apiPost(API + ".get_affiliate_coach_performance", currentDateFilters());
    } catch (error) {
      container.innerHTML = '<div class="dashboard-empty">Could not load coach performance.</div>';
      return;
    }

    if (!rows.length) {
      container.innerHTML = '<div class="dashboard-empty">No affiliate link activity yet.</div>';
      return;
    }

    container.innerHTML =
      '<table class="dashboard-table"><thead><tr>' +
        "<th>Coach</th><th>Clicks</th><th>Sales</th><th>Pending</th><th>Paid</th>" +
      "</tr></thead><tbody>" +
      rows.map(function (row) {
        return (
          "<tr>" +
            "<td>" + escapeHtml(row.coach_label) + "</td>" +
            "<td>" + Number(row.click_count) + "</td>" +
            "<td>" + Number(row.sale_count) + "</td>" +
            "<td>" + formatCurrency(row.pending_total) + "</td>" +
            "<td>" + formatCurrency(row.paid_total) + "</td>" +
          "</tr>"
        );
      }).join("") +
      "</tbody></table>";
  }

  async function loadCoachFilterOptions() {
    var select = el("affiliateCommissionCoach");
    if (!select) return;

    try {
      var coaches = await apiPost(API + ".get_coach_options_for_affiliates", {});
      select.innerHTML = '<option value="">All Coaches</option>' + coaches.map(function (c) {
        return '<option value="' + escapeHtml(c.name) + '">' + escapeHtml(c.coach_name || c.name) + "</option>";
      }).join("");
    } catch (error) {
      // Leave the "All Coaches" default in place.
    }
  }

  async function loadCommissionsTable() {
    var container = el("affiliateCommissionsTable");
    var coach = el("affiliateCommissionCoach").value;
    var status = el("affiliateCommissionStatus").value;

    var rows;
    try {
      var payload = currentDateFilters();
      payload.coach = coach;
      payload.status = status;
      rows = await apiPost(API + ".get_affiliate_commissions", payload);
    } catch (error) {
      container.innerHTML = '<div class="dashboard-empty">Could not load commissions.</div>';
      return;
    }

    var pendingTotal = rows.filter(function (r) { return r.status === "Pending"; })
      .reduce(function (sum, r) { return sum + Number(r.commission_amount || 0); }, 0);
    var paidTotal = rows.filter(function (r) { return r.status === "Paid"; })
      .reduce(function (sum, r) { return sum + Number(r.commission_amount || 0); }, 0);

    el("affiliateCommissionsPendingTotal").textContent = formatCurrency(pendingTotal);
    el("affiliateCommissionsPaidTotal").textContent = formatCurrency(paidTotal);

    if (!rows.length) {
      container.innerHTML = '<div class="dashboard-empty">No commissions yet.</div>';
      return;
    }

    var colspan = 8;

    container.innerHTML =
      '<table class="dashboard-table"><thead><tr>' +
        "<th></th><th>Coach</th><th>Product</th><th>Customer</th><th>Sale</th><th>Rate</th><th>Commission</th><th>Status</th>" +
      "</tr></thead><tbody>" +
      rows.map(function (row) {
        return (
          '<tr class="js-affiliate-commission-row" data-commission="' + escapeHtml(row.name) + '" style="cursor:pointer;" title="Click to see what they bought">' +
            '<td>' + (row.status === "Pending" ? '<input type="checkbox" class="js-affiliate-commission-check" value="' + escapeHtml(row.name) + '">' : "") + "</td>" +
            "<td>" + escapeHtml(row.coach_label) + "</td>" +
            "<td>" + escapeHtml(row.product_label) + "</td>" +
            "<td>" + escapeHtml(row.client_full_name || "") + (row.client_email ? '<br><span style="color:#839898; font-size:12px;">' + escapeHtml(row.client_email) + "</span>" : "") + "</td>" +
            "<td>" + formatCurrency(row.sale_amount) + "</td>" +
            "<td>" + escapeHtml(row.commission_rate_snapshot || "") + "</td>" +
            "<td style=\"font-weight:700;\">" + formatCurrency(row.commission_amount) + "</td>" +
            "<td>" + escapeHtml(row.status) + "</td>" +
          "</tr>"
        );
      }).join("") +
      "</tbody></table>";

    Array.prototype.slice.call(container.querySelectorAll(".js-affiliate-commission-row")).forEach(function (row) {
      row.addEventListener("click", function (event) {
        if (event.target.closest(".js-affiliate-commission-check")) return;
        toggleSaleDetail(row, row.dataset.commission, colspan, false);
      });
    });
  }

  function initCommissionsFilters() {
    el("affiliateCommissionCoach").addEventListener("change", loadCommissionsTable);
    el("affiliateCommissionStatus").addEventListener("change", loadCommissionsTable);

    // Shared by Coach Performance and Commissions - one period filter.
    var fromEl = el("affiliateFromDate");
    var toEl = el("affiliateToDate");
    if (fromEl) {
      fromEl.addEventListener("change", function () {
        loadCoachPerformanceTable();
        loadCommissionsTable();
      });
    }
    if (toEl) {
      toEl.addEventListener("change", function () {
        loadCoachPerformanceTable();
        loadCommissionsTable();
      });
    }

    el("markAffiliateCommissionsPaidBtn").addEventListener("click", async function () {
      var names = Array.prototype.slice.call(document.querySelectorAll(".js-affiliate-commission-check:checked"))
        .map(function (input) { return input.value; });

      if (!names.length) {
        window.alert("Select at least one Pending commission first.");
        return;
      }

      try {
        await apiPost(API + ".mark_affiliate_commissions_paid", { names: JSON.stringify(names) });
        await loadCommissionsTable();
        await loadCoachPerformanceTable();
      } catch (error) {
        window.alert(error.message || "Could not mark these as paid.");
      }
    });
  }

  // =====================================================
  // COACH'S OWN LINK (coach_db/affiliate)
  // =====================================================

  async function initCoachAffiliatePage() {
    var linkInput = el("coachAffiliateLink");
    if (!linkInput) return;

    try {
      var summary = await apiPost(API + ".get_my_affiliate_summary", {});
      linkInput.value = summary.link || "";
      el("coachAffiliatePendingTotal").textContent = formatCurrency(summary.pending_total);
      el("coachAffiliatePaidTotal").textContent = formatCurrency(summary.paid_total);
      el("coachAffiliateSaleCount").textContent = String(summary.sale_count || 0);
      var clicksEl = el("coachAffiliateClickCount");
      if (clicksEl) clicksEl.textContent = String(summary.click_count || 0);
    } catch (error) {
      linkInput.value = "";
      linkInput.placeholder = "Could not load your link.";
    }

    var copyBtn = el("copyAffiliateLinkBtn");
    if (copyBtn) {
      copyBtn.addEventListener("click", function () {
        if (!linkInput.value) return;
        linkInput.select();
        try {
          navigator.clipboard.writeText(linkInput.value);
          copyBtn.textContent = "Copied!";
          setTimeout(function () { copyBtn.textContent = "Copy Link"; }, 1500);
        } catch (error) {
          document.execCommand("copy");
        }
      });
    }

    await loadMyAffiliateSales();
  }

  async function loadMyAffiliateSales() {
    var container = el("coachAffiliateSalesTable");
    if (!container) return;

    var rows;
    try {
      rows = await apiPost(API + ".get_my_affiliate_commissions", {});
    } catch (error) {
      container.innerHTML = '<div class="dashboard-empty">Could not load your sales.</div>';
      return;
    }

    if (!rows.length) {
      container.innerHTML = '<div class="dashboard-empty">No sales through your link yet.</div>';
      return;
    }

    var colspan = 6;

    container.innerHTML =
      '<table class="dashboard-table"><thead><tr>' +
        "<th>Product</th><th>Customer</th><th>Sale Price</th><th>Rate</th><th>Commission</th><th>Status</th>" +
      "</tr></thead><tbody>" +
      rows.map(function (row) {
        return (
          '<tr class="js-affiliate-commission-row" data-commission="' + escapeHtml(row.name) + '" style="cursor:pointer;" title="Click to see what they bought">' +
            "<td>" + escapeHtml(row.product_label) + "</td>" +
            "<td>" + escapeHtml(row.client_full_name || "") + (row.client_email ? '<br><span style="color:#839898; font-size:12px;">' + escapeHtml(row.client_email) + "</span>" : "") + "</td>" +
            "<td>" + formatCurrency(row.sale_amount) + "</td>" +
            "<td>" + escapeHtml(row.commission_rate_snapshot || "") + "</td>" +
            "<td style=\"font-weight:700;\">" + formatCurrency(row.commission_amount) + "</td>" +
            "<td>" + escapeHtml(row.status) + "</td>" +
          "</tr>"
        );
      }).join("") +
      "</tbody></table>";

    Array.prototype.slice.call(container.querySelectorAll(".js-affiliate-commission-row")).forEach(function (row) {
      row.addEventListener("click", function () {
        toggleSaleDetail(row, row.dataset.commission, colspan, true);
      });
    });
  }

  function init() {
    if (el("affiliatesPage")) {
      initCatalogSave();
      initCommissionsFilters();

      loadCatalogTable();
      loadCoachPerformanceTable();
      loadCoachFilterOptions();
      loadCommissionsTable();
    }

    if (el("coachAffiliatePage")) {
      initCoachAffiliatePage();
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
