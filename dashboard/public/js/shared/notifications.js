(function () {
  "use strict";

  function el(id) {
    return document.getElementById(id);
  }

  function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta && meta.content ? meta.content : "";
  }

  function getDashboardBaseUrl() {
    const path = window.location.pathname || "";

    if (path.indexOf("/coach_db/") === 0) return "/coach_db";
    if (path.indexOf("/session_worker_db/") === 0) return "/session_worker_db";
    return "/franchisor_db";
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
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function applyFilters() {
    const searchInput = el("notificationSearch");
    const statusFilter = el("notificationStatusFilter");
    const typeFilter = el("notificationTypeFilter");
    const rows = document.querySelectorAll(".dashboard-notification-row");
    const countEl = el("notificationCount");

    const search = searchInput ? searchInput.value.toLowerCase().trim() : "";
    const status = statusFilter ? statusFilter.value : "All";
    const type = typeFilter ? typeFilter.value : "All";

    let visibleCount = 0;

    rows.forEach(function (row) {
      const rowSearch = row.getAttribute("data-search") || "";
      const rowStatus = row.getAttribute("data-status") || "";
      const rowReadStatus = row.getAttribute("data-read-status") || "";
      const rowType = row.getAttribute("data-type") || "";

      const statusMatch = status === "All" || rowStatus === status || rowReadStatus === status;
      const typeMatch = type === "All" || rowType === type;
      const searchMatch = !search || rowSearch.indexOf(search) !== -1;
      const visible = searchMatch && statusMatch && typeMatch;

      row.style.display = visible ? "" : "none";
      if (visible) visibleCount += 1;
    });

    if (countEl) {
      countEl.textContent = visibleCount + (visibleCount === 1 ? " conversation" : " conversations");
    }
  }

  function renderGroup(title, items) {
    if (!items || !items.length) return "";

    return [
      '<div class="dashboard-detail-section" style="margin-top:12px;">',
      '<h4 style="margin-bottom:12px;">' + escapeHtml(title) + '</h4>',
      '<div class="dashboard-detail-grid dashboard-detail-grid-2">',
      items.map(function (item) {
        return [
          '<label class="dashboard-checkbox-label">',
          '<input type="checkbox" name="notification_recipients" value="' + escapeHtml(item.recipient_user) + '">',
          '<span>' + escapeHtml(item.label || item.recipient_user) + '</span>',
          '</label>'
        ].join("");
      }).join(""),
      '</div>',
      '</div>'
    ].join("");
  }

  function renderDatalist(id, rows) {
    let list = document.getElementById(id);

    if (!list) {
      list = document.createElement("datalist");
      list.id = id;
      document.body.appendChild(list);
    }

    list.innerHTML = (rows || []).map(function (row) {
      return '<option value="' + escapeHtml(row.value || "") + '">' + escapeHtml(row.label || row.value || "") + '</option>';
    }).join("");
  }

  async function loadLinkOptions() {
    const clientInput = el("notificationLinkedClient");
    const eventInput = el("notificationLinkedEvent");

    if (clientInput) {
      clientInput.setAttribute("list", "notificationLinkedClientOptions");
      clientInput.placeholder = "Start typing or select a client";
    }

    if (eventInput) {
      eventInput.setAttribute("list", "notificationLinkedEventOptions");
      eventInput.placeholder = "Start typing or select a session/event";
    }

    try {
      const data = await callApi("dashboard.api.shared.notifications.get_notification_link_options", {});

      renderDatalist("notificationLinkedClientOptions", data.clients || []);
      renderDatalist("notificationLinkedEventOptions", data.events || []);
    } catch (error) {
      console.error("Could not load linked client/event options", error);
    }
  }

  async function loadRecipients() {
    const container = el("notificationRecipients");
    if (!container) return;

    container.innerHTML = "Loading recipients...";

    try {
      const data = await callApi("dashboard.api.shared.notifications.get_notification_recipients", {});

      container.innerHTML = [
        renderGroup("Franchisor / Admin", data.admins || []),
        renderGroup("Coaches", data.coaches || []),
        renderGroup("Session Workers", data.session_workers || [])
      ].join("");

      if (!container.innerHTML.trim()) {
        container.innerHTML = "No available recipients found.";
      }
    } catch (error) {
      console.error("Could not load recipients", error);
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
    loadLinkOptions();
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

    const titleInput = el("notificationTitle");
    const typeInput = el("notificationType");
    const priorityInput = el("notificationPriority");
    const messageInput = el("notificationMessage");
    const clientInput = el("notificationLinkedClient");
    const eventInput = el("notificationLinkedEvent");
    const requiresResponseInput = el("notificationRequiresResponse");
    const dueDateInput = el("notificationDueDate");
    const statusMessage = el("sendNotificationMessage");

    const recipients = selectedRecipients();
    const title = titleInput ? titleInput.value.trim() : "";
    const notificationType = typeInput ? typeInput.value : "Message";
    const priority = priorityInput ? priorityInput.value : "Normal";
    const message = messageInput ? messageInput.value.trim() : "";
    const linkedClient = clientInput ? clientInput.value.trim() : "";
    const linkedEvent = eventInput ? eventInput.value.trim() : "";
    const requiresResponse = requiresResponseInput && requiresResponseInput.checked ? 1 : 0;
    const dueDate = dueDateInput ? dueDateInput.value : "";

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
        title: title || notificationType,
        notification_type: notificationType,
        priority: priority,
        message: message,
        linked_client: linkedClient,
        linked_event: linkedEvent,
        requires_response: requiresResponse,
        due_date: dueDate
      });

      if (statusMessage) statusMessage.textContent = result.message || "Notification sent.";

      setTimeout(function () {
        window.location.reload();
      }, 700);
    } catch (error) {
      if (statusMessage) statusMessage.textContent = error.message || "Request failed.";
    }
  }

  function makeRowsClickable() {
    const baseUrl = getDashboardBaseUrl();

    document.querySelectorAll(".dashboard-notification-row").forEach(function (row) {
      row.addEventListener("click", function (event) {
        if (event.target.closest("a, button, input, select, textarea")) return;

        const name = row.getAttribute("data-name") || "";
        if (!name) return;

        window.location.href = baseUrl + "/notification_details?name=" + encodeURIComponent(name);
      });
    });
  }

  function init() {
    const searchInput = el("notificationSearch");
    const statusFilter = el("notificationStatusFilter");
    const typeFilter = el("notificationTypeFilter");
    const refreshBtn = el("refreshNotifications");
    const openBtn = el("openSendNotification");
    const cancelBtn = el("cancelSendNotification");
    const form = el("sendNotificationForm");

    if (searchInput) searchInput.addEventListener("input", applyFilters);
    if (statusFilter) statusFilter.addEventListener("change", applyFilters);
    if (typeFilter) typeFilter.addEventListener("change", applyFilters);

    if (refreshBtn) {
      refreshBtn.addEventListener("click", function () {
        window.location.reload();
      });
    }

    if (openBtn) openBtn.addEventListener("click", openPanel);
    if (cancelBtn) cancelBtn.addEventListener("click", closePanel);
    if (form) form.addEventListener("submit", sendNotification);

    makeRowsClickable();
    applyFilters();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
