(function () {
  let editMode = false;
  let isSaving = false;

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

  function parseServerMessages(serverMessages) {
    if (!serverMessages) return "";

    try {
      const decoded = JSON.parse(serverMessages);

      return decoded.map(function (msg) {
        try {
          return JSON.parse(msg).message || msg;
        } catch (e) {
          return msg;
        }
      }).join("<br>");
    } catch (e) {
      return "";
    }
  }

  function showSuccess(message) {
    if (window.frappe && typeof window.frappe.show_alert === "function") {
      window.frappe.show_alert({ message: message, indicator: "green" });
    } else {
      alert(message);
    }
  }

  function showError(message) {
    if (window.frappe && typeof window.frappe.msgprint === "function") {
      window.frappe.msgprint(message);
    } else {
      alert(message);
    }
  }

  async function apiPost(method, args) {
    const body = new URLSearchParams();

    Object.entries(args || {}).forEach(function ([key, value]) {
      body.append(key, typeof value === "string" ? value : JSON.stringify(value));
    });

    const response = await fetch("/api/method/" + method, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Frappe-CSRF-Token": getCsrfToken()
      },
      body: body.toString()
    });

    const data = await response.json().catch(function () {
      return {};
    });

    if (!response.ok || data.exc) {
      throw new Error(
        parseServerMessages(data._server_messages) ||
        data.message ||
        data.exception ||
        "Request failed."
      );
    }

    return data;
  }

  function activateTab(targetId) {
    if (!targetId) return;

    qsa(".dashboard-tab-btn[data-tab-target]").forEach(function (button) {
      const isActive = button.dataset.tabTarget === targetId;
      button.classList.toggle("is-active", isActive);
      button.setAttribute("aria-selected", isActive ? "true" : "false");
    });

    qsa(".dashboard-tab-panel").forEach(function (panel) {
      const isActive = panel.id === targetId;

      panel.classList.toggle("is-active", isActive);
      panel.classList.toggle("dashboard-tab-panel-active", isActive);

      if (isActive) {
        panel.removeAttribute("hidden");
        panel.removeAttribute("aria-hidden");
        panel.style.cssText += ";display:block!important;visibility:visible!important;opacity:1!important;";
      } else {
        panel.setAttribute("hidden", "hidden");
        panel.setAttribute("aria-hidden", "true");
        panel.style.cssText += ";display:none!important;visibility:hidden!important;opacity:0!important;";
      }
    });

    try {
      sessionStorage.setItem(getStorageKey(), targetId);
    } catch (e) {}
  }

  function getScope() {
    return el("contactDetailsScope") ? el("contactDetailsScope").value : inferScopeFromPath();
  }

  function inferScopeFromPath() {
    const path = window.location.pathname || "";

    if (path.startsWith("/franchisor_db")) return "franchisor";
    if (path.startsWith("/session_worker_db")) return "session_worker";

    return "coach";
  }

  function getBaseUrl() {
    const field = el("contactBaseUrl");
    if (field && field.value) return field.value;

    const scope = getScope();

    if (scope === "franchisor") return "/franchisor_db";
    if (scope === "session_worker") return "/session_worker_db";

    return "/coach_db";
  }

  function getSaveMethod() {
    const field = el("saveContactMethod");
    return field && field.value
      ? field.value
      : "dashboard.api.shared.contact_details.save_contact";
  }

  function getStorageKey() {
    return getScope() + "_contact_details_active_tab";
  }

  function initTabs() {
    const buttons = qsa(".dashboard-tab-btn[data-tab-target]");

    if (!buttons.length) return;

    document.addEventListener("click", function (event) {
      const button = event.target.closest(".dashboard-tab-btn[data-tab-target]");
      if (!button) return;

      event.preventDefault();
      event.stopPropagation();

      activateTab(button.dataset.tabTarget);
    }, true);

    let savedTab = "";

    if (window.location.search.indexOf("new=1") !== -1) {
      savedTab = "contact-details-tab";
      try {
        sessionStorage.setItem(getStorageKey(), savedTab);
      } catch (e) {}
    } else {
      try {
        savedTab = sessionStorage.getItem(getStorageKey()) || "";
      } catch (e) {
        savedTab = "";
      }
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

  function setFieldState(field) {
    const readonly = field.dataset.metaReadonly === "1";
    const tag = field.tagName.toUpperCase();
    const type = (field.type || "").toLowerCase();

    if (tag === "SELECT" || type === "checkbox") {
      field.disabled = readonly || !editMode;
    } else {
      field.readOnly = readonly || !editMode;
    }
  }

  function applyEditMode() {
    qsa("[data-contact-field='1']").forEach(setFieldState);

    const button = el("editContact");

    if (button) {
      button.textContent = isSaving ? "Saving..." : editMode ? "Save Contact" : "Edit Contact";
      button.disabled = isSaving;
    }

    document.body.classList.toggle("contact-edit-mode", editMode);
    document.body.classList.toggle("dashboard-detail-edit-mode", editMode);
  }

  function collectContactData() {
    const data = {};

    qsa("[data-contact-field='1']").forEach(function (field) {
      const fieldname = field.dataset.fieldname;
      const fieldtype = field.dataset.fieldtype || "Data";

      if (!fieldname || field.dataset.metaReadonly === "1") return;

      if ((field.type || "").toLowerCase() === "checkbox" || fieldtype === "Check") {
        data[fieldname] = field.checked ? 1 : 0;
      } else {
        data[fieldname] = field.value;
      }
    });

    return data;
  }

  async function saveContact() {
    if (isSaving) return;

    isSaving = true;
    applyEditMode();

    try {
      const result = await apiPost(getSaveMethod(), {
        scope: getScope(),
        docname: el("contactDocname") ? el("contactDocname").value || "" : "",
        data: JSON.stringify(collectContactData())
      });

      const msg = result.message || {};

      if (msg.name && el("contactDocname")) {
        el("contactDocname").value = msg.name;

        if (window.location.search.indexOf("new=1") !== -1) {
          window.history.replaceState(
            {},
            "",
            getBaseUrl() + "/contact_details?name=" + encodeURIComponent(msg.name)
          );
        }
      }

      editMode = false;
      isSaving = false;
      applyEditMode();
      showSuccess("Contact saved");
    } catch (error) {
      isSaving = false;
      applyEditMode();
      showError(error.message || "Could not save contact.");
    }
  }

  function initEdit() {
    const editButton = el("editContact");
    if (!editButton) return;

    editMode = el("contactIsNew") && el("contactIsNew").value === "1";

    applyEditMode();

    editButton.addEventListener("click", function (event) {
      event.preventDefault();

      if (!editMode) {
        editMode = true;
        applyEditMode();
      } else {
        saveContact();
      }
    });
  }

  function initRefreshBack() {
    const refresh = el("refreshContactDetails");

    if (refresh) {
      refresh.addEventListener("click", function () {
        window.location.reload();
      });
    }
  }

  function initChangeRequest() {
    const button = el("submitContactChangeRequest");
    if (!button) return;

    button.addEventListener("click", async function () {
      try {
        button.disabled = true;
        button.textContent = "Submitting...";

        await apiPost("dashboard.api.session_worker.change_requests.submit_change_request", {
          client_name: el("changeRequestClient") ? el("changeRequestClient").value || "" : "",
          request_type: el("changeRequestType") ? el("changeRequestType").value || "Contact Details" : "Contact Details",
          requested_section: el("changeRequestSection") ? el("changeRequestSection").value || "Contact Details" : "Contact Details",
          requested_change: el("changeRequestText") ? el("changeRequestText").value || "" : "",
          reason: el("changeRequestReason") ? el("changeRequestReason").value || "" : ""
        });

        if (el("changeRequestSection")) el("changeRequestSection").value = "";
        if (el("changeRequestText")) el("changeRequestText").value = "";
        if (el("changeRequestReason")) el("changeRequestReason").value = "";

        showSuccess("Change request submitted");
      } catch (error) {
        showError(error.message || "Could not submit change request.");
      } finally {
        button.disabled = false;
        button.textContent = "Submit Change Request";
      }
    });
  }

  function getContactField(fieldname) {
    return document.querySelector('[data-fieldname="' + fieldname + '"]');
  }

  function isNewContactPage() {
    return el("contactIsNew") && el("contactIsNew").value === "1";
  }

  function updateNewContactFullName() {
    if (!isNewContactPage()) return;

    const fullNameField = getContactField("full_name");
    if (!fullNameField) return;

    const first = (getContactField("first_name") && getContactField("first_name").value) || "";
    const last = (getContactField("last_name") && getContactField("last_name").value) || "";

    if (!fullNameField.value || fullNameField.dataset.autoBuilt === "1") {
      fullNameField.value = [first, last].map(function (part) {
        return String(part || "").trim();
      }).filter(Boolean).join(" ");

      fullNameField.dataset.autoBuilt = "1";
    }
  }

  function initNewContactFullNameBuilder() {
    if (!isNewContactPage()) return;

    ["first_name", "last_name"].forEach(function (fieldname) {
      const field = getContactField(fieldname);
      if (!field) return;

      field.addEventListener("input", updateNewContactFullName);
      field.addEventListener("change", updateNewContactFullName);
    });

    const fullNameField = getContactField("full_name");
    if (fullNameField) {
      fullNameField.addEventListener("input", function () {
        fullNameField.dataset.autoBuilt = fullNameField.value ? "0" : "1";
      });
    }

    updateNewContactFullName();
  }

  function forceNewContactDetailsVisible() {
    if (!isNewContactPage()) return;

    const panel = el("contact-details-tab");
    if (panel) {
      panel.classList.add("is-active");
      panel.classList.add("dashboard-tab-panel-active");
      panel.removeAttribute("hidden");
      panel.removeAttribute("aria-hidden");
      panel.style.setProperty("display", "block", "important");
      panel.style.setProperty("visibility", "visible", "important");
      panel.style.setProperty("opacity", "1", "important");
    }
  }

  function init() {
    if (!el("contactDetailsForm")) return;

    forceNewContactDetailsVisible();
    initTabs();
    initEdit();
    initNewContactFullNameBuilder();
    initRefreshBack();
    initChangeRequest();
    forceNewContactDetailsVisible();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
