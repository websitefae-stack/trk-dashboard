(function () {
  "use strict";

  var el = Dashboard.el;

  const API = "dashboard.api.shared.item_access";

  const state = {
    documents: [],
    items: []
  };

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

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

  function itemLabel(itemCode) {
    const item = state.items.find(function (i) { return i.name === itemCode; });
    return item ? item.label : itemCode;
  }

  function linkedItemsSummary(document_) {
    const linkedItems = document_.linked_items || [];

    if (!linkedItems.length) {
      return '<span class="dashboard-field-hint">Not linked to any item yet.</span>';
    }

    return escapeHtml(linkedItems.map(itemLabel).join(", "));
  }

  function renderRow(document_) {
    return '<tr>'
      + '<td>' + escapeHtml(document_.label) + '</td>'
      + '<td>' + escapeHtml(document_.document_type) + '</td>'
      + '<td>' + escapeHtml(document_.resource_availability || "—") + '</td>'
      + '<td>' + linkedItemsSummary(document_) + '</td>'
      + '</tr>';
  }

  function filteredDocuments(searchText) {
    if (!searchText) return state.documents;

    const needle = searchText.toLowerCase();

    return state.documents.filter(function (document_) {
      if ((document_.label || "").toLowerCase().indexOf(needle) !== -1) return true;

      return (document_.linked_items || []).some(function (itemCode) {
        return itemLabel(itemCode).toLowerCase().indexOf(needle) !== -1;
      });
    });
  }

  function renderTable(searchText) {
    const body = el("workshopResourcesTableBody");
    if (!body) return;

    const rows = filteredDocuments(searchText);

    if (!rows.length) {
      body.innerHTML = '<tr><td colspan="4" class="dashboard-empty">No documents found.</td></tr>';
      return;
    }

    body.innerHTML = rows.map(renderRow).join("");
  }

  async function loadWorkshopResources() {
    const body = el("workshopResourcesTableBody");
    if (!body) return;

    body.innerHTML = '<tr><td colspan="4" class="dashboard-empty">Loading…</td></tr>';

    try {
      const result = await apiPost(`${API}.get_workshop_resources`, {});
      state.documents = result.documents || [];
      state.items = result.items || [];
      renderTable(el("workshopResourcesSearch") ? el("workshopResourcesSearch").value : "");
    } catch (error) {
      body.innerHTML = '<tr><td colspan="4" class="dashboard-empty">' + escapeHtml(error.message || "Could not load documents.") + '</td></tr>';
    }
  }

  function initSectionTabs() {
    const tabsWrap = el("documentSectionTabs");
    if (!tabsWrap) return;

    let loaded = false;

    tabsWrap.querySelectorAll(".dashboard-tab-btn[data-section-target]").forEach(function (button) {
      button.addEventListener("click", function () {
        tabsWrap.querySelectorAll(".dashboard-tab-btn").forEach(function (btn) {
          btn.classList.toggle("is-active", btn === button);
        });

        const targetId = button.dataset.sectionTarget;
        ["myDocumentsSection", "workshopResourcesSection"].forEach(function (sectionId) {
          const section = el(sectionId);
          if (section) section.style.display = sectionId === targetId ? "block" : "none";
        });

        if (targetId === "workshopResourcesSection" && !loaded) {
          loaded = true;
          loadWorkshopResources();
        }
      });
    });
  }

  function init() {
    if (!el("workshopResourcesTableBody")) return;

    initSectionTabs();

    const search = el("workshopResourcesSearch");
    if (search) {
      search.addEventListener("input", Dashboard.debounce(function () {
        renderTable(search.value);
      }, 200));
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
