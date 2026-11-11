(function () {
  "use strict";

  if (window.__trkDashboardSidebarLoaded) {
    return;
  }

  window.__trkDashboardSidebarLoaded = true;

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
    document.body.classList.add("dashboard-menu-open");
  }

  function closeSidebar() {
    document.body.classList.remove("dashboard-menu-open");
  }

  function getViewAsParams() {
    const params = new URLSearchParams(window.location.search);
    const viewAs = params.get("view_as");
    const viewer = params.get("viewer");

    return viewAs && viewer ? { view_as: viewAs, viewer: viewer } : {};
  }

  async function loadNotificationBadges() {
    const badges = qsa(".js-notification-badge");

    if (!badges.length) return;

    try {
      const data = await callApi(
        "dashboard.api.shared.notifications.get_dashboard_notification_summary",
        getViewAsParams()
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

  function bindNavGroupToggles() {
    qsa(".dashboard-nav-group-toggle").forEach(function (button) {
      if (button.dataset.navGroupBound === "1") return;
      button.dataset.navGroupBound = "1";

      button.addEventListener("click", function () {
        const group = button.closest(".dashboard-nav-group");
        if (group) group.classList.toggle("is-open");
      });
    });
  }

  function bindSidebarEvents() {
    const menuBtn = qs(".dashboard-menu-toggle");
    const closeBtn = qs(".dashboard-sidebar-close");
    const overlay = qs(".dashboard-sidebar-overlay");
    const logoutBtn = qs("#dashboardLogoutBtn");

    bindNavGroupToggles();

    if (menuBtn && menuBtn.dataset.sidebarBound !== "1") {
      menuBtn.dataset.sidebarBound = "1";
      menuBtn.addEventListener("click", openSidebar);
    }

    if (closeBtn && closeBtn.dataset.sidebarBound !== "1") {
      closeBtn.dataset.sidebarBound = "1";
      closeBtn.addEventListener("click", closeSidebar);
    }

    if (overlay && overlay.dataset.sidebarBound !== "1") {
      overlay.dataset.sidebarBound = "1";
      overlay.addEventListener("click", closeSidebar);
    }

    if (logoutBtn && logoutBtn.dataset.logoutBound !== "1") {
      logoutBtn.dataset.logoutBound = "1";
      logoutBtn.addEventListener("click", logout);
    }

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") {
        closeSidebar();
      }
    });
  }

  // Most existing coaches/session workers were never opted into the
  // onboarding journey (it's opt-in, per person - see start_onboarding
  // on Coach/Session Worker), so the sidebar link is only worth showing
  // to someone who actually has a checklist. Franchisor-side nav keeps
  // its own Onboarding link regardless, since that one is the overview
  // across everyone, not tied to any single person having steps.
  async function hideOnboardingLinkIfUnused() {
    var isCoach = window.location.pathname.indexOf("/coach_db/") === 0;
    var isSessionWorker = window.location.pathname.indexOf("/session_worker_db/") === 0;
    if (!isCoach && !isSessionWorker) return;

    var base = isCoach ? "/coach_db/onboarding" : "/session_worker_db/onboarding";
    var method = isCoach
      ? "dashboard.api.shared.onboarding.coach_has_onboarding_steps"
      : "dashboard.api.shared.onboarding.session_worker_has_onboarding_steps";

    const link = qs('.dashboard-nav a[href^="' + base + '"]');
    if (!link) return;

    const data = await callApi(method, {});
    if (data && (!data.has_steps || data.all_done)) {
      link.style.display = "none";
    }
  }

  function init() {
    bindSidebarEvents();
    loadNotificationBadges();
    hideOnboardingLinkIfUnused();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
