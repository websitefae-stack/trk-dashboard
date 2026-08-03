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

  function showMessage(message, isError) {
    const banner = el("workshopResourcesMessage");
    if (!banner) return;
    banner.textContent = message || "";
    banner.style.color = isError ? "#C01C3E" : "#258D3B";
  }

  function itemLabel(itemCode) {
    const item = state.items.find(function (i) { return i.name === itemCode; });
    return item ? item.label : itemCode;
  }

  function linkedItemsSummary(document_) {
    const linkedItems = document_.linked_items || [];

    if (!linkedItems.length) {
      return '<div class="dashboard-field-hint" style="margin-bottom:6px;">Not linked to any item yet.</div>';
    }

    const labels = linkedItems.map(itemLabel).join(", ");
    return '<div style="margin-bottom:6px;"><strong>Linked to:</strong> ' + escapeHtml(labels) + '</div>';
  }

  function renderRow(document_) {
    const options = state.items.map(function (item) {
      const selected = (document_.linked_items || []).indexOf(item.name) !== -1 ? "selected" : "";
      return '<option value="' + escapeHtml(item.name) + '" ' + selected + '>' + escapeHtml(item.label) + '</option>';
    }).join("");

    return '<tr>'
      + '<td>' + escapeHtml(document_.label) + '</td>'
      + '<td>' + escapeHtml(document_.document_type) + '</td>'
      + '<td>' + escapeHtml(document_.resource_availability || "—") + '</td>'
      + '<td>'
        + linkedItemsSummary(document_)
        + '<select multiple size="4" class="dashboard-select" style="min-width:260px;" data-linked-items data-document="' + escapeHtml(document_.name) + '">'
          + options
        + '</select>'
        + '<div class="dashboard-field-hint">Ctrl/Cmd-click to select more than one. Saves automatically.</div>'
      + '</td>'
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

    body.querySelectorAll("[data-linked-items]").forEach(function (select) {
      select.addEventListener("change", function () {
        saveLinkedItems(select);
      });
    });
  }

  async function saveLinkedItems(select) {
    const documentName = select.dataset.document;
    const selectedItemCodes = Array.from(select.selectedOptions).map(function (option) {
      return option.value;
    });

    select.disabled = true;
    showMessage("Saving...");

    try {
      await apiPost(`${API}.set_workshop_resource_items`, {
        practice_document: documentName,
        item_codes: selectedItemCodes
      });

      const document_ = state.documents.find(function (d) { return d.name === documentName; });
      if (document_) document_.linked_items = selectedItemCodes;

      showMessage("Saved - coach access to this document has been updated to match.");
      renderTable(el("workshopResourcesSearch") ? el("workshopResourcesSearch").value : "");
    } catch (error) {
      showMessage(error.message || "Could not save this change.", true);
      select.disabled = false;
    }
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
