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

  function updateCoachCount() {
    const countEl = el("coachCount");
    if (!countEl) return;

    const rows = qsa(".dashboard-coach-row");
    const visible = rows.filter((row) => row.style.display !== "none").length;

    countEl.textContent = `${visible} coach${visible === 1 ? "" : "es"}`;
  }

  function coachMatches(row, filters) {
    const coachName = (row.dataset.name || "").toLowerCase();

    if (filters.search && !coachName.includes(filters.search)) {
      return false;
    }

    return true;
  }

  function getFilters() {
    return {
      search: (getFilterValue("coachSearch", "") || "").trim().toLowerCase()
    };
  }

  function renderCoachFilters() {
    const filters = getFilters();

    qsa(".dashboard-coach-row").forEach((row) => {
      row.style.display = coachMatches(row, filters) ? "" : "none";
    });

    updateCoachCount();
  }

  function initCoachFilterEvents() {
    const field = el("coachSearch");

    if (!field || field.dataset.coachFilterBound === "1") return;

    field.dataset.coachFilterBound = "1";
    field.addEventListener("input", renderCoachFilters);
  }

  function initRefreshButton() {
    const refreshBtn = el("refreshCoaches");

    if (!refreshBtn || refreshBtn.dataset.refreshBound === "1") return;

    refreshBtn.dataset.refreshBound = "1";

    refreshBtn.addEventListener("click", function () {
      window.location.reload();
    });
  }

  function initCoachSearchToggle() {
    const toggleBtn = el("toggleCoachSearch") || el("openCoachSearch");
    const closeBtn = el("closeCoachSearch");
    const panel = el("coachFilterPanel") || el("coachFilterBody");

    if (toggleBtn && toggleBtn.dataset.searchToggleBound !== "1") {
      toggleBtn.dataset.searchToggleBound = "1";

      toggleBtn.addEventListener("click", function () {
        if (panel) panel.classList.add("is-open");
        document.body.classList.add("coach-search-open");
      });
    }

    if (closeBtn && closeBtn.dataset.searchCloseBound !== "1") {
      closeBtn.dataset.searchCloseBound = "1";

      closeBtn.addEventListener("click", function () {
        if (panel) panel.classList.remove("is-open");
        document.body.classList.remove("coach-search-open");
      });
    }
  }

  function initAddCoachButton() {
    const addBtn = el("addCoach");

    if (!addBtn || addBtn.dataset.addCoachBound === "1") return;

    const targetUrl = addBtn.dataset.addCoachUrl || "/app/coach/new-coach";

    addBtn.dataset.addCoachBound = "1";

    addBtn.addEventListener("click", function () {
      window.location.href = targetUrl;
    });
  }

  function initClickableCoachRows() {
    qsa(".dashboard-coach-name-link").forEach((link) => {
      if (link.dataset.coachNameLinkBound === "1") return;

      link.dataset.coachNameLinkBound = "1";

      link.addEventListener("click", function (event) {
        event.stopPropagation();
      });
    });
  }

  function initCoachesPage() {
    if (!el("coachTable") && !document.querySelector(".dashboard-coach-row")) {
      return;
    }

    initCoachFilterEvents();
    initRefreshButton();
    initCoachSearchToggle();
    initAddCoachButton();
    initClickableCoachRows();

    renderCoachFilters();
  }

  window.TRKDashboardCoaches = {
    renderCoachFilters,
    updateCoachCount
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initCoachesPage);
  } else {
    initCoachesPage();
  }
})();
