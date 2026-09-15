(function () {
  "use strict";

  var el = Dashboard.el;

  const API = "dashboard.api.shared.school_pipeline";
  const TEMPLATE_API = "dashboard.api.shared.email_templates.get_email_template_options";

  let templateOptions = [];

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

  // ---------- List ----------

  async function loadSequenceList() {
    const body = el("sequenceListBody");
    if (!body) return;

    try {
      const sequences = await apiPost(`${API}.get_sequences`, {});

      if (!sequences.length) {
        body.innerHTML = `<tr><td colspan="4" class="dashboard-empty">No sequences yet.</td></tr>`;
        return;
      }

      body.innerHTML = sequences.map((s) => `
        <tr>
          <td>${escapeHtml(s.sequence_name)}</td>
          <td>${s.is_active ? "Yes" : "No"}</td>
          <td>${s.step_count}</td>
          <td class="dashboard-action-cell">
            <button type="button" class="dashboard-link-btn sequence-edit-btn" data-name="${escapeHtml(s.name)}">Edit</button>
          </td>
        </tr>
      `).join("");

      body.querySelectorAll(".sequence-edit-btn").forEach((btn) => {
        btn.addEventListener("click", function () { openEditor(btn.dataset.name); });
      });
    } catch (error) {
      body.innerHTML = `<tr><td colspan="4" class="dashboard-empty">${escapeHtml(error.message || "Could not load sequences.")}</td></tr>`;
    }
  }

  // ---------- Steps ----------

  function templateOptionsHtml(selected) {
    return `<option value="">— write a new email below —</option>` +
      templateOptions.map((t) => `<option value="${escapeHtml(t.value)}" ${t.value === selected ? "selected" : ""}>${escapeHtml(t.label)}</option>`).join("");
  }

  function stepRowHtml(step) {
    step = step || {};
    return `
      <div class="dashboard-detail-section" style="background:#F2F8F8; padding:12px; border-radius:10px; margin-bottom:10px;">
        <div style="display:flex; gap:10px; align-items:center; margin-bottom:8px;">
          <label style="white-space:nowrap;">Days after previous step</label>
          <input type="number" min="0" class="dashboard-input step-delay-days" value="${step.delay_days ?? 0}" style="width:100px;">
          <button type="button" class="dashboard-btn dashboard-btn-light step-remove-btn" style="margin-left:auto;">Remove Step</button>
        </div>

        <label>Use an existing Email Template</label>
        <select class="dashboard-select step-template-select">${templateOptionsHtml(step.email_template)}</select>

        <div class="dashboard-field-hint" style="margin:6px 0;">Or write this step's email from scratch:</div>

        <label>Subject</label>
        <input type="text" class="dashboard-input step-subject" value="${escapeHtml(step.subject || "")}">

        <label style="margin-top:8px;">Message</label>
        <textarea class="dashboard-input step-message" rows="4">${escapeHtml(step.message || "")}</textarea>
      </div>
    `;
  }

  function wireStepRemoveButtons() {
    document.querySelectorAll(".step-remove-btn").forEach((btn) => {
      btn.onclick = function () { btn.closest(".dashboard-detail-section")?.remove(); };
    });
  }

  function addStepRow(step) {
    const wrap = el("sequenceStepsList");
    if (!wrap) return;
    wrap.insertAdjacentHTML("beforeend", stepRowHtml(step));
    wireStepRemoveButtons();
  }

  function readSteps() {
    return Array.from(document.querySelectorAll("#sequenceStepsList > .dashboard-detail-section")).map((row) => ({
      delay_days: parseInt(row.querySelector(".step-delay-days")?.value || "0", 10) || 0,
      email_template: row.querySelector(".step-template-select")?.value || "",
      subject: row.querySelector(".step-subject")?.value.trim() || "",
      message: row.querySelector(".step-message")?.value || "",
    }));
  }

  // ---------- Editor ----------

  function showEditor(show) {
    if (el("sequenceEditorCard")) el("sequenceEditorCard").style.display = show ? "block" : "none";
    if (el("sequenceListCard")) el("sequenceListCard").style.display = show ? "none" : "block";
  }

  async function openEditor(name) {
    showEditor(true);
    if (el("sequenceEditorTitle")) el("sequenceEditorTitle").textContent = name ? "Edit Sequence" : "New Sequence";
    if (el("sequenceDocname")) el("sequenceDocname").value = name || "";
    if (el("sequenceNameInput")) { el("sequenceNameInput").value = ""; el("sequenceNameInput").disabled = !!name; }
    if (el("sequenceDescriptionInput")) el("sequenceDescriptionInput").value = "";
    if (el("sequenceActiveInput")) el("sequenceActiveInput").checked = true;
    if (el("sequenceStepsList")) el("sequenceStepsList").innerHTML = "";

    if (!name) {
      addStepRow({});
      return;
    }

    try {
      const sequence = await apiPost(`${API}.get_sequence`, { name });
      if (el("sequenceNameInput")) el("sequenceNameInput").value = sequence.sequence_name;
      if (el("sequenceDescriptionInput")) el("sequenceDescriptionInput").value = sequence.description || "";
      if (el("sequenceActiveInput")) el("sequenceActiveInput").checked = !!sequence.is_active;

      (sequence.steps || []).forEach(addStepRow);
      if (!sequence.steps || !sequence.steps.length) addStepRow({});
    } catch (error) {
      alert(error.message || "Could not load this sequence.");
      showEditor(false);
    }
  }

  async function saveSequence() {
    const sequenceName = el("sequenceNameInput")?.value.trim();
    if (!sequenceName) {
      alert("Sequence name is required.");
      return;
    }

    const steps = readSteps();
    if (!steps.length) {
      alert("Add at least one step.");
      return;
    }

    try {
      await apiPost(`${API}.save_sequence`, {
        docname: el("sequenceDocname")?.value || undefined,
        data: JSON.stringify({
          sequence_name: sequenceName,
          description: el("sequenceDescriptionInput")?.value || "",
          is_active: el("sequenceActiveInput")?.checked ? 1 : 0,
          steps,
        }),
      });
      showEditor(false);
      await loadSequenceList();
    } catch (error) {
      alert(error.message || "Could not save this sequence.");
    }
  }

  async function loadTemplateOptions() {
    try {
      templateOptions = await apiPost(TEMPLATE_API, {});
    } catch (error) {
      templateOptions = [];
    }
  }

  // ---------- Event bindings ----------

  function bindEvents() {
    el("addStepBtn")?.addEventListener("click", function () { addStepRow({}); });
    el("newSequenceBtn")?.addEventListener("click", function () { openEditor(null); });
    el("cancelSequenceEdit")?.addEventListener("click", function () { showEditor(false); });
    el("saveSequenceBtn")?.addEventListener("click", saveSequence);
  }

  async function init() {
    const listCard = el("sequenceListCard");
    if (!listCard) return;

    bindEvents();
    await loadTemplateOptions();
    await loadSequenceList();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
