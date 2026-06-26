(function () {
  function el(id) {
    return document.getElementById(id);
  }

  function qsa(selector, root) {
    return Array.from((root || document).querySelectorAll(selector));
  }

  function updateContactCount() {
    const countEl = el("contactCount");
    if (!countEl) return;

    const visible = qsa(".dashboard-contact-row").filter(function (row) {
      return row.style.display !== "none";
    }).length;

    countEl.textContent = visible + " contact" + (visible === 1 ? "" : "s");
  }

  function getFilterValue(id, fallback) {
    const field = el(id);
    return field ? field.value || fallback || "" : fallback || "";
  }

  function rowMatches(row, search) {
    const haystack = [
      row.dataset.name || "",
      row.dataset.email || "",
      row.dataset.mobile || "",
      row.dataset.company || "",
      row.dataset.designation || "",
      row.dataset.linkedClients || "",
      row.dataset.coach || "",
      row.dataset.sessionWorker || ""
    ].join(" ").toLowerCase();

    const sessionWorkerFilter = getFilterValue("contactSessionWorkerFilter", "All");

    if (search && !haystack.includes(search)) {
      return false;
    }

    if (
      sessionWorkerFilter !== "All" &&
      (row.dataset.sessionWorker || "") !== sessionWorkerFilter
    ) {
      return false;
    }

    return true;
  }

  function renderFilters() {
    const search = (getFilterValue("contactSearch", "") || "").trim().toLowerCase();

    qsa(".dashboard-contact-row").forEach(function (row) {
      row.style.display = rowMatches(row, search) ? "" : "none";
    });

    updateContactCount();
  }

    function debounce(fn, wait) {
    let timer = null;

    return function () {
      const args = arguments;

      clearTimeout(timer);
      timer = setTimeout(function () {
        fn.apply(null, args);
      }, wait || 500);
    };
  }

  function runServerContactSearch() {
    const searchField = el("contactSearch");
    const params = new URLSearchParams(window.location.search);
    const searchValue = searchField ? searchField.value.trim() : "";

    if (searchValue) {
      params.set("search", searchValue);
    } else {
      params.delete("search");
    }

    params.set("page", "1");

    window.location.href = window.location.pathname + "?" + params.toString();
  }

  function initSearchFilter() {
    const searchField = el("contactSearch");

    if (searchField && searchField.dataset.contactsSearchBound !== "1") {
      searchField.dataset.contactsSearchBound = "1";
      searchField.addEventListener("input", debounce(runServerContactSearch, 500));
    }
  }

  function initSessionWorkerFilter() {
    const sessionWorkerField = el("contactSessionWorkerFilter");

    if (sessionWorkerField && sessionWorkerField.dataset.contactsSessionWorkerBound !== "1") {
      sessionWorkerField.dataset.contactsSessionWorkerBound = "1";
      sessionWorkerField.addEventListener("change", renderFilters);
    }
  }

  function initRefreshButton() {
    const refreshBtn = el("refreshContacts");

    if (refreshBtn && refreshBtn.dataset.contactsRefreshBound !== "1") {
      refreshBtn.dataset.contactsRefreshBound = "1";
      refreshBtn.addEventListener("click", function () {
        window.location.reload();
      });
    }
  }

  function initAddButton() {
    const addBtn = el("addContact");

    if (addBtn && addBtn.dataset.contactsAddBound !== "1") {
      addBtn.dataset.contactsAddBound = "1";
      addBtn.addEventListener("click", function () {
        const url = addBtn.dataset.url || addBtn.dataset.addContactUrl || "/coach_db/contact_details?new=1";
        window.location.href = url;
      });
    }
  }

  function initScopeFilter() {
    const contactScopeFilter = el("contactScopeFilter");

    if (contactScopeFilter && contactScopeFilter.dataset.contactsScopeBound !== "1") {
      contactScopeFilter.dataset.contactsScopeBound = "1";
      contactScopeFilter.addEventListener("change", function () {
        const scope = encodeURIComponent(contactScopeFilter.value || "my");
        window.location.href = "/franchisor_db/contacts?contact_scope=" + scope;
      });
    }
  }

  function initUnauthorisedContacts() {
    qsa(".dashboard-contact-unauthorised").forEach(function (button) {
      if (button.dataset.contactUnauthorisedBound === "1") return;

      button.dataset.contactUnauthorisedBound = "1";

      button.addEventListener("click", function (event) {
        event.preventDefault();
        event.stopPropagation();

        alert("You are not authorised to view this contact.");
      });
    });
  }

  function initContactsPage() {
    if (!el("contactTable") && !el("refreshContacts")) return;

    initSearchFilter();
    initSessionWorkerFilter();
    initRefreshButton();
    initAddButton();
    initScopeFilter();
    initUnauthorisedContacts();

    renderFilters();
    updateContactCount();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initContactsPage);
  } else {
    initContactsPage();
  }
})();
