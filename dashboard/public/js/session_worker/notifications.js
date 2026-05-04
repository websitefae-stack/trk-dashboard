(function () {
  const API_PREFIX = "dashboard.api.session_worker.notifications";

  function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta && meta.content ? meta.content : "";
  }

  async function callApi(method, payload) {
    const response = await fetch("/api/method/" + API_PREFIX + "." + method, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-Frappe-CSRF-Token": getCsrfToken()
      },
      body: JSON.stringify(payload || {})
    });

    const data = await response.json();

    if (!response.ok || data.exc) {
      throw new Error(data.message || "Request failed.");
    }

    return data.message || data;
  }

  function applyFilters() {
    const searchInput = document.getElementById("notificationSearch");
    const statusFilter = document.getElementById("notificationStatusFilter");
    const rows = document.querySelectorAll(".dashboard-notification-row");
    const countEl = document.getElementById("notificationCount");

    const search = searchInput ? searchInput.value.toLowerCase().trim() : "";
    const status = statusFilter ? statusFilter.value : "All";

    let visibleCount = 0;

    rows.forEach(function (row) {
      const rowSearch = row.getAttribute("data-search") || "";
      const rowStatus = row.getAttribute("data-status") || "";
      const visible = (!search || rowSearch.includes(search)) && (status === "All" || rowStatus === status);

      row.style.display = visible ? "" : "none";
      if (visible) visibleCount += 1;
    });

    if (countEl) countEl.textContent = visibleCount + " notifications";
  }

  async function loadRecipients() {
    const select = document.getElementById("sendNotificationRecipients");
    if (!select) return;

    select.innerHTML = '<option value="">Loading...</option>';

    try {
      const recipients = await callApi("get_notification_recipients", {});
      select.innerHTML = '<option value="">Select recipient</option>';

      recipients.forEach(function (row) {
        const option = document.createElement("option");
        option.value = row.recipient_user;
        option.textContent = row.label + " (" + row.recipient_type + ")";
        select.appendChild(option);
      });
    } catch (error) {
      select.innerHTML = '<option value="">Could not load recipients</option>';
    }
  }

  function openSendPanel() {
    const panel = document.getElementById("sendNotificationPanel");
    if (panel) panel.style.display = "";
    loadRecipients();
  }

  function closeSendPanel() {
    const panel = document.getElementById("sendNotificationPanel");
    const form = document.getElementById("sendNotificationForm");

    if (panel) panel.style.display = "none";
    if (form) form.reset();
  }

  async function sendNotification(event) {
    event.preventDefault();

    const form = document.getElementById("sendNotificationForm");
    const messageEl = document.getElementById("sendNotificationMessage");

    if (!form) return;

    const formData = new FormData(form);
    const recipient = formData.get("recipient_user");

    if (messageEl) messageEl.textContent = "Sending...";

    try {
      const result = await callApi("send_dashboard_notification", {
        recipient_users: [recipient],
        notification_type: formData.get("notification_type"),
        priority: formData.get("priority"),
        message: formData.get("message")
      });

      if (messageEl) messageEl.textContent = result.message || "Notification sent.";

      setTimeout(function () {
        window.location.reload();
      }, 700);
    } catch (error) {
      if (messageEl) messageEl.textContent = error.message || "Could not send notification.";
    }
  }

  function init() {
    const searchInput = document.getElementById("notificationSearch");
    const statusFilter = document.getElementById("notificationStatusFilter");
    const refreshBtn = document.getElementById("refreshNotifications");
    const openBtn = document.getElementById("openSendNotification");
    const cancelBtn = document.getElementById("cancelSendNotification");
    const form = document.getElementById("sendNotificationForm");

    if (searchInput) searchInput.addEventListener("input", applyFilters);
    if (statusFilter) statusFilter.addEventListener("change", applyFilters);
    if (refreshBtn) refreshBtn.addEventListener("click", function () { window.location.reload(); });
    if (openBtn) openBtn.addEventListener("click", openSendPanel);
    if (cancelBtn) cancelBtn.addEventListener("click", closeSendPanel);
    if (form) form.addEventListener("submit", sendNotification);

    applyFilters();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
