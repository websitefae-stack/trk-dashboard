(function () {
  function el(id) {
    return document.getElementById(id);
  }

  function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta && meta.content ? meta.content : "";
  }

  async function callApi(method, payload) {
    const response = await fetch("/api/method/" + method, {
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
      console.error(data);
      throw new Error(data.message || "Request failed.");
    }

    return data.message || data;
  }

  function escapeHtml(value) {
    if (value === null || value === undefined) return "";

    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function renderGroup(title, items) {
    if (!items || !items.length) return "";

    return `
      <div class="dashboard-detail-section" style="margin-top:12px;">
        <h4 style="margin-bottom:12px;">${escapeHtml(title)}</h4>
        <div class="dashboard-detail-grid dashboard-detail-grid-2">
          ${items.map(function (item) {
            return `
              <label class="dashboard-checkbox-label">
                <input type="checkbox" name="notification_recipients" value="${escapeHtml(item.recipient_user)}">
                <span>${escapeHtml(item.label)}</span>
              </label>
            `;
          }).join("")}
        </div>
      </div>
    `;
  }

  async function loadRecipients() {
    const container = el("notificationRecipients");
    if (!container) return;

    container.innerHTML = "Loading recipients...";

    try {
      const data = await callApi("dashboard.api.shared.notifications.get_notification_recipients", {});

      container.innerHTML = `
        ${renderGroup("Coaches", data.coaches)}
        ${renderGroup("Session Workers", data.session_workers)}
        ${renderGroup("Admin", data.admins)}
      `;

      if (!container.innerHTML.trim()) {
        container.innerHTML = "No recipients found.";
      }
    } catch (error) {
      container.innerHTML = "Failed to load recipients.";
    }
  }

  function selectedRecipients() {
    return Array.from(document.querySelectorAll('input[name="notification_recipients"]:checked'))
      .map(function (input) {
        return input.value;
      });
  }

  function openPanel() {
    const panel = el("sendNotificationPanel");
    const message = el("sendNotificationMessage");

    if (panel) panel.style.display = "";
    if (message) message.textContent = "";

    loadRecipients();
  }

  function closePanel() {
    const panel = el("sendNotificationPanel");
    const form = el("sendNotificationForm");
    const message = el("sendNotificationMessage");

    if (panel) panel.style.display = "none";
    if (form) form.reset();
    if (message) message.textContent = "";
  }

  async function sendNotification(event) {
    event.preventDefault();

    const typeInput = el("notificationType");
    const priorityInput = el("notificationPriority");
    const messageInput = el("notificationMessage");
    const statusMessage = el("sendNotificationMessage");

    const recipients = selectedRecipients();
    const notificationType = typeInput ? typeInput.value : "Dashboard Message";
    const priority = priorityInput ? priorityInput.value : "Normal";
    const message = messageInput ? messageInput.value.trim() : "";

    if (!recipients.length) {
      if (statusMessage) statusMessage.textContent = "Select at least one recipient.";
      return;
    }

    if (!message) {
      if (statusMessage) statusMessage.textContent = "Enter a message.";
      return;
    }

    if (statusMessage) statusMessage.textContent = "Sending...";

    try {
      const result = await callApi("dashboard.api.shared.notifications.send_dashboard_notification", {
        recipient_users: recipients,
        notification_type: notificationType,
        priority: priority,
        message: message
      });

      if (statusMessage) statusMessage.textContent = result.message || "Notification sent.";

      setTimeout(function () {
        window.location.reload();
      }, 700);
    } catch (error) {
      if (statusMessage) statusMessage.textContent = error.message || "Request failed.";
    }
  }

  function init() {
    const openBtn = el("openSendNotification");
    const cancelBtn = el("cancelSendNotification");
    const form = el("sendNotificationForm");

    if (openBtn) openBtn.addEventListener("click", openPanel);
    if (cancelBtn) cancelBtn.addEventListener("click", closePanel);
    if (form) form.addEventListener("submit", sendNotification);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
