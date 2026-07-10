(function () {
  "use strict";

  var debounce = Dashboard.debounce;

  function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta && meta.content ? meta.content : "";
  }

  async function apiPost(method, args) {
    const response = await fetch(`/api/method/${method}`, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-Frappe-CSRF-Token": getCsrfToken(),
      },
      body: JSON.stringify(args || {}),
    });

    const data = await response.json();

    if (!response.ok || data.exc) {
      throw new Error(data.message || "Search failed.");
    }

    return data.message || {};
  }

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  const GROUP_LABELS = {
    client: "Clients",
    invoice: "Invoices",
    "invoice-list": "Invoices",
  };

  function renderResults(container, results) {
    if (!results.length) {
      container.innerHTML = '<div class="dashboard-topbar-search-empty">No matches found</div>';
      container.style.display = "block";
      return;
    }

    let lastGroup = null;
    let html = "";

    results.forEach((row) => {
      const groupLabel = GROUP_LABELS[row.type] || "";
      if (groupLabel !== lastGroup) {
        html += `<div class="dashboard-topbar-search-group-label">${escapeHtml(groupLabel)}</div>`;
        lastGroup = groupLabel;
      }

      html += `
        <a class="dashboard-topbar-search-result" href="${escapeHtml(row.url)}">
          <div class="dashboard-topbar-search-result-title">${escapeHtml(row.title)}</div>
          ${row.subtitle ? `<div class="dashboard-topbar-search-result-subtitle">${escapeHtml(row.subtitle)}</div>` : ""}
        </a>
      `;
    });

    container.innerHTML = html;
    container.style.display = "block";
  }

  function init() {
    const wrap = document.getElementById("dashboardGlobalSearch");
    const input = document.getElementById("dashboardGlobalSearchInput");
    const results = document.getElementById("dashboardGlobalSearchResults");

    if (!wrap || !input || !results) return;

    const runSearch = debounce(async function () {
      const query = input.value.trim();

      if (query.length < 2) {
        results.style.display = "none";
        results.innerHTML = "";
        return;
      }

      try {
        const data = await apiPost("dashboard.api.shared.global_search.search", { query });
        renderResults(results, data.results || []);
      } catch (error) {
        console.error("Global search failed", error);
      }
    }, 250);

    input.addEventListener("input", runSearch);

    input.addEventListener("focus", function () {
      if (input.value.trim().length >= 2 && results.innerHTML) {
        results.style.display = "block";
      }
    });

    document.addEventListener("click", function (event) {
      if (!wrap.contains(event.target)) {
        results.style.display = "none";
      }
    });

    input.addEventListener("keydown", function (event) {
      if (event.key === "Escape") {
        results.style.display = "none";
        input.blur();
      }

      if (event.key === "Enter") {
        const first = results.querySelector(".dashboard-topbar-search-result");
        if (first) {
          event.preventDefault();
          window.location.href = first.getAttribute("href");
        }
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
