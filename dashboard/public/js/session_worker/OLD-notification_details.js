(function () {
  function el(id) {
    return document.getElementById(id);
  }

  function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    if (meta && meta.content) return meta.content;

    const hidden = el("csrfToken");
    return hidden ? hidden.value : "";
  }

  async function saveStatus() {
    const docname = el("notificationDocname") ? el("notificationDocname").value : "";
    const status = el("notificationStatus") ? el("notificationStatus").value : "";

    if (!docname || !status) return;

    const response = await fetch("/api/method/dashboard.api.session_worker.notifications.update_notification_status", {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-Frappe-CSRF-Token": getCsrfToken()
      },
      body: JSON.stringify({
        name: docname,
        status: status
      })
    });

    const data = await response.json();

    if (!response.ok || data.exc) {
      alert("Could not update notification status.");
      return;
    }

    alert("Notification status updated.");
    window.location.reload();
  }

  function init() {
    const saveBtn = el("saveNotificationStatus");

    if (saveBtn) {
      saveBtn.addEventListener("click", saveStatus);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
