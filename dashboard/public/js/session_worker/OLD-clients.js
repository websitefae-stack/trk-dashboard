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

  function getFilterValue(id, fallback) {
    return el(id) ? el(id).value : fallback;
  }

  function clientMatches(row, search, status, clientType) {
    const haystack = [
      row.dataset.name || "",
      row.dataset.preferred || "",
      row.dataset.email || "",
      row.dataset.mobile || "",
      row.dataset.coach || "",
      row.dataset.type || "",
      row.dataset.status || ""
    ].join(" ").toLowerCase();

    if (search && !haystack.includes(search)) return false;
    if (status && status !== "All" && row.dataset.status !== status) return false;
    if (clientType && clientType !== "All" && row.dataset.type !== clientType) return false;

    return true;
  }

  function renderClientFilters() {
    const search = (getFilterValue("clientSearch", "") || "").trim().toLowerCase();
    const status = getFilterValue("statusFilter", "All") || "All";
    const clientType = getFilterValue("clientTypeFilter", "All") || "All";

    qsa(".dashboard-client-row").forEach((row) => {
      row.style.display = clientMatches(row, search, status, clientType) ? "" : "none";
    });

    updateClientCount();
  }

  function initClientSearchToggle() {
    const toggleBtn = el("toggleClientSearch");
    const closeBtn = el("closeClientSearch");
    const panel = el("clientFilterPanel");

    if (!panel) return;

    if (toggleBtn) {
      toggleBtn.addEventListener("click", function () {
        panel.classList.add("is-open");
      });
    }

    if (closeBtn) {
      closeBtn.addEventListener("click", function () {
        panel.classList.remove("is-open");
      });
    }
  }

  function init() {
    if (!el("clientTable") && !document.querySelector(".dashboard-client-row")) return;

    ["clientSearch", "statusFilter", "clientTypeFilter"].forEach((id) => {
      const field = el(id);
      if (!field) return;

      field.addEventListener(field.tagName === "SELECT" ? "change" : "input", renderClientFilters);
    });

    const refreshBtn = el("refreshClients");
    if (refreshBtn) {
      refreshBtn.addEventListener("click", function () {
        window.location.reload();
      });
    }

    initClientSearchToggle();
    renderClientFilters();
  }

  document.addEventListener("DOMContentLoaded", init);
})();
