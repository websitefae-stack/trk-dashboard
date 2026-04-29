(function () {
  "use strict";

  function openMenu() {
    document.body.classList.add("dashboard-menu-open");
  }

  function closeMenu() {
    document.body.classList.remove("dashboard-menu-open");
  }

  document.addEventListener("click", function (event) {
    if (event.target.closest(".dashboard-menu-toggle")) {
      openMenu();
      return;
    }

    if (
      event.target.closest(".dashboard-sidebar-close") ||
      event.target.closest(".dashboard-sidebar-overlay") ||
      event.target.closest(".dashboard-sidebar a") ||
      event.target.closest(".dashboard-sidebar button")
    ) {
      closeMenu();
    }
  });

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") {
      closeMenu();
    }
  });
})();
