(function () {
  function inferRoleConfig() {
    const path = window.location.pathname || "";

    if (path.startsWith("/franchisor_db")) {
      return {
        role: "franchisor",
        baseUrl: "/franchisor_db",
        apiBase: "dashboard.api.shared.client_details",
        storageKey: "franchisor_client_details_active_tab",
        canEdit: true,
        canInvoice: true,
        canRequestChange: false
      };
    }

    if (path.startsWith("/session_worker_db")) {
      return {
        role: "session_worker",
        baseUrl: "/session_worker_db",
        apiBase: "dashboard.api.shared.client_details",
        storageKey: "session_worker_client_details_active_tab",
        canEdit: false,
        canInvoice: false,
        canRequestChange: true
      };
    }

    return {
      role: "coach",
      baseUrl: "/coach_db",
      apiBase: "dashboard.api.shared.client_details",
      storageKey: "coach_client_details_active_tab",
      canEdit: true,
      canInvoice: true,
      canRequestChange: false
    };
  }

  const roleConfig = Object.assign(
    inferRoleConfig(),
    window.TRKClientDetailsRole || {}
  );

  var el = Dashboard.el;
  var qsa = Dashboard.qsa;

  function getClientName() {
    return el("clientDocname") ? el("clientDocname").value : "";
  }

  function getCsrfToken() {
    const hidden = el("csrfToken");
    if (hidden && hidden.value) return hidden.value;

    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta && meta.content ? meta.content : "";
  }

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function showSuccess(message) {
    if (window.frappe && typeof window.frappe.show_alert === "function") {
      window.frappe.show_alert({ message: message, indicator: "green" });
    } else {
      console.log(message);
    }
  }

  function showError(message) {
    if (window.frappe && typeof window.frappe.msgprint === "function") {
      window.frappe.msgprint(message);
    } else {
      alert(message || "Something went wrong.");
    }
  }

  async function apiPost(methodName, args) {
    const response = await fetch("/api/method/" + roleConfig.apiBase + "." + methodName, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-Frappe-CSRF-Token": getCsrfToken()
      },
      body: JSON.stringify(args || {})
    });

    let data = {};
    try {
      data = await response.json();
    } catch (error) {
      throw new Error("Could not read server response.");
    }

    if (!response.ok || data.exc) {
      throw new Error(data.message || "Request failed.");
    }

    return data.message;
  }

  function activateTab(targetId) {
    if (!targetId) return;
  
    const buttons = qsa(".dashboard-tab-btn");
    const panels = qsa(".dashboard-tab-panel");
  
    buttons.forEach(function (button) {
      const isActive = button.dataset.tabTarget === targetId;
      button.classList.toggle("is-active", isActive);
      button.setAttribute("aria-selected", isActive ? "true" : "false");
    });
  
    panels.forEach(function (panel) {
      const isActive = panel.id === targetId;
  
      panel.classList.toggle("is-active", isActive);
  
      if (isActive) {
        panel.removeAttribute("hidden");
        panel.style.setProperty("display", "block", "important");
        panel.style.setProperty("visibility", "visible", "important");
      } else {
        panel.setAttribute("hidden", "hidden");
        panel.style.setProperty("display", "none", "important");
        panel.style.setProperty("visibility", "hidden", "important");
      }
    });
  
    try {
      sessionStorage.setItem(roleConfig.storageKey, targetId);
    } catch (error) {}
  
    if (targetId === "client-contacts-tab") loadSessionWorkerContacts();
    if (targetId === "client-notes-tab") loadSessionWorkerNotes();
    if (targetId === "client-appointments-tab") loadSessionWorkerAppointments();
  }
  
  
  function initTabs() {
    const buttons = qsa(".dashboard-tab-btn");
    const panels = qsa(".dashboard-tab-panel");
  
    if (!buttons.length || !panels.length) return;
  
    document.addEventListener("click", function (event) {
      const button = event.target.closest(".dashboard-tab-btn");
  
      if (!button) return;
  
      const targetId = button.dataset.tabTarget;
  
      if (!targetId) return;
  
      event.preventDefault();
      event.stopPropagation();
  
      activateTab(targetId);
    }, true);
  
    let savedTab = "";
  
    try {
      savedTab = sessionStorage.getItem(roleConfig.storageKey) || "";
    } catch (error) {
      savedTab = "";
    }
  
    const savedButton = savedTab
      ? buttons.find(function (button) {
          return button.dataset.tabTarget === savedTab;
        })
      : null;
  
    if (savedButton) {
      activateTab(savedTab);
      return;
    }
  
    const activeButton = buttons.find(function (button) {
      return button.classList.contains("is-active");
    });
  
    activateTab(activeButton ? activeButton.dataset.tabTarget : buttons[0].dataset.tabTarget);
  }

  function setFieldState(field, isEditing) {
    const readOnly = field.dataset.metaReadonly === "1";

    if (!roleConfig.canEdit || readOnly) {
      field.disabled = true;
      field.readOnly = true;
      return;
    }

    if (field.tagName === "SELECT" || field.type === "checkbox") {
      field.disabled = !isEditing;
    } else {
      field.readOnly = !isEditing;
    }
  }

  function applyClientDetailVisibility(isEditing) {
    const fullNameWrap = document.querySelector("[data-field-wrap='full_name']");
    const firstNameWrap = document.querySelector("[data-field-wrap='name1'], [data-field-wrap='first_name']");
    const lastNameWrap = document.querySelector("[data-field-wrap='last_name']");

    if (fullNameWrap) fullNameWrap.style.display = isEditing ? "none" : "";
    if (firstNameWrap) firstNameWrap.style.display = isEditing ? "" : "none";
    if (lastNameWrap) lastNameWrap.style.display = isEditing ? "" : "none";
  }

  function applyEditMode(isEditing, isSaving) {
    qsa("[data-client-field='1']").forEach(function (field) {
      setFieldState(field, isEditing);
    });

    qsa("[data-diagnosis-field]").forEach(function (field) {
      if (!roleConfig.canEdit) {
        field.disabled = true;
        field.readOnly = true;
        return;
      }

      if (field.tagName === "SELECT" || field.type === "file") {
        field.disabled = !isEditing;
      } else {
        field.readOnly = !isEditing;
      }
    });

    applyClientDetailVisibility(isEditing || isNewClientPage());

    const addTherapyLocationBtn = el("addTherapyLocationBtn");
    if (addTherapyLocationBtn) {
      addTherapyLocationBtn.disabled = !roleConfig.canEdit || !isEditing;
    }

    const editButton = el("editClient");

    if (editButton) {
      if (!roleConfig.canEdit) {
        editButton.style.display = "none";
      } else {
        editButton.disabled = !!isSaving;
        editButton.textContent = isSaving ? "Saving..." : isEditing ? "Save Client" : "Edit Client";
        editButton.classList.toggle("is-save-mode", !!isEditing);
      }
    }

    const invoiceButton = el("createClientInvoice");
    if (invoiceButton && !roleConfig.canInvoice) {
      invoiceButton.style.display = "none";
    }

    document.body.classList.toggle("client-edit-mode", !!isEditing);
  }

      function collectClientData() {
        const data = {};
    
        qsa("[data-client-field='1']").forEach(function (field) {
          const fieldname = field.dataset.fieldname;
          if (!fieldname) return;
    
          if (field.type === "checkbox") {
            data[fieldname] = field.checked ? 1 : 0;
          } else {
            data[fieldname] = field.value;
          }
        });
    
        const diagnosisRows = [];
    
        qsa("[data-diagnosis-row='1']").forEach(function (row) {
          const diagnosisField = row.querySelector("[data-diagnosis-field='diagnosis'], [data-diagnosis-field='diagnoses']");
          const newDiagnosisField = row.querySelector("[data-diagnosis-field='new_diagnosis']");
          const attachementField = row.querySelector("[data-diagnosis-field='attachement']");
          const dateField = row.querySelector("[data-diagnosis-field='date']");
          const diagnosisValue = diagnosisField ? diagnosisField.value : "";
          const newDiagnosisValue = newDiagnosisField && !diagnosisValue ? newDiagnosisField.value : "";

          diagnosisRows.push({
            diagnosis: diagnosisValue,
            diagnoses: diagnosisValue,
            new_diagnosis: newDiagnosisValue,
            attachement: attachementField ? attachementField.value : "",
            date: dateField ? dateField.value : ""
          });
        });
    
        data.diagnosis = diagnosisRows;
    
        return data;
      }

  function isNewClientPage() {
    const params = new URLSearchParams(window.location.search);
    return params.get("new") === "1" || !getClientName();
  }

  function getField(fieldname) {
    return document.querySelector('[data-fieldname="' + fieldname + '"]');
  }

  function updateNewClientFullName() {
    if (!isNewClientPage()) return;

    const fullNameField = getField("full_name");
    if (!fullNameField) return;

    const first = (getField("name1") && getField("name1").value) || (getField("first_name") && getField("first_name").value) || "";
    const middle = (getField("middle_name") && getField("middle_name").value) || "";
    const last = (getField("last_name") && getField("last_name").value) || "";

    fullNameField.value = [first, middle, last]
      .map(function (part) {
        return String(part || "").trim();
      })
      .filter(Boolean)
      .join(" ");
  }

    function calculateAgeFromDob(dobValue) {
      if (!dobValue) return "";
  
      const dob = new Date(dobValue);
  
      if (Number.isNaN(dob.getTime())) return "";
  
      const today = new Date();
  
      let age = today.getFullYear() - dob.getFullYear();
      const monthDiff = today.getMonth() - dob.getMonth();
  
      if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < dob.getDate())) {
        age--;
      }
  
      return age;
    }
  
    function updateAgeFromDateOfBirth() {
      const dobField = getField("date_of_birth");
      const ageField = getField("age");
  
      if (!dobField || !ageField) return;
  
      ageField.value = calculateAgeFromDob(dobField.value);
    }
  
    function initAgeBuilder() {
      const dobField = getField("date_of_birth");
  
      if (!dobField) return;
  
      dobField.addEventListener("input", updateAgeFromDateOfBirth);
      dobField.addEventListener("change", updateAgeFromDateOfBirth);
  
      updateAgeFromDateOfBirth();
    }

  function initFullNameBuilder() {
    if (!isNewClientPage()) return;

    ["name1", "first_name", "middle_name", "last_name"].forEach(function (fieldname) {
      const field = getField(fieldname);
      if (!field) return;

      field.addEventListener("input", updateNewClientFullName);
      field.addEventListener("change", updateNewClientFullName);
    });

    updateNewClientFullName();
  }

  function getOptionLabel(row) {
    return (
      row.diagnosis_name ||
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

      if (currentValue && !rows.some(function (row) { return row.name === currentValue; })) {
        const currentOption = document.createElement("option");
        currentOption.value = currentValue;
        currentOption.textContent = currentValue;
        currentOption.selected = true;
        select.appendChild(currentOption);
      }

      rows.forEach(function (row) {
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

  function setSelectValue(field, value) {
    if (!field || value == null) return;

    const textValue = String(value || "");

    if (field.tagName === "SELECT") {
      let option = Array.from(field.options).find(function (item) {
        return item.value === textValue;
      });

      if (!option && textValue) {
        option = document.createElement("option");
        option.value = textValue;
        option.textContent = textValue;
        field.appendChild(option);
      }

      field.value = textValue;
      field.dataset.currentValue = textValue;
      return;
    }

    field.value = textValue;
  }

  function setFieldValueIfExists(fieldnames, value) {
    fieldnames.forEach(function (fieldname) {
      const field = getField(fieldname);
      if (!field) return;

      setSelectValue(field, value);
      field.dispatchEvent(new Event("change", { bubbles: true }));
    });
  }

  async function applyPrimaryCoachDefaults() {
    const primaryCoachField = getField("primary_coach");

    if (!primaryCoachField || !primaryCoachField.value) return;

    try {
      const defaults = await apiPost("get_coach_defaults", {
        coach_name: primaryCoachField.value
      });

      if (!defaults) return;

      setFieldValueIfExists(
        ["coach_banking_details", "banking"],
        defaults.coach_banking_details || defaults.banking || ""
      );

      setFieldValueIfExists(
        ["pricelist", "price_list"],
        defaults.pricelist || defaults.price_list || ""
      );

      setFieldValueIfExists(
        ["company"],
        defaults.company || ""
      );
    } catch (error) {
      console.warn("Could not load coach defaults", error);
    }
  }

  function initPrimaryCoachDefaults() {
    const primaryCoachField = getField("primary_coach");

    if (!primaryCoachField || primaryCoachField.dataset.coachDefaultsBound === "1") return;

    primaryCoachField.dataset.coachDefaultsBound = "1";

    primaryCoachField.addEventListener("change", applyPrimaryCoachDefaults);
  }

  function setSelectValue(field, value) {
    if (!field) return;

    const textValue = String(value || "");

    if (field.tagName === "SELECT") {
      let option = Array.from(field.options).find(function (item) {
        return item.value === textValue;
      });

      if (!option && textValue) {
        option = document.createElement("option");
        option.value = textValue;
        option.textContent = textValue;
        field.appendChild(option);
      }

      field.value = textValue;
      field.dataset.currentValue = textValue;
      return;
    }

    field.value = textValue;
  }

  function setFieldValue(fieldnames, value) {
    fieldnames.forEach(function (fieldname) {
      const field = getField(fieldname);
      if (!field) return;

      setSelectValue(field, value);
      field.dispatchEvent(new Event("change", { bubbles: true }));
    });
  }

  async function applyPrimaryCoachDefaults() {
    const primaryCoachField = getField("primary_coach");

    if (!primaryCoachField || !primaryCoachField.value) return;

    try {
      const defaults = await apiPost("get_coach_defaults", {
        coach_name: primaryCoachField.value
      });

      if (!defaults) return;

      setFieldValue(["banking", "coach_banking_details"], defaults.banking || defaults.coach_banking_details || "");
      setFieldValue(["pricelist", "price_list"], defaults.pricelist || defaults.price_list || "");
      setFieldValue(["company"], defaults.company || "");
    } catch (error) {
      console.warn("Could not load coach defaults", error);
    }
  }

  function initPrimaryCoachDefaults() {
    const primaryCoachField = getField("primary_coach");

    if (!primaryCoachField || primaryCoachField.dataset.coachDefaultsBound === "1") return;

    primaryCoachField.dataset.coachDefaultsBound = "1";
    primaryCoachField.addEventListener("change", applyPrimaryCoachDefaults);

    if (isNewClientPage() && primaryCoachField.value) {
      applyPrimaryCoachDefaults();
    }
  }

  function initLinkOptions() {
    qsa("select[data-link-doctype]").forEach(function (select) {
      ["focus", "mousedown", "touchstart"].forEach(function (eventName) {
        select.addEventListener(eventName, function () {
          loadLinkOptions(select);
        });
      });
    });

    if (isNewClientPage()) {
      qsa("select[data-link-doctype]").forEach(loadLinkOptions);
    }
  }
  function initEditButton() {
    const editButton = el("editClient");
    if (!editButton) return;

    let isEditing = isNewClientPage() && !!roleConfig.canEdit;
    let isSaving = false;

    applyEditMode(isEditing, isSaving);

    editButton.addEventListener("click", async function (event) {
      event.preventDefault();

      if (!roleConfig.canEdit) return;

      if (!isEditing) {
        isEditing = true;
        applyEditMode(isEditing, false);
        return;
      }

      updateNewClientFullName();

      isSaving = true;
      applyEditMode(isEditing, isSaving);

      try {
        const result = await apiPost("save_client", {
          docname: getClientName(),
          data: JSON.stringify(collectClientData())
        });

        if (result && result.name && !getClientName()) {
          window.location.href = roleConfig.baseUrl + "/client_details?name=" + encodeURIComponent(result.name);
          return;
        }

        isEditing = false;
        showSuccess("Client saved");
      } catch (error) {
        showError(error.message || "Could not save client.");
      }

      isSaving = false;
      applyEditMode(isEditing, isSaving);
    });
  }

  function initInvoiceButton() {
    const invoiceButton = el("createClientInvoice");
    if (!invoiceButton) return;

    if (!roleConfig.canInvoice) {
      invoiceButton.style.display = "none";
      return;
    }

    invoiceButton.addEventListener("click", function (event) {
      event.preventDefault();

      const client = getClientName();

      if (!client) {
        showError("Please save the client before creating an invoice.");
        return;
      }

      window.location.href = roleConfig.baseUrl + "/invoice_details?new=1&client=" + encodeURIComponent(client);
    });
  }

  async function addClientNote() {
    const field = el("newClientNoteText");
    if (!field) return;

    const noteText = field.value || "";

    if (!noteText.trim()) {
      showError("Enter a note.");
      return;
    }

    const dateField = el("newClientNoteDate");
    const fileInput = el("newClientNoteFile");
    const file = fileInput && fileInput.files && fileInput.files[0];

    try {
      let attachement = "";

      if (file) {
        const uploaded = await uploadFile(file);
        attachement = (uploaded && uploaded.file_url) || "";
      }

      await apiPost("add_client_note", {
        client_name: getClientName(),
        note_text: noteText,
        session_date: dateField ? dateField.value : "",
        attachement: attachement
      });

      field.value = "";
      if (dateField) dateField.value = "";
      if (fileInput) fileInput.value = "";
      showSuccess("Note added");

      if (roleConfig.role === "session_worker") {
        loadSessionWorkerNotes();
      } else {
        window.location.reload();
      }
    } catch (error) {
      showError(error.message || "Could not add note.");
    }
  }

  function initAddNote() {
    const button = el("addClientNote");
    if (!button) return;

    button.addEventListener("click", function (event) {
      event.preventDefault();
      addClientNote();
    });
  }

  function renderSimpleTable(bodyId, rows, emptyMessage, columns) {
    const body = el(bodyId);
    if (!body) return;

    if (!rows || !rows.length) {
      body.innerHTML = '<tr><td colspan="' + columns + '" class="dashboard-empty">' + escapeHtml(emptyMessage) + '</td></tr>';
      return;
    }

    body.innerHTML = rows.join("");
  }

  function formatDate(value) {
    if (!value) return "—";

    const text = String(value);
    if (text.length >= 10) return escapeHtml(text.slice(0, 10));

    return escapeHtml(text);
  }

  function formatTime(value) {
    if (!value) return "";

    const text = String(value);
    if (text.length >= 16) return escapeHtml(text.slice(11, 16));

    return "";
  }

  async function loadSessionWorkerContacts() {
    if (roleConfig.role !== "session_worker") return;
    if (!el("clientContactsTableBody")) return;

    try {
      const contacts = await apiPost("get_client_contacts", {
        client_name: getClientName(),
        contact_detail_base_url: roleConfig.baseUrl + "/contact_details"
      });

      const rows = (contacts || []).map(function (row) {
        return (
          "<tr>" +
            "<td>" +
              "<a class=\"dashboard-inline-link\" href=\"" + escapeHtml(row.link || "#") + "\">" +
                escapeHtml(row.display_name || row.contact_name || "—") +
              "</a>" +
              "<div class=\"dashboard-client-type-mobile\">" +
                escapeHtml(row.phone || "—") +
              "</div>" +
            "</td>" +
            "<td>" + escapeHtml(row.phone || "—") + "</td>" +
            "<td>" + escapeHtml(row.email || "—") + "</td>" +
            "<td>" + escapeHtml(row.relationship || "—") + "</td>" +
            "<td class=\"dashboard-action-cell\"><a class=\"dashboard-link-btn\" href=\"" + escapeHtml(row.link || "#") + "\">View</a></td>" +
          "</tr>"
        );
      });;

      renderSimpleTable("clientContactsTableBody", rows, "No linked contacts found.", 5);
    } catch (error) {
      renderSimpleTable("clientContactsTableBody", [], error.message || "Could not load contacts.", 5);
    }
  }

  async function loadSessionWorkerNotes() {
    if (roleConfig.role !== "session_worker") return;
    if (!el("clientNotesTableBody")) return;

    try {
      const notes = await apiPost("get_client_notes", {
        client_name: getClientName()
      });

      const rows = (notes || []).map(function (row) {
        const attachment = row.attachement
          ? "<a href=\"" + escapeHtml(row.attachement) + "\" target=\"_blank\" rel=\"noopener noreferrer\">View</a>"
          : "—";

        return (
          "<tr>" +
            "<td>" + formatDate(row.note_date || row.session_date) + "</td>" +
            "<td class=\"dashboard-note-user-cell\">" + escapeHtml(row.note_user_name || row.user_full_name || row.note_user || row.user || "—") + "</td>" +
            "<td>" + escapeHtml(row.note_text || row.notes || "—") + "</td>" +
            "<td>" + attachment + "</td>" +
          "</tr>"
        );
      });

      renderSimpleTable("clientNotesTableBody", rows, "No notes found.", 4);
    } catch (error) {
      renderSimpleTable("clientNotesTableBody", [], error.message || "Could not load notes.", 3);
    }
  }

  async function loadSessionWorkerAppointments() {
    if (roleConfig.role !== "session_worker") return;
    if (!el("clientAppointmentsTableBody")) return;

    try {
      const appointments = await apiPost("get_client_appointments", {
        client_name: getClientName(),
        calendar_detail_base_url: roleConfig.baseUrl + "/calendar_details"
      });

      const rows = (appointments || []).map(function (row) {
        const link = row.record_url || row.view_link || "#";
        const dateValue = row.date || row.appointment_start || "";
        const timeValue = row.time || formatTime(row.appointment_start || "");

        return (
          "<tr class=\"dashboard-client-appointment-row\">" +
            "<td><div class=\"dashboard-table-date\">" + formatDate(dateValue) + "</div><div class=\"dashboard-table-time\">" + escapeHtml(timeValue || "") + "</div></td>" +
            "<td><a class=\"dashboard-inline-link\" href=\"" + escapeHtml(link) + "\">" + escapeHtml(row.appointment_type || row.item_display_name || row.item || "—") + "</a></td>" +
            "<td>" + escapeHtml(row.ui_status || row.display_status || row.status || "—") + "</td>" +
            "<td>" + escapeHtml(row.location || "—") + "</td>" +
            "<td class=\"dashboard-action-cell\"><a class=\"dashboard-link-btn\" href=\"" + escapeHtml(link) + "\">View</a></td>" +
          "</tr>"
        );
      });

      renderSimpleTable("clientAppointmentsTableBody", rows, "No appointments found.", 5);
    } catch (error) {
      renderSimpleTable("clientAppointmentsTableBody", [], error.message || "Could not load appointments.", 5);
    }
  }

    function initTravelChargeToggle() {
    const checkbox = getField("travel_charged");
    const wrap = el("clientTravelChargePerSessionWrap");
    if (!checkbox || !wrap || checkbox.dataset.travelChargeToggleBound === "1") return;

    checkbox.dataset.travelChargeToggleBound = "1";

    function applyTravelChargeVisibility() {
      wrap.style.display = checkbox.checked ? "" : "none";
    }

    checkbox.addEventListener("change", applyTravelChargeVisibility);
    applyTravelChargeVisibility();
  }

    function initCompletedPackToggle() {
    const button = el("toggleCompletedPacks");
    if (!button || button.dataset.completedPacksBound === "1") return;

    button.dataset.completedPacksBound = "1";

    let showingAll = false;

    function applyPackVisibility() {
      qsa("[data-pack-exhausted='1']").forEach(function (row) {
        row.style.display = showingAll ? "" : "none";
      });

      button.textContent = showingAll ? "Hide Completed Session Packs" : "Show All Session Packs";
    }

    button.addEventListener("click", function () {
      showingAll = !showingAll;
      applyPackVisibility();
    });

    applyPackVisibility();
  }

  function initChangeRequest() {
    if (!roleConfig.canRequestChange) return;

    const requestButton = el("requestChangeButton");
    const modal = el("changeRequestModal");

    if (!requestButton || !modal) return;

    function openModal(event) {
      if (event) event.preventDefault();
      modal.classList.add("is-open");
      document.body.classList.add("dashboard-modal-open");
    }

    function closeModal(event) {
      if (event) event.preventDefault();
      modal.classList.remove("is-open");
      document.body.classList.remove("dashboard-modal-open");
    }

    requestButton.addEventListener("click", openModal);

    if (el("closeChangeRequestModal")) {
      el("closeChangeRequestModal").addEventListener("click", closeModal);
    }

    if (el("closeChangeRequestModalFooter")) {
      el("closeChangeRequestModalFooter").addEventListener("click", closeModal);
    }
  }

  async function loadExistingContactOptions() {
    const select = el("existingContactSelect");
    if (!select) return;
  
    select.innerHTML = '<option value="">Loading...</option>';
  
    try {
      const contacts = await apiPost("get_link_options", {
        doctype: "Contact",
        limit_page_length: 5000
      });
  
      select.innerHTML = '<option value="">Select Contact</option>';
  
      (contacts || []).forEach(function (row) {
        if (!row.name) return;
  
        const option = document.createElement("option");
        option.value = row.name;
        option.textContent = getOptionLabel(row);
        select.appendChild(option);
      });
    } catch (error) {
      select.innerHTML = '<option value="">Could not load contacts</option>';
    }
  }

    async function saveClientAndOpenNewContact(event, link) {
      event.preventDefault();
  
      if (!roleConfig.canEdit) return;
  
      const existingClient = getClientName();
  
      if (existingClient) {
        window.location.href = link.href;
        return;
      }
  
      updateNewClientFullName();
  
      try {
        link.classList.add("is-loading");
        link.textContent = "Saving client...";
  
        const result = await apiPost("save_client", {
          docname: "",
          data: JSON.stringify(collectClientData())
        });
  
        if (!result || !result.name) {
          throw new Error("Client was saved but no client name was returned.");
        }
  
        window.location.href =
          roleConfig.baseUrl +
          "/contact_details?new=1&client=" +
          encodeURIComponent(result.name);
  
      } catch (error) {
        link.classList.remove("is-loading");
        link.textContent = "Add New Contact";
        showError(error.message || "Could not save client before adding contact.");
      }
    }
  
    function initSaveBeforeNewContactLinks() {
      qsa("a[data-save-client-before-contact='1']").forEach(function (link) {
        if (link.dataset.saveBeforeContactBound === "1") return;
  
        link.dataset.saveBeforeContactBound = "1";
  
        link.addEventListener("click", function (event) {
          saveClientAndOpenNewContact(event, link);
        });
      });
    }

    function todayIsoDate() {
      return new Date().toISOString().slice(0, 10);
    }

    function setupDiagnosisRow(row) {
      const select = row.querySelector("[data-diagnosis-field='diagnosis'], [data-diagnosis-field='diagnoses']");
      const input = row.querySelector("[data-diagnosis-field='new_diagnosis']");
      const dateField = row.querySelector("[data-diagnosis-field='date']");

      if (!input || input.dataset.diagnosisSetup === "1") return;

      input.dataset.diagnosisSetup = "1";
      input.style.display = input.value ? "" : "none";

      const addBtn = document.createElement("button");
      addBtn.type = "button";
      addBtn.className = "dashboard-link-btn";
      addBtn.textContent = "+ Add New Diagnosis";
      addBtn.style.marginTop = "6px";

      input.parentNode.insertBefore(addBtn, input);

      addBtn.addEventListener("click", function () {
        if (select) select.value = "";
        input.style.display = "";
        input.focus();
      });

      if (select) {
        select.addEventListener("change", function () {
          if (select.value) {
            input.value = "";
            input.style.display = "none";
          }
        });
      }

      if (dateField && !dateField.value) {
        dateField.value = todayIsoDate();
      }
    }

    async function uploadFile(file) {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("is_private", 1);

      const response = await fetch("/api/method/upload_file", {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "X-Frappe-CSRF-Token": getCsrfToken()
        },
        body: formData
      });

      const data = await response.json();

      if (!response.ok || data.exc) {
        throw new Error(data.message || "Could not upload the file.");
      }

      return data.message;
    }

    function initDiagnosisAttachments() {
      document.addEventListener("change", async function (event) {
        const fileInput = event.target.closest("[data-diagnosis-field='attachement_file']");
        if (!fileInput) return;

        const row = fileInput.closest("[data-diagnosis-row='1']");
        if (!row) return;

        const file = fileInput.files && fileInput.files[0];
        if (!file) return;

        const hiddenField = row.querySelector("[data-diagnosis-field='attachement']");
        const status = row.querySelector("[data-diagnosis-attachment-status='1']");

        if (status) status.textContent = "Uploading...";

        try {
          const uploaded = await uploadFile(file);
          const fileUrl = uploaded && uploaded.file_url;

          if (hiddenField) hiddenField.value = fileUrl || "";

          if (status) {
            status.innerHTML = fileUrl
              ? "Current file: <a href=\"" + fileUrl + "\" target=\"_blank\" rel=\"noopener noreferrer\">View</a>"
              : "No file attached";
          }
        } catch (error) {
          if (status) status.textContent = "Upload failed.";
          showError(error.message || "Could not upload the file.");
        }
      });
    }

    function openTherapyLocationModal() {
      const modal = el("therapyLocationModal");
      if (modal) modal.classList.add("show");
    }

    function closeTherapyLocationModal() {
      const modal = el("therapyLocationModal");
      if (modal) modal.classList.remove("show");
    }

    async function saveTherapyLocation() {
      const nameField = el("newTherapyLocationName");
      const typeField = el("newTherapyLocationType");
      const address1Field = el("newTherapyAddress1");
      const address2Field = el("newTherapyAddress2");
      const cityField = el("newTherapyCity");
      const postalField = el("newTherapyPostalCode");

      const locationName = nameField ? nameField.value.trim() : "";
      const locationType = typeField ? typeField.value : "";

      if (!locationName) {
        showError("Enter a location name.");
        return;
      }

      if (!locationType) {
        showError("Select a location type.");
        return;
      }

      const button = el("saveTherapyLocationBtn");
      if (button) {
        button.disabled = true;
        button.textContent = "Saving...";
      }

      try {
        const result = await apiPost("create_therapy_location", {
          location_name: locationName,
          location_type: locationType,
          address_line_1: address1Field ? address1Field.value : "",
          address_line_2: address2Field ? address2Field.value : "",
          city: cityField ? cityField.value : "",
          postal_code: postalField ? postalField.value : ""
        });

        const select = el("field_main_therapy_location") || el("field_therapy_location");
        if (select && result && result.name) {
          const option = document.createElement("option");
          option.value = result.name;
          option.textContent = result.label || result.name;
          option.selected = true;
          select.appendChild(option);
          select.value = result.name;
        }

        if (nameField) nameField.value = "";
        if (typeField) typeField.value = "";
        if (address1Field) address1Field.value = "";
        if (address2Field) address2Field.value = "";
        if (cityField) cityField.value = "";
        if (postalField) postalField.value = "";

        closeTherapyLocationModal();
        showSuccess("Location added");
      } catch (error) {
        showError(error.message || "Could not save the location.");
      } finally {
        if (button) {
          button.disabled = false;
          button.textContent = "Save Location";
        }
      }
    }

    async function apiPostRaw(fullMethod, args) {
      const response = await fetch("/api/method/" + fullMethod, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-Frappe-CSRF-Token": getCsrfToken()
        },
        body: JSON.stringify(args || {})
      });

      let data = {};
      try {
        data = await response.json();
      } catch (error) {
        throw new Error("Could not read server response.");
      }

      if (!response.ok || data.exc) {
        throw new Error(data.message || "Request failed.");
      }

      return data.message;
    }

    const sendInvoiceState = {
      invoiceOptions: [],
      emailOptions: [],
      templateOptions: []
    };

    function fillSelect(select, options, placeholder) {
      if (!select) return;

      const previous = select.value;
      let html = placeholder ? `<option value="">${escapeHtml(placeholder)}</option>` : "";

      html += options.map(function (opt) {
        return `<option value="${escapeHtml(opt.value)}">${escapeHtml(opt.label)}</option>`;
      }).join("");

      select.innerHTML = html;

      if (previous && options.some(function (opt) { return opt.value === previous; })) {
        select.value = previous;
      }
    }

    function defaultInvoiceValue(options) {
      const outstanding = options.find(function (opt) { return Number(opt.outstanding_amount || 0) > 0; });
      return (outstanding || options[0] || {}).value || "";
    }

    function defaultTemplateValue(options) {
      const preferred = options.find(function (opt) { return opt.value === "Invoice Email - Resilient Kid"; });
      return (preferred || options[0] || {}).value || "";
    }

    async function refreshSendInvoiceMessage() {
      const invoiceSelect = el("sendInvoiceInvoice");
      const templateSelect = el("sendInvoiceTemplate");
      const subjectField = el("sendInvoiceSubject");
      const messageField = el("sendInvoiceMessage");

      const docname = invoiceSelect ? invoiceSelect.value : "";
      if (!docname) return;

      try {
        const defaults = await apiPostRaw("dashboard.api.shared.invoices.get_invoice_email_defaults", {
          docname: docname,
          template_name: templateSelect ? templateSelect.value : ""
        });

        if (subjectField && defaults && defaults.subject) subjectField.value = defaults.subject;
        if (messageField && defaults && defaults.message) messageField.value = defaults.message;
      } catch (error) {
        showError(error.message || "Could not load the email template.");
      }
    }

    async function openSendInvoiceModal() {
      const modal = el("sendInvoiceModal");
      const client = getClientName();

      if (!modal || !client) return;

      modal.classList.add("show");

      const statusEl = el("sendInvoiceStatus");
      if (statusEl) statusEl.textContent = "";

      const invoiceSelect = el("sendInvoiceInvoice");
      const emailSelect = el("sendInvoiceEmail");
      const templateSelect = el("sendInvoiceTemplate");

      if (invoiceSelect) invoiceSelect.innerHTML = '<option value="">Loading...</option>';
      if (emailSelect) emailSelect.innerHTML = '<option value="">Loading...</option>';
      if (templateSelect) templateSelect.innerHTML = '<option value="">Loading...</option>';

      try {
        const [invoiceOptions, emailOptions, templateOptions] = await Promise.all([
          apiPostRaw("dashboard.api.shared.invoices.get_client_invoice_options", { client_name: client }),
          apiPostRaw("dashboard.api.shared.invoices.get_client_email_options", { client_name: client }),
          apiPostRaw("dashboard.api.shared.email_templates.get_email_template_options", {})
        ]);

        sendInvoiceState.invoiceOptions = invoiceOptions || [];
        sendInvoiceState.emailOptions = emailOptions || [];
        sendInvoiceState.templateOptions = templateOptions || [];

        if (!sendInvoiceState.invoiceOptions.length) {
          if (statusEl) statusEl.textContent = "This client has no submitted invoices to send.";
        }

        fillSelect(invoiceSelect, sendInvoiceState.invoiceOptions, sendInvoiceState.invoiceOptions.length ? "" : "No invoices");
        fillSelect(emailSelect, sendInvoiceState.emailOptions, sendInvoiceState.emailOptions.length ? "" : "No email on file");
        fillSelect(templateSelect, sendInvoiceState.templateOptions, sendInvoiceState.templateOptions.length ? "" : "No templates");

        if (invoiceSelect) invoiceSelect.value = defaultInvoiceValue(sendInvoiceState.invoiceOptions);
        if (templateSelect) templateSelect.value = defaultTemplateValue(sendInvoiceState.templateOptions);

        await refreshSendInvoiceMessage();
      } catch (error) {
        showError(error.message || "Could not load invoice details.");
      }
    }

    function closeSendInvoiceModal() {
      const modal = el("sendInvoiceModal");
      if (modal) modal.classList.remove("show");
    }

    async function sendClientInvoiceEmail() {
      const invoiceSelect = el("sendInvoiceInvoice");
      const emailSelect = el("sendInvoiceEmail");
      const subjectField = el("sendInvoiceSubject");
      const messageField = el("sendInvoiceMessage");
      const statusEl = el("sendInvoiceStatus");
      const sendBtn = el("sendInvoiceSubmit");

      const docname = invoiceSelect ? invoiceSelect.value : "";
      const recipient = emailSelect ? emailSelect.value : "";
      const subject = subjectField ? subjectField.value.trim() : "";
      const message = messageField ? messageField.value.trim() : "";

      if (!docname) {
        showError("Select an invoice to send.");
        return;
      }

      if (!recipient) {
        showError("Select an email address to send to.");
        return;
      }

      if (sendBtn) {
        sendBtn.disabled = true;
        sendBtn.textContent = "Sending...";
      }

      if (statusEl) statusEl.textContent = "";

      try {
        await apiPostRaw("dashboard.api.shared.invoices.send_invoice_email", {
          docname: docname,
          recipient: recipient,
          subject: subject,
          message: message
        });

        showSuccess("Invoice email sent");
        closeSendInvoiceModal();
      } catch (error) {
        showError(error.message || "Could not send the invoice email.");
      } finally {
        if (sendBtn) {
          sendBtn.disabled = false;
          sendBtn.textContent = "Send";
        }
      }
    }

    function initSendInvoiceModal() {
      const openBtn = el("sendClientInvoiceBtn");

      if (!roleConfig.canInvoice) {
        if (openBtn) openBtn.style.display = "none";
        return;
      }

      if (openBtn) {
        openBtn.addEventListener("click", function (event) {
          event.preventDefault();
          openSendInvoiceModal();
        });
      }

      const closeBtn = el("sendInvoiceModalClose");
      if (closeBtn) closeBtn.addEventListener("click", closeSendInvoiceModal);

      const cancelBtn = el("sendInvoiceCancel");
      if (cancelBtn) cancelBtn.addEventListener("click", closeSendInvoiceModal);

      const invoiceSelect = el("sendInvoiceInvoice");
      if (invoiceSelect) invoiceSelect.addEventListener("change", refreshSendInvoiceMessage);

      const templateSelect = el("sendInvoiceTemplate");
      if (templateSelect) templateSelect.addEventListener("change", refreshSendInvoiceMessage);

      const submitBtn = el("sendInvoiceSubmit");
      if (submitBtn) submitBtn.addEventListener("click", sendClientInvoiceEmail);
    }

    function initTherapyLocationModal() {
      const addBtn = el("addTherapyLocationBtn");
      if (addBtn) {
        addBtn.addEventListener("click", function (event) {
          event.preventDefault();
          openTherapyLocationModal();
        });
      }

      const closeBtn = el("therapyLocationModalClose");
      if (closeBtn) closeBtn.addEventListener("click", closeTherapyLocationModal);

      const cancelBtn = el("therapyLocationModalCancel");
      if (cancelBtn) cancelBtn.addEventListener("click", closeTherapyLocationModal);

      const saveBtn = el("saveTherapyLocationBtn");
      if (saveBtn) {
        saveBtn.addEventListener("click", function (event) {
          event.preventDefault();
          saveTherapyLocation();
        });
      }
    }

    function initDiagnosisRows() {
      qsa("[data-diagnosis-row='1']").forEach(setupDiagnosisRow);
      initDiagnosisAttachments();

      document.addEventListener("click", function (event) {
        const button = event.target.closest("#addDiagnosisRow");
        if (!button) return;

        event.preventDefault();

        const body = el("diagnosisTableBody");
        if (!body) return;

        const emptyRow = body.querySelector("[data-diagnosis-empty-row='1']");
        if (emptyRow) emptyRow.remove();

        const row = document.createElement("tr");
        row.setAttribute("data-diagnosis-row", "1");

        row.innerHTML =
          '<td>' +
            '<select class="dashboard-select" data-diagnosis-field="diagnosis" data-link-doctype="Diagnosis Option">' +
              '<option value=""></option>' +
            '</select>' +
            '<input class="dashboard-input" data-diagnosis-field="new_diagnosis" placeholder="Type new diagnosis" style="margin-top:6px;display:none;">' +
          '</td>' +
          '<td><input type="date" class="dashboard-input" data-diagnosis-field="date" value="' + todayIsoDate() + '"></td>' +
          '<td>' +
            '<input type="file" class="dashboard-input" data-diagnosis-field="attachement_file">' +
            '<input type="hidden" data-diagnosis-field="attachement" value="">' +
            '<div class="dashboard-field-note" data-diagnosis-attachment-status="1">No file attached</div>' +
          '</td>';

        body.appendChild(row);

        const select = row.querySelector("select[data-link-doctype]");
        if (select) {
          loadLinkOptions(select);
        }

        setupDiagnosisRow(row);
        applyEditMode(true, false);
      }, true);
    }
    
    function initExistingContactModal() {
      const buttons = qsa(".select-existing-contact-btn");
      const panel = el("existingContactPanel");
      const cancelBtn = el("cancelExistingContact");
      const linkBtn = el("linkExistingContact");
    
      if (!buttons.length || !panel) return;
    
      buttons.forEach(function (button) {
        button.addEventListener("click", function (event) {
          event.preventDefault();
          panel.style.display = "block";
          loadExistingContactOptions();
        });
      });
    
      if (cancelBtn) {
        cancelBtn.addEventListener("click", function (event) {
          event.preventDefault();
          panel.style.display = "none";
        });
      }
    
      if (linkBtn) {
        linkBtn.addEventListener("click", async function (event) {
          event.preventDefault();
    
          const contactName = el("existingContactSelect") ? el("existingContactSelect").value : "";
          const relationshipType = el("existingContactRelationship") ? el("existingContactRelationship").value : "";
          const isBilling = el("existingContactBilling") && el("existingContactBilling").checked ? 1 : 0;
    
          if (!contactName) {
            showError("Please select a contact.");
            return;
          }
    
          try {
            linkBtn.disabled = true;
            linkBtn.textContent = "Linking...";
    
            await apiPost("link_existing_contact_to_client", {
              client_name: getClientName(),
              contact_name: contactName,
              relationship_type: relationshipType,
              is_billing_contact: isBilling
            });
    
            showSuccess("Contact linked");
            window.location.reload();
          } catch (error) {
            showError(error.message || "Could not link contact.");
          } finally {
            linkBtn.disabled = false;
            linkBtn.textContent = "Link Contact";
          }
        });
      }
    }

  function initFileUpload() {
    const input = el("clientFileUploadInput");
    if (!input) return;

    input.addEventListener("change", async function () {
      const file = input.files && input.files[0];
      if (!file) return;

      const status = el("clientFileUploadStatus");
      if (status) status.textContent = "Uploading...";

      const formData = new FormData();
      formData.append("file", file);
      formData.append("is_private", 1);
      formData.append("doctype", "Client");
      formData.append("docname", getClientName());

      try {
        const response = await fetch("/api/method/upload_file", {
          method: "POST",
          credentials: "same-origin",
          headers: { "X-Frappe-CSRF-Token": getCsrfToken() },
          body: formData
        });

        const data = await response.json();

        if (!response.ok || data.exc) {
          throw new Error(data.message || "Could not upload the file.");
        }

        window.location.reload();
      } catch (error) {
        if (status) status.textContent = "";
        showError(error.message || "Could not upload the file.");
      }
    });
  }

  function init() {
    if (!el("clientDetailsForm")) return;

    initTabs();
    initEditButton();
    initInvoiceButton();
    initFileUpload();
    initAddNote();
    initLinkOptions();
    initPrimaryCoachDefaults();
    initFullNameBuilder();
    initAgeBuilder();
    initCompletedPackToggle();
    initTravelChargeToggle();
    initChangeRequest();
    initExistingContactModal();
    initTherapyLocationModal();
    initSendInvoiceModal();
    initDiagnosisRows();
    initSaveBeforeNewContactLinks();

    if (roleConfig.role === "session_worker") {
      loadSessionWorkerContacts();
      loadSessionWorkerNotes();
      loadSessionWorkerAppointments();
    }
  }

  window.TRKClientDetails = {
    apiPost: apiPost,
    el: el,
    escapeHtml: escapeHtml,
    qsa: qsa,
    renderSimpleTable: renderSimpleTable,
    showError: showError,
    showSuccess: showSuccess,
    activateTab: activateTab
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
