(function () {
  "use strict";

  function qs(selector) {
    return document.querySelector(selector);
  }

  function qsa(selector) {
    return Array.from(document.querySelectorAll(selector));
  }

  function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');

    if (meta && meta.content) {
      return meta.content;
    }

    if (window.frappe && window.frappe.csrf_token) {
      return window.frappe.csrf_token;
    }

    return "";
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
      return null;
    }

    return data.message || data;
  }

  function openSidebar() {
    const sidebar = qs(".dashboard-sidebar");
    const overlay = qs(".dashboard-sidebar-overlay");

    if (sidebar) sidebar.classList.add("is-open");
    if (overlay) overlay.classList.add("is-open");
  }

  function closeSidebar() {
    const sidebar = qs(".dashboard-sidebar");
    const overlay = qs(".dashboard-sidebar-overlay");

    if (sidebar) sidebar.classList.remove("is-open");
    if (overlay) overlay.classList.remove("is-open");
  }

  async function loadNotificationBadges() {
    const badges = qsa(".js-notification-badge");
  
    if (!badges.length) return;
  
    try {
      const data = await callApi(
        "dashboard.api.shared.notifications.get_dashboard_notification_summary",
        {}
      );
  
      if (!data) return;
  
      const unreadCount = Number(data.unread_count || 0);
  
      badges.forEach(function (badge) {
        badge.classList.remove(
          "dashboard-status-unread",
          "dashboard-status-read",
          "dashboard-status-active",
          "dashboard-status-onhold"
        );
  
        if (unreadCount > 0) {
          badge.style.display = "inline-flex";
          badge.textContent = unreadCount;
  
          badge.classList.add(
            "dashboard-badge",
            "dashboard-status-unread"
          );
  
          return;
        }
  
        badge.textContent = "0";
        badge.style.display = "none";
      });
  
    } catch (error) {
      console.error("Notification badge error", error);
    }
  }

  async function logout() {
    try {
      await fetch("/api/method/logout", {
        method: "GET",
        credentials: "same-origin"
      });
    } catch (error) {
      console.error(error);
    }

    window.location.href = "/login";
  }

  function bindSidebarEvents() {
    const menuBtn = qs(".dashboard-menu-toggle");
    const closeBtn = qs(".dashboard-sidebar-close");
    const overlay = qs(".dashboard-sidebar-overlay");
    const logoutBtn = qs("#dashboardLogoutBtn");

    if (menuBtn) {
      menuBtn.addEventListener("click", openSidebar);
    }

    if (closeBtn) {
      closeBtn.addEventListener("click", closeSidebar);
    }

    if (overlay) {
      overlay.addEventListener("click", closeSidebar);
    }

    if (logoutBtn) {
      logoutBtn.addEventListener("click", logout);
    }
  }

  function init() {
    bindSidebarEvents();
    loadNotificationBadges();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
