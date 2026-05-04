(function () {
  function getCSRFToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute("content") : "";
  }

  function applyFilters() {
    const searchInput = document.getElementById("notificationSearch");
    const statusFilter = document.getElementById("notificationStatusFilter");
    const rows = document.querySelectorAll(".dashboard-notification-row");
    const countEl = document.getElementById("notificationCount");

    const search = searchInput ? searchInput.value.toLowerCase().trim() : "";
    const status = statusFilter ? statusFilter.value : "All";

    let visibleCount = 0;

    rows.forEach(function (row) {
      const rowSearch = row.getAttribute("data-search") || "";
      const rowStatus = row.getAttribute("data-status") || "";

      const searchMatches = !search || rowSearch.includes(search);
      const statusMatches = status === "All" || rowStatus === status;

      if (searchMatches && statusMatches) {
        row.style.display = "";
        visibleCount += 1;
      } else {
        row.style.display = "none";
      }
    });

    if (countEl) {
      countEl.textContent = visibleCount + " notifications";
    }
  }

  function refreshNotifications() {
    window.location.reload();
  }

  document.addEventListener("DOMContentLoaded", function () {
    const searchInput = document.getElementById("notificationSearch");
    const statusFilter = document.getElementById("notificationStatusFilter");
    const refreshBtn = document.getElementById("refreshNotifications");

    if (searchInput) {
      searchInput.addEventListener("input", applyFilters);
    }

    if (statusFilter) {
      statusFilter.addEventListener("change", applyFilters);
    }

    if (refreshBtn) {
      refreshBtn.addEventListener("click", refreshNotifications);
    }

    applyFilters();
  });
})();
