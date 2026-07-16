(function () {
  "use strict";

  var el = Dashboard.el;

  function getCsrfToken() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    if (meta && meta.content) return meta.content;
    if (window.frappe && window.frappe.csrf_token) return window.frappe.csrf_token;
    var match = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  async function callApi(method, payload) {
    var response = await fetch("/api/method/" + method, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-Frappe-CSRF-Token": getCsrfToken()
      },
      body: JSON.stringify(payload || {})
    });

    var data = await response.json();

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

  function connectUrl(returnTo) {
    return "/api/method/dashboard.api.shared.google_mail_connect.start_google_mail_connect?return_to="
      + encodeURIComponent(returnTo || "/coach_db/profile");
  }

  function render(container, returnTo, status) {
    if (!status.configured) {
      container.innerHTML = '<p class="dashboard-help">' + escapeHtml(status.message) + '</p>';
      return;
    }

    if (status.connected) {
      container.innerHTML =
        '<p class="dashboard-help" style="color:#1a7f37;">&#10003; Google Email Connected'
        + (status.email ? ' (' + escapeHtml(status.email) + ')' : '')
        + '</p>'
        + '<a class="dashboard-btn dashboard-btn-light" href="' + connectUrl(returnTo) + '">Reconnect Google Email</a>';
      return;
    }

    container.innerHTML =
      '<a class="dashboard-btn dashboard-btn-primary" href="' + connectUrl(returnTo) + '">Connect Google Email</a>';
  }

  function showBanner(container, message, isError) {
    var banner = document.createElement("p");
    banner.className = "dashboard-help";
    banner.style.color = isError ? "#c0392b" : "#1a7f37";
    banner.textContent = message;
    container.parentNode.insertBefore(banner, container);
  }

  async function loadStatus(field, container) {
    var returnTo = field.getAttribute("data-return-to") || "/coach_db/profile";

    try {
      var status = await callApi("dashboard.api.shared.google_mail_connect.get_google_mail_status", {});
      render(container, returnTo, status);
    } catch (error) {
      console.error("Google Mail status failed:", error);
      container.innerHTML = '<p class="dashboard-help">Could not check Google Email status.</p>';
    }
  }

  function consumeResultQueryParam(container) {
    var params = new URLSearchParams(window.location.search);
    var result = params.get("google_mail");

    if (result === "connected") {
      showBanner(container, "Google Email connected successfully.", false);
    } else if (result === "failed") {
      showBanner(container, "Could not connect Google Email. Please try again or contact the office.", true);
    }

    if (result) {
      params.delete("google_mail");
      var newQuery = params.toString();
      var newUrl = window.location.pathname + (newQuery ? "?" + newQuery : "") + window.location.hash;
      window.history.replaceState({}, "", newUrl);
    }
  }

  function init() {
    var field = el("googleMailConnectField");
    var container = el("googleMailConnectStatus");
    if (!field || !container) return; // not on this dashboard / not a coach

    consumeResultQueryParam(container);
    loadStatus(field, container);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
