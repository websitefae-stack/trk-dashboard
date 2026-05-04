(function () {
  function el(id) {
    return document.getElementById(id);
  }

  function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta && meta.content ? meta.content : "";
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

    return data;
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
      throw new Error(data.message || "There was a problem loading notifications.");
    }

    return data;
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

  function renderUpcomingAppointments(items) {
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

    tbody.innerHTML = items.map((item) => {
      const dateText = formatDisplayDate(item.date);
      const timeText = item.time || "";
      const detailsText = item.appointment_name || item.appointment_details || item.details || "Appointment";

      return `
        <tr>
          <td>
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

  function renderLatestNotifications(summary) {
    const tbody = el("swDashboardNotificationsTableBody");
    const countNode = el("swDashboardNotificationCount");

    if (!tbody) return;

    const latest = summary.latest || [];
    const unreadCount = summary.unread_count || 0;

    if (countNode) {
      countNode.textContent = `${unreadCount} unread`;
    }

    if (!latest.length) {
      tbody.innerHTML = `
        <tr>
          <td colspan="5" class="dashboard-empty">No notifications found.</td>
        </tr>
      `;
      return;
    }

    tbody.innerHTML = latest.map((notification) => {
      return `
        <tr>
          <td>
            <div class="dashboard-table-date">${escapeHtml(formatDisplayDate(notification.notification_date || notification.creation || ""))}</div>
          </td>
          <td>${escapeHtml(notification.notification_type || "Notification")}</td>
          <td>${escapeHtml(notification.status || "Unread")}</td>
          <td>${escapeHtml(notification.priority || "Normal")}</td>
          <td class="dashboard-text-right">
            <a class="dashboard-link-btn" href="/session_worker_db/notification_details?name=${encodeURIComponent(notification.name)}">View</a>
          </td>
        </tr>
      `;
    }).join("");
  }

  async function loadDashboardSummary() {
    const result = await apiGet("dashboard.api.session_worker.dashboard.get_dashboard_summary");
    const payload = result.message || {};

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

    renderUpcomingAppointments(payload.upcoming_appointments || []);
  }

  async function loadDashboardNotifications() {
    const result = await apiPost(
      "dashboard.api.session_worker.notifications.get_dashboard_notification_summary",
      {}
    );

    renderLatestNotifications(result.message || {});
  }

  async function init() {
    if (!el("sessionWorkerDashboardHome")) return;

    const refreshButton = el("refreshDashboard");
    if (refreshButton) {
      refreshButton.addEventListener("click", function () {
        window.location.reload();
      });
    }

    try {
      await loadDashboardSummary();
    } catch (error) {
      console.error("Could not load dashboard summary", error);

      const tbody = el("swDashboardUpcomingTableBody");
      if (tbody) {
        tbody.innerHTML = `
          <tr>
            <td colspan="4" class="dashboard-empty">${escapeHtml(error.message || "Could not load dashboard.")}</td>
          </tr>
        `;
      }
    }

    try {
      await loadDashboardNotifications();
    } catch (error) {
      console.error("Could not load dashboard notifications", error);

      const tbody = el("swDashboardNotificationsTableBody");
      if (tbody) {
        tbody.innerHTML = `
          <tr>
            <td colspan="5" class="dashboard-empty">Could not load notifications.</td>
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
