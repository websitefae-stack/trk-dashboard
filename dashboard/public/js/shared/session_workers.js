(function () {
  function el(id) {
    return document.getElementById(id);
  }

  function qsa(selector, root) {
    return Array.from((root || document).querySelectorAll(selector));
  }

  function getFilterValue(id, fallback) {
    const field = el(id);
    return field ? field.value || fallback || "" : fallback || "";
  }

  function updateSessionWorkerCount() {
    const countEl = el("sessionWorkerCount");
    if (!countEl) return;

    const rows = qsa(".dashboard-session-worker-row");
    const visible = rows.filter((row) => row.style.display !== "none").length;

    countEl.textContent = `${visible} session worker${visible === 1 ? "" : "s"}`;
  }

  function sessionWorkerMatches(row, filters) {
    const haystack = [
      row.dataset.name || "",
      row.dataset.email || "",
      row.dataset.mobile || "",
      row.dataset.linkedCoach || "",
      row.dataset.linkedCoachNames || "",
      row.dataset.linkedClientsCount || ""
    ].join(" ").toLowerCase();

    if (filters.search && !haystack.includes(filters.search)) return false;

    if (
      filters.coach &&
      filters.coach !== "All" &&
      !(row.dataset.linkedCoachNames || "").split("|").includes(filters.coach)
    ) {
      return false;
    }

    return true;
  }

  function getFilters() {
    return {
      search: (getFilterValue("sessionWorkerSearch", "") || "").trim().toLowerCase(),
      coach: getFilterValue("sessionWorkerCoachFilter", "All")
    };
  }

  function renderSessionWorkerFilters() {
    const filters = getFilters();

    qsa(".dashboard-session-worker-row").forEach((row) => {
      row.style.display = sessionWorkerMatches(row, filters) ? "" : "none";
    });

    updateSessionWorkerCount();
  }

  function initSessionWorkerFilterEvents() {
    [
      "sessionWorkerSearch",
      "sessionWorkerCoachFilter"
    ].forEach((id) => {
      const field = el(id);
      if (!field || field.dataset.sessionWorkerFilterBound === "1") return;

      field.dataset.sessionWorkerFilterBound = "1";

      const eventName = field.tagName === "SELECT" ? "change" : "input";
      field.addEventListener(eventName, renderSessionWorkerFilters);
    });
  }

  function initRefreshButton() {
    const refreshBtn = el("refreshSessionWorkers");
    if (!refreshBtn || refreshBtn.dataset.refreshBound === "1") return;

    refreshBtn.dataset.refreshBound = "1";
    refreshBtn.addEventListener("click", function () {
      window.location.reload();
    });
  }

  function initSessionWorkerSearchToggle() {
    const toggleBtn = el("toggleSessionWorkerSearch") || el("openSessionWorkerSearch");
    const closeBtn = el("closeSessionWorkerSearch");
    const panel = el("sessionWorkerFilterPanel") || el("sessionWorkerFilterBody");

    if (toggleBtn && toggleBtn.dataset.searchToggleBound !== "1") {
      toggleBtn.dataset.searchToggleBound = "1";
      toggleBtn.addEventListener("click", function () {
        if (panel) panel.classList.add("is-open");
        document.body.classList.add("session-worker-search-open");
      });
    }

    if (closeBtn && closeBtn.dataset.searchCloseBound !== "1") {
      closeBtn.dataset.searchCloseBound = "1";
      closeBtn.addEventListener("click", function () {
        if (panel) panel.classList.remove("is-open");
        document.body.classList.remove("session-worker-search-open");
      });
    }
  }

  function initClickableSessionWorkerRows() {
    qsa(".dashboard-session-worker-name-link").forEach((link) => {
      if (link.dataset.sessionWorkerNameLinkBound === "1") return;

      link.dataset.sessionWorkerNameLinkBound = "1";
      link.addEventListener("click", function (event) {
        event.stopPropagation();
      });
    });

    qsa(".dashboard-session-worker-row").forEach((row) => {
      if (row.dataset.sessionWorkerRowBound === "1") return;

      const targetUrl = row.dataset.href || "";
      if (!targetUrl) return;

      row.dataset.sessionWorkerRowBound = "1";
      row.addEventListener("click", function () {
        window.location.href = targetUrl;
      });
    });
  }

  function initSessionWorkersPage() {
    if (!el("sessionWorkerTable") && !document.querySelector(".dashboard-session-worker-row")) return;

    initSessionWorkerFilterEvents();
    initRefreshButton();
    initSessionWorkerSearchToggle();
    initClickableSessionWorkerRows();
    renderSessionWorkerFilters();
  }

  window.TRKDashboardSessionWorkers = {
    renderSessionWorkerFilters,
    updateSessionWorkerCount
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initSessionWorkersPage);
  } else {
    initSessionWorkersPage();
  }
})();
