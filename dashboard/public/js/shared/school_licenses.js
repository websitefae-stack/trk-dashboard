(function () {
  "use strict";

  var el = Dashboard.el;

  const SHARED_API = "dashboard.api.shared.school_licenses";

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
    const div = document.createElement("div");
    div.textContent = value === null || value === undefined ? "" : String(value);
    return div.innerHTML;
  }

  let editingCustomer = "";

  function renderRow(row) {
    const activeBadge = row.portal_active
      ? `<span class="dashboard-badge dashboard-status-active">Active</span>`
      : `<span class="dashboard-badge">Inactive</span>`;

    const seats = row.number_of_seats
      ? `${row.seats_used} / ${row.number_of_seats}`
      : `${row.seats_used}`;

    return `
      <tr>
        <td>${escapeHtml(row.client_name)}</td>
        <td>${escapeHtml(row.account_manager || "—")}</td>
        <td>${activeBadge}</td>
        <td>${escapeHtml(row.licence_type || "—")}</td>
        <td>${escapeHtml(row.licence_start || "—")}</td>
        <td>${escapeHtml(row.licence_end || "—")}</td>
        <td>${escapeHtml(seats)}</td>
        <td>
          <button type="button" class="dashboard-btn dashboard-btn-light" data-edit-license="${escapeHtml(row.customer)}">Edit</button>
        </td>
      </tr>
    `;
  }

  let cachedLicenses = [];

  async function loadLicenses() {
    const bodyEl = el("schoolLicensesTableBody");
    try {
      const licenses = await apiPost(`${SHARED_API}.get_school_licenses`, {});
      cachedLicenses = licenses;

      bodyEl.innerHTML = licenses.length
        ? licenses.map(renderRow).join("")
        : `<tr><td colspan="8" class="dashboard-empty">No schools licensed yet.</td></tr>`;

      bodyEl.querySelectorAll("[data-edit-license]").forEach(function (button) {
        button.addEventListener("click", function () {
          openModal(button.dataset.editLicense);
        });
      });
    } catch (error) {
      bodyEl.innerHTML = `<tr><td colspan="8" class="dashboard-empty">${escapeHtml(error.message || "Could not load school licenses.")}</td></tr>`;
    }
  }

  async function populateClientSelect(selectedClient) {
    const select = el("schoolLicenseClient");
    select.innerHTML = `<option value="">Loading…</option>`;

    try {
      const options = await apiPost(`${SHARED_API}.get_school_client_options`, {});

      if (!options.length) {
        select.innerHTML = `<option value="">No School clients found</option>`;
        return;
      }

      select.innerHTML = options.map(function (option) {
        const disabled = option.already_licensed && option.name !== selectedClient ? "disabled" : "";
        const note = option.already_licensed && option.name !== selectedClient ? " (already licensed)" : "";
        return `<option value="${escapeHtml(option.name)}" ${disabled}>${escapeHtml(option.client_name)}${escapeHtml(note)}</option>`;
      }).join("");

      if (selectedClient) select.value = selectedClient;
    } catch (error) {
      select.innerHTML = `<option value="">${escapeHtml(error.message || "Could not load clients.")}</option>`;
    }
  }

  function clearForm() {
    el("schoolLicenseAccountManager").value = "";
    el("schoolLicensePortalActive").checked = true;
    el("schoolLicenseType").value = "";
    el("schoolLicenseStart").value = "";
    el("schoolLicenseEnd").value = "";
    el("schoolLicenseSeats").value = "";
    const messageEl = el("schoolLicenseModalMessage");
    if (messageEl) messageEl.textContent = "";
  }

  async function openModal(customerName) {
    editingCustomer = customerName || "";
    clearForm();

    const titleEl = el("schoolLicenseModalTitle");
    const clientSelect = el("schoolLicenseClient");

    let selectedClient = "";

    if (editingCustomer) {
      titleEl.textContent = "Edit School License";
      const existing = cachedLicenses.find(function (row) { return row.customer === editingCustomer; });
      if (existing) {
        selectedClient = existing.client;
        el("schoolLicenseAccountManager").value = existing.account_manager || "";
        el("schoolLicensePortalActive").checked = !!existing.portal_active;
        el("schoolLicenseType").value = existing.licence_type || "";
        el("schoolLicenseStart").value = existing.licence_start || "";
        el("schoolLicenseEnd").value = existing.licence_end || "";
        el("schoolLicenseSeats").value = existing.number_of_seats || "";
      }
      clientSelect.disabled = true;
    } else {
      titleEl.textContent = "Add School License";
      clientSelect.disabled = false;
    }

    await populateClientSelect(selectedClient);

    const modal = el("schoolLicenseModal");
    if (modal) modal.classList.add("is-open");
  }

  function closeModal() {
    const modal = el("schoolLicenseModal");
    if (modal) modal.classList.remove("is-open");
  }

  async function saveLicense() {
    const saveBtn = el("saveSchoolLicenseBtn");
    const messageEl = el("schoolLicenseModalMessage");
    const client = el("schoolLicenseClient").value;

    if (!client) {
      if (messageEl) messageEl.textContent = "Choose a school first.";
      return;
    }

    if (saveBtn) { saveBtn.disabled = true; saveBtn.textContent = "Saving..."; }
    if (messageEl) messageEl.textContent = "";

    try {
      await apiPost(`${SHARED_API}.save_school_license`, {
        client: client,
        account_manager: el("schoolLicenseAccountManager").value,
        portal_active: el("schoolLicensePortalActive").checked ? 1 : 0,
        licence_type: el("schoolLicenseType").value,
        licence_start: el("schoolLicenseStart").value,
        licence_end: el("schoolLicenseEnd").value,
        number_of_seats: el("schoolLicenseSeats").value,
      });

      closeModal();
      await loadLicenses();
    } catch (error) {
      if (messageEl) messageEl.textContent = error.message || "Could not save this license.";
    } finally {
      if (saveBtn) { saveBtn.disabled = false; saveBtn.textContent = "Save"; }
    }
  }

  function init() {
    if (!el("schoolLicensesTableBody")) return;

    el("addSchoolLicenseBtn")?.addEventListener("click", function () { openModal(""); });
    el("closeSchoolLicenseModal")?.addEventListener("click", closeModal);
    el("cancelSchoolLicenseModal")?.addEventListener("click", closeModal);
    el("saveSchoolLicenseBtn")?.addEventListener("click", saveLicense);

    const modal = el("schoolLicenseModal");
    if (modal) {
      modal.addEventListener("click", function (event) {
        if (event.target === modal) closeModal();
      });
    }

    loadLicenses();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
