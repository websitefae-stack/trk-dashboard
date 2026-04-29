(function () {
  "use strict";

  function openDashboardMenu() {
    document.body.classList.add("dashboard-menu-open");
  }

  function closeDashboardMenu() {
    document.body.classList.remove("dashboard-menu-open");
  }

  document.addEventListener("click", function (event) {
    if (event.target.closest(".dashboard-menu-toggle")) {
      openDashboardMenu();
      return;
    }

    if (
      event.target.closest(".dashboard-sidebar-close") ||
      event.target.closest(".dashboard-sidebar-overlay")
    ) {
      closeDashboardMenu();
      return;
    }

    if (
      event.target.closest(".dashboard-sidebar .dashboard-nav a") &&
      window.innerWidth <= 860
    ) {
      closeDashboardMenu();
    }
  });

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") {
      closeDashboardMenu();
    }
  });

  window.addEventListener("resize", function () {
    if (window.innerWidth > 860) {
      closeDashboardMenu();
    }
  });
})();
