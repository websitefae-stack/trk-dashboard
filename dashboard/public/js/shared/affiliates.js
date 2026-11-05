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

  function showSettingError(message) {
    var box = el("affiliateSettingError");
    if (!box) return;
    box.textContent = message || "";
    box.style.display = message ? "" : "none";
  }

  // =====================================================
  // SETTINGS
  // =====================================================

  var itemOptionsByLabel = {};
  var courseOptionsByLabel = {};

  async function loadItemOptions(query) {
    var items = await apiPost(API + ".search_affiliate_items", { query: query || "" });
    itemOptionsByLabel = {};
    var list = el("affiliateItemOptions");
    if (!list) return;
    list.innerHTML = items.map(function (item) {
      var label = item.item_name + (item.has_variants ? " (has variants)" : "") + " — " + item.name;
      itemOptionsByLabel[label] = item.name;
      return '<option value="' + escapeHtml(label) + '"></option>';
    }).join("");
  }

  async function loadCourseOptions(query) {
    var courses = await apiPost(API + ".search_affiliate_courses", { query: query || "" });
    courseOptionsByLabel = {};
    var list = el("affiliateCourseOptions");
    if (!list) return;
    list.innerHTML = courses.map(function (course) {
      var label = course.title + " — " + course.name;
      courseOptionsByLabel[label] = course.name;
      return '<option value="' + escapeHtml(label) + '"></option>';
    }).join("");
  }

  function applicableTypeFields() {
    var isItem = el("affiliateSettingType").value === "item";
    el("affiliateSettingItemField").style.display = isItem ? "" : "none";
    el("affiliateSettingCourseField").style.display = isItem ? "none" : "";
  }

  function applicableCommissionFields() {
    var isPercent = el("affiliateSettingCommissionType").value === "Percentage";
    el("affiliateSettingPercentField").style.display = isPercent ? "" : "none";
    el("affiliateSettingFlatField").style.display = isPercent ? "none" : "";
  }

  function resetSettingForm() {
    el("affiliateSettingName").value = "";
    el("affiliateSettingType").value = "item";
    el("affiliateSettingItem").value = "";
    el("affiliateSettingCourse").value = "";
    el("affiliateSettingCommissionType").value = "Percentage";
    el("affiliateSettingPercent").value = "";
    el("affiliateSettingFlat").value = "";
    el("affiliateSettingEnabled").checked = true;
    showSettingError("");

    el("affiliateSettingFormHeading").textContent = "Add a Commission Setting";
    el("saveAffiliateSettingBtn").textContent = "Save Setting";
    el("cancelEditAffiliateSettingBtn").style.display = "none";

    applicableTypeFields();
    applicableCommissionFields();
  }

  function loadSettingIntoForm(row) {
    el("affiliateSettingName").value = row.name;
    el("affiliateSettingType").value = row.item ? "item" : "course";

    if (row.item) {
      el("affiliateSettingItem").value = row.label + " — " + row.item;
      itemOptionsByLabel[row.label + " — " + row.item] = row.item;
    } else {
      el("affiliateSettingCourse").value = row.label + " — " + row.course;
      courseOptionsByLabel[row.label + " — " + row.course] = row.course;
    }

    el("affiliateSettingCommissionType").value = row.commission_type;
    el("affiliateSettingPercent").value = row.commission_percent || "";
    el("affiliateSettingFlat").value = row.commission_flat_amount || "";
    el("affiliateSettingEnabled").checked = !!row.enabled;
    showSettingError("");

    el("affiliateSettingFormHeading").textContent = "Edit Commission Setting";
    el("saveAffiliateSettingBtn").textContent = "Update Setting";
    el("cancelEditAffiliateSettingBtn").style.display = "";

    applicableTypeFields();
    applicableCommissionFields();
    el("affiliateSettingForm").scrollIntoView({ behavior: "smooth", block: "start" });
  }

  var latestSettings = [];

  async function loadSettingsTable() {
    var container = el("affiliateSettingsTable");
    try {
      latestSettings = await apiPost(API + ".get_affiliate_product_settings", {});
    } catch (error) {
      container.innerHTML = '<div class="dashboard-empty">Could not load settings.</div>';
      return;
    }

    if (!latestSettings.length) {
      container.innerHTML = '<div class="dashboard-empty">No commission settings yet - add one above.</div>';
      return;
    }

    container.innerHTML =
      '<table class="dashboard-table"><thead><tr>' +
        "<th>Applies To</th><th>Commission</th><th>Enabled</th><th></th>" +
      "</tr></thead><tbody>" +
      latestSettings.map(function (row) {
        var commission = row.commission_type === "Flat Amount"
          ? formatCurrency(row.commission_flat_amount) + " flat"
          : Number(row.commission_percent || 0) + "%";
        return (
          "<tr>" +
            "<td>" + escapeHtml(row.label) + (row.course ? " (Course)" : "") + "</td>" +
            "<td>" + escapeHtml(commission) + "</td>" +
            "<td>" + (row.enabled ? "Yes" : "No") + "</td>" +
            '<td><button type="button" class="dashboard-btn dashboard-btn-light dashboard-btn-sm js-edit-affiliate-setting" data-name="' + escapeHtml(row.name) + '">Edit</button> ' +
            '<button type="button" class="dashboard-btn dashboard-btn-light dashboard-btn-sm js-delete-affiliate-setting" data-name="' + escapeHtml(row.name) + '">Delete</button></td>' +
          "</tr>"
        );
      }).join("") +
      "</tbody></table>";
  }

  function initSettingForm() {
    el("affiliateSettingType").addEventListener("change", applicableTypeFields);
    el("affiliateSettingCommissionType").addEventListener("change", applicableCommissionFields);

    el("affiliateSettingItem").addEventListener("input", function () {
      loadItemOptions(this.value);
    });
    el("affiliateSettingCourse").addEventListener("input", function () {
      loadCourseOptions(this.value);
    });

    el("cancelEditAffiliateSettingBtn").addEventListener("click", resetSettingForm);

    el("saveAffiliateSettingBtn").addEventListener("click", async function () {
      showSettingError("");

      var isItem = el("affiliateSettingType").value === "item";
      var item = isItem ? (itemOptionsByLabel[el("affiliateSettingItem").value] || "") : "";
      var course = !isItem ? (courseOptionsByLabel[el("affiliateSettingCourse").value] || "") : "";

      if (isItem && !item) {
        showSettingError("Pick an item from the list.");
        return;
      }
      if (!isItem && !course) {
        showSettingError("Pick a course from the list.");
        return;
      }

      var payload = {
        name: el("affiliateSettingName").value || "",
        item: item,
        course: course,
        commission_type: el("affiliateSettingCommissionType").value,
        commission_percent: el("affiliateSettingPercent").value || 0,
        commission_flat_amount: el("affiliateSettingFlat").value || 0,
        enabled: el("affiliateSettingEnabled").checked ? 1 : 0,
      };

      try {
        el("saveAffiliateSettingBtn").disabled = true;
        await apiPost(API + ".save_affiliate_product_setting", payload);
        resetSettingForm();
        await loadSettingsTable();
      } catch (error) {
        showSettingError(error.message || "Could not save this setting.");
      } finally {
        el("saveAffiliateSettingBtn").disabled = false;
      }
    });

    document.addEventListener("click", async function (event) {
      var editBtn = event.target.closest(".js-edit-affiliate-setting");
      if (editBtn) {
        var row = latestSettings.filter(function (r) { return r.name === editBtn.dataset.name; })[0];
        if (row) loadSettingIntoForm(row);
        return;
      }

      var deleteBtn = event.target.closest(".js-delete-affiliate-setting");
      if (deleteBtn) {
        if (!window.confirm("Delete this commission setting?")) return;
        try {
          await apiPost(API + ".delete_affiliate_product_setting", { name: deleteBtn.dataset.name });
          await loadSettingsTable();
        } catch (error) {
          window.alert(error.message || "Could not delete this setting.");
        }
      }
    });
  }

  // =====================================================
  // COMMISSIONS
  // =====================================================

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
      rows = await apiPost(API + ".get_affiliate_commissions", { coach: coach, status: status });
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

    container.innerHTML =
      '<table class="dashboard-table"><thead><tr>' +
        "<th></th><th>Coach</th><th>Product</th><th>Customer</th><th>Sale</th><th>Rate</th><th>Commission</th><th>Status</th>" +
      "</tr></thead><tbody>" +
      rows.map(function (row) {
        return (
          "<tr>" +
            '<td>' + (row.status === "Pending" ? '<input type="checkbox" class="js-affiliate-commission-check" value="' + escapeHtml(row.name) + '">' : "") + "</td>" +
            "<td>" + escapeHtml(row.coach_label) + "</td>" +
            "<td>" + escapeHtml(row.product_label) + "</td>" +
            "<td>" + escapeHtml(row.client_full_name || "") + "</td>" +
            "<td>" + formatCurrency(row.sale_amount) + "</td>" +
            "<td>" + escapeHtml(row.commission_rate_snapshot || "") + "</td>" +
            "<td style=\"font-weight:700;\">" + formatCurrency(row.commission_amount) + "</td>" +
            "<td>" + escapeHtml(row.status) + "</td>" +
          "</tr>"
        );
      }).join("") +
      "</tbody></table>";
  }

  function initCommissionsFilters() {
    el("affiliateCommissionCoach").addEventListener("change", loadCommissionsTable);
    el("affiliateCommissionStatus").addEventListener("change", loadCommissionsTable);

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
  }

  function init() {
    if (el("affiliatesPage")) {
      initSettingForm();
      initCommissionsFilters();
      applicableTypeFields();
      applicableCommissionFields();

      loadSettingsTable();
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
