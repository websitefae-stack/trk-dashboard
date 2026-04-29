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

  function updateClientCount() {
    const countEl = el("clientCount");
    if (!countEl) return;

    const rows = qsa(".dashboard-client-row");
    const visible = rows.filter((row) => row.style.display !== "none").length;

    countEl.textContent = `${visible} client${visible === 1 ? "" : "s"}`;
  }

  function clientMatches(row, filters) {
    const haystack = [
      row.dataset.name || "",
      row.dataset.preferred || "",
      row.dataset.email || "",
      row.dataset.mobile || "",
      row.dataset.coach || "",
      row.dataset.sessionWorker || "",
      row.dataset.type || "",
      row.dataset.status || ""
    ].join(" ").toLowerCase();

    if (filters.search && !haystack.includes(filters.search)) return false;

    if (filters.status && filters.status !== "All" && row.dataset.status !== filters.status) {
      return false;
    }

    if (filters.type && filters.type !== "All" && row.dataset.type !== filters.type) {
      return false;
    }

    if (
      filters.sessionWorker &&
      filters.sessionWorker !== "All" &&
      row.dataset.sessionWorker !== filters.sessionWorker
    ) {
      return false;
    }

    if (filters.coach && filters.coach !== "All" && row.dataset.coach !== filters.coach) {
      return false;
    }

    if (filters.clientScope && filters.clientScope !== "All" && row.dataset.scope !== filters.clientScope) {
      return false;
    }

    return true;
  }

  function getFilters() {
    return {
      search: (getFilterValue("clientSearch", "") || "").trim().toLowerCase(),
      status: getFilterValue("statusFilter", "All"),
      type: getFilterValue("clientTypeFilter", "All"),
      sessionWorker: getFilterValue("sessionWorkerFilter", "All"),
      coach: getFilterValue("coachFilter", "All"),
      clientScope: getFilterValue("clientScopeFilter", "All")
    };
  }

  function renderClientFilters() {
    const filters = getFilters();

    qsa(".dashboard-client-row").forEach((row) => {
      row.style.display = clientMatches(row, filters) ? "" : "none";
    });

    updateClientCount();
  }

  function initClientFilterEvents() {
    [
      "clientSearch",
      "statusFilter",
      "clientTypeFilter",
      "sessionWorkerFilter",
      "coachFilter",
      "clientScopeFilter"
    ].forEach((id) => {
      const field = el(id);
      if (!field || field.dataset.clientFilterBound === "1") return;

      field.dataset.clientFilterBound = "1";

      const eventName = field.tagName === "SELECT" ? "change" : "input";
      field.addEventListener(eventName, renderClientFilters);
    });
  }

  function initRefreshButton() {
    const refreshBtn = el("refreshClients");
    if (!refreshBtn || refreshBtn.dataset.refreshBound === "1") return;

    refreshBtn.dataset.refreshBound = "1";
    refreshBtn.addEventListener("click", function () {
      window.location.reload();
    });
  }

  function initClientSearchToggle() {
    const toggleBtn = el("toggleClientSearch") || el("openClientSearch");
    const closeBtn = el("closeClientSearch");
    const panel = el("clientFilterPanel") || el("clientFilterBody");

    if (toggleBtn && toggleBtn.dataset.searchToggleBound !== "1") {
      toggleBtn.dataset.searchToggleBound = "1";
      toggleBtn.addEventListener("click", function () {
        if (panel) panel.classList.add("is-open");
        document.body.classList.add("client-search-open");
      });
    }

    if (closeBtn && closeBtn.dataset.searchCloseBound !== "1") {
      closeBtn.dataset.searchCloseBound = "1";
      closeBtn.addEventListener("click", function () {
        if (panel) panel.classList.remove("is-open");
        document.body.classList.remove("client-search-open");
      });
    }
  }

  function initAddClientButton() {
    const addBtn = el("addClient");
    if (!addBtn || addBtn.dataset.addClientBound === "1") return;

    const targetUrl = addBtn.dataset.addClientUrl || "/app/client/new-client";

    addBtn.dataset.addClientBound = "1";
    addBtn.addEventListener("click", function () {
      window.location.href = targetUrl;
    });
  }

  function initClickableClientRows() {
    qsa(".dashboard-client-name-link").forEach((link) => {
      if (link.dataset.clientNameLinkBound === "1") return;

      link.dataset.clientNameLinkBound = "1";
      link.addEventListener("click", function (event) {
        event.stopPropagation();
      });
    });
  }

  function initClientsPage() {
    if (!el("clientTable") && !document.querySelector(".dashboard-client-row")) return;

    initClientFilterEvents();
    initRefreshButton();
    initClientSearchToggle();
    initAddClientButton();
    initClickableClientRows();
    renderClientFilters();
  }

  window.TRKDashboardClients = {
    renderClientFilters,
    updateClientCount
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initClientsPage);
  } else {
    initClientsPage();
  }
})();
