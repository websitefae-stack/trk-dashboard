(function () {
  "use strict";

  function el(id) {
    return document.getElementById(id);
  }

  function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    if (meta && meta.content) return meta.content;

    const hidden = el("csrfToken");
    return hidden ? hidden.value : "";
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

  function getNotificationName() {
    const hidden = el("notificationDocname");
    if (hidden && hidden.value) return hidden.value;

    const params = new URLSearchParams(window.location.search);
    return params.get("name") || "";
  }

  function setMessage(text, isError) {
    const node = el("notificationDetailMessage");
    if (!node) return;

    node.textContent = text || "";
    node.style.display = text ? "" : "none";
    node.classList.toggle("dashboard-notice-error", !!isError);
  }

  async function saveStatus() {
    const docname = getNotificationName();
    const status = el("notificationStatus") ? el("notificationStatus").value : "";

    if (!docname || !status) return;

    setMessage("Saving...", false);

    try {
      await callApi("dashboard.api.shared.notifications.update_notification_status", {
        name: docname,
        status: status
      });

      setMessage("Status updated.", false);

      setTimeout(function () {
        window.location.reload();
      }, 500);
    } catch (error) {
      setMessage(error.message || "Could not update notification status.", true);
    }
  }

  async function saveReply(event) {
    event.preventDefault();

    const docname = getNotificationName();
    const replyInput = el("notificationReplyMessage");
    const replyMessage = replyInput ? replyInput.value.trim() : "";

    if (!docname) {
      setMessage("Notification not found.", true);
      return;
    }

    if (!replyMessage) {
      setMessage("Please enter a reply.", true);
      return;
    }

    const button = el("sendNotificationReply");

    if (button) {
      button.disabled = true;
      button.textContent = "Sending...";
    }

    setMessage("Sending reply...", false);

    try {
      await callApi("dashboard.api.shared.notifications.reply_to_notification", {
        name: docname,
        message: replyMessage
      });

      if (replyInput) replyInput.value = "";

      setMessage("Reply sent.", false);

      setTimeout(function () {
        window.location.reload();
      }, 500);
    } catch (error) {
      setMessage(error.message || "Could not send reply.", true);
    } finally {
      if (button) {
        button.disabled = false;
        button.textContent = "Send Reply";
      }
    }
  }

  async function markRead() {
    const docname = getNotificationName();

    if (!docname) return;

    try {
      await callApi("dashboard.api.shared.notifications.mark_notification_read", {
        name: docname
      });
    } catch (error) {
      console.warn("Could not mark notification read", error);
    }
  }

  function init() {
    const saveBtn = el("saveNotificationStatus");
    const replyForm = el("notificationReplyForm");

    if (saveBtn) {
      saveBtn.addEventListener("click", saveStatus);
    }

    if (replyForm) {
      replyForm.addEventListener("submit", saveReply);
    }

    markRead();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
