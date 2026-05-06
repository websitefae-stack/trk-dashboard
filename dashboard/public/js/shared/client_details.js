(function () {
  const roleConfig = window.TRKClientDetailsRole || {
    role: "coach",
    baseUrl: "/coach_db",
    apiBase: "dashboard.api.shared.client_details",
    storageKey: "client_details_active_tab",
    canEdit: true,
    canInvoice: true,
    canRequestChange: false
  };

  function el(id) {
    return document.getElementById(id);
  }

  function qsa(selector) {
    return Array.from(document.querySelectorAll(selector));
  }

  function activateTab(targetId) {
    if (!targetId) return;

    qsa(".dashboard-tab-btn").forEach(function (btn) {
      btn.classList.toggle("is-active", btn.dataset.tabTarget === targetId);
    });

    qsa(".dashboard-tab-panel").forEach(function (panel) {
      panel.classList.toggle("is-active", panel.id === targetId);
    });

    try {
      sessionStorage.setItem(roleConfig.storageKey, targetId);
    } catch (e) {}
  }

  function initTabs() {
    const buttons = qsa(".dashboard-tab-btn");

    if (!buttons.length) return;

    buttons.forEach(function (btn) {
      btn.addEventListener("click", function (event) {
        event.preventDefault();
        activateTab(btn.dataset.tabTarget);
      });
    });

    let saved = "";

    try {
      saved = sessionStorage.getItem(roleConfig.storageKey) || "";
    } catch (e) {}

    const savedBtn = saved
      ? buttons.find(function (btn) {
          return btn.dataset.tabTarget === saved;
        })
      : null;

    if (savedBtn) {
      activateTab(saved);
      return;
    }

    activateTab(buttons[0].dataset.tabTarget);
  }

  function getCsrfToken() {
    const hidden = el("csrfToken");
    if (hidden && hidden.value) return hidden.value;

    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta && meta.content ? meta.content : "";
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

    const data = await response.json();

    if (!response.ok || data.exc) {
      throw new Error(data.message || "Request failed");
    }

    return data.message;
  }

  function getClientName() {
    const field = el("clientDocname");
    return field ? field.value : "";
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

  function setEditMode(isEditing) {
    qsa("[data-client-field='1']").forEach(function (field) {
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
    });

    const btn = el("editClient");
    if (btn) {
      if (!roleConfig.canEdit) {
        btn.style.display = "none";
      } else {
        btn.textContent = isEditing ? "Save Client" : "Edit Client";
      }
    }

    const invoiceBtn = el("createClientInvoice");
    if (invoiceBtn && !roleConfig.canInvoice) {
      invoiceBtn.style.display = "none";
    }
  }

  function collectClientData() {
    const data = {};

    qsa("[data-client-field='1']").forEach(function (field) {
      const name = field.dataset.fieldname;
      if (!name) return;

      data[name] = field.type === "checkbox" ? (field.checked ? 1 : 0) : field.value;
    });

    return data;
  }

  async function saveClient() {
    try {
      const result = await apiPost("save_client", {
        docname: getClientName(),
        data: JSON.stringify(collectClientData())
      });

      if (result && result.name && !getClientName()) {
        window.location.href = roleConfig.baseUrl + "/client_details?name=" + encodeURIComponent(result.name);
        return;
      }

      showSuccess("Client saved");
      setEditMode(false);
    } catch (error) {
      showError(error.message || "Could not save client.");
    }
  }

  function initEditButton() {
    const btn = el("editClient");
    if (!btn) return;

    let editing = false;

    if (!roleConfig.canEdit) {
      btn.style.display = "none";
      return;
    }

    btn.addEventListener("click", function (event) {
      event.preventDefault();

      if (!editing) {
        editing = true;
        setEditMode(true);
      } else {
        editing = false;
        saveClient();
      }
    });

    setEditMode(false);
  }

  function initInvoiceButton() {
    const btn = el("createClientInvoice");
    if (!btn) return;

    if (!roleConfig.canInvoice) {
      btn.style.display = "none";
      return;
    }

    btn.addEventListener("click", function (event) {
      event.preventDefault();

      const client = getClientName();

      if (!client) {
        showError("Please save the client before creating an invoice.");
        return;
      }

      window.location.href = roleConfig.baseUrl + "/invoice_details?new=1&client=" + encodeURIComponent(client);
    });
  }

  function initAddNote() {
    const btn = el("addClientNote");
    const field = el("newClientNoteText");

    if (!btn || !field) return;

    btn.addEventListener("click", async function (event) {
      event.preventDefault();

      const note = field.value || "";

      if (!note.trim()) {
        showError("Enter a note");
        return;
      }

      try {
        await apiPost("add_client_note", {
          client_name: getClientName(),
          note_text: note
        });

        showSuccess("Note added");
        window.location.reload();
      } catch (error) {
        showError(error.message || "Could not add note.");
      }
    });
  }

  function initChangeRequest() {
    if (!roleConfig.canRequestChange) return;

    const btn = el("requestChangeButton");
    const modal = el("changeRequestModal");

    if (!btn || !modal) return;

    function openModal(event) {
      event.preventDefault();
      modal.classList.add("is-open");
      document.body.classList.add("dashboard-modal-open");
    }

    function closeModal(event) {
      event.preventDefault();
      modal.classList.remove("is-open");
      document.body.classList.remove("dashboard-modal-open");
    }

    btn.addEventListener("click", openModal);

    if (el("closeChangeRequestModal")) {
      el("closeChangeRequestModal").addEventListener("click", closeModal);
    }

    if (el("closeChangeRequestModalFooter")) {
      el("closeChangeRequestModalFooter").addEventListener("click", closeModal);
    }
  }

  function init() {
    if (!el("clientDetailsForm")) return;

    initTabs();
    initEditButton();
    initInvoiceButton();
    initAddNote();
    initChangeRequest();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
