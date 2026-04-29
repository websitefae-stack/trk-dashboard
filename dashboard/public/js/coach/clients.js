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
    const type = getValue("clientTypeFilter", getValue("typeFilter", "All")) || "All";
    const sessionWorker = getValue("sessionWorkerFilter", getValue("swFilter", "All")) || "All";

    const haystack = [
      row.dataset.name || "",
      row.dataset.preferred || "",
      row.dataset.email || "",
      row.dataset.mobile || "",
      row.dataset.type || "",
      row.dataset.status || "",
      row.dataset.sessionWorker || "",
      row.dataset.sw || ""
    ].join(" ").toLowerCase();

    if (search && !haystack.includes(search)) return false;
    if (status !== "All" && status !== "" && row.dataset.status !== status) return false;
    if (type !== "All" && type !== "" && row.dataset.type !== type) return false;

    const rowSessionWorker = row.dataset.sessionWorker || row.dataset.sw || "";
    if (sessionWorker !== "All" && sessionWorker !== "" && rowSessionWorker !== sessionWorker) return false;

    return true;
  }

  function renderFilters() {
    qsa(".dashboard-client-row").forEach((row) => {
      row.style.display = clientMatches(row) ? "" : "none";
    });

    updateClientCount();
  }

  function initSearchToggle() {
    const openBtn = el("openClientSearch") || el("toggleClientSearch");
    const closeBtn = el("closeClientSearch");
    const panel = el("clientFilterPanel");

    if (openBtn) {
      openBtn.addEventListener("click", function () {
        document.body.classList.add("client-search-open");
        if (panel) panel.classList.add("is-open");
      });
    }

    if (closeBtn) {
      closeBtn.addEventListener("click", function () {
        document.body.classList.remove("client-search-open");
        if (panel) panel.classList.remove("is-open");
      });
    }
  }

  function initActions() {
    const refreshBtn = el("refreshClients");
    if (refreshBtn) {
      refreshBtn.addEventListener("click", function () {
        window.location.reload();
      });
    }

    const addBtn = el("addClient");
    if (addBtn) {
      addBtn.addEventListener("click", function () {
        window.location.href = "/coach_db/client_details?new=1";
      });
    }
  }

  function init() {
    if (!el("clientTable") && !document.querySelector(".dashboard-client-row")) return;

    [
      "clientSearch",
      "statusFilter",
      "clientTypeFilter",
      "typeFilter",
      "sessionWorkerFilter",
      "swFilter"
    ].forEach((id) => {
      const field = el(id);
      if (!field) return;

      field.addEventListener(field.tagName === "SELECT" ? "change" : "input", renderFilters);
    });

    initSearchToggle();
    initActions();
    renderFilters();
  }

  document.addEventListener("DOMContentLoaded", init);
})();
