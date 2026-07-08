(function () {
  var el = Dashboard.el;
  var qsa = Dashboard.qsa;

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
      row.dataset.attendingCoach || "",
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

    if (
      filters.coach &&
      filters.coach !== "All" &&
      row.dataset.coach !== filters.coach &&
      row.dataset.attendingCoach !== filters.coach
    ) {
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

  function isFranchisorClientsPage() {
    return window.location.pathname.indexOf("/franchisor_db/clients") !== -1;
  }

  function runServerSearchForFranchisor() {
    if (!isFranchisorClientsPage()) return;

    const searchValue = (getFilterValue("clientSearch", "") || "").trim();
    const params = new URLSearchParams(window.location.search);

    if (searchValue) {
      params.set("search", searchValue);
    } else {
      params.delete("search");
    }

    params.set("page", "1");

    window.location.href = window.location.pathname + "?" + params.toString();
  }

  function defaultFranchisorCoachFilter() {
    const coachFilter = el("coachFilter");
    if (!coachFilter || coachFilter.dataset.defaultCoachDone === "1") return;

    const stored = window.sessionStorage.getItem("trkFranchisorClientCoachFilter");
    if (stored) {
      coachFilter.value = stored;
      coachFilter.dataset.defaultCoachDone = "1";
      return;
    }

    const currentName = (coachFilter.dataset.currentUserFullName || "").trim().toLowerCase();

    if (currentName) {
      const match = Array.from(coachFilter.options).find(function (option) {
        return (option.text || "").trim().toLowerCase() === currentName;
      });

      if (match) {
        coachFilter.value = match.value;
      }
    }

    coachFilter.dataset.defaultCoachDone = "1";
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

      if (id === "clientSearch" && isFranchisorClientsPage()) {
        // Server-side search only runs on explicit submit (button/Enter),
        // not on every keystroke - reloading the page mid-typing was
        // cutting searches off before the coach had finished typing.
        field.addEventListener("keydown", function (event) {
          if (event.key === "Enter") {
            event.preventDefault();
            runServerSearchForFranchisor();
          }
        });
      } else {
        field.addEventListener(eventName, renderClientFilters);
      }

      if (id === "coachFilter") {
        field.addEventListener("change", function () {
          window.sessionStorage.setItem("trkFranchisorClientCoachFilter", field.value || "All");
          renderClientFilters();
        });
      }
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

  function initClientSearchButton() {
    const searchBtn = el("clientSearchBtn");
    if (!searchBtn || searchBtn.dataset.searchBound === "1") return;

    searchBtn.dataset.searchBound = "1";
    searchBtn.addEventListener("click", runServerSearchForFranchisor);
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

    qsa(".dashboard-client-unauthorised").forEach((button) => {
      if (button.dataset.clientUnauthorisedBound === "1") return;

      button.dataset.clientUnauthorisedBound = "1";
      button.addEventListener("click", function (event) {
        event.preventDefault();
        event.stopPropagation();

        alert("You are not authorised to view this client.");
      });
    });
  }
  function initClientsPage() {
    if (!el("clientTable") && !document.querySelector(".dashboard-client-row")) return;

    defaultFranchisorCoachFilter();
    initClientFilterEvents();
    initRefreshButton();
    initClientSearchButton();
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
