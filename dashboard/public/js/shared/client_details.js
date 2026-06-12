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

  function el(id) {
    return document.getElementById(id);
  }

  function qsa(selector, root) {
    return Array.from((root || document).querySelectorAll(selector));
  }

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

  function applyEditMode(isEditing, isSaving) {
    qsa("[data-client-field='1']").forEach(function (field) {
      setFieldState(field, isEditing);
    });

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
          const selectField = row.querySelector("[data-diagnosis-field='diagnoses']");
          const newField = row.querySelector("[data-diagnosis-field='new_diagnosis']");
          const noteField = row.querySelector("[data-diagnosis-field='note']");
          const dateField = row.querySelector("[data-diagnosis-field='date']");
    
          diagnosisRows.push({
            diagnoses: selectField ? selectField.value : "",
            new_diagnosis: newField ? newField.value : "",
            note: noteField ? noteField.value : "",
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

    try {
      await apiPost("add_client_note", {
        client_name: getClientName(),
        note_text: noteText
      });

      field.value = "";
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
            "<td>" + escapeHtml(row.company || "—") + "</td>" +
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
        return (
          "<tr>" +
            "<td>" + formatDate(row.note_date || row.session_date) + "</td>" +
            "<td class=\"dashboard-note-user-cell\">" + escapeHtml(row.note_user_name || row.user_full_name || row.note_user || row.user || "—") + "</td>" +
            "<td>" + escapeHtml(row.note_text || row.notes || "—") + "</td>" +
          "</tr>"
        );
      });

      renderSimpleTable("clientNotesTableBody", rows, "No notes found.", 3);
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

    function initDiagnosisRows() {
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
            '<select class="dashboard-select" data-diagnosis-field="diagnoses" data-link-doctype="Diagnosis Option">' +
              '<option value=""></option>' +
            '</select>' +
            '<input class="dashboard-input" data-diagnosis-field="new_diagnosis" placeholder="Or type new diagnosis" style="margin-top:6px;">' +
          '</td>' +
          '<td><input class="dashboard-input" data-diagnosis-field="note"></td>' +
          '<td><input type="date" class="dashboard-input" data-diagnosis-field="date"></td>';
  
        body.appendChild(row);
  
        const select = row.querySelector("select[data-link-doctype]");
        if (select) {
          loadLinkOptions(select);
        }
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

  function init() {
    if (!el("clientDetailsForm")) return;

    initTabs();
    initEditButton();
    initInvoiceButton();
    initAddNote();
    initLinkOptions();
    initFullNameBuilder();
    initAgeBuilder();
    initChangeRequest();
    initExistingContactModal();
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
