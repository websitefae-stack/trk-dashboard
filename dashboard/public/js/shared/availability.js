(function () {
  "use strict";

  var el = Dashboard.el;

  const SHARED_API = "dashboard.api.shared.coach_availability";

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
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function showMessage(message, isError) {
    const banner = el("availabilityFormMessage");
    if (!banner) return;
    banner.textContent = message || "";
    banner.style.color = isError ? "#C01C3E" : "#258D3B";
  }

  function renderRows(rows) {
    const body = el("availabilityTableBody");
    if (!body) return;

    if (!rows || !rows.length) {
      body.innerHTML = '<tr><td colspan="6" class="dashboard-empty">No availability set yet.</td></tr>';
      return;
    }

    body.innerHTML = rows.map((row) => `
      <tr>
        <td>${escapeHtml(row.appointment_label || row.appointment_name)}</td>
        <td>${escapeHtml(row.day_of_the_week)}</td>
        <td>${escapeHtml(row.start_time)}</td>
        <td>${escapeHtml(row.end_time)}</td>
        <td>${row.active ? "Yes" : "No"}</td>
        <td class="dashboard-action-cell">
          <a class="dashboard-link-btn" href="#" data-edit-row="${escapeHtml(row.name)}">Edit</a>
          <a class="dashboard-link-btn" href="#" data-delete-row="${escapeHtml(row.name)}">Delete</a>
        </td>
      </tr>
    `).join("");

    body.querySelectorAll("[data-edit-row]").forEach((link) => {
      link.addEventListener("click", function (event) {
        event.preventDefault();
        const row = rows.find((r) => r.name === link.dataset.editRow);
        if (row) openForm(row);
      });
    });

    body.querySelectorAll("[data-delete-row]").forEach((link) => {
      link.addEventListener("click", function (event) {
        event.preventDefault();
        deleteRow(link.dataset.deleteRow);
      });
    });
  }

  async function loadRows() {
    const body = el("availabilityTableBody");
    if (!body) return;

    try {
      const rows = await apiPost(`${SHARED_API}.get_my_availability`, {});
      renderRows(rows);
    } catch (error) {
      body.innerHTML = `<tr><td colspan="6" class="dashboard-empty">${escapeHtml(error.message || "Could not load availability.")}</td></tr>`;
    }
  }

  async function loadAppointmentTypeOptions() {
    const select = el("availabilityAppointmentType");
    if (!select || select.dataset.loaded === "1") return;

    select.dataset.loaded = "1";

    try {
      const options = await apiPost(`${SHARED_API}.get_appointment_template_options`, {});
      (options || []).forEach((option) => {
        const opt = document.createElement("option");
        opt.value = option.value;
        opt.textContent = option.label;
        select.appendChild(opt);
      });
    } catch (error) {
      console.error("Could not load appointment types:", error);
    }
  }

  function openForm(row) {
    const section = el("availabilityFormSection");
    if (section) section.style.display = "";

    showMessage("");

    el("availabilityRowName").value = row ? row.name : "";
    el("availabilityAppointmentType").value = row ? row.appointment_name : "";
    el("availabilityDay").value = row ? row.day_of_the_week : "Monday";
    el("availabilityStartTime").value = row ? row.start_time : "";
    el("availabilityEndTime").value = row ? row.end_time : "";
    el("availabilityActive").checked = row ? !!row.active : true;

    const addBtn = el("addAvailabilityBtn");
    if (addBtn) addBtn.textContent = row ? "+ Add Availability" : "+ Add Availability";
  }

  function closeForm() {
    const section = el("availabilityFormSection");
    if (section) section.style.display = "none";

    const form = el("availabilityForm");
    if (form) form.reset();

    el("availabilityRowName").value = "";
  }

  async function deleteRow(rowName) {
    if (!window.confirm("Remove this availability window?")) return;

    try {
      const result = await apiPost(`${SHARED_API}.delete_availability_row`, { row_name: rowName });
      renderRows(result.rows || []);
    } catch (error) {
      showMessage(error.message || "Could not remove this row.", true);
    }
  }

  async function submitForm(event) {
    event.preventDefault();

    const rowName = el("availabilityRowName").value;
    const payload = {
      appointment_name: el("availabilityAppointmentType").value,
      day_of_the_week: el("availabilityDay").value,
      start_time: el("availabilityStartTime").value,
      end_time: el("availabilityEndTime").value,
      active: el("availabilityActive").checked ? 1 : 0,
    };

    const saveBtn = el("saveAvailabilityBtn");
    if (saveBtn) saveBtn.disabled = true;

    try {
      const method = rowName ? "update_availability_row" : "add_availability_row";
      if (rowName) payload.row_name = rowName;

      const result = await apiPost(`${SHARED_API}.${method}`, payload);
      renderRows(result.rows || []);
      closeForm();
    } catch (error) {
      showMessage(error.message || "Could not save this availability window.", true);
    } finally {
      if (saveBtn) saveBtn.disabled = false;
    }
  }

  function init() {
    const panel = el("availabilityTableBody");
    if (!panel) return;

    loadRows();
    loadAppointmentTypeOptions();

    const addBtn = el("addAvailabilityBtn");
    if (addBtn) addBtn.addEventListener("click", function () { openForm(null); });

    const cancelBtn = el("cancelAvailabilityBtn");
    if (cancelBtn) cancelBtn.addEventListener("click", closeForm);

    const form = el("availabilityForm");
    if (form) form.addEventListener("submit", submitForm);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
