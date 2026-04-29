(function () {
    function openSidebar() {
        document.body.classList.add("dashboard-sidebar-open");
    }

    function closeSidebar() {
        document.body.classList.remove("dashboard-sidebar-open");
    }

    document.addEventListener("click", function (event) {
        if (event.target.closest(".dashboard-menu-toggle")) {
            openSidebar();
            return;
        }

        if (
            event.target.closest(".dashboard-sidebar-close") ||
            event.target.closest(".dashboard-sidebar-overlay")
        ) {
            closeSidebar();
            return;
        }

        if (
            event.target.closest(".dashboard-sidebar .dashboard-nav a") &&
            window.innerWidth <= 768
        ) {
            closeSidebar();
        }
    });

    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape") {
            closeSidebar();
        }
    });
})();
