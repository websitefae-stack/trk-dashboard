(function () {
  "use strict";

  var el = Dashboard.el;

  const API = "dashboard.api.shared.school_pipeline";
  const STAGES = ["New", "In Sequence", "Idle", "Responded", "Call Booked", "Customer", "Declined"];

  let board;
  let schools = [];
  let selected = new Set();

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
      throw new Error(data.message || "There was a problem.");
    }

    return data.message;
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function renderCard(school) {
    const progress = school.active_sequence
      ? `<div class="dashboard-field-hint">${escapeHtml(school.active_sequence.sequence)} - step ${school.active_sequence.current_step}/${school.active_sequence.total_steps}</div>`
      : "";

    return `
      <div class="dashboard-lead-card dashboard-school-card" data-school="${escapeHtml(school.name)}">
        <label class="dashboard-school-card-select">
          <input type="checkbox" class="school-select-checkbox" data-school="${escapeHtml(school.name)}" ${selected.has(school.name) ? "checked" : ""}>
        </label>
        <div class="dashboard-school-card-body">
          <div class="dashboard-lead-card-client">${escapeHtml(school.school_name)}</div>
          <div class="dashboard-field-hint">${school.area ? escapeHtml(school.area) + " · " : ""}${school.contact_count} contact${school.contact_count === 1 ? "" : "s"}${school.linked_client ? " · Customer" : ""}</div>
          ${progress}
        </div>
      </div>
    `;
  }

  function getFilteredSchools() {
    const search = (el("schoolsSearchInput")?.value || "").trim().toLowerCase();
    const area = el("schoolsAreaFilter")?.value || "";
    const stage = el("schoolsStageFilter")?.value || "";

    return schools.filter((school) => {
      if (area && school.area !== area) return false;
      if (stage && school.stage !== stage) return false;

      if (search) {
        const nameMatch = (school.school_name || "").toLowerCase().includes(search);
        const contactMatch = (school.contact_names || []).some((name) => (name || "").toLowerCase().includes(search));
        if (!nameMatch && !contactMatch) return false;
      }

      return true;
    });
  }

  function populateAreaFilterOptions() {
    const select = el("schoolsAreaFilter");
    if (!select) return;

    const currentValue = select.value;
    const areas = Array.from(new Set(schools.map((s) => (s.area || "").trim()).filter(Boolean))).sort();

    select.innerHTML = '<option value="">All Areas</option>' +
      areas.map((area) => `<option value="${escapeHtml(area)}">${escapeHtml(area)}</option>`).join("");

    if (areas.includes(currentValue)) select.value = currentValue;
  }

  function render() {
    const filtered = getFilteredSchools();

    const byStage = {};
    STAGES.forEach((stage) => { byStage[stage] = []; });
    filtered.forEach((school) => {
      (byStage[school.stage] || byStage.New).push(school);
    });

    board.innerHTML = STAGES.map((stage) => `
      <div class="dashboard-lead-column">
        <div class="dashboard-lead-column-head">
          <span>${escapeHtml(stage)}</span>
          <span class="dashboard-lead-column-count">${byStage[stage].length}</span>
        </div>
        <div class="dashboard-lead-column-body">
          ${byStage[stage].length ? byStage[stage].map(renderCard).join("") : `<div class="dashboard-lead-column-empty">No schools</div>`}
        </div>
      </div>
    `).join("");

    const countEl = el("schoolsCount");
    if (countEl) {
      countEl.textContent = filtered.length === schools.length
        ? `${schools.length} school${schools.length === 1 ? "" : "s"}`
        : `${filtered.length} of ${schools.length} school${schools.length === 1 ? "" : "s"}`;
    }

    board.querySelectorAll(".dashboard-school-card").forEach((card) => {
      card.addEventListener("click", function () {
        window.location.href = `/franchisor_db/school_details?name=${encodeURIComponent(card.dataset.school)}`;
      });
    });

    board.querySelectorAll(".dashboard-school-card-select").forEach((label) => {
      // Stops a click on the checkbox from also triggering the card's own
      // click-to-navigate handler above - was an inline onclick, moved
      // here since some site CSP configurations block inline handlers
      // outright with no visible error, which is indistinguishable from
      // the checkbox silently doing nothing at all.
      label.addEventListener("click", function (event) { event.stopPropagation(); });
    });

    board.querySelectorAll(".school-select-checkbox").forEach((checkbox) => {
      checkbox.addEventListener("change", function () {
        if (checkbox.checked) selected.add(checkbox.dataset.school);
        else selected.delete(checkbox.dataset.school);
        updateBulkBar();
      });
    });
  }

  function updateBulkBar() {
    const bar = el("schoolsBulkBar");
    const countLabel = el("schoolsSelectedCount");
    if (!bar) return;

    bar.style.display = selected.size ? "flex" : "none";
    if (countLabel) countLabel.textContent = `${selected.size} selected`;
  }

  async function loadSequenceOptions() {
    const select = el("schoolsBulkSequence");
    if (!select) return;

    try {
      const sequences = await apiPost(`${API}.get_sequences`, {});
      select.innerHTML = '<option value="">Enrol in sequence…</option>' +
        sequences.filter((s) => s.is_active).map((s) => `<option value="${escapeHtml(s.name)}">${escapeHtml(s.sequence_name)}</option>`).join("");
    } catch (error) {
      // Non-fatal - the board itself still works without sequence options loaded.
    }
  }

  async function loadSchools() {
    board.innerHTML = `<div class="dashboard-empty">Loading schools…</div>`;
    try {
      schools = await apiPost(`${API}.get_school_pipeline`, {});
      populateAreaFilterOptions();
      render();
    } catch (error) {
      board.innerHTML = `<div class="dashboard-empty">${escapeHtml(error.message || "Could not load schools.")}</div>`;
    }
  }

  function bindEvents() {
  el("schoolsSearchInput")?.addEventListener("input", Dashboard.debounce(render, 200));
  el("schoolsAreaFilter")?.addEventListener("change", render);
  el("schoolsStageFilter")?.addEventListener("change", render);
  el("schoolsFilterClear")?.addEventListener("click", function () {
    if (el("schoolsSearchInput")) el("schoolsSearchInput").value = "";
    if (el("schoolsAreaFilter")) el("schoolsAreaFilter").value = "";
    if (el("schoolsStageFilter")) el("schoolsStageFilter").value = "";
    render();
  });

  el("schoolsBulkEnroll")?.addEventListener("click", async function () {
    const sequence = el("schoolsBulkSequence")?.value;
    const startDate = el("schoolsBulkStartDate")?.value;

    if (!sequence) {
      alert("Choose a sequence first.");
      return;
    }
    if (!selected.size) return;

    try {
      const result = await apiPost(`${API}.enroll_schools`, {
        school_names: Array.from(selected),
        sequence,
        start_date: startDate || undefined,
      });
      let message = `Enrolled ${result.enrolled.length} school(s).`;
      if (result.skipped.length) message += ` ${result.skipped.length} already had an active sequence and were skipped.`;
      alert(message);
      selected.clear();
      await loadSchools();
      updateBulkBar();
    } catch (error) {
      alert(error.message || "Could not enrol the selected schools.");
    }
  });

  el("schoolsBulkMove")?.addEventListener("click", async function () {
    const stage = el("schoolsBulkStage")?.value;
    if (!stage || !selected.size) return;

    try {
      for (const schoolName of selected) {
        await apiPost(`${API}.set_school_stage`, { school: schoolName, stage });
      }
      selected.clear();
      await loadSchools();
      updateBulkBar();
    } catch (error) {
      alert(error.message || "Could not move the selected schools.");
    }
  });

  el("schoolsBulkClear")?.addEventListener("click", function () {
    selected.clear();
    render();
    updateBulkBar();
  });

  // ---------- Add School modal ----------

  function contactRowHtml(index) {
    return `
      <div class="dashboard-school-contact-row" data-row="${index}">
        <input type="text" class="dashboard-input school-contact-name" placeholder="Name">
        <select class="dashboard-select school-contact-role">
          <option value="">Role</option>
          <option value="SENCO">SENCO</option>
          <option value="Head">Head</option>
          <option value="Deputy Head">Deputy Head</option>
          <option value="Reception">Reception</option>
          <option value="Other">Other</option>
        </select>
        <input type="email" class="dashboard-input school-contact-email" placeholder="Email">
        <button type="button" class="dashboard-btn dashboard-btn-light school-contact-remove">Remove</button>
      </div>
    `;
  }

  let contactRowCount = 0;

  function addContactRow() {
    const wrap = el("newSchoolContacts");
    if (!wrap) return;
    wrap.insertAdjacentHTML("beforeend", contactRowHtml(contactRowCount++));
    wrap.querySelectorAll(".school-contact-remove").forEach((btn) => {
      btn.onclick = function () { btn.closest(".dashboard-school-contact-row")?.remove(); };
    });
  }

  function openAddSchoolModal() {
    const modal = el("addSchoolModal");
    if (!modal) return;

    if (el("newSchoolName")) el("newSchoolName").value = "";
    if (el("newSchoolWebsite")) el("newSchoolWebsite").value = "";
    if (el("newSchoolArea")) el("newSchoolArea").value = "";
    if (el("newSchoolContacts")) el("newSchoolContacts").innerHTML = "";
    contactRowCount = 0;
    addContactRow();

    modal.classList.add("is-open");
  }

  function closeAddSchoolModal() {
    el("addSchoolModal")?.classList.remove("is-open");
  }

  el("addSchoolBtn")?.addEventListener("click", openAddSchoolModal);
  el("closeAddSchoolModal")?.addEventListener("click", closeAddSchoolModal);
  el("cancelAddSchoolModal")?.addEventListener("click", closeAddSchoolModal);
  el("addSchoolContactRow")?.addEventListener("click", addContactRow);

  el("saveNewSchool")?.addEventListener("click", async function () {
    const schoolName = (el("newSchoolName")?.value || "").trim();
    if (!schoolName) {
      alert("School name is required.");
      return;
    }

    const contacts = Array.from(document.querySelectorAll(".dashboard-school-contact-row")).map((row) => ({
      contact_name: row.querySelector(".school-contact-name")?.value.trim() || "",
      role: row.querySelector(".school-contact-role")?.value || "",
      email: row.querySelector(".school-contact-email")?.value.trim() || "",
    })).filter((c) => c.contact_name && c.email);

    try {
      await apiPost(`${API}.save_school`, {
        data: JSON.stringify({
          school_name: schoolName,
          website: el("newSchoolWebsite")?.value.trim() || "",
          area: el("newSchoolArea")?.value.trim() || "",
          contacts,
        }),
      });
      closeAddSchoolModal();
      await loadSchools();
    } catch (error) {
      alert(error.message || "Could not save this school.");
    }
  });

  // ---------- Import Schools modal ----------

  function openImportSchoolsModal() {
    const modal = el("importSchoolsModal");
    if (!modal) return;

    if (el("importSchoolsFile")) el("importSchoolsFile").value = "";
    if (el("importSchoolsResult")) el("importSchoolsResult").innerHTML = "";

    modal.classList.add("is-open");
  }

  function closeImportSchoolsModal() {
    el("importSchoolsModal")?.classList.remove("is-open");
  }

  el("importSchoolsBtn")?.addEventListener("click", openImportSchoolsModal);
  el("closeImportSchoolsModal")?.addEventListener("click", closeImportSchoolsModal);
  el("cancelImportSchoolsModal")?.addEventListener("click", closeImportSchoolsModal);

  el("runImportSchools")?.addEventListener("click", async function () {
    const fileInput = el("importSchoolsFile");
    const resultBox = el("importSchoolsResult");
    const file = fileInput?.files?.[0];

    if (!file) {
      alert("Choose a CSV file first.");
      return;
    }

    const btn = el("runImportSchools");
    const originalLabel = btn.textContent;
    btn.disabled = true;
    btn.textContent = "Importing…";
    if (resultBox) resultBox.innerHTML = "";

    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await fetch(`/api/method/${API}.import_schools_from_csv`, {
        method: "POST",
        credentials: "same-origin",
        headers: { "X-Frappe-CSRF-Token": getCsrfToken() },
        body: formData,
      });
      const data = await response.json();
      if (!response.ok || data.exc) {
        throw new Error(data.message || "Could not import this file.");
      }

      const result = data.message;
      const errorsHtml = result.row_errors && result.row_errors.length
        ? `<div class="dashboard-field-hint" style="margin-top:8px; color:#B3261E;">${result.row_errors.map(escapeHtml).join("<br>")}</div>`
        : "";

      if (resultBox) {
        resultBox.innerHTML = `
          <div class="dashboard-field-hint">
            ${result.schools_created} school(s) created, ${result.schools_updated} existing school(s) updated,
            ${result.contacts_added} contact(s) added${result.contacts_skipped_duplicate ? `, ${result.contacts_skipped_duplicate} contact(s) skipped (already existed)` : ""}.
          </div>
          ${errorsHtml}
        `;
      }

      await loadSchools();
    } catch (error) {
      if (resultBox) resultBox.innerHTML = `<div class="dashboard-field-hint" style="color:#B3261E;">${escapeHtml(error.message || "Could not import this file.")}</div>`;
    } finally {
      btn.disabled = false;
      btn.textContent = originalLabel;
    }
  });
  } // end bindEvents

  function init() {
    board = el("schoolsBoard");
    if (!board) return;

    bindEvents();
    loadSchools();
    loadSequenceOptions();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
