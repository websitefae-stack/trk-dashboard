(function () {
  "use strict";

    if (window.__trkSharedNotificationsLoaded) {
    return;
  }

  window.__trkSharedNotificationsLoaded = true;

  let notificationLinkOptions = {
    clients: [],
    events: []
  };

  var el = Dashboard.el;

  function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');

    if (meta && meta.content) {
      return meta.content;
    }

    if (window.frappe && window.frappe.csrf_token) {
      return window.frappe.csrf_token;
    }

    const match = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  function getDashboardBaseUrl() {
    const path = window.location.pathname || "";
    const params = new URLSearchParams(window.location.search);

    if (params.get("view_as") && params.get("viewer")) {
      if (path.indexOf("/coach_db/") === 0) return "/coach_db";
      if (path.indexOf("/session_worker_db/") === 0) return "/session_worker_db";
    }

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

  const STATUS_COLUMNS = ["New", "In Progress", "Past Due", "Archived"];

  let allNotifications = [];

  function todayIso() {
    const now = new Date();
    return now.getFullYear() + "-" + String(now.getMonth() + 1).padStart(2, "0") + "-" + String(now.getDate()).padStart(2, "0");
  }

  // Bucket is derived from status + due_date rather than a stored value,
  // so it works the same way whether a row came from the "Dashboard
  // Conversation" doctype or the legacy Notification Log fallback (see
  // _format_conversation / _format_notification_log in notifications.py)
  // - both already expose status/due_date/read_status in this same shape.
  function bucketFor(row) {
    if ((row.status || "Open") === "Archived") return "Archived";

    const dueDate = row.due_date || "";
    if (!dueDate) return "New";

    return dueDate < todayIso() ? "Past Due" : "In Progress";
  }

  function borderClassFor(bucket) {
    if (bucket === "Archived") return "status-border-archived";
    if (bucket === "Past Due") return "status-border-overdue";
    if (bucket === "In Progress") return "status-border-unread";
    return "";
  }

  function getViewModeQueryString() {
    const params = new URLSearchParams(window.location.search);
    const keep = new URLSearchParams();

    ["view_as", "viewer"].forEach(function (key) {
      const value = params.get(key);
      if (value) keep.set(key, value);
    });

    const query = keep.toString();
    return query ? "&" + query : "";
  }

  function getDetailUrl(row) {
    return getDashboardBaseUrl()
      + "/notification_details?name="
      + encodeURIComponent(row.name)
      + getViewModeQueryString();
  }

  function formatDate(value) {
    if (!value) return "—";

    try {
      const date = new Date(value);
      return date.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
    } catch (error) {
      return String(value);
    }
  }

  function renderCard(row) {
    const priorityClass = (row.priority || "Normal").toLowerCase().replace(/\s+/g, "-");
    const readStatus = row.read_status || "Read";
    const bucket = bucketFor(row);
    const canArchive = Number(row.can_archive || 0);
    const isArchived = bucket === "Archived";

    return `
      <div class="dashboard-notif-card ${borderClassFor(bucket)}" draggable="true" data-name="${escapeHtml(row.name)}" data-detail-url="${escapeHtml(getDetailUrl(row))}">
        <div class="dashboard-notif-card-heading">
          <h3 class="dashboard-notif-card-title">${escapeHtml(row.title || row.notification_type || "Notification")}</h3>
          <span class="dashboard-priority-pill priority-${priorityClass}">${escapeHtml(row.priority || "Normal")}</span>
        </div>
        <div class="dashboard-notif-card-message">${escapeHtml(row.message || "")}</div>
        <div class="dashboard-notif-card-meta">
          <span>${readStatus === "Unread" ? "Unread · " : ""}${row.due_date ? "Due " + formatDate(row.due_date) : formatDate(row.notification_date)}</span>
          ${canArchive ? `<button type="button" class="dashboard-notif-card-archive-btn" data-archive-toggle="${isArchived ? "unarchive" : "archive"}">${isArchived ? "Restore" : "Archive"}</button>` : ""}
        </div>
      </div>
    `;
  }

  async function toggleArchive(name, action) {
    const method = action === "unarchive"
      ? "dashboard.api.shared.notifications.unarchive_notification"
      : "dashboard.api.shared.notifications.archive_notification";

    await callApi(method, { name: name });
    await loadNotifications();
  }

  async function setDueDate(name, dueDate) {
    await callApi("dashboard.api.shared.notifications.set_notification_due_date", {
      name: name,
      due_date: dueDate || ""
    });
    await loadNotifications();
  }

  function suggestedDueDate() {
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    return tomorrow.getFullYear() + "-" + String(tomorrow.getMonth() + 1).padStart(2, "0") + "-" + String(tomorrow.getDate()).padStart(2, "0");
  }

  let pendingDueDateName = null;

  function openDueDateModal(name) {
    pendingDueDateName = name;

    const input = el("notifDueDateInput");
    if (input) input.value = suggestedDueDate();

    const modal = el("notifDueDateModal");
    if (modal) modal.classList.add("show");
  }

  function closeDueDateModal() {
    pendingDueDateName = null;

    const modal = el("notifDueDateModal");
    if (modal) modal.classList.remove("show");
  }

  async function confirmDueDateModal() {
    if (!pendingDueDateName) return;

    const input = el("notifDueDateInput");
    const value = input ? input.value : "";

    if (!value) {
      window.alert("Please choose a due date.");
      return;
    }

    await setDueDate(pendingDueDateName, value);
    closeDueDateModal();
  }

  // New/In Progress/Past Due aren't independent states a card can just be
  // set to - they're derived from due_date (see bucketFor). So dropping on
  // New clears the due date, and dropping on In Progress/Past Due asks for
  // one (there's no other way to know what date the coach means) via a
  // small modal (a real date field, not a browser prompt asking for
  // YYYY-MM-DD), then lets bucketFor() sort out which of those two columns
  // it actually lands in once that date is saved.
  function handleColumnDrop(name, bucket) {
    if (bucket === "Archived") {
      toggleArchive(name, "archive");
      return;
    }

    if (bucket === "New") {
      setDueDate(name, "");
      return;
    }

    openDueDateModal(name);
  }

  function renderBoard(rows) {
    const board = el("notificationsKanbanBoard");
    if (!board) return;

    const byBucket = {};
    STATUS_COLUMNS.forEach(function (bucket) { byBucket[bucket] = []; });

    rows.forEach(function (row) {
      byBucket[bucketFor(row)].push(row);
    });

    STATUS_COLUMNS.forEach(function (bucket) {
      byBucket[bucket].sort(function (a, b) {
        return String(b.notification_date || "").localeCompare(String(a.notification_date || ""));
      });
    });

    board.innerHTML = STATUS_COLUMNS.map(function (bucket) {
      const items = byBucket[bucket];
      const body = items.length
        ? items.map(renderCard).join("")
        : '<div class="dashboard-notif-column-empty">Nothing here</div>';

      return `
        <div class="dashboard-notif-column" data-bucket="${escapeHtml(bucket)}">
          <div class="dashboard-notif-column-head">
            <span>${escapeHtml(bucket)}</span>
            <span class="dashboard-notif-column-count">${items.length}</span>
          </div>
          <div class="dashboard-notif-column-body">${body}</div>
        </div>
      `;
    }).join("");

    board.querySelectorAll(".dashboard-notif-card").forEach(function (card) {
      card.addEventListener("click", function (event) {
        const archiveBtn = event.target.closest("[data-archive-toggle]");

        if (archiveBtn) {
          event.stopPropagation();
          toggleArchive(card.getAttribute("data-name"), archiveBtn.getAttribute("data-archive-toggle"));
          return;
        }

        const url = card.getAttribute("data-detail-url");
        if (url) window.location.href = url;
      });

      card.addEventListener("dragstart", function (event) {
        event.dataTransfer.setData("text/plain", card.getAttribute("data-name"));
        event.dataTransfer.effectAllowed = "move";
        card.classList.add("is-dragging");
      });

      card.addEventListener("dragend", function () {
        card.classList.remove("is-dragging");
      });
    });

    board.querySelectorAll(".dashboard-notif-column").forEach(function (column) {
      column.addEventListener("dragover", function (event) {
        event.preventDefault();
        event.dataTransfer.dropEffect = "move";
        column.classList.add("is-drag-over");
      });

      column.addEventListener("dragleave", function () {
        column.classList.remove("is-drag-over");
      });

      column.addEventListener("drop", function (event) {
        event.preventDefault();
        column.classList.remove("is-drag-over");

        const name = event.dataTransfer.getData("text/plain");
        const bucket = column.getAttribute("data-bucket");

        if (name && bucket) {
          handleColumnDrop(name, bucket);
        }
      });
    });

    const countEl = el("notificationCount");
    if (countEl) {
      countEl.textContent = rows.length + (rows.length === 1 ? " notification" : " notifications");
    }
  }

  function applyFilters() {
    const searchInput = el("notificationSearch");
    const typeFilter = el("notificationTypeFilter");

    const search = searchInput ? searchInput.value.toLowerCase().trim() : "";
    const type = typeFilter ? typeFilter.value : "All";

    const filtered = allNotifications.filter(function (row) {
      const rowType = row.conversation_type || row.notification_type || "Message";
      const typeMatch = type === "All" || rowType === type;

      const searchBlob = [row.title, row.notification_type, row.message, row.client, row.event, row.created_by_label, row.reference_name]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      const searchMatch = !search || searchBlob.indexOf(search) !== -1;

      return typeMatch && searchMatch;
    });

    renderBoard(filtered);
  }

  async function loadNotifications() {
    const board = el("notificationsKanbanBoard");
    if (!board) return;

    try {
      const rows = await callApi("dashboard.api.shared.notifications.get_notification_list_for_page", {
        status: "All",
        limit: 500,
      });

      allNotifications = Array.isArray(rows) ? rows : [];
      applyFilters();
    } catch (error) {
      console.error("Failed to load notifications:", error);
      board.innerHTML = `<div class="dashboard-empty">${escapeHtml(error.message || "Could not load notifications.")}</div>`;
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

  function renderClientSelect() {
    const select = el("notificationLinkedClient");

    if (!select) return;

    let html = '<option value="">No linked client</option>';

    notificationLinkOptions.clients.forEach(function (client) {
      html += '<option value="' + escapeHtml(client.value || "") + '">'
        + escapeHtml(client.label || client.value || "")
        + '</option>';
    });

    select.innerHTML = html;
  }

  function getEventsForClient(clientName) {
    if (!clientName) return [];

    return notificationLinkOptions.events.filter(function (event) {
      return event.client === clientName || event.custom_client === clientName || event.client_name === clientName;
    });
  }

  function renderEventSelect(clientName) {
    const select = el("notificationLinkedEvent");

    if (!select) return;

    const events = getEventsForClient(clientName);

    if (!clientName) {
      select.disabled = true;
      select.innerHTML = '<option value="">Select a client first</option>';
      return;
    }

    if (!events.length) {
      select.disabled = true;
      select.innerHTML = '<option value="">No sessions found for this client</option>';
      return;
    }

    select.disabled = false;

    let html = '<option value="">No linked session/event</option>';

    events.forEach(function (event) {
      html += '<option value="' + escapeHtml(event.value || "") + '">'
        + escapeHtml(event.label || event.value || "")
        + '</option>';
    });

    select.innerHTML = html;
  }

  async function loadLinkOptions() {
    const clientSelect = el("notificationLinkedClient");
    const eventSelect = el("notificationLinkedEvent");

    if (clientSelect) {
      clientSelect.innerHTML = '<option value="">Loading clients...</option>';
    }

    if (eventSelect) {
      eventSelect.disabled = true;
      eventSelect.innerHTML = '<option value="">Select a client first</option>';
    }

    try {
      const data = await callApi("dashboard.api.shared.notifications.get_notification_link_options", {});

      notificationLinkOptions = {
        clients: Array.isArray(data.clients) ? data.clients : [],
        events: Array.isArray(data.events) ? data.events : []
      };

      renderClientSelect();
      renderEventSelect("");

    } catch (error) {
      console.error("Could not load linked client/event options", error);

      if (clientSelect) {
        clientSelect.innerHTML = '<option value="">Could not load clients</option>';
      }

      if (eventSelect) {
        eventSelect.disabled = true;
        eventSelect.innerHTML = '<option value="">Could not load sessions</option>';
      }
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

    renderEventSelect("");
  }

  async function uploadNotificationFile() {
    const fileInput = el("notificationFile");
    const attachmentInput = el("notificationAttachment");
    const help = el("notificationAttachmentHelp");
  
    if (!fileInput || !fileInput.files || !fileInput.files.length) {
      return "";
    }
  
    const file = fileInput.files[0];
    const formData = new FormData();
  
    formData.append("file", file);
    formData.append("is_private", "1");
    formData.append("folder", "Home/Attachments");
  
    if (help) {
      help.textContent = "Uploading attachment...";
    }
  
    const response = await fetch("/api/method/upload_file", {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "X-Frappe-CSRF-Token": getCsrfToken()
      },
      body: formData
    });
  
    const data = await response.json();
  
    if (!response.ok || data.exc) {
      throw new Error("Could not upload attachment.");
    }
  
    const fileUrl = data.message && data.message.file_url ? data.message.file_url : "";
  
    if (attachmentInput) {
      attachmentInput.value = fileUrl;
    }
  
    if (help) {
      help.textContent = fileUrl ? "Attachment uploaded." : "No attachment uploaded.";
    }
  
    return fileUrl;
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
    const attachmentInput = el("notificationAttachment");

    const recipients = selectedRecipients();
    const title = titleInput ? titleInput.value.trim() : "";
    const notificationType = typeInput ? typeInput.value : "Message";
    const priority = priorityInput ? priorityInput.value : "Normal";
    const message = messageInput ? messageInput.value.trim() : "";
    const linkedClient = clientInput ? clientInput.value : "";
    const linkedEvent = eventInput && !eventInput.disabled ? eventInput.value : "";
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

    let attachment = "";

    try {
      attachment = await uploadNotificationFile();
    } catch (error) {
      if (statusMessage) {
        statusMessage.textContent = error.message || "Could not upload attachment.";
      }
      return;
    }
        
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
        due_date: dueDate,
        attachment: attachment || (attachmentInput ? attachmentInput.value : "")
      });

      if (statusMessage) {
        statusMessage.textContent = result.message || "Notification sent.";
      }

      setTimeout(function () {
        window.location.reload();
      }, 700);

    } catch (error) {
      if (statusMessage) {
        statusMessage.textContent = error.message || "Request failed.";
      }
    }
  }

  function bindLinkedClientChange() {
    const clientSelect = el("notificationLinkedClient");

    if (!clientSelect) return;

    clientSelect.addEventListener("change", function () {
      renderEventSelect(this.value || "");
    });
  }

  function init() {
    const searchInput = el("notificationSearch");
    const typeFilter = el("notificationTypeFilter");
    const refreshBtn = el("refreshNotifications");
    const openBtn = el("openSendNotification");
    const cancelBtn = el("cancelSendNotification");
    const form = el("sendNotificationForm");

    if (searchInput) searchInput.addEventListener("input", applyFilters);
    if (typeFilter) typeFilter.addEventListener("change", applyFilters);

    if (refreshBtn) {
      refreshBtn.addEventListener("click", loadNotifications);
    }

    if (openBtn) openBtn.addEventListener("click", openPanel);
    if (cancelBtn) cancelBtn.addEventListener("click", closePanel);

    if (form && form.dataset.notificationsBound !== "1") {
      form.dataset.notificationsBound = "1";
      form.addEventListener("submit", sendNotification);
    }

    const dueDateClose = el("notifDueDateModalClose");
    const dueDateCancel = el("notifDueDateCancel");
    const dueDateConfirm = el("notifDueDateConfirm");

    if (dueDateClose) dueDateClose.addEventListener("click", closeDueDateModal);
    if (dueDateCancel) dueDateCancel.addEventListener("click", closeDueDateModal);
    if (dueDateConfirm) dueDateConfirm.addEventListener("click", confirmDueDateModal);

    bindLinkedClientChange();
    loadNotifications();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
