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
    return el("csrfToken")?.value || document.querySelector('meta[name="csrf-token"]')?.content || "";
  }

  function parseServerMessages(serverMessages) {
    if (!serverMessages) return "";

    try {
      const decoded = JSON.parse(serverMessages);
      return decoded.map((msg) => {
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
    if (window.frappe?.show_alert) {
      window.frappe.show_alert({ message, indicator: "green" });
    } else {
      alert(message);
    }
  }

  function showError(message) {
    if (window.frappe?.msgprint) {
      window.frappe.msgprint(message);
    } else {
      alert(message);
    }
  }

  async function apiPost(method, args) {
    const body = new URLSearchParams();

    Object.entries(args || {}).forEach(([key, value]) => {
      body.append(key, typeof value === "string" ? value : JSON.stringify(value));
    });

    const response = await fetch(`/api/method/${method}`, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Frappe-CSRF-Token": getCsrfToken()
      },
      body: body.toString()
    });

    const data = await response.json().catch(() => ({}));

    if (!response.ok || data.exc) {
      throw new Error(parseServerMessages(data._server_messages) || data.message || data.exception || "Request failed.");
    }

    return data;
  }

  function activateTab(targetId) {
    if (!targetId) return;

    qsa(".dashboard-tab-btn[data-tab-target]").forEach((button) => {
      button.classList.toggle("is-active", button.dataset.tabTarget === targetId);
    });

    qsa(".dashboard-tab-panel").forEach((panel) => {
      panel.classList.toggle("is-active", panel.id === targetId);
    });
  }

  function initTabs() {
    qsa(".dashboard-tab-btn[data-tab-target]").forEach((button) => {
      button.addEventListener("click", function () {
        activateTab(button.dataset.tabTarget);
      });
    });

    const first = qsa(".dashboard-tab-btn[data-tab-target]")[0];
    if (first) activateTab(first.dataset.tabTarget);
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

    qsa("[data-contact-field='1']").forEach((field) => {
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
      const method = el("saveContactMethod")?.value;
      const result = await apiPost(method, {
        docname: el("contactDocname")?.value || "",
        data: JSON.stringify(collectContactData())
      });

      const msg = result.message || {};
      if (msg.name) {
        el("contactDocname").value = msg.name;

        if (window.location.search.indexOf("new=1") !== -1) {
          const baseUrl = el("contactBaseUrl")?.value || "";
          window.history.replaceState({}, "", `${baseUrl}/contact_details?name=${encodeURIComponent(msg.name)}`);
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

    editMode = el("contactIsNew")?.value === "1";
    applyEditMode();

    editButton.addEventListener("click", function () {
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
          client_name: el("changeRequestClient")?.value || "",
          request_type: el("changeRequestType")?.value || "Contact Details",
          requested_section: el("changeRequestSection")?.value || "Contact Details",
          requested_change: el("changeRequestText")?.value || "",
          reason: el("changeRequestReason")?.value || ""
        });

        el("changeRequestSection").value = "";
        el("changeRequestText").value = "";
        el("changeRequestReason").value = "";

        showSuccess("Change request submitted");
      } catch (error) {
        showError(error.message || "Could not submit change request.");
      } finally {
        button.disabled = false;
        button.textContent = "Submit Change Request";
      }
    });
  }

  function init() {
    if (!el("contactDetailsForm")) return;

    initTabs();
    initEdit();
    initRefreshBack();
    initChangeRequest();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
