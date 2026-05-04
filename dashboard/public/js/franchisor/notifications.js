(function () {
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
      const visible = (!search || rowSearch.includes(search)) && (status === "All" || rowStatus === status);

      row.style.display = visible ? "" : "none";
      if (visible) visibleCount += 1;
    });

    if (countEl) countEl.textContent = visibleCount + " notifications";
  }

  function init() {
    const searchInput = document.getElementById("notificationSearch");
    const statusFilter = document.getElementById("notificationStatusFilter");
    const refreshBtn = document.getElementById("refreshNotifications");

    if (searchInput) searchInput.addEventListener("input", applyFilters);
    if (statusFilter) statusFilter.addEventListener("change", applyFilters);
    if (refreshBtn) refreshBtn.addEventListener("click", function () { window.location.reload(); });

    applyFilters();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
