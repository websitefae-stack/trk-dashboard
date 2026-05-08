(function () {
  "use strict";

  const SHARED_API = "dashboard.api.shared.dashboard";

  function el(id) {
    return document.getElementById(id);
  }

  function getDashboardType() {
    const path = window.location.pathname || "";

    if (path.indexOf("/coach_db") !== -1) return "coach";
    if (path.indexOf("/franchisor_db") !== -1) return "franchisor";

    return "session_worker";
  }

  function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta && meta.content ? meta.content : "";
  }

  async function apiGet(method, args) {
    const params = new URLSearchParams(args || {});
    const url = "/api/method/" + method + (params.toString() ? "?" + params.toString() : "");

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
    const response = await fetch("/api/method/" + method, {
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

  function setHref(id, value) {
    const node = el(id);
    if (!node || !value) return;
    node.href = value;
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
    return (number % 1 === 0 ? number.toFixed(0) : number.toFixed(2)) + " miles";
  }

  function formatCurrency(value, currency) {
    const number = Number(value || 0);
    const code = currency || "GBP";

    try {
      return new Intl.NumberFormat("en-GB", {
        style: "currency",
        currency: code
      }).format(number);
    } catch (error) {
      return "£" + number.toFixed(2);
    }
  }

  function formatDisplayDate(value) {
    if (!value) return "";

    const text = String(value).trim();

    const ukMatch = text.match(/^(\d{2})-(\d{2})-(\d{4})(?:\s+(\d{2}):(\d{2}))?/);
    if (ukMatch) {
      const day = Number(ukMatch[1]);
      const month = Number(ukMatch[2]) - 1;
      const year = Number(ukMatch[3]);
      const date = new Date(year, month, day);

      return date.toLocaleDateString("en-GB", {
        day: "numeric",
        month: "long",
        year: "numeric"
      });
    }

    const isoMatch = text.match(/^(\d{4})-(\d{2})-(\d{2})/);
    if (isoMatch) {
      const year = Number(isoMatch[1]);
      const month = Number(isoMatch[2]) - 1;
      const day = Number(isoMatch[3]);
      const date = new Date(year, month, day);

      return date.toLocaleDateString("en-GB", {
        day: "numeric",
        month: "long",
        year: "numeric"
      });
    }

    const date = new Date(text);

    if (Number.isNaN(date.getTime())) {
      return text;
    }

    return date.toLocaleDateString("en-GB", {
      day: "numeric",
      month: "long",
      year: "numeric"
    });
  }

  function todayDateKey() {
    const date = new Date();
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");
    return date.getFullYear() + "-" + month + "-" + day;
  }

  function renderSessionWorkerAppointments(items) {
    const tbody = el("swDashboardUpcomingTableBody");
    if (!tbody) return;

    if (!items || !items.length) {
      tbody.innerHTML = `
        <tr>
          <td colspan="4" class="dashboard-empty">No upcoming appointments found.</td>
        </tr>
      `;
      return;
    }

    tbody.innerHTML = items.map(function (item) {
      const dateText = formatDisplayDate(item.date);
      const timeText = item.time || "";
      const detailsText = item.appointment_name || item.appointment_details || item.details || "Appointment";

      return `
        <tr>
          <td class="dashboard-upcoming-date-cell">
            <div class="dashboard-table-date">${escapeHtml(dateText)}</div>
            <div class="dashboard-table-time">${escapeHtml(timeText)}</div>
          </td>
          <td>${escapeHtml(detailsText)}</td>
          <td>${escapeHtml(item.location || "—")}</td>
          <td class="dashboard-text-right">
            <a class="dashboard-link-btn" href="${escapeHtml(item.detail_link || item.record_url || "#")}">View</a>
          </td>
        </tr>
      `;
    }).join("");
  }

  function renderMainDashboardAppointments(items, calendarUrl) {
    const tbody = el("dashboardUpcomingTableBody");
    if (!tbody) return;

    if (!items || !items.length) {
      tbody.innerHTML = `
        <tr>
          <td colspan="4" class="dashboard-empty">No upcoming appointments found.</td>
        </tr>
      `;
      return;
    }

    tbody.innerHTML = items.map(function (item) {
      return `
        <tr>
          <td>
            <div class="dashboard-table-date">${escapeHtml(formatDisplayDate(item.date))}</div>
            <div class="dashboard-table-time">${escapeHtml(item.time || "")}</div>
          </td>
          <td>${escapeHtml(item.appointment_name || "Appointment")}</td>
          <td>${escapeHtml(item.location || "—")}</td>
          <td class="dashboard-text-right">
            <a class="dashboard-link-btn" href="${escapeHtml(item.detail_link || calendarUrl || "#")}">View</a>
          </td>
        </tr>
      `;
    }).join("");
  }

  function renderOutstandingInvoices(items, invoicesUrl) {
    const tbody = el("dashboardOutstandingInvoicesTableBody");
    if (!tbody) return;

    if (!items || !items.length) {
      tbody.innerHTML = `
        <tr>
          <td colspan="7" class="dashboard-empty">No outstanding invoices found.</td>
        </tr>
      `;
      return;
    }

    tbody.innerHTML = items.map(function (invoice) {
      const currency = invoice.currency || "GBP";

      return `
        <tr data-invoice-row="${escapeHtml(invoice.name)}">
          <td>
            <strong>${escapeHtml(invoice.name)}</strong>
            <div class="dashboard-client-sub">${escapeHtml(invoice.client_name || "—")}</div>
          </td>
          <td>${escapeHtml(formatDisplayDate(invoice.posting_date))}</td>
          <td>${escapeHtml(formatDisplayDate(invoice.due_date))}</td>
          <td>${escapeHtml(invoice.status || "—")}</td>
          <td>${escapeHtml(formatCurrency(invoice.grand_total || 0, currency))}</td>
          <td>${escapeHtml(formatCurrency(invoice.outstanding_amount || 0, currency))}</td>
          <td class="dashboard-text-right">
            <div class="dashboard-inline-action">
              <input
                type="date"
                class="dashboard-input dashboard-payment-date-input"
                data-payment-date="${escapeHtml(invoice.name)}"
                value="${escapeHtml(todayDateKey())}"
                aria-label="Payment date for ${escapeHtml(invoice.name)}"
              >
              <button
                type="button"
                class="dashboard-link-btn"
                data-mark-paid="${escapeHtml(invoice.name)}"
              >
                Mark paid
              </button>
            </div>
          </td>
        </tr>
      `;
    }).join("");

    setHref("dashboardViewAllInvoicesBtn", invoicesUrl);
  }

  function bindInvoiceActions(dashboardType) {
    document.addEventListener("click", async function (event) {
      const button = event.target.closest("[data-mark-paid]");
      if (!button) return;

      event.preventDefault();

      const invoice = button.dataset.markPaid || "";
      const dateInput = document.querySelector('[data-payment-date="' + CSS.escape(invoice) + '"]');
      const paymentDate = dateInput ? dateInput.value : todayDateKey();

      if (!invoice) return;

      button.disabled = true;
      button.textContent = "Saving...";

      try {
        await apiPost(SHARED_API + ".mark_invoice_paid", {
          dashboard_type: dashboardType,
          invoice: invoice,
          payment_date: paymentDate
        });

        await loadDashboard();
      } catch (error) {
        console.error("Mark invoice paid failed:", error);
        button.disabled = false;
        button.textContent = "Mark paid";
        alert(error.message || "Could not mark invoice as paid.");
      }
    });
  }

  function renderSessionWorkerSummary(payload) {
    const previousLabel = payload.previous_label || "Previous";
    const currentLabel = payload.current_label || "Current";

    setText("swOneToOnePreviousLabel", "1 on 1 Sessions " + previousLabel);
    setText("swOneToOneCurrentLabel", "1 on 1 Sessions " + currentLabel);
    setText("swGroupPreviousLabel", "Group Sessions " + previousLabel);
    setText("swGroupCurrentLabel", "Group Sessions " + currentLabel);
    setText("swWorkshopPreviousLabel", "Workshops " + previousLabel);
    setText("swWorkshopCurrentLabel", "Workshops " + currentLabel);
    setText("swTravelPreviousLabel", "Distance Travelled " + previousLabel);
    setText("swTravelCurrentLabel", "Distance Travelled " + currentLabel);

    setText("swOneToOnePreviousValue", payload.one_to_one_previous ?? 0);
    setText("swOneToOneCurrentValue", payload.one_to_one_current ?? 0);
    setText("swGroupPreviousValue", payload.group_previous ?? 0);
    setText("swGroupCurrentValue", payload.group_current ?? 0);
    setText("swWorkshopPreviousValue", payload.workshop_previous ?? 0);
    setText("swWorkshopCurrentValue", payload.workshop_current ?? 0);
    setText("swTravelPreviousValue", formatMiles(payload.travel_miles_previous ?? 0));
    setText("swTravelCurrentValue", formatMiles(payload.travel_miles_current ?? 0));

    renderSessionWorkerAppointments(payload.upcoming_appointments || []);
  }

  function renderCoachFranchisorSummary(payload) {
    const currentLabel = payload.current_label || "This month";
    const previousLabel = payload.previous_label || "Last month";

    setText("dashboardTotalClientsValue", payload.total_clients ?? 0);
    setText("dashboardNewClientsCurrentValue", payload.new_clients_current_month ?? 0);
    setText("dashboardNewClientsPreviousValue", payload.new_clients_previous_month ?? 0);

    setText("dashboardNewClientsCurrentLabel", "New Clients " + currentLabel);
    setText("dashboardNewClientsPreviousLabel", "New Clients " + previousLabel);

    setText("dashboardInvoiceCurrentLabel", "Monthly Invoice Total " + currentLabel);
    setText("dashboardInvoicePreviousLabel", "Monthly Invoice Total " + previousLabel);

    setText("dashboardInvoiceCurrentValue", formatCurrency(payload.monthly_invoice_total_current || 0, "GBP"));
    setText("dashboardInvoicePreviousValue", formatCurrency(payload.monthly_invoice_total_previous || 0, "GBP"));

    setText("dashboardSessionWorkersValue", payload.total_session_workers ?? 0);
    setText("dashboardCoachesValue", payload.total_coaches ?? 0);

    setHref("dashboardClientsCardLink", payload.clients_url);
    setHref("dashboardSessionWorkersCardLink", payload.session_workers_url);
    setHref("dashboardCoachesCardLink", payload.coaches_url);
    setHref("dashboardViewCalendarBtn", payload.calendar_url);
    setHref("dashboardViewAllInvoicesBtn", payload.invoices_url);

    renderMainDashboardAppointments(payload.upcoming_appointments || [], payload.calendar_url);
    renderOutstandingInvoices(payload.outstanding_invoices || [], payload.invoices_url);
  }

  async function loadDashboard() {
    const root =
      el("sessionWorkerDashboardHome") ||
      el("coachDashboardHome") ||
      el("franchisorDashboardHome");

    if (!root) return;

    const dashboardType = getDashboardType();

    const payload = await apiGet(SHARED_API + ".get_dashboard_summary", {
      dashboard_type: dashboardType
    });

    if (dashboardType === "session_worker") {
      renderSessionWorkerSummary(payload);
      return;
    }

    renderCoachFranchisorSummary(payload);
  }

  function bindRefresh() {
    const button = el("refreshDashboard");
    if (!button) return;

    button.addEventListener("click", async function () {
      button.disabled = true;
      button.textContent = "Refreshing...";

      try {
        await loadDashboard();
      } catch (error) {
        console.error("Dashboard refresh failed:", error);
        alert(error.message || "Could not refresh dashboard.");
      }

      button.disabled = false;
      button.textContent = "Refresh";
    });
  }

  async function init() {
    const root =
      el("sessionWorkerDashboardHome") ||
      el("coachDashboardHome") ||
      el("franchisorDashboardHome");

    if (!root) return;

    bindRefresh();
    bindInvoiceActions(getDashboardType());

    try {
      await loadDashboard();
    } catch (error) {
      console.error("Could not load dashboard", error);

      const swBody = el("swDashboardUpcomingTableBody");
      if (swBody) {
        swBody.innerHTML = `
          <tr>
            <td colspan="4" class="dashboard-empty">${escapeHtml(error.message || "Could not load dashboard.")}</td>
          </tr>
        `;
      }

      const mainBody = el("dashboardUpcomingTableBody");
      if (mainBody) {
        mainBody.innerHTML = `
          <tr>
            <td colspan="4" class="dashboard-empty">${escapeHtml(error.message || "Could not load dashboard.")}</td>
          </tr>
        `;
      }

      const invoiceBody = el("dashboardOutstandingInvoicesTableBody");
      if (invoiceBody) {
        invoiceBody.innerHTML = `
          <tr>
            <td colspan="7" class="dashboard-empty">${escapeHtml(error.message || "Could not load invoices.")}</td>
          </tr>
        `;
      }
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
