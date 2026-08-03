(function () {
  "use strict";

  var el = Dashboard.el;

  const SHARED_API = "dashboard.api.shared.item_access";

  const state = {
    items: [],
    coaches: [],
    brandFields: [],
    // grantsByItem[item][company] = { access: bool, showOnSite: bool }
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

  function filteredItems(filterText) {
    if (!filterText) return state.items;
    const needle = filterText.toLowerCase();
    return state.items.filter(function (item) {
      return item.label.toLowerCase().indexOf(needle) !== -1;
    });
  }

  // ---------------------------------------------------------------
  // Item Brands table
  // ---------------------------------------------------------------

  function renderBrandsHead() {
    const head = el("itemBrandsTableHead");
    if (!head) return;

    let html = '<tr><th class="item-access-name-col">Item</th>';
    state.brandFields.forEach(function (brand) {
      html += "<th>" + escapeHtml(brand.label) + "</th>";
    });
    head.innerHTML = html + "</tr>";
  }

  function renderBrandsBody(filterText) {
    const body = el("itemBrandsTableBody");
    if (!body) return;

    const rows = filteredItems(filterText);

    if (!rows.length) {
      const colspan = state.brandFields.length + 1;
      body.innerHTML = '<tr><td colspan="' + colspan + '" class="dashboard-empty">No items found.</td></tr>';
      return;
    }

    body.innerHTML = rows.map(function (item) {
      const cells = state.brandFields.map(function (brand) {
        const checked = item.brands && item.brands[brand.fieldname] ? "checked" : "";
        return '<td style="text-align:center;">'
          + '<input type="checkbox" data-brand-toggle data-item="' + escapeHtml(item.name) + '" data-brand-field="' + escapeHtml(brand.fieldname) + '" ' + checked + '>'
          + '</td>';
      }).join("");

      return '<tr><td class="item-access-name-col">' + escapeHtml(item.label) + '</td>' + cells + '</tr>';
    }).join("");

    body.querySelectorAll("[data-brand-toggle]").forEach(function (checkbox) {
      checkbox.addEventListener("change", function () {
        toggleBrand(checkbox);
      });
    });
  }

  async function toggleBrand(checkbox) {
    const itemCode = checkbox.dataset.item;
    const brandField = checkbox.dataset.brandField;
    const enabled = checkbox.checked;

    checkbox.disabled = true;
    showMessage("Saving...");

    try {
      await apiPost(`${SHARED_API}.set_item_brand`, {
        item_code: itemCode,
        brand_field: brandField,
        enabled: enabled ? 1 : 0
      });

      const item = state.items.find(function (i) { return i.name === itemCode; });
      if (item) {
        item.brands = item.brands || {};
        item.brands[brandField] = enabled;
      }

      showMessage("Saved.");
    } catch (error) {
      checkbox.checked = !enabled;
      showMessage(error.message || "Could not save this change.", true);
    } finally {
      checkbox.disabled = false;
    }
  }

  // ---------------------------------------------------------------
  // Item Access (+ Show on site) table
  // ---------------------------------------------------------------

  function renderAccessHead() {
    const head = el("itemAccessTableHead");
    if (!head) return;

    let html = '<tr><th class="item-access-name-col">Item</th>';
    state.coaches.forEach(function (coach) {
      html += "<th>" + escapeHtml(coach.label) + "</th>";
    });
    head.innerHTML = html + "</tr>";
  }

  function accessCellHtml(item, coach) {
    const grant = (state.grantsByItem[item.name] || {})[coach.company] || { access: false, showOnSite: false };

    return '<td>'
      + '<label style="display:flex;align-items:center;gap:6px;white-space:nowrap;">'
      + '<input type="checkbox" data-access-toggle data-item="' + escapeHtml(item.name) + '" data-coach="' + escapeHtml(coach.name) + '" ' + (grant.access ? "checked" : "") + '>'
      + ' Access'
      + '</label>'
      + '<label style="display:flex;align-items:center;gap:6px;white-space:nowrap;margin-top:4px;">'
      + '<input type="checkbox" data-show-on-site-toggle data-item="' + escapeHtml(item.name) + '" data-coach="' + escapeHtml(coach.name) + '" '
      + (grant.showOnSite ? "checked" : "") + (grant.access ? "" : " disabled") + '>'
      + ' Show on site'
      + '</label>'
      + '</td>';
  }

  function renderAccessBody(filterText) {
    const body = el("itemAccessTableBody");
    if (!body) return;

    const rows = filteredItems(filterText);

    if (!rows.length) {
      const colspan = state.coaches.length + 1;
      body.innerHTML = '<tr><td colspan="' + colspan + '" class="dashboard-empty">No items found.</td></tr>';
      return;
    }

    body.innerHTML = rows.map(function (item) {
      const cells = state.coaches.map(function (coach) {
        return accessCellHtml(item, coach);
      }).join("");

      const nameCell = '<td class="item-access-name-col">'
        + '<div>' + escapeHtml(item.label) + '</div>'
        + '<button type="button" class="dashboard-btn dashboard-btn-light" style="margin-top:6px;font-size:11px;padding:4px 8px;white-space:nowrap;" '
        + 'data-grant-all data-item="' + escapeHtml(item.name) + '">Give access to all coaches</button>'
        + '</td>';

      return '<tr>' + nameCell + cells + '</tr>';
    }).join("");

    body.querySelectorAll("[data-access-toggle]").forEach(function (checkbox) {
      checkbox.addEventListener("change", function () {
        toggleAccess(checkbox);
      });
    });

    body.querySelectorAll("[data-show-on-site-toggle]").forEach(function (checkbox) {
      checkbox.addEventListener("change", function () {
        toggleShowOnSite(checkbox);
      });
    });

    body.querySelectorAll("[data-grant-all]").forEach(function (button) {
      button.addEventListener("click", function () {
        grantAllForItem(button);
      });
    });
  }

  function getGrant(itemCode, company) {
    state.grantsByItem[itemCode] = state.grantsByItem[itemCode] || {};
    state.grantsByItem[itemCode][company] = state.grantsByItem[itemCode][company] || { access: false, showOnSite: false };
    return state.grantsByItem[itemCode][company];
  }

  function findCoach(coachName) {
    return state.coaches.find(function (c) { return c.name === coachName; });
  }

  async function toggleAccess(checkbox) {
    const itemCode = checkbox.dataset.item;
    const coachName = checkbox.dataset.coach;
    const granted = checkbox.checked;
    const coach = findCoach(coachName);

    checkbox.disabled = true;
    showMessage("Saving...");

    // The matching "Show on site" checkbox lives in the same cell -
    // removing Access clears and disables it immediately client-side too,
    // since the backend deletes the whole Item Default row (and
    // custom_show_on_site along with it) the moment access is revoked.
    const cell = checkbox.closest("td");
    const showOnSiteCheckbox = cell ? cell.querySelector("[data-show-on-site-toggle]") : null;

    try {
      await apiPost(`${SHARED_API}.set_item_access`, {
        item_code: itemCode,
        coach: coachName,
        granted: granted ? 1 : 0
      });

      if (coach) {
        const grant = getGrant(itemCode, coach.company);
        grant.access = granted;
        if (!granted) grant.showOnSite = false;
      }

      if (showOnSiteCheckbox) {
        showOnSiteCheckbox.disabled = !granted;
        if (!granted) showOnSiteCheckbox.checked = false;
      }

      showMessage(granted ? "Access granted." : "Access removed.");
    } catch (error) {
      checkbox.checked = !granted;
      showMessage(error.message || "Could not save this change.", true);
    } finally {
      checkbox.disabled = false;
    }
  }

  async function toggleShowOnSite(checkbox) {
    const itemCode = checkbox.dataset.item;
    const coachName = checkbox.dataset.coach;
    const showOnSite = checkbox.checked;
    const coach = findCoach(coachName);

    checkbox.disabled = true;
    showMessage("Saving...");

    try {
      await apiPost(`${SHARED_API}.set_item_show_on_site`, {
        item_code: itemCode,
        coach: coachName,
        show_on_site: showOnSite ? 1 : 0
      });

      if (coach) {
        getGrant(itemCode, coach.company).showOnSite = showOnSite;
      }

      showMessage(showOnSite ? "Now showing on their profile." : "No longer shown on their profile.");
    } catch (error) {
      checkbox.checked = !showOnSite;
      showMessage(error.message || "Could not save this change.", true);
    } finally {
      checkbox.disabled = false;
    }
  }

  async function grantAllForItem(button) {
    const itemCode = button.dataset.item;
    const item = state.items.find(function (i) { return i.name === itemCode; });
    const itemLabel = item ? item.label : itemCode;

    if (!window.confirm('Give every coach Access and Show on site for "' + itemLabel + '"? This will not remove access anyone already has, and can be individually undone afterwards.')) {
      return;
    }

    button.disabled = true;
    button.textContent = "Granting...";
    showMessage("Granting access to all coaches...");

    try {
      const result = await apiPost(`${SHARED_API}.grant_item_access_to_all_coaches`, {
        item_code: itemCode,
        show_on_site: 1
      });

      showMessage(
        (result.granted || 0) + " coach(es) granted access and show on site."
        + (result.skipped && result.skipped.length ? " " + result.skipped.length + " skipped (no company set)." : "")
      );

      await loadGrid();
    } catch (error) {
      showMessage(error.message || "Could not grant access to all coaches.", true);
      button.disabled = false;
      button.textContent = "Give access to all coaches";
    }
  }

  // ---------------------------------------------------------------

  function renderAll(filterText) {
    renderBrandsHead();
    renderBrandsBody(filterText);
    renderAccessHead();
    renderAccessBody(filterText);
  }

  async function loadGrid() {
    const brandsBody = el("itemBrandsTableBody");
    const accessBody = el("itemAccessTableBody");
    if (!accessBody) return;

    accessBody.innerHTML = '<tr><td class="dashboard-empty">Loading…</td></tr>';
    if (brandsBody) brandsBody.innerHTML = '<tr><td class="dashboard-empty">Loading…</td></tr>';

    try {
      const result = await apiPost(`${SHARED_API}.get_item_access_grid`, {});

      state.items = result.items || [];
      state.coaches = result.coaches || [];
      state.brandFields = result.brand_fields || [];

      state.grantsByItem = {};
      (result.grants || []).forEach(function (grant) {
        state.grantsByItem[grant.item] = state.grantsByItem[grant.item] || {};
        state.grantsByItem[grant.item][grant.company] = {
          access: true,
          showOnSite: !!grant.show_on_site
        };
      });

      renderAll(el("itemAccessSearch") ? el("itemAccessSearch").value : "");
    } catch (error) {
      const message = escapeHtml(error.message || "Could not load items.");
      accessBody.innerHTML = '<tr><td class="dashboard-empty">' + message + '</td></tr>';
      if (brandsBody) brandsBody.innerHTML = '<tr><td class="dashboard-empty">' + message + '</td></tr>';
    }
  }

  function initTabs() {
    const tabsWrap = el("itemAccessTabs");
    if (!tabsWrap) return;

    tabsWrap.querySelectorAll(".dashboard-tab-btn[data-tab-target]").forEach(function (button) {
      button.addEventListener("click", function () {
        tabsWrap.querySelectorAll(".dashboard-tab-btn").forEach(function (btn) {
          btn.classList.toggle("is-active", btn === button);
        });

        document.querySelectorAll(".dashboard-tab-panel").forEach(function (panel) {
          const isActive = panel.id === button.dataset.tabTarget;
          panel.classList.toggle("is-active", isActive);
          panel.style.display = isActive ? "block" : "none";
        });
      });
    });
  }

  function init() {
    if (!el("itemAccessTableBody")) return;

    initTabs();
    loadGrid();

    const search = el("itemAccessSearch");
    if (search) {
      search.addEventListener("input", Dashboard.debounce(function () {
        renderAll(search.value);
      }, 200));
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
