(function () {
  "use strict";

  var el = Dashboard.el;

  function getDashboardBasePath() {
    const path = window.location.pathname || "";
    if (path.startsWith("/franchisor_db")) return "/franchisor_db";
    return "/coach_db";
  }

  function updateInvoiceCount() {
    const countEl = el("invoiceCount");
    if (!countEl) return;

    const rows = Array.from(document.querySelectorAll(".dashboard-invoice-row"));
    const visible = rows.filter((row) => row.style.display !== "none").length;

    countEl.textContent = `${visible} invoice${visible === 1 ? "" : "s"}`;
  }

  function invoiceMatches(row, search, fromDate, toDate, status) {
    const haystack = [
      row.dataset.name || "",
      row.dataset.client || "",
      row.dataset.customer || "",
      row.dataset.company || ""
    ].join(" ").toLowerCase();

    const rowDate = row.dataset.date || "";
    const rowStatus = row.dataset.status || "";

    if (search && !haystack.includes(search)) return false;

    if (!search) {
      if (status === "Outstanding") {
        if (!["Unpaid", "Overdue", "Partly Paid"].includes(rowStatus)) return false;
      } else if (status && rowStatus !== status) {
        return false;
      }
    }

    if (fromDate && rowDate < fromDate) return false;
    if (toDate && rowDate > toDate) return false;

    return true;
  }

  function renderFilters() {
    const search = (el("invoiceSearch")?.value || "").trim().toLowerCase();
    const fromDate = el("invoiceFromDate")?.value || "";
    const toDate = el("invoiceToDate")?.value || "";
    const status = el("invoiceStatusFilter")?.value || "";

    const rows = document.querySelectorAll(".dashboard-invoice-row");
    let visible = 0;

    rows.forEach((row) => {
      const show = invoiceMatches(row, search, fromDate, toDate, status);
      row.style.display = show ? "" : "none";
      if (show) visible++;
    });

    const emptyState = el("invoiceEmptyState");
    if (emptyState) {
      emptyState.style.display = visible ? "none" : "block";
    }

    updateInvoiceCount();
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

  function goToInvoiceListWithCoach(selectedCoach) {
    const selector = el("invoiceCoachSelector");
    const currentCoach = selector ? selector.dataset.currentCoach || "" : "";

    const params = new URLSearchParams();

    if (selectedCoach && selectedCoach !== currentCoach) {
      params.set("coach", selectedCoach);
    }

    params.set("_refresh", Date.now());

    window.location.href = window.location.pathname + "?" + params.toString();
  }

  function initCoachSelector() {
    const selector = el("invoiceCoachSelector");
    if (!selector) return;

    selector.addEventListener("change", function () {
      goToInvoiceListWithCoach(selector.value || "");
    });
  }

  var debounce = Dashboard.debounce;

  function runServerInvoiceSearch() {
    const searchField = el("invoiceSearch");
    const params = new URLSearchParams(window.location.search);
    const coachSelector = el("invoiceCoachSelector");
    const searchValue = searchField ? searchField.value.trim() : "";

    if (searchValue) {
      params.set("search", searchValue);
    } else {
      params.delete("search");
    }

    if (coachSelector && coachSelector.value) {
      params.set("coach", coachSelector.value);
    }
    
    params.set("page", "1");

    window.location.href = window.location.pathname + "?" + params.toString();
  }
  
  function initFilters() {
    ["invoiceSearch", "invoiceFromDate", "invoiceToDate", "invoiceStatusFilter"].forEach((id) => {
      const field = el(id);
      if (!field) return;

      if (id === "invoiceSearch") {
        field.addEventListener("input", debounce(runServerInvoiceSearch, 500));
      } else {
        field.addEventListener("change", renderFilters);
      }
    });
  }

  function initRefresh() {
    const button = el("refreshInvoices");
    if (!button) return;

    button.addEventListener("click", function () {
      const selector = el("invoiceCoachSelector");
      const selectedCoach = selector ? selector.value || "" : "";

      button.disabled = true;
      button.textContent = "Refreshing...";

      goToInvoiceListWithCoach(selectedCoach);
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
    renderFilters();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initInvoicesPage);
  } else {
    initInvoicesPage();
  }
})();
