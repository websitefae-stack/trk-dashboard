(function () {
  "use strict";

  function initInvoicesPage() {
    if (document.getElementById("invoiceDetailsForm")) return;
  
    const hasInvoicePage =
      document.getElementById("refreshInvoices") ||
      document.getElementById("invoiceCoachSelector") ||
      document.getElementById("invoiceSearch") ||
      document.getElementById("invoiceTable");
  
    if (!hasInvoicePage) return;

    const el = (id) => document.getElementById(id);

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
      if (status && rowStatus !== status) return false;
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

    function getDashboardBasePath() {
      const path = window.location.pathname || "";
      if (path.startsWith("/franchisor_db")) return "/franchisor_db";
      return "/coach_db";
    }

    function openInvoiceDetails(name) {
      if (!name) return;
      window.location.href = `${getDashboardBasePath()}/invoice_details?name=${encodeURIComponent(name)}`;
    }

    function initRowNavigation() {
      document.querySelectorAll(".dashboard-invoice-row").forEach((row) => {
        row.addEventListener("click", function (event) {
          const interactive = event.target.closest("a, button, input, select, textarea, label");
          if (interactive) return;

          const name = row.dataset.name || "";
          if (!name) return;

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

    function initCoachSelector() {
      const selector = el("invoiceCoachSelector");
      if (!selector) return;

      selector.addEventListener("change", function () {
        const selected = selector.value || "";
        const currentCoach = selector.dataset.currentCoach || "";

        const params = new URLSearchParams(window.location.search);

        /*
          Important:
          The logged-in user's own invoice list is the DEFAULT view.
          So if the dropdown is blank OR current coach, remove ?coach= entirely.
        */
        if (!selected || selected === currentCoach) {
          params.delete("coach");
        } else {
          params.set("coach", selected);
        }

        window.location.href = window.location.pathname + (params.toString() ? `?${params.toString()}` : "");
      });
    }

    ["invoiceSearch", "invoiceFromDate", "invoiceToDate", "invoiceStatusFilter"].forEach((id) => {
      const field = el(id);
      if (!field) return;
      field.addEventListener(id === "invoiceSearch" ? "input" : "change", renderFilters);
    });

    el("refreshInvoices")?.addEventListener("click", function () {
      const params = new URLSearchParams(window.location.search);
      params.set("_refresh", Date.now());
    
      window.location.href = window.location.pathname + "?" + params.toString();
    });

    el("addInvoice")?.addEventListener("click", function () {
      window.location.href = `${getDashboardBasePath()}/invoice_details?new=1`;
    });

    initCoachSelector();
    initRowNavigation();
    updateInvoiceCount();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initInvoicesPage);
  } else {
    initInvoicesPage();
  }
})();
