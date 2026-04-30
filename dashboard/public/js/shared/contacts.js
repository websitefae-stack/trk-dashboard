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

    const visible = qsa(".dashboard-contact-row").filter((row) => {
      return row.style.display !== "none";
    }).length;

    countEl.textContent = `${visible} contact${visible === 1 ? "" : "s"}`;
  }

  function rowMatches(row, search) {
    const haystack = [
      row.dataset.name || "",
      row.dataset.email || "",
      row.dataset.mobile || "",
      row.dataset.company || "",
      row.dataset.designation || "",
      row.dataset.linkedClients || "",
      row.dataset.coach || ""
    ].join(" ").toLowerCase();

    return !search || haystack.includes(search);
  }

  function renderFilters() {
    const search = (el("contactSearch")?.value || "").trim().toLowerCase();

    qsa(".dashboard-contact-row").forEach((row) => {
      row.style.display = rowMatches(row, search) ? "" : "none";
    });

    updateContactCount();
  }

  function init() {
    if (!el("contactTable") && !el("refreshContacts")) return;

    const searchField = el("contactSearch");
    if (searchField) {
      searchField.addEventListener("input", renderFilters);
    }

    const refreshBtn = el("refreshContacts");
    if (refreshBtn) {
      refreshBtn.addEventListener("click", function () {
        window.location.reload();
      });
    }

    const addBtn = el("addContact");
    if (addBtn) {
      addBtn.addEventListener("click", function () {
        const url = addBtn.dataset.url || "/coach_db/contact_details?new=1";
        window.location.href = url;
      });
    }

    const contactScopeFilter = el("contactScopeFilter");
    if (contactScopeFilter) {
      contactScopeFilter.addEventListener("change", function () {
        const scope = encodeURIComponent(contactScopeFilter.value || "my");
        window.location.href = `/franchisor_db/contacts?contact_scope=${scope}`;
      });
    }

    renderFilters();
    updateContactCount();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
