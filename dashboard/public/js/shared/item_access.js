(function () {
  "use strict";

  var el = Dashboard.el;

  const SHARED_API = "dashboard.api.shared.item_access";

  const state = {
    items: [],
    coaches: [],
    grantsByItem: {}
  };

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
      throw new Error(data.message || "There was a problem saving.");
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

  function showMessage(message, isError) {
    const banner = el("itemAccessMessage");
    if (!banner) return;
    banner.textContent = message || "";
    banner.style.color = isError ? "#C01C3E" : "#258D3B";
  }

  function renderHead() {
    const head = el("itemAccessTableHead");
    if (!head) return;

    let html = "<tr><th>Item</th>";
    state.coaches.forEach(function (coach) {
      html += "<th>" + escapeHtml(coach.label) + "</th>";
    });
    html += "</tr>";

    head.innerHTML = html;
  }

  function renderBody(filterText) {
    const body = el("itemAccessTableBody");
    if (!body) return;

    const filtered = state.items.filter(function (item) {
      if (!filterText) return true;
      return item.label.toLowerCase().indexOf(filterText.toLowerCase()) !== -1;
    });

    if (!filtered.length) {
      const colspan = state.coaches.length + 1;
      body.innerHTML = '<tr><td colspan="' + colspan + '" class="dashboard-empty">No items found.</td></tr>';
      return;
    }

    body.innerHTML = filtered.map(function (item) {
      const grantedCompanies = state.grantsByItem[item.name] || {};

      const cells = state.coaches.map(function (coach) {
        const checked = grantedCompanies[coach.company] ? "checked" : "";
        return '<td style="text-align:center;">'
          + '<input type="checkbox" data-item-access-toggle data-item="' + escapeHtml(item.name) + '" data-coach="' + escapeHtml(coach.name) + '" ' + checked + '>'
          + '</td>';
      }).join("");

      return '<tr><td>' + escapeHtml(item.label) + '</td>' + cells + '</tr>';
    }).join("");

    body.querySelectorAll("[data-item-access-toggle]").forEach(function (checkbox) {
      checkbox.addEventListener("change", function () {
        toggleAccess(checkbox);
      });
    });
  }

  async function toggleAccess(checkbox) {
    const itemCode = checkbox.dataset.item;
    const coach = checkbox.dataset.coach;
    const granted = checkbox.checked;

    checkbox.disabled = true;
    showMessage("Saving...");

    try {
      await apiPost(`${SHARED_API}.set_item_access`, {
        item_code: itemCode,
        coach: coach,
        granted: granted ? 1 : 0
      });

      state.grantsByItem[itemCode] = state.grantsByItem[itemCode] || {};

      const coachRow = state.coaches.find(function (c) { return c.name === coach; });
      const company = coachRow ? coachRow.company : "";

      if (company) {
        state.grantsByItem[itemCode][company] = granted;
      }

      showMessage(granted ? "Access granted." : "Access removed.");
    } catch (error) {
      checkbox.checked = !granted;
      showMessage(error.message || "Could not save this change.", true);
    } finally {
      checkbox.disabled = false;
    }
  }

  async function loadGrid() {
    const body = el("itemAccessTableBody");
    if (!body) return;

    body.innerHTML = '<tr><td class="dashboard-empty">Loading…</td></tr>';

    try {
      const result = await apiPost(`${SHARED_API}.get_item_access_grid`, {});

      state.items = result.items || [];
      state.coaches = result.coaches || [];

      state.grantsByItem = {};
      (result.grants || []).forEach(function (grant) {
        state.grantsByItem[grant.item] = state.grantsByItem[grant.item] || {};
        state.grantsByItem[grant.item][grant.company] = true;
      });

      renderHead();
      renderBody(el("itemAccessSearch") ? el("itemAccessSearch").value : "");
    } catch (error) {
      body.innerHTML = '<tr><td class="dashboard-empty">' + escapeHtml(error.message || "Could not load items.") + '</td></tr>';
    }
  }

  function init() {
    if (!el("itemAccessTableBody")) return;

    loadGrid();

    const search = el("itemAccessSearch");
    if (search) {
      search.addEventListener("input", Dashboard.debounce(function () {
        renderBody(search.value);
      }, 200));
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
