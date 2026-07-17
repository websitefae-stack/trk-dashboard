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

    // Franchise-type rows represent coaches themselves (for cross-coach/HQ
    // invoicing) and aren't assigned to any one coach or session worker, so
    // those two filters must never hide them - otherwise the "show only my
    // clients" default (which auto-selects the current user in the Coach
    // filter) silently hides every other coach's record.
    const isFranchiseRow = row.dataset.type === "Franchise";

    if (
      !isFranchiseRow &&
      filters.sessionWorker &&
      filters.sessionWorker !== "All" &&
      row.dataset.sessionWorker !== filters.sessionWorker
    ) {
      return false;
    }

    if (
      !isFranchiseRow &&
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

  // Franchisor loads clients page-by-page from the server (in pages of
  // 25), so every filter here needs to be a real server round trip, not
  // just a client-side hide/show over whatever 25 rows happen to already
  // be on the page - otherwise picking a Client Type only hides rows on
  // the current page, the pagination total still reflects everything, and
  // clicking Next reloads unfiltered data with the dropdowns reset to
  // "All" (no server-restored selected state). Same fix pattern as the
  // invoices list. Coach/session worker pages load every client they're
  // allowed to see up front, so those keep the pure client-side filters.
  function buildFranchisorClientParams(overrides) {
    const params = new URLSearchParams(window.location.search);

    const searchValue = (getFilterValue("clientSearch", "") || "").trim();
    const clientType = getFilterValue("clientTypeFilter", "All");
    const status = getFilterValue("statusFilter", "All");
    const sessionWorker = getFilterValue("sessionWorkerFilter", "All");
    const coach = getFilterValue("coachFilter", "All");

    if (searchValue) { params.set("search", searchValue); } else { params.delete("search"); }
    if (clientType && clientType !== "All") { params.set("client_type", clientType); } else { params.delete("client_type"); }
    if (status && status !== "All") { params.set("status", status); } else { params.delete("status"); }
    if (sessionWorker && sessionWorker !== "All") { params.set("session_worker", sessionWorker); } else { params.delete("session_worker"); }
    if (coach && coach !== "All") { params.set("coach", coach); } else { params.delete("coach"); }

    Object.keys(overrides || {}).forEach(function (key) {
      const value = overrides[key];
      if (value === null || value === undefined || value === "") {
        params.delete(key);
      } else {
        params.set(key, value);
      }
    });

    return params;
  }

  function navigateFranchisorClients(overrides) {
    const params = buildFranchisorClientParams(overrides);
    window.location.href = window.location.pathname + "?" + params.toString();
  }

  function runServerSearchForFranchisor() {
    if (!isFranchisorClientsPage()) return;
    navigateFranchisorClients({ page: 1 });
  }

  function runClientSearch() {
    // Franchisor loads clients page-by-page from the server, so a search
    // needs a fresh page load. Coach/session worker pages load every client
    // they're allowed to see up front, so the search just re-applies the
    // existing client-side filters - no reload needed.
    if (isFranchisorClientsPage()) {
      runServerSearchForFranchisor();
    } else {
      renderClientFilters();
    }
  }

  function defaultFranchisorCoachFilter() {
    const coachFilter = el("coachFilter");
    if (!coachFilter || coachFilter.dataset.defaultCoachDone === "1") return;

    coachFilter.dataset.defaultCoachDone = "1";

    // An explicit ?coach= in the URL is already reflected as the selected
    // option server-side - only fall back to a remembered/current-user
    // default when nothing was selected server-side, and reload (rather
    // than just changing the dropdown) so the client list actually
    // reflects the default instead of only the dropdown appearing to.
    if (coachFilter.value && coachFilter.value !== "All") return;

    let defaultValue = window.sessionStorage.getItem("trkFranchisorClientCoachFilter") || "";

    if (!defaultValue) {
      const currentName = (coachFilter.dataset.currentUserFullName || "").trim().toLowerCase();

      if (currentName) {
        const match = Array.from(coachFilter.options).find(function (option) {
          return (option.text || "").trim().toLowerCase() === currentName;
        });

        if (match) defaultValue = match.value;
      }
    }

    if (defaultValue && defaultValue !== "All") {
      navigateFranchisorClients({ coach: defaultValue, page: 1 });
    }
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
      const isFranchisorServerFilter = isFranchisorClientsPage()
        && ["statusFilter", "clientTypeFilter", "sessionWorkerFilter", "coachFilter"].indexOf(id) !== -1;

      if (id === "clientSearch") {
        // Search only runs on explicit submit (button/Enter), not on every
        // keystroke - filtering/reloading mid-typing was cutting searches
        // off before the coach had finished typing.
        field.addEventListener("keydown", function (event) {
          if (event.key === "Enter") {
            event.preventDefault();
            runClientSearch();
          }
        });
      } else if (isFranchisorServerFilter) {
        field.addEventListener(eventName, function () {
          if (id === "coachFilter") {
            window.sessionStorage.setItem("trkFranchisorClientCoachFilter", field.value || "All");
          }
          navigateFranchisorClients({ page: 1 });
        });
      } else {
        field.addEventListener(eventName, renderClientFilters);

        if (id === "coachFilter") {
          field.addEventListener("change", function () {
            window.sessionStorage.setItem("trkFranchisorClientCoachFilter", field.value || "All");
          });
        }
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
    searchBtn.addEventListener("click", runClientSearch);
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
