(function () {
  "use strict";

  const state = {
    notificationName: "",
    notification: null,
    savingStatus: false,
    sendingReply: false
  };

  function el(id) {
    return document.getElementById(id);
  }

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

    if (path.indexOf("/coach_db/") === 0) return "/coach_db";
    if (path.indexOf("/session_worker_db/") === 0) return "/session_worker_db";

    return "/franchisor_db";
  }

  function getQueryParam(name) {
    const params = new URLSearchParams(window.location.search);
    return params.get(name) || "";
  }

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
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

    let data = {};

    try {
      data = await response.json();
    } catch (error) {
      throw new Error("Could not read server response.");
    }

    if (!response.ok || data.exc) {
      console.error(data);
      throw new Error(getServerMessage(data) || data.message || "Request failed.");
    }

    return data.message || data;
  }

  function getServerMessage(data) {
    if (!data) return "";

    if (typeof data._server_messages === "string" && data._server_messages) {
      try {
        const messages = JSON.parse(data._server_messages);
        if (!Array.isArray(messages) || !messages.length) return "";

        const first = JSON.parse(messages[0]);
        return first.message || "";
      } catch (error) {
        return "";
      }
    }

    if (typeof data.message === "string") return data.message;
    if (data.exception) return String(data.exception);

    return "";
  }

  function setText(id, value) {
    const node = el(id);
    if (!node) return;
    node.textContent = value || "—";
  }

  function setHtml(id, value) {
    const node = el(id);
    if (!node) return;
    node.innerHTML = value || "—";
  }

  function setValue(id, value) {
    const node = el(id);
    if (!node) return;
    node.value = value || "";
  }

  function getValue(id) {
    const node = el(id);
    return node ? node.value : "";
  }

  function formatDateTime(value) {
    if (!value) return "—";

    const parsed = new Date(value);

    if (Number.isNaN(parsed.getTime())) {
      return String(value);
    }

    return parsed.toLocaleString("en-GB", {
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit"
    });
  }

  function badge(value, type) {
    const clean = value || "Open";
    let cls = "dashboard-status-onhold";

    if (clean === "Open" || clean === "Read") cls = "dashboard-status-active";
    if (clean === "Unread" || clean === "Waiting") cls = "dashboard-status-onhold";
    if (clean === "In Progress") cls = "dashboard-status-onhold";
    if (clean === "Done") cls = "dashboard-status-active";
    if (clean === "Archived") cls = "dashboard-status-archived";
    if (type === "priority" && clean === "Urgent") cls = "dashboard-status-archived";
    if (type === "priority" && clean === "High") cls = "dashboard-status-onhold";

    return '<span class="dashboard-badge ' + cls + '">' + escapeHtml(clean) + "</span>";
  }

  function showNotice(message) {
    const notice = el("notificationDetailsNotice");
    const content = el("notificationDetailsContent");

    if (notice) {
      notice.style.display = "";
      notice.textContent = message || "";
    }

    if (content) {
      content.style.display = "none";
    }
  }

  function showContent() {
    const notice = el("notificationDetailsNotice");
    const content = el("notificationDetailsContent");

    if (notice) {
      notice.style.display = "none";
    }

    if (content) {
      content.style.display = "";
    }
  }

  function getLinkHtml(label, url) {
    if (!url) return escapeHtml(label || "—");

    return '<a class="dashboard-link-btn" href="' + escapeHtml(url) + '">'
      + escapeHtml(label || "Open")
      + '</a>';
  }

  async function loadNotification() {
    state.notificationName = getQueryParam("name");

    if (!state.notificationName) {
      const hidden = el("notificationDocname");
      state.notificationName = hidden ? hidden.value : "";
    }

    if (!state.notificationName) {
      showNotice("Notification not found.");
      return;
    }

    showNotice("Loading notification...");

    try {
      const data = await callApi("dashboard.api.shared.notifications.get_notification_detail", {
        name: state.notificationName
      });

      state.notification = data;
      renderNotification(data);
      showContent();
    } catch (error) {
      console.error("Could not load notification", error);
      showNotice(error.message || "Could not load notification.");
    }
  }

  function renderNotification(data) {
    const baseUrl = getDashboardBaseUrl();

    setText("notificationTitleText", data.title || data.notification_type || "Notification");
    setText("notificationTypeText", data.conversation_type || data.notification_type || "Message");
    setHtml("notificationStatusText", badge(data.status || "Open"));
    setHtml("notificationReadStatusText", badge(data.read_status || "Read"));
    setHtml("notificationPriorityText", badge(data.priority || "Normal", "priority"));
    setText("notificationCreatedByText", data.created_by_label || data.sent_from || "—");
    setText("notificationCreatedDateText", formatDateTime(data.notification_date));
    setText("notificationDueDateText", data.due_date || "—");
    setText("notificationRequiresResponseText", Number(data.requires_response || 0) ? "Yes" : "No");

    setHtml(
      "notificationLinkedClientText",
      data.client
        ? getLinkHtml(data.client, data.client_link || (baseUrl + "/client_details?name=" + encodeURIComponent(data.client)))
        : "—"
    );

    setHtml(
      "notificationLinkedEventText",
      data.event
        ? getLinkHtml(data.event, data.event_link || (baseUrl + "/calendar_details?event=" + encodeURIComponent(data.event)))
        : "—"
    );

    setText("notificationMessageText", data.message || "—");
    setValue("notificationStatus", data.status || "Open");

    renderRecipients(data.recipients || []);
    renderTimeline(data.messages || data.replies || []);
    renderReplyArea(data);
  }

  function renderRecipients(recipients) {
    const wrap = el("notificationRecipientsSummary");

    if (!wrap) return;

    if (!recipients.length) {
      wrap.innerHTML = '<div class="dashboard-empty">No recipients found.</div>';
      return;
    }

    wrap.innerHTML = recipients.map(function (recipient) {
      const readText = Number(recipient.read || 0) ? "Read" : "Unread";

      return [
        '<div class="dashboard-mini-card" style="padding:10px 12px;border:1px solid #D9E6E6;border-radius:12px;margin-bottom:8px;">',
        '<div style="font-weight:700;">' + escapeHtml(recipient.recipient_label || recipient.recipient_user || "Recipient") + '</div>',
        '<div style="font-size:12px;color:#667;">',
        escapeHtml(recipient.recipient_role || ""),
        recipient.recipient_role ? " · " : "",
        escapeHtml(readText),
        '</div>',
        '</div>'
      ].join("");
    }).join("");
  }

  function renderTimeline(messages) {
    const wrap = el("notificationTimeline");

    if (!wrap) return;

    if (!messages.length) {
      wrap.innerHTML = '<div class="dashboard-empty">No messages yet.</div>';
      return;
    }

    wrap.innerHTML = messages.map(function (message) {
      const isSystem = message.message_type === "Status Update" || message.message_type === "System";

      return [
        '<div class="notification-thread-item' + (isSystem ? ' is-system' : '') + '" style="border:1px solid #D9E6E6;border-radius:16px;padding:14px;margin-bottom:12px;background:#fff;">',
        '<div style="display:flex;justify-content:space-between;gap:12px;align-items:flex-start;margin-bottom:8px;">',
        '<div>',
        '<div style="font-weight:800;">' + escapeHtml(message.sent_by_label || message.sent_by_name || message.sent_by || "System") + '</div>',
        '<div style="font-size:12px;color:#667;">',
        escapeHtml(message.role_type || ""),
        message.role_type ? " · " : "",
        escapeHtml(message.message_type || "Message"),
        '</div>',
        '</div>',
        '<div style="font-size:12px;color:#667;white-space:nowrap;">' + escapeHtml(formatDateTime(message.created_on)) + '</div>',
        '</div>',
        '<div style="white-space:pre-wrap;line-height:1.5;">' + escapeHtml(message.message || "") + '</div>',
        message.attachment ? '<div style="margin-top:10px;"><a class="dashboard-link-btn" href="' + escapeHtml(message.attachment) + '" target="_blank">Open attachment</a></div>' : '',
        '</div>'
      ].join("");
    }).join("");
  }

  function renderReplyArea(data) {
    const wrap = el("notificationReplySection");

    if (!wrap) return;

    if (!data || !data.name) {
      wrap.style.display = "none";
      return;
    }

    wrap.style.display = "";
  }

  async function saveStatus() {
    if (state.savingStatus) return;

    const name = state.notificationName || getValue("notificationDocname");
    const status = getValue("notificationStatus");

    if (!name || !status) return;

    state.savingStatus = true;

    const button = el("saveNotificationStatus");

    if (button) {
      button.disabled = true;
      button.textContent = "Saving...";
    }

    try {
      await callApi("dashboard.api.shared.notifications.update_notification_status", {
        name: name,
        status: status
      });

      await loadNotification();
    } catch (error) {
      alert(error.message || "Could not update status.");
    } finally {
      state.savingStatus = false;

      if (button) {
        button.disabled = false;
        button.textContent = "Save Status";
      }
    }
  }

  async function sendReply() {
    if (state.sendingReply) return;

    const textarea = el("notificationReplyText");
    const message = textarea ? textarea.value.trim() : "";

    if (!state.notificationName) {
      alert("Notification not found.");
      return;
    }

    if (!message) {
      alert("Please enter a reply.");
      return;
    }

    state.sendingReply = true;

    const button = el("sendNotificationReplyBtn");

    if (button) {
      button.disabled = true;
      button.textContent = "Sending...";
    }

    try {
      await callApi("dashboard.api.shared.notifications.reply_to_notification", {
        name: state.notificationName,
        message: message
      });

      if (textarea) {
        textarea.value = "";
      }

      await loadNotification();
    } catch (error) {
      alert(error.message || "Could not send reply.");
    } finally {
      state.sendingReply = false;

      if (button) {
        button.disabled = false;
        button.textContent = "Send Reply";
      }
    }
  }

  function bindEvents() {
    const saveBtn = el("saveNotificationStatus");
    const replyBtn = el("sendNotificationReplyBtn");
    const toggleDetailsBtn = el("toggleNotificationDetails");
    const detailsMeta = el("notificationDetailsMeta");
  
    if (saveBtn) {
      saveBtn.addEventListener("click", saveStatus);
    }
  
    if (replyBtn) {
      replyBtn.addEventListener("click", sendReply);
    }
  
    if (toggleDetailsBtn && detailsMeta) {
      toggleDetailsBtn.addEventListener("click", function () {
        const isCollapsed = detailsMeta.classList.toggle("is-collapsed");
        toggleDetailsBtn.textContent = isCollapsed ? "Show Details" : "Hide Details";
      });
    }
  }
  
  function init() {
    if (!el("notificationDetailsRoot")) {
      return;
    }
  
    bindEvents();
    loadNotification();
  }
  
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
  })();
