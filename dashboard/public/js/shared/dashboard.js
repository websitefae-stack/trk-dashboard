(function () {
  "use strict";

  const SHARED_API = "dashboard.api.shared.dashboard";

  var el = Dashboard.el;

  function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta && meta.content ? meta.content : "";
  }

  function getDashboardType() {
    const path = window.location.pathname || "";
    if (path.startsWith("/coach_db")) return "coach";
    if (path.startsWith("/franchisor_db")) return "franchisor";
    return "session_worker";
  }

  async function apiGet(method, args) {
    const params = new URLSearchParams(args || {});
    const response = await fetch(`/api/method/${method}?${params.toString()}`, {
      method: "GET",
      credentials: "same-origin"
    });

    const data = await response.json();

    if (!response.ok || data.exc) {
      throw new Error(data.message || "There was a problem loading the dashboard.");
    }

    return data.message || {};
  }

  async function apiPost(method, args) {
    const response = await fetch(`/api/method/${method}`, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-Frappe-CSRF-Token": getCsrfToken()
      },
      body: JSON.stringify(args || {})
    });

    const data = await response.json();

    if (!response.ok || data.exc) {
      throw new Error(data.message || "There was a problem saving.");
    }

    return data.message || {};
  }

  function setText(id, value) {
    const node = el(id);
    if (node) node.textContent = value ?? "";
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function formatMoney(value, currency) {
    const number = Number(value || 0);
    try {
      return new Intl.NumberFormat("en-GB", {
        style: "currency",
        currency: currency || "GBP"
      }).format(number);
    } catch {
      return `£${number.toFixed(2)}`;
    }
  }

  function flt2(value) {
    return (Number(value || 0)).toFixed(2);
  }

  function formatMiles(value) {
    const number = Number(value || 0);
    return `${number % 1 === 0 ? number.toFixed(0) : number.toFixed(2)} miles`;
  }

  function formatDisplayDate(value) {
    if (!value) return "";

    const text = String(value).trim();
    const uk = text.match(/^(\d{2})-(\d{2})-(\d{4})$/);

    if (uk) {
      return `${uk[1]}/${uk[2]}/${uk[3]}`;
    }

    const date = new Date(text);
    if (Number.isNaN(date.getTime())) return text;

    return date.toLocaleDateString("en-GB", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric"
    });
  }

  function todayIso() {
    return new Date().toISOString().slice(0, 10);
  }

  function renderUpcomingAppointments(tableBodyId, items) {
    const tbody = el(tableBodyId);
    if (!tbody) return;

    if (!items || !items.length) {
      tbody.innerHTML = `
        <tr>
          <td colspan="4" class="dashboard-empty">No upcoming appointments found.</td>
        </tr>
      `;
      return;
    }

    tbody.innerHTML = items.map((item) => {
      const link = item.detail_link || "#";
      const dateText = formatDisplayDate(item.date);
      const timeText = item.time || "";
      const title = item.appointment_name || "Appointment";

      return `
        <tr>
          <td class="dashboard-home-date-col">
            <a class="dashboard-table-link" href="${escapeHtml(link)}">${escapeHtml(dateText)}</a>
            <div class="dashboard-table-time">${escapeHtml(timeText)}</div>
          </td>
          <td class="dashboard-home-details-col">${escapeHtml(title)}</td>
          <td class="dashboard-home-location-col">${escapeHtml(item.location || "—")}</td>
          <td class="dashboard-text-right dashboard-home-action-col">
            <a class="dashboard-link-btn" href="${escapeHtml(link)}">View</a>
          </td>
        </tr>
      `;
    }).join("");
  }

  function renderOutstandingInvoices(items) {
    const tbody = el("dashboardOutstandingInvoicesTableBody");
    if (!tbody) return;

    if (!items || !items.length) {
      tbody.innerHTML = `
        <tr>
          <td colspan="8" class="dashboard-empty">No outstanding invoices found.</td>
        </tr>
      `;
      return;
    }

    tbody.innerHTML = items.map((item) => {
      return `
        <tr>
          <td class="dashboard-home-invoice-number-col">
            <a class="dashboard-table-link" href="${escapeHtml(item.invoice_url || "#")}">
              ${escapeHtml(item.name || "")}
            </a>
          </td>
          <td>${escapeHtml(formatDisplayDate(item.posting_date))}</td>
          <td>${escapeHtml(item.client_name || "")}</td>
          <td>${escapeHtml(item.status || "")}</td>
          <td>${escapeHtml(formatMoney(item.outstanding_amount, item.currency))}</td>
          <td>
            <input
              type="number"
              step="0.01"
              min="0"
              class="dashboard-home-payment-amount"
              value="${escapeHtml(flt2(item.outstanding_amount))}"
              data-payment-amount-for="${escapeHtml(item.name || "")}"
            >
          </td>
          <td>
            <input
              type="date"
              class="dashboard-home-payment-date"
              value="${todayIso()}"
              data-payment-date-for="${escapeHtml(item.name || "")}"
            >
          </td>
          <td class="dashboard-text-right">
            <button
              type="button"
              class="dashboard-link-btn"
              data-dashboard-pay-invoice="${escapeHtml(item.name || "")}"
              data-dashboard-pay-outstanding="${escapeHtml(flt2(item.outstanding_amount))}"
            >
              Mark Paid
            </button>
          </td>
        </tr>
      `;
    }).join("");
  }

  function renderOutstandingInternalInvoices(items, dashboardType) {
    const tbody = el("dashboardOutstandingInternalInvoicesTableBody");
    if (!tbody) return;

    const showCoachColumn = dashboardType === "franchisor";
    const colspan = showCoachColumn ? 7 : 6;

    if (!items || !items.length) {
      tbody.innerHTML = `
        <tr>
          <td colspan="${colspan}" class="dashboard-empty">No outstanding internal invoices found.</td>
        </tr>
      `;
      return;
    }

    tbody.innerHTML = items.map((item) => {
      return `
        <tr>
          <td class="dashboard-home-invoice-number-col">
            <a class="dashboard-table-link" href="${escapeHtml(item.invoice_url || "#")}">
              ${escapeHtml(item.name || "")}
            </a>
          </td>
          ${showCoachColumn ? `<td>${escapeHtml(item.coach_label || "")}</td>` : ""}
          <td>${escapeHtml(formatDisplayDate(item.posting_date))}</td>
          <td>${escapeHtml(formatDisplayDate(item.due_date))}</td>
          <td>${escapeHtml(item.status || "")}</td>
          <td>${escapeHtml(formatMoney(item.outstanding_amount, item.currency))}</td>
          <td class="dashboard-text-right">
            <a class="dashboard-link-btn" href="${escapeHtml(item.invoice_url || "#")}">View</a>
          </td>
        </tr>
      `;
    }).join("");
  }

  async function handlePayInvoice(button) {
    const invoice = button.dataset.dashboardPayInvoice || "";
    if (!invoice) return;

    const dateInput = document.querySelector(`[data-payment-date-for="${CSS.escape(invoice)}"]`);
    const paymentDate = dateInput ? dateInput.value : todayIso();

    if (!paymentDate) {
      alert("Please enter the payment date.");
      return;
    }

    const amountInput = document.querySelector(`[data-payment-amount-for="${CSS.escape(invoice)}"]`);
    const outstanding = Number(button.dataset.dashboardPayOutstanding || 0);
    const amountPaid = amountInput && amountInput.value !== "" ? Number(amountInput.value) : outstanding;

    if (!amountPaid || amountPaid <= 0) {
      alert("Please enter the amount paid.");
      return;
    }

    if (amountPaid > outstanding) {
      alert("Amount paid cannot be greater than the outstanding amount.");
      return;
    }

    const isPartial = amountPaid < outstanding;

    const confirmed = window.confirm(
      isPartial
        ? `Record a partial payment of ${formatMoney(amountPaid)} for invoice ${invoice}?`
        : `Are you sure you want to mark invoice ${invoice} as paid in full?`
    );

    if (!confirmed) {
      return;
    }

    button.disabled = true;
    button.textContent = "Saving...";

    try {
      await apiPost(SHARED_API + ".mark_invoice_paid", {
        dashboard_type: getDashboardType(),
        invoice: invoice,
        payment_date: paymentDate,
        amount_paid: amountPaid
      });

      await loadDashboardSummary();
    } catch (error) {
      console.error("Could not mark invoice paid", error);
      alert(error.message || "Could not mark invoice as paid.");
      button.disabled = false;
      button.textContent = "Mark Paid";
    }
  }

  function bindInvoicePaymentButtons() {
    document.addEventListener("click", function (event) {
      const button = event.target.closest("[data-dashboard-pay-invoice]");
      if (!button) return;

      event.preventDefault();
      handlePayInvoice(button);
    });
  }

  function renderSessionWorkerDashboard(payload) {
    const previousLabel = payload.previous_label || "Previous";
    const currentLabel = payload.current_label || "Current";

    setText("swOneToOnePreviousLabel", `1 on 1 Sessions ${previousLabel}`);
    setText("swOneToOneCurrentLabel", `1 on 1 Sessions ${currentLabel}`);
    setText("swGroupPreviousLabel", `Group Sessions ${previousLabel}`);
    setText("swGroupCurrentLabel", `Group Sessions ${currentLabel}`);
    setText("swWorkshopPreviousLabel", `Workshops ${previousLabel}`);
    setText("swWorkshopCurrentLabel", `Workshops ${currentLabel}`);
    setText("swTravelPreviousLabel", `Distance Travelled ${previousLabel}`);
    setText("swTravelCurrentLabel", `Distance Travelled ${currentLabel}`);

    setText("swOneToOnePreviousValue", payload.one_to_one_previous ?? 0);
    setText("swOneToOneCurrentValue", payload.one_to_one_current ?? 0);
    setText("swGroupPreviousValue", payload.group_previous ?? 0);
    setText("swGroupCurrentValue", payload.group_current ?? 0);
    setText("swWorkshopPreviousValue", payload.workshop_previous ?? 0);
    setText("swWorkshopCurrentValue", payload.workshop_current ?? 0);
    setText("swTravelPreviousValue", formatMiles(payload.travel_miles_previous ?? 0));
    setText("swTravelCurrentValue", formatMiles(payload.travel_miles_current ?? 0));

    renderUpcomingAppointments("swDashboardUpcomingTableBody", payload.upcoming_appointments || []);
  }

  function renderCoachFranchisorDashboard(payload) {
    setText("dashboardTotalClients", payload.total_clients ?? 0);
    setText("dashboardTotalSessionWorkers", payload.total_session_workers ?? 0);
    setText("dashboardTotalCoaches", payload.total_coaches ?? 0);
    setText("dashboardYearToDateIncome", formatMoney(payload.year_to_date_income || 0, "GBP"));

    setText("dashboardNewClientsPrevious", payload.new_clients_previous_month ?? 0);
    setText("dashboardNewClientsCurrent", payload.new_clients_current_month ?? 0);

    setText("dashboardPreviousMonthLabel", `New Clients ${payload.previous_label || "Last Month"}`);
    setText("dashboardCurrentMonthLabel", `New Clients ${payload.current_label || "This Month"}`);

    setText("dashboardRevenuePreviousLabel", payload.previous_label || "Last Month");
    setText("dashboardRevenueCurrentLabel", payload.current_label || "This Month");

    setText("dashboardRevenuePreviousTotal", formatMoney(payload.revenue_total_previous || 0, "GBP"));
    setText("dashboardRevenueCurrentTotal", formatMoney(payload.revenue_total_current || 0, "GBP"));

    setText("dashboardRevenuePreviousClient", formatMoney(payload.revenue_client_previous || 0, "GBP"));
    setText("dashboardRevenueCurrentClient", formatMoney(payload.revenue_client_current || 0, "GBP"));

    setText("dashboardRevenuePreviousTravel", formatMoney(payload.revenue_travel_previous || 0, "GBP"));
    setText("dashboardRevenueCurrentTravel", formatMoney(payload.revenue_travel_current || 0, "GBP"));

    setText("dashboardRevenuePreviousInterbusiness", formatMoney(payload.revenue_interbusiness_previous || 0, "GBP"));
    setText("dashboardRevenueCurrentInterbusiness", formatMoney(payload.revenue_interbusiness_current || 0, "GBP"));

    renderUpcomingAppointments("dashboardUpcomingTableBody", payload.upcoming_appointments || []);
    renderOutstandingInvoices(payload.outstanding_invoices || []);
    renderOutstandingInternalInvoices(payload.outstanding_internal_invoices || [], payload.dashboard_type);
  }

  async function loadDashboardSummary() {
    const dashboardType = getDashboardType();
    const params = new URLSearchParams(window.location.search);

    const payload = await apiGet(SHARED_API + ".get_dashboard_summary", {
      dashboard_type: dashboardType,
      view_as: params.get("view_as") || "",
      viewer: params.get("viewer") || "",
      cache_bust: Date.now()
    });

    if (dashboardType === "session_worker") {
      renderSessionWorkerDashboard(payload);
    } else {
      renderCoachFranchisorDashboard(payload);
    }
  }

  function bindRefresh() {
    const button = el("refreshDashboard");
    if (!button) return;

    button.addEventListener("click", async function () {
      button.disabled = true;
      button.textContent = "Refreshing...";

      try {
        await loadDashboardSummary();
      } finally {
        button.disabled = false;
        button.textContent = "Refresh";
      }
    });
  }

  function init() {
    if (
      !el("sessionWorkerDashboardHome") &&
      !el("coachDashboardHome") &&
      !el("franchisorDashboardHome")
    ) {
      return;
    }

    bindRefresh();
    bindInvoicePaymentButtons();
    loadDashboardSummary();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
