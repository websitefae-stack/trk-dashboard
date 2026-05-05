(function () {
  function el(id) {
    return document.getElementById(id);
  }

  function qsa(selector, root) {
    return Array.from((root || document).querySelectorAll(selector));
  }

  function updateClientCount() {
    const countEl = el("clientCount");
    if (!countEl) return;

    const rows = qsa(".dashboard-client-row");
    const visible = rows.filter((row) => row.style.display !== "none").length;

    countEl.textContent = `${visible} client${visible === 1 ? "" : "s"}`;
  }

  function getValue(id, fallback) {
    return el(id) ? el(id).value : fallback;
  }

  function clientMatches(row) {
    const search = (getValue("clientSearch", "") || "").trim().toLowerCase();
    const status = getValue("statusFilter", "All") || "All";
    const type = getValue("clientTypeFilter", "All") || "All";
    const sessionWorker = getValue("sessionWorkerFilter", "All") || "All";

    const haystack = [
      row.dataset.name || "",
      row.dataset.preferred || "",
      row.dataset.email || "",
      row.dataset.mobile || "",
      row.dataset.type || "",
      row.dataset.status || "",
      row.dataset.sessionWorker || "",
      row.dataset.coach || ""
    ].join(" ").toLowerCase();

    if (search && !haystack.includes(search)) return false;
    if (status !== "All" && status !== "" && row.dataset.status !== status) return false;
    if (type !== "All" && type !== "" && row.dataset.type !== type) return false;

    const rowSessionWorker = row.dataset.sessionWorker || "";
    if (sessionWorker !== "All" && sessionWorker !== "" && rowSessionWorker !== sessionWorker) return false;

    return true;
  }

  function renderFilters() {
    qsa(".dashboard-client-row").forEach((row) => {
      row.style.display = clientMatches(row) ? "" : "none";
    });

    updateClientCount();
  }

  function getCurrentScope() {
    const scopeField = el("clientScopeFilter");
    return scopeField ? scopeField.value || "my" : "my";
  }

  function reloadForScope(scope) {
    const url = new URL(window.location.href);
    url.searchParams.set("scope", scope || "my");
    url.searchParams.set("_ts", Date.now().toString());
    window.location.href = url.toString();
  }

  function initActions() {
    const refreshBtn = el("refreshClients");
    if (refreshBtn) {
      refreshBtn.addEventListener("click", function () {
        reloadForScope(getCurrentScope());
      });
    }

    const addBtn = el("addClient");
    if (addBtn) {
      addBtn.addEventListener("click", function () {
        window.location.href = "/franchisor_db/client_details?new=1";
      });
    }
  }

  function init() {
    const scopeField = el("clientScopeFilter");

    if (scopeField) {
      scopeField.addEventListener("change", function () {
        reloadForScope(scopeField.value || "my");
      });
    }

    [
      "clientSearch",
      "statusFilter",
      "clientTypeFilter",
      "sessionWorkerFilter"
    ].forEach((id) => {
      const field = el(id);
      if (!field) return;

      field.addEventListener(field.tagName === "SELECT" ? "change" : "input", renderFilters);
    });

    initActions();
    renderFilters();
  }

  document.addEventListener("DOMContentLoaded", init);
})();
