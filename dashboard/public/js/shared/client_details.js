(function () {
  const roleConfig = window.TRKClientDetailsRole || {
    role: "coach",
    baseUrl: "/coach_db",
    apiBase: "dashboard.api.coach.client_details",
    storageKey: "coach_client_details_active_tab",
    canEdit: true,
    canInvoice: true,
    canRequestChange: false
  };

  function el(id) {
    return document.getElementById(id);
  }

  function qsa(selector, root) {
    return Array.from((root || document).querySelectorAll(selector));
  }

  function getCsrfToken() {
    const hidden = el("csrfToken");
    if (hidden && hidden.value) return hidden.value;

    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta && meta.content ? meta.content : "";
  }

  async function apiPost(methodName, args) {
    const res = await fetch(`/api/method/${roleConfig.apiBase}.${methodName}`, {
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

  function showSuccess(message) {
    if (window.frappe && frappe.show_alert) {
      frappe.show_alert({ message: message, indicator: "green" });
    } else {
      console.log(message);
    }
  }

  function showError(message) {
    if (window.frappe && frappe.msgprint) {
      frappe.msgprint(message);
    } else {
      alert(message);
    }
  }

  function getClientName() {
    return el("clientDocname") ? el("clientDocname").value : "";
  }

  function isNewClientPage() {
    const params = new URLSearchParams(window.location.search);
    return params.get("new") === "1" || !getClientName();
  }

  function setFieldState(field, editing) {
    const readOnly = field.dataset.metaReadonly === "1";

    if (readOnly || !roleConfig.canEdit) {
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

  function applyEditMode(editMode, isSaving) {
    qsa("[data-client-field='1']").forEach((field) => {
      setFieldState(field, editMode);
    });

    const editBtn = el("editClient");
    if (editBtn) {
      if (!roleConfig.canEdit) {
        editBtn.style.display = "none";
        return;
      }

      editBtn.textContent = isSaving ? "Saving..." : editMode ? "Save Client" : "Edit Client";
      editBtn.disabled = !!isSaving;
      editBtn.classList.toggle("is-save-mode", !!editMode);
    }

    const invoiceBtn = el("createClientInvoice");
    if (invoiceBtn && !roleConfig.canInvoice) {
      invoiceBtn.style.display = "none";
    }

    document.body.classList.toggle("client-edit-mode", !!editMode);
  }

  function collectData() {
    const data = {};

    qsa("[data-client-field='1']").forEach((field) => {
      const fieldname = field.dataset.fieldname;
      if (!fieldname) return;

      data[fieldname] = field.type === "checkbox" ? (field.checked ? 1 : 0) : field.value;
    });

    return data;
  }

  function getField(fieldname) {
    return document.querySelector(`[data-fieldname="${fieldname}"]`);
  }

  function updateNewClientFullName() {
    if (!isNewClientPage()) return;

    const fullNameField = getField("full_name");
    if (!fullNameField) return;

    const first = getField("name1")?.value || getField("first_name")?.value || "";
    const middle = getField("middle_name")?.value || "";
    const last = getField("last_name")?.value || "";

    fullNameField.value = [first, middle, last]
      .map((part) => String(part || "").trim())
      .filter(Boolean)
      .join(" ");
  }

  function getOptionLabel(row) {
    return (
      row.coach_name ||
      row.sw_name ||
      row.session_worker_name ||
      row.full_name ||
      row.customer_name ||
      row.item_name ||
      row.title ||
      row.name ||
      ""
    );
  }

  async function loadLinkOptions(select) {
    if (!select) return;

    const doctype = select.dataset.linkDoctype;
    if (!doctype) return;

    const currentValue = select.dataset.currentValue || select.value || "";

    try {
      const options = await apiPost("get_link_options", {
        doctype: doctype,
        limit_page_length: 1000
      });

      const rows = Array.isArray(options) ? options : [];

      select.innerHTML = '<option value=""></option>';

      if (currentValue && !rows.some((row) => row.name === currentValue)) {
        const currentOption = document.createElement("option");
        currentOption.value = currentValue;
        currentOption.textContent = currentValue;
        currentOption.selected = true;
        select.appendChild(currentOption);
      }

      rows.forEach((row) => {
        if (!row.name) return;

        const option = document.createElement("option");
        option.value = row.name;
        option.textContent = getOptionLabel(row);

        if (row.name === currentValue) {
          option.selected = true;
        }

        select.appendChild(option);
      });

      select.dataset.optionsLoaded = "1";
    } catch (error) {
      console.warn("Could not load link options", error);
    }
  }

  function initLinkOptions() {
    qsa("select[data-link-doctype]").forEach((select) => {
      ["focus", "mousedown", "touchstart"].forEach((eventName) => {
        select.addEventListener(eventName, function () {
          loadLinkOptions(select);
        });
      });
    });

    if (isNewClientPage()) {
      qsa("select[data-link-doctype]").forEach(loadLinkOptions);
    }
  }

  function initFullNameBuilder() {
    if (!isNewClientPage()) return;

    ["name1", "first_name", "middle_name", "last_name"].forEach((fieldname) => {
      const field = getField(fieldname);
      if (!field) return;

      field.addEventListener("input", updateNewClientFullName);
      field.addEventListener("change", updateNewClientFullName);
    });

    updateNewClientFullName();
  }

  function activateTab(targetId) {
    qsa(".dashboard-tab-btn").forEach((btn) => {
      btn.classList.toggle("is-active", btn.dataset.tabTarget === targetId);
    });

    qsa(".dashboard-tab-panel").forEach((panel) => {
      panel.classList.toggle("is-active", panel.id === targetId);
    });

    try {
      sessionStorage.setItem(roleConfig.storageKey, targetId);
    } catch (e) {}
  }

  function initTabs() {
    const buttons = qsa(".dashboard-tab-btn");

    buttons.forEach((btn) => {
      btn.addEventListener("click", function () {
        activateTab(btn.dataset.tabTarget);
      });
    });

    let savedTab = "";

    try {
      savedTab = sessionStorage.getItem(roleConfig.storageKey) || "";
    } catch (e) {}

    if (savedTab && !isNewClientPage()) {
      const savedBtn = buttons.find((btn) => btn.dataset.tabTarget === savedTab);
      if (savedBtn) activateTab(savedTab);
    }
  }

  async function saveClient(state) {
    if (state.isSaving) return;

    updateNewClientFullName();

    state.isSaving = true;
    applyEditMode(state.editMode, true);

    try {
      const result = await apiPost("save_client", {
        docname: getClientName(),
        data: JSON.stringify(collectData())
      });

      if (result && result.name && !getClientName()) {
        window.location.href = `${roleConfig.baseUrl}/client_details?name=${encodeURIComponent(result.name)}`;
        return;
      }

      state.editMode = false;
      showSuccess("Client saved");
    } catch (error) {
      showError(error.message || "Could not save client.");
    }

    state.isSaving = false;
    applyEditMode(state.editMode, false);
  }

  async function addNote(state) {
    if (state.isAddingNote) return;

    const noteText = el("newClientNoteText") ? el("newClientNoteText").value : "";

    if (!noteText.trim()) {
      showError("Enter a note");
      return;
    }

    state.isAddingNote = true;

    try {
      await apiPost("add_client_note", {
        client_name: getClientName(),
        note_text: noteText
      });

      el("newClientNoteText").value = "";
      showSuccess("Note added");
      window.location.reload();
    } catch (error) {
      showError(error.message || "Could not add note.");
    }

    state.isAddingNote = false;
  }

  function initChangeRequest() {
    if (!roleConfig.canRequestChange) return;

    const requestBtn = el("requestChangeButton");
    const modal = el("changeRequestModal");

    if (!requestBtn || !modal) return;

    function openModal() {
      modal.classList.add("is-open");
      document.body.classList.add("dashboard-modal-open");
    }

    function closeModal() {
      modal.classList.remove("is-open");
      document.body.classList.remove("dashboard-modal-open");
    }

    requestBtn.addEventListener("click", openModal);

    el("closeChangeRequestModal")?.addEventListener("click", closeModal);
    el("closeChangeRequestModalFooter")?.addEventListener("click", closeModal);
  }

  function initInvoiceButton() {
    const invoiceBtn = el("createClientInvoice");

    if (!invoiceBtn) return;

    if (!roleConfig.canInvoice) {
      invoiceBtn.style.display = "none";
      return;
    }

    invoiceBtn.addEventListener("click", function (event) {
      event.preventDefault();

      const client = getClientName();

      if (!client) {
        showError("Please save the client before creating an invoice.");
        return;
      }

      window.location.href = `${roleConfig.baseUrl}/invoice_details?new=1&client=${encodeURIComponent(client)}`;
    });
  }

  function init() {
    if (!el("clientDetailsForm")) return;

    const state = {
      editMode: isNewClientPage() && roleConfig.canEdit,
      isSaving: false,
      isAddingNote: false
    };

    applyEditMode(state.editMode, false);
    initTabs();
    initLinkOptions();
    initFullNameBuilder();
    initChangeRequest();
    initInvoiceButton();

    el("editClient")?.addEventListener("click", function (event) {
      event.preventDefault();

      if (!roleConfig.canEdit) return;

      if (!state.editMode) {
        state.editMode = true;
        applyEditMode(state.editMode, false);
      } else {
        saveClient(state);
      }
    });

    el("addClientNote")?.addEventListener("click", function (event) {
      event.preventDefault();
      addNote(state);
    });
  }

  document.addEventListener("DOMContentLoaded", init);
})();
