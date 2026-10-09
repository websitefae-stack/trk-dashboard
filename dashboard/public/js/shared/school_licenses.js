(function () {
  "use strict";

  var el = Dashboard.el;

  const SHARED_API = "dashboard.api.shared.school_licenses";
  const SCHOOL_API = "school_dashboard.api.school";

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
  let editingExistingContactEmail = "";

  function renderRow(row) {
    const activeBadge = row.portal_active
      ? `<span class="dashboard-badge dashboard-status-active">Active</span>`
      : `<span class="dashboard-badge">Inactive</span>`;

    const seats = row.number_of_seats
      ? `${row.seats_used} / ${row.number_of_seats}`
      : `${row.seats_used}`;

    const contactStatusBadge = row.primary_contact_status === "Active"
      ? `<span class="dashboard-badge dashboard-status-active">Active</span>`
      : row.primary_contact_status === "Invited"
        ? `<span class="dashboard-badge dashboard-status-unread">Invited</span>`
        : "";

    const resetLabel = row.primary_contact_status === "Active" ? "Reset Login" : "Send Login";

    const contactCell = row.primary_contact_email
      ? `${escapeHtml(row.primary_contact_email)} ${contactStatusBadge}<br>
         <button type="button" class="dashboard-link-btn" data-reset-login="${escapeHtml(row.customer)}" data-contact-email="${escapeHtml(row.primary_contact_email)}" data-contact-status="${escapeHtml(row.primary_contact_status)}">${resetLabel}</button>`
      : `<span class="dashboard-empty">None yet</span>`;

    return `
      <tr>
        <td>${escapeHtml(row.client_name)}</td>
        <td>${escapeHtml(row.account_manager || "—")}</td>
        <td>${contactCell}</td>
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
        : `<tr><td colspan="9" class="dashboard-empty">No schools licensed yet.</td></tr>`;

      bodyEl.querySelectorAll("[data-edit-license]").forEach(function (button) {
        button.addEventListener("click", function () {
          openModal(button.dataset.editLicense);
        });
      });

      bodyEl.querySelectorAll("[data-reset-login]").forEach(function (button) {
        button.addEventListener("click", function () {
          resetLogin(button.dataset.resetLogin, button.dataset.contactEmail, button.dataset.contactStatus, button);
        });
      });
    } catch (error) {
      bodyEl.innerHTML = `<tr><td colspan="9" class="dashboard-empty">${escapeHtml(error.message || "Could not load school licenses.")}</td></tr>`;
    }
  }

  async function resetLogin(customerName, email, status, button) {
    if (!email) return;

    const confirmMessage = status === "Active"
      ? `Send a password reset email to ${email}?`
      : `Send/resend a login invite to ${email}?`;
    if (!window.confirm(confirmMessage)) return;

    if (button) { button.disabled = true; button.textContent = "Sending..."; }

    try {
      if (status === "Active") {
        await apiPost("frappe.core.doctype.user.user.reset_password", { user: email });
      } else {
        await apiPost(`${SCHOOL_API}.invite_first_school_contact`, { organisation: customerName, email: email });
      }
      window.alert("Sent.");
    } catch (error) {
      window.alert(error.message || "Could not send this.");
    } finally {
      if (button) { button.disabled = false; button.textContent = status === "Active" ? "Reset Login" : "Send Login"; }
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
    el("schoolLicensePrimaryContact").value = "";
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
    const contactHelp = el("schoolLicensePrimaryContactHelp");
    editingExistingContactEmail = "";

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
        editingExistingContactEmail = existing.primary_contact_email || "";
        el("schoolLicensePrimaryContact").value = editingExistingContactEmail;
      }
      clientSelect.disabled = true;
      if (contactHelp) {
        contactHelp.textContent = editingExistingContactEmail
          ? "Currently invited: " + editingExistingContactEmail + ". Change this and save to invite someone new instead (e.g. if the primary contact has left) - leave as-is to keep them."
          : "No primary contact yet - enter an email and save to send them a login invite.";
      }
    } else {
      titleEl.textContent = "Add School License";
      clientSelect.disabled = false;
      if (contactHelp) {
        contactHelp.textContent = "The first person at the school who'll get a login - they can then invite their own colleagues. Leave blank to skip for now.";
      }
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
      const contactEmailInput = el("schoolLicensePrimaryContact").value.trim();
      const contactEmail = contactEmailInput && contactEmailInput !== editingExistingContactEmail
        ? contactEmailInput
        : "";

      const result = await apiPost(`${SHARED_API}.save_school_license`, {
        client: client,
        account_manager: el("schoolLicenseAccountManager").value,
        portal_active: el("schoolLicensePortalActive").checked ? 1 : 0,
        licence_type: el("schoolLicenseType").value,
        licence_start: el("schoolLicenseStart").value,
        licence_end: el("schoolLicenseEnd").value,
        number_of_seats: el("schoolLicenseSeats").value,
      });

      if (contactEmail && result.customer) {
        try {
          await apiPost(`${SCHOOL_API}.invite_first_school_contact`, {
            organisation: result.customer,
            email: contactEmail,
          });
        } catch (inviteError) {
          window.alert(
            "The license was saved, but the login invite could not be sent: " +
            (inviteError.message || "unknown error") +
            ". Use the Send Login button in the table to try again."
          );
        }
      }

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
