(function () {
  "use strict";

  const SHARED_API = "dashboard.api.shared.dashboard";

  function el(id) {
    return document.getElementById(id);
  }

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
    const url = `/api/method/${method}${params.toString() ? `?${params.toString()}` : ""}`;

    const response = await fetch(url, {
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

  function setText(id, value, fallback) {
    const node = el(id);
    if (!node) return;
    node.textContent = value ?? fallback ?? "";
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function formatMiles(value) {
    const number = Number(value || 0);
    return `${number % 1 === 0 ? number.toFixed(0) : number.toFixed(2)} miles`;
  }

  function formatMoney(value, currency) {
    const number = Number(value || 0);
    const code = currency || "GBP";

    try {
      return new Intl.NumberFormat("en-GB", {
        style: "currency",
        currency: code
      }).format(number);
    } catch (error) {
      return `£${number.toFixed(2)}`;
    }
  }

  function formatDisplayDate(value) {
    if (!value) return "";

    const text = String(value).trim();

    const date = new Date(text);
    if (Number.isNaN(date.getTime())) return text;

    return date.toLocaleDateString("en-GB", {
      day: "numeric",
      month: "long",
      year: "numeric"
    });
  }

  function renderUpcomingAppointments(tableBodyId, items, emptyColspan) {
    const tbody = el(tableBodyId);
    if (!tbody) return;

    if (!items || !items.length) {
      tbody.innerHTML = `
        <tr>
          <td colspan="${emptyColspan}" class="dashboard-empty">No upcoming appointments found.</td>
        </tr>
      `;
      return;
    }

    tbody.innerHTML = items.map((item) => {
      const detailLink = item.detail_link || "#";
      const dateText = item.display_date || formatDisplayDate(item.date);
      const timeText = item.time || "";
      const detailsText = item.appointment_name || "Appointment";

      return `
        <tr>
          <td class="dashboard-home-date-col">
            <a class="dashboard-link-btn dashboard-home-date-link" href="${escapeHtml(detailLink)}">
              ${escapeHtml(dateText)}
            </a>
            <div class="dashboard-table-time">${escapeHtml(timeText)}</div>
          </td>
          <td class="dashboard-home-details-col">${escapeHtml(detailsText)}</td>
          <td class="dashboard-home-location-col">${escapeHtml(item.location || "—")}</td>
          <td class="dashboard-text-right dashboard-home-action-col">
            <a class="dashboard-link-btn" href="${escapeHtml(detailLink)}">View</a>
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
          <td colspan="6" class="dashboard-empty">No outstanding invoices found.</td>
        </tr>
      `;
      return;
    }

    tbody.innerHTML = items.map((item) => {
      return `
        <tr>
          <td>${escapeHtml(item.name || "")}</td>
          <td>${escapeHtml(item.client_name || "")}</td>
          <td>${escapeHtml(formatDisplayDate(item.due_date || item.posting_date))}</td>
          <td>${escapeHtml(item.status || "")}</td>
          <td>${escapeHtml(formatMoney(item.outstanding_amount, item.currency))}</td>
          <td class="dashboard-text-right">
            <button
              type="button"
              class="dashboard-link-btn"
              data-dashboard-pay-invoice="${escapeHtml(item.name || "")}"
              data-dashboard-pay-outstanding="${escapeHtml(item.outstanding_amount || 0)}"
            >
              Mark Paid
            </button>
          </td>
        </tr>
      `;
    }).join("");
  }

  async function handlePayInvoice(button) {
    const invoiceName = button.dataset.dashboardPayInvoice || "";
    const outstanding = Number(button.dataset.dashboardPayOutstanding || 0);

    if (!invoiceName) return;

    const amount = window.prompt("Amount received", outstanding ? outstanding.toFixed(2) : "");
    if (amount === null) return;

    const paymentDate = window.prompt("Payment date YYYY-MM-DD", new Date().toISOString().slice(0, 10));
    if (paymentDate === null) return;

    button.disabled = true;
    button.textContent = "Saving...";

    try {
      await apiPost(SHARED_API + ".mark_invoice_paid", {
        dashboard_type: getDashboardType(),
        invoice_name: invoiceName,
        amount_received: amount,
        payment_date: paymentDate
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

    renderUpcomingAppointments("swDashboardUpcomingTableBody", payload.upcoming_appointments || [], 4);
  }

  function renderCoachFranchisorDashboard(payload) {
    setText("dashboardTotalClients", payload.total_clients ?? 0);
    setText("dashboardNewClientsPrevious", payload.new_clients_previous_month ?? 0);
    setText("dashboardNewClientsCurrent", payload.new_clients_current_month ?? 0);

    setText("dashboardPreviousMonthLabel", `New Clients ${payload.previous_month_label || "Last Month"}`);
    setText("dashboardCurrentMonthLabel", `New Clients ${payload.current_month_label || "This Month"}`);

    setText("dashboardInvoicePreviousLabel", `Invoice Total ${payload.previous_month_label || "Last Month"}`);
    setText("dashboardInvoiceCurrentLabel", `Invoice Total ${payload.current_month_label || "This Month"}`);

    setText("dashboardInvoicePreviousValue", formatMoney(payload.monthly_invoice_total_previous || 0, "GBP"));
    setText("dashboardInvoiceCurrentValue", formatMoney(payload.monthly_invoice_total_current || 0, "GBP"));

    setText("dashboardTotalSessionWorkers", payload.total_session_workers ?? 0);
    setText("dashboardTotalCoaches", payload.total_coaches ?? 0);

    renderUpcomingAppointments("dashboardUpcomingTableBody", payload.upcoming_appointments || [], 4);
    renderOutstandingInvoices(payload.outstanding_invoices || []);
  }

  async function loadDashboardSummary() {
    const dashboardType = getDashboardType();

    const payload = await apiGet(SHARED_API + ".get_dashboard_summary", {
      dashboard_type: dashboardType
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

    button.addEventListener("click", function () {
      loadDashboardSummary();
    });
  }

  async function init() {
    if (
      !el("sessionWorkerDashboardHome") &&
      !el("coachDashboardHome") &&
      !el("franchisorDashboardHome")
    ) {
      return;
    }

    bindRefresh();
    bindInvoicePaymentButtons();

    try {
      await loadDashboardSummary();
    } catch (error) {
      console.error("Could not load dashboard summary", error);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
