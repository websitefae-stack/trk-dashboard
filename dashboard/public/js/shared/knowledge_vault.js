(function () {
  "use strict";

  var el = Dashboard.el;

  const SHARED_API = "dashboard.api.shared.knowledge_vault";

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
      throw new Error(Dashboard.extractErrorMessage(data, "There was a problem saving."));
    }

    return data.message || {};
  }

  function escapeHtml(value) {
    const div = document.createElement("div");
    div.textContent = value === null || value === undefined ? "" : String(value);
    return div.innerHTML;
  }

  let cachedResources = [];
  let cachedOptions = { role_options: [], year_group_options: [], resource_type_options: [] };
  let cachedSchools = [];
  let editingName = "";

  function renderForList(list) {
    return list && list.length ? list.join(", ") : "All";
  }

  function renderRow(row) {
    const forText = [renderForList(row.target_roles), renderForList(row.target_year_groups)]
      .map(function (part, index) { return (index === 0 ? "Roles: " : "Years: ") + part; })
      .join(" · ");

    const activeBadge = row.is_active
      ? `<span class="dashboard-badge dashboard-status-active">Active</span>`
      : `<span class="dashboard-badge">Inactive</span>`;

    return `
      <tr>
        <td>${escapeHtml(row.title)}</td>
        <td>${escapeHtml(row.resource_type || "—")}</td>
        <td style="font-size:12px; color:#666;">${escapeHtml(forText)}</td>
        <td>${row.allocated_school_count}</td>
        <td>${activeBadge}</td>
        <td>
          <button type="button" class="dashboard-btn dashboard-btn-light" data-edit-kv="${escapeHtml(row.name)}">Edit</button>
          <button type="button" class="dashboard-link-btn" style="color:#C01C3E;" data-delete-kv="${escapeHtml(row.name)}">Delete</button>
        </td>
      </tr>
    `;
  }

  async function loadResources() {
    const bodyEl = el("kvResourceTableBody");
    try {
      cachedResources = await apiPost(`${SHARED_API}.get_knowledge_vault_resources`, {});

      bodyEl.innerHTML = cachedResources.length
        ? cachedResources.map(renderRow).join("")
        : `<tr><td colspan="6" class="dashboard-empty">No resources yet.</td></tr>`;

      bodyEl.querySelectorAll("[data-edit-kv]").forEach(function (button) {
        button.addEventListener("click", function () { openModal(button.dataset.editKv); });
      });

      bodyEl.querySelectorAll("[data-delete-kv]").forEach(function (button) {
        button.addEventListener("click", function () { deleteResource(button.dataset.deleteKv); });
      });
    } catch (error) {
      bodyEl.innerHTML = `<tr><td colspan="6" class="dashboard-empty">${escapeHtml(error.message || "Could not load resources.")}</td></tr>`;
    }
  }

  async function deleteResource(name) {
    if (!window.confirm("Delete this resource? This can't be undone.")) return;

    try {
      await apiPost(`${SHARED_API}.delete_knowledge_vault_resource`, { name: name });
      await loadResources();
    } catch (error) {
      window.alert(error.message || "Could not delete this resource.");
    }
  }

  function checkboxListHtml(name, options, selected) {
    return labeledCheckboxListHtml(name, options.map(function (option) {
      return { value: option, label: option };
    }), selected);
  }

  function labeledCheckboxListHtml(name, items, selected) {
    return items.map(function (item) {
      const checked = selected.indexOf(item.value) !== -1 ? "checked" : "";
      const id = name + "_" + item.value.replace(/[^a-zA-Z0-9]/g, "_");
      return `
        <label style="display:flex; align-items:center; gap:6px; font-size:13px; cursor:pointer;">
          <input type="checkbox" data-${name}-option value="${escapeHtml(item.value)}" id="${escapeHtml(id)}" ${checked}>
          ${escapeHtml(item.label)}
        </label>
      `;
    }).join("");
  }

  function getCheckedValues(containerSelector) {
    return Array.prototype.map.call(
      document.querySelectorAll(containerSelector + ":checked"),
      function (input) { return input.value; }
    );
  }

  async function ensureOptionsLoaded() {
    if (cachedOptions.resource_type_options.length) return;

    cachedOptions = await apiPost(`${SHARED_API}.get_knowledge_vault_options`, {});
    cachedSchools = await apiPost(`${SHARED_API}.get_knowledge_vault_school_options`, {});

    const typeSelect = el("kvResourceType");
    if (typeSelect) {
      typeSelect.innerHTML = cachedOptions.resource_type_options.map(function (option) {
        return `<option value="${escapeHtml(option)}">${escapeHtml(option)}</option>`;
      }).join("");
    }
  }

  function clearForm() {
    el("kvTitle").value = "";
    el("kvDescription").value = "";
    el("kvVideoUrl").value = "";
    el("kvTextContent").value = "";
    el("kvIsActive").checked = true;
    el("kvFileInput").value = "";
    el("kvCurrentFile").textContent = "";
    const messageEl = el("kvResourceModalMessage");
    if (messageEl) messageEl.textContent = "";
  }

  async function openModal(name) {
    editingName = name || "";
    clearForm();

    await ensureOptionsLoaded();

    const titleEl = el("kvResourceModalTitle");
    let resource = null;

    if (editingName) {
      titleEl.textContent = "Edit Resource";
      // Autoincrement-named doctype - doc.name comes back from the API as
      // a JSON number, while editingName (read off a button's dataset)
      // is always a string. A strict === here silently never matched
      // anything, so Edit always opened a blank "Add" form instead -
      // confirmed live.
      resource = cachedResources.find(function (row) { return String(row.name) === String(editingName); }) || null;
    } else {
      titleEl.textContent = "Add Resource";
    }

    if (resource) {
      el("kvTitle").value = resource.title || "";
      el("kvDescription").value = resource.description || "";
      el("kvResourceType").value = resource.resource_type || "Video";
      el("kvVideoUrl").value = resource.video_url || "";
      el("kvTextContent").value = resource.text_content || "";
      el("kvIsActive").checked = !!resource.is_active;
      if (resource.file) {
        el("kvCurrentFile").innerHTML = `Current file: <a href="${escapeHtml(resource.file)}" target="_blank" rel="noopener">${escapeHtml(resource.file)}</a> (choose a new file above to replace it)`;
      }
    }

    el("kvRoleCheckboxes").innerHTML = checkboxListHtml("kv-role", cachedOptions.role_options, resource ? resource.target_roles : []);
    el("kvYearGroupCheckboxes").innerHTML = checkboxListHtml("kv-yeargroup", cachedOptions.year_group_options, resource ? resource.target_year_groups : []);

    el("kvSchoolCheckboxes").innerHTML = cachedSchools.length
      ? labeledCheckboxListHtml(
          "kv-school",
          cachedSchools.map(function (s) { return { value: s.customer, label: s.label }; }),
          resource ? resource.allocated_schools : []
        )
      : `<span class="dashboard-help">No schools have a license yet.</span>`;

    const modal = el("kvResourceModal");
    if (modal) modal.classList.add("is-open");
  }

  function closeModal() {
    const modal = el("kvResourceModal");
    if (modal) modal.classList.remove("is-open");
  }

  async function uploadFileIfNeeded(resourceName) {
    const fileInput = el("kvFileInput");
    if (!fileInput || !fileInput.files || !fileInput.files[0]) return;

    const formData = new FormData();
    formData.append("file", fileInput.files[0]);
    formData.append("name", resourceName);

    const response = await fetch(`/api/method/${SHARED_API}.upload_knowledge_vault_resource_file`, {
      method: "POST",
      credentials: "same-origin",
      headers: { "X-Frappe-CSRF-Token": getCsrfToken() },
      body: formData,
    });

    const data = await response.json();
    if (!response.ok || data.exc) {
      throw new Error(Dashboard.extractErrorMessage(data, "Could not upload the file."));
    }
  }

  async function saveResource() {
    const saveBtn = el("saveKvResourceBtn");
    const messageEl = el("kvResourceModalMessage");
    const title = el("kvTitle").value.trim();

    if (!title) {
      if (messageEl) messageEl.textContent = "Please enter a title.";
      return;
    }

    if (saveBtn) { saveBtn.disabled = true; saveBtn.textContent = "Saving..."; }
    if (messageEl) messageEl.textContent = "";

    try {
      const result = await apiPost(`${SHARED_API}.save_knowledge_vault_resource`, {
        name: editingName,
        title: title,
        description: el("kvDescription").value,
        resource_type: el("kvResourceType").value,
        video_url: el("kvVideoUrl").value,
        text_content: el("kvTextContent").value,
        is_active: el("kvIsActive").checked ? 1 : 0,
        target_roles: JSON.stringify(getCheckedValues("[data-kv-role-option]")),
        target_year_groups: JSON.stringify(getCheckedValues("[data-kv-yeargroup-option]")),
        allocated_schools: JSON.stringify(getCheckedValues("[data-kv-school-option]")),
      });

      await uploadFileIfNeeded(result.name);

      closeModal();
      await loadResources();
    } catch (error) {
      if (messageEl) messageEl.textContent = error.message || "Could not save this resource.";
    } finally {
      if (saveBtn) { saveBtn.disabled = false; saveBtn.textContent = "Save"; }
    }
  }

  function init() {
    if (!el("kvResourceTableBody")) return;

    el("addKvResourceBtn")?.addEventListener("click", function () { openModal(""); });
    el("closeKvResourceModal")?.addEventListener("click", closeModal);
    el("cancelKvResourceModal")?.addEventListener("click", closeModal);
    el("saveKvResourceBtn")?.addEventListener("click", saveResource);

    const modal = el("kvResourceModal");
    if (modal) {
      modal.addEventListener("click", function (event) {
        if (event.target === modal) closeModal();
      });
    }

    loadResources();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
