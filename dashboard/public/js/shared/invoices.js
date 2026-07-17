(function () {
  "use strict";

  var el = Dashboard.el;

  function getDashboardBasePath() {
    const path = window.location.pathname || "";
    if (path.startsWith("/franchisor_db")) return "/franchisor_db";
    return "/coach_db";
  }

  function openInvoiceDetails(name) {
    if (!name) return;

    const params = new URLSearchParams(window.location.search);
    params.set("name", name);

    params.delete("coach");
    params.delete("_refresh");

    window.location.href = `${getDashboardBasePath()}/invoice_details?${params.toString()}`;
  }

  function initRowNavigation() {
    document.querySelectorAll(".dashboard-invoice-row").forEach((row) => {
      row.addEventListener("click", function (event) {
        const interactive = event.target.closest("a, button, input, select, textarea, label");
        if (interactive) return;

        const name = row.dataset.name || "";
        openInvoiceDetails(name);
      });
    });

    document.querySelectorAll("[data-invoice-open='1']").forEach((button) => {
      button.addEventListener("click", function (event) {
        event.preventDefault();
        const name = button.dataset.name || button.closest(".dashboard-invoice-row")?.dataset.name || "";
        openInvoiceDetails(name);
      });
    });
  }

  // Every filter (search, coach, from/to date, status) round-trips through
  // the server now - the list itself is server-paginated, so filtering only
  // the rows already on the current page (the old approach) couldn't work
  // once you left page 1: the date/status inputs are blank on a fresh page
  // load, so paging reset the filter and showed an unrelated page's worth
  // of invoices. Building the params from the CURRENT field values (rather
  // than only what's already in the URL) means changing one filter carries
  // the others along with it instead of clobbering them.
  function buildInvoiceParams(overrides) {
    const params = new URLSearchParams(window.location.search);

    const searchField = el("invoiceSearch");
    const coachSelector = el("invoiceCoachSelector");
    const fromDateField = el("invoiceFromDate");
    const toDateField = el("invoiceToDate");
    const statusField = el("invoiceStatusFilter");

    if (searchField && searchField.value.trim()) {
      params.set("search", searchField.value.trim());
    } else {
      params.delete("search");
    }

    if (coachSelector && coachSelector.value) {
      params.set("coach", coachSelector.value);
    } else {
      params.delete("coach");
    }

    if (fromDateField && fromDateField.value) {
      params.set("from_date", fromDateField.value);
    } else {
      params.delete("from_date");
    }

    if (toDateField && toDateField.value) {
      params.set("to_date", toDateField.value);
    } else {
      params.delete("to_date");
    }

    // Always set explicitly (even when empty, meaning "All statuses") so
    // it never silently falls back to the server's "Outstanding" default
    // once the user has deliberately chosen something else.
    if (statusField) {
      params.set("status", statusField.value || "");
    }

    params.delete("_refresh");

    Object.keys(overrides || {}).forEach(function (key) {
      const value = overrides[key];
      if (value === null || value === undefined || value === "") {
        params.delete(key);
      } else {
        params.set(key, value);
      }
    });

    return params;
  }

  function navigateInvoices(overrides) {
    const params = buildInvoiceParams(overrides);
    window.location.href = window.location.pathname + "?" + params.toString();
  }

  var debounce = Dashboard.debounce;

  function initFilters() {
    const searchField = el("invoiceSearch");
    if (searchField) {
      searchField.addEventListener("input", debounce(function () {
        navigateInvoices({ page: 1 });
      }, 500));
    }

    ["invoiceFromDate", "invoiceToDate", "invoiceStatusFilter"].forEach((id) => {
      const field = el(id);
      if (!field) return;
      field.addEventListener("change", function () {
        navigateInvoices({ page: 1 });
      });
    });
  }

  function initCoachSelector() {
    const selector = el("invoiceCoachSelector");
    if (!selector) return;

    selector.addEventListener("change", function () {
      navigateInvoices({ page: 1 });
    });
  }

  function initRefresh() {
    const button = el("refreshInvoices");
    if (!button) return;

    button.addEventListener("click", function () {
      button.disabled = true;
      button.textContent = "Refreshing...";

      navigateInvoices({ _refresh: Date.now() });
    });
  }

  function initAddInvoice() {
    const button = el("addInvoice");
    if (!button) return;

    button.addEventListener("click", function () {
      window.location.href = `${getDashboardBasePath()}/invoice_details?new=1`;
    });
  }

  function initInvoicesPage() {
    if (el("invoiceDetailsForm")) return;

    const isInvoicePage =
      el("invoiceCoachSelector") ||
      el("refreshInvoices") ||
      el("invoiceSearch") ||
      el("invoiceTable") ||
      el("invoiceCount");

    if (!isInvoicePage) return;

    initCoachSelector();
    initFilters();
    initRefresh();
    initAddInvoice();
    initRowNavigation();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initInvoicesPage);
  } else {
    initInvoicesPage();
  }
})();
