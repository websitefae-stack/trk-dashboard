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

  function isNewClientPage() {
    const params = new URLSearchParams(window.location.search);
    return params.get("new") === "1" || !getClientName();
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

    btn.classList.toggle("is-save-mode", editMode);
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

  function getOptionLabel(row) {
    return row.coach_name || row.sw_name || row.customer_name || row.item_name || row.name || "";
  }

  async function loadLinkOptions(select) {
    if (!select || select.dataset.optionsLoaded === "1") return;

    const doctype = select.dataset.linkDoctype;
    if (!doctype) return;

    const currentValue = select.dataset.currentValue || select.value || "";

    try {
      const options = await apiPost("dashboard.api.coach.client_details.get_link_options", {
        doctype: doctype,
        limit_page_length: 500
      });

      const values = Array.isArray(options) ? options : [];

      select.innerHTML = '<option value=""></option>';

      if (currentValue && !values.some((row) => row.name === currentValue)) {
        const option = document.createElement("option");
        option.value = currentValue;
        option.textContent = currentValue;
        option.selected = true;
        select.appendChild(option);
      }

      values.forEach((row) => {
        const value = row.name || "";
        if (!value) return;

        const option = document.createElement("option");
        option.value = value;
        option.textContent = getOptionLabel(row);

        if (value === currentValue) {
          option.selected = true;
        }

        select.appendChild(option);
      });

      select.dataset.optionsLoaded = "1";
    } catch (e) {
      console.warn("Could not load options for " + doctype, e);
    }
  }

  function initLinkOptions() {
    qsa("select[data-link-doctype]").forEach((select) => {
      select.addEventListener("focus", function () {
        loadLinkOptions(select);
      });

      select.addEventListener("mousedown", function () {
        loadLinkOptions(select);
      });

      select.addEventListener("touchstart", function () {
        loadLinkOptions(select);
      });

      if (isNewClientPage()) {
        loadLinkOptions(select);
      }
    });
  }

  async function saveClient() {
    if (isSaving) return;

    isSaving = true;
    applyEditMode();

    try {
      const result = await apiPost("dashboard.api.coach.client_details.save_client", {
        docname: getClientName(),
        data: JSON.stringify(collectData())
      });

      if (result && result.name && !getClientName()) {
        window.location.href = `/coach_db/client_details?name=${encodeURIComponent(result.name)}`;
        return;
      }

      editMode = false;
      showSuccess("Client saved");
    } catch (e) {
      showError(e.message);
    }

    isSaving = false;
    applyEditMode();
  }

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

  function activateTab(id) {
    qsa(".dashboard-tab-btn").forEach((btn) => {
      btn.classList.toggle("is-active", btn.dataset.tabTarget === id);
    });

    qsa(".dashboard-tab-panel").forEach((panel) => {
      panel.classList.toggle("is-active", panel.id === id);
    });

    try {
      sessionStorage.setItem("coach_client_details_active_tab", id);
    } catch (e) {
      console.warn("Could not save active tab", e);
    }
  }

  function initTabs() {
    qsa(".dashboard-tab-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        activateTab(btn.dataset.tabTarget);
      });
    });

    let savedTab = "";

    try {
      savedTab = sessionStorage.getItem("coach_client_details_active_tab") || "";
    } catch (e) {
      savedTab = "";
    }

    const savedButton = savedTab
      ? qsa(".dashboard-tab-btn").find((btn) => btn.dataset.tabTarget === savedTab)
      : null;

    if (savedButton && !isNewClientPage()) {
      activateTab(savedTab);
    }
  }

  function init() {
    if (!el("clientDetailsForm")) return;

    editMode = isNewClientPage();

    applyEditMode();
    initTabs();
    initLinkOptions();

    el("editClient")?.addEventListener("click", (e) => {
      e.preventDefault();

      if (!editMode) {
        editMode = true;
        applyEditMode();
      } else {
        saveClient();
      }
    });

    el("addClientNote")?.addEventListener("click", (e) => {
      e.preventDefault();
      addNote();
    });

    el("createClientInvoice")?.addEventListener("click", (e) => {
      e.preventDefault();

      const client = getClientName();
      if (!client) {
        showError("Please save the client before creating an invoice.");
        return;
      }

      window.location.href = `/coach_db/invoice_details?new=1&client=${encodeURIComponent(client)}`;
    });
  }

  document.addEventListener("DOMContentLoaded", init);
})();
