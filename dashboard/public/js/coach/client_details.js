(function () {
  let editMode = false;
  let isSaving = false;
  let isAddingNote = false;

  function el(id) {
    return document.getElementById(id);
  }

  function qsa(selector) {
    return Array.from(document.querySelectorAll(selector));
  }

  function getClientName() {
    return el("clientDocname")?.value || "";
  }

  function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    if (meta) return meta.content;

    const hidden = el("csrfToken");
    return hidden ? hidden.value : "";
  }

  async function apiPost(method, args) {
    const res = await fetch(`/api/method/${method}`, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-Frappe-CSRF-Token": getCsrfToken()
      },
      body: JSON.stringify(args || {})
    });

    const data = await res.json();

    if (!res.ok || data.exc) {
      throw new Error(data.message || "Request failed");
    }

    return data.message;
  }

  function showSuccess(msg) {
    if (window.frappe?.show_alert) {
      frappe.show_alert({ message: msg, indicator: "green" });
    } else {
      console.log(msg);
    }
  }

  function showError(msg) {
    if (window.frappe?.msgprint) {
      frappe.msgprint(msg);
    } else {
      alert(msg);
    }
  }

  /* =========================
     EDIT MODE
  ========================= */

  function setFieldState(field, editing) {
    const readOnly = field.dataset.metaReadonly === "1";

    if (readOnly) {
      field.disabled = true;
      field.readOnly = true;
      return;
    }

    if (field.tagName === "SELECT" || field.type === "checkbox") {
      field.disabled = !editing;
    } else {
      field.readOnly = !editing;
    }
  }

  function applyEditMode() {
    qsa("[data-client-field='1']").forEach((f) => {
      setFieldState(f, editMode);
    });

    const btn = el("editClient");

    if (!btn) return;

    if (isSaving) {
      btn.textContent = "Saving...";
      btn.disabled = true;
    } else {
      btn.textContent = editMode ? "Save Client" : "Edit Client";
      btn.disabled = false;
    }

    document.body.classList.toggle("client-edit-mode", editMode);
  }

  function collectData() {
    const data = {};

    qsa("[data-client-field='1']").forEach((field) => {
      const name = field.dataset.fieldname;
      if (!name) return;

      if (field.type === "checkbox") {
        data[name] = field.checked ? 1 : 0;
      } else {
        data[name] = field.value;
      }
    });

    return data;
  }

  async function saveClient() {
    if (isSaving) return;

    isSaving = true;
    applyEditMode();

    try {
      await apiPost("dashboard.api.coach.client_details.save_client", {
        docname: getClientName(),
        data: JSON.stringify(collectData())
      });

      editMode = false;
      showSuccess("Client saved");
    } catch (e) {
      showError(e.message);
    }

    isSaving = false;
    applyEditMode();
  }

  function toggleEdit() {
    if (!editMode) {
      editMode = true;
      applyEditMode();
    } else {
      saveClient();
    }
  }

  /* =========================
     NOTES
  ========================= */

  async function addNote() {
    if (isAddingNote) return;

    const text = el("newClientNoteText")?.value || "";

    if (!text.trim()) {
      showError("Enter a note");
      return;
    }

    isAddingNote = true;

    try {
      await apiPost("dashboard.api.coach.client_details.add_client_note", {
        client_name: getClientName(),
        note_text: text
      });

      el("newClientNoteText").value = "";
      showSuccess("Note added");

      window.location.reload();
    } catch (e) {
      showError(e.message);
    }

    isAddingNote = false;
  }

  /* =========================
     TABS
  ========================= */

  function activateTab(id) {
    qsa(".dashboard-tab-btn").forEach((btn) => {
      btn.classList.toggle("is-active", btn.dataset.tabTarget === id);
    });

    qsa(".dashboard-tab-panel").forEach((panel) => {
      panel.classList.toggle("is-active", panel.id === id);
    });
  }

  function initTabs() {
    qsa(".dashboard-tab-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        activateTab(btn.dataset.tabTarget);
      });
    });
  }

  /* =========================
     APPOINTMENTS CLEANUP
  ========================= */

  function cleanAppointments() {
    qsa(".dashboard-client-appointment-row").forEach((row) => {
      const status = (row.dataset.appointmentStatus || "").toLowerCase();

      if (status.includes("cancel")) {
        row.remove();
      }
    });
  }

  /* =========================
     INIT
  ========================= */

  function init() {
    if (!el("clientDetailsForm")) return;

    applyEditMode();
    initTabs();
    cleanAppointments();

    el("editClient")?.addEventListener("click", (e) => {
      e.preventDefault();
      toggleEdit();
    });

    el("addClientNote")?.addEventListener("click", (e) => {
      e.preventDefault();
      addNote();
    });
  }

  document.addEventListener("DOMContentLoaded", init);
})();
