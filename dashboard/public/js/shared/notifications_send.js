(function () {
  function getCSRFToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute("content") : "";
  }

  function callFrappe(method, args) {
    return fetch("/api/method/" + method, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Frappe-CSRF-Token": getCSRFToken()
      },
      body: JSON.stringify(args || {})
    })
      .then(r => r.json())
      .then(data => {
        if (data.exc) {
          console.error(data);
          throw new Error("Server error");
        }
        return data.message;
      });
  }

  function el(id) {
    return document.getElementById(id);
  }

  function createCheckbox(name, label, value) {
    return `
      <label class="dashboard-checkbox">
        <input type="checkbox" name="${name}" value="${value}">
        <span>${label}</span>
      </label>
    `;
  }

  function renderGroup(title, name, items) {
    if (!items || !items.length) return "";

    return `
      <div class="dashboard-notification-group">
        <div class="dashboard-notification-group-title">${title}</div>
        <div class="dashboard-checkbox-list">
          ${items.map(i => createCheckbox(name, i.label, i.recipient_user)).join("")}
        </div>
      </div>
    `;
  }

  async function loadRecipients() {
    const container = el("notificationRecipients");
    if (!container) return;

    container.innerHTML = "Loading...";

    try {
      const data = await callFrappe("dashboard.api.shared.notifications.get_notification_recipients");

      container.innerHTML = `
        ${renderGroup("Coaches", "recipients", data.coaches)}
        ${renderGroup("Session Workers", "recipients", data.session_workers)}
        ${renderGroup("Franchisors", "recipients", data.franchisors)}
      `;
    } catch (err) {
      container.innerHTML = "Failed to load recipients";
    }
  }

  function getSelectedRecipients() {
    return Array.from(document.querySelectorAll('input[name="recipients"]:checked'))
      .map(el => el.value);
  }

  async function sendNotification() {
    const message = el("notificationMessage").value.trim();
    const type = el("notificationType").value;
    const priority = el("notificationPriority").value;

    const recipients = getSelectedRecipients();

    if (!recipients.length) {
      alert("Select at least one recipient");
      return;
    }

    if (!message) {
      alert("Enter a message");
      return;
    }

    try {
      await callFrappe("dashboard.api.shared.notifications.send_dashboard_notification", {
        recipient_users: recipients,
        notification_type: type,
        message: message,
        priority: priority
      });

      alert("Notification sent");
      window.location.reload();

    } catch (err) {
      alert("Request failed");
      console.error(err);
    }
  }

  function init() {
    loadRecipients();

    const btn = el("sendNotificationBtn");
    if (btn) {
      btn.addEventListener("click", sendNotification);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
