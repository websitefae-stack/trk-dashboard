(function () {
  "use strict";

  if (window.__trkSharedProfileLoaded) {
    return;
  }

  window.__trkSharedProfileLoaded = true;

  function el(id) {
    return document.getElementById(id);
  }

  function getProfileConfig() {
    const page = document.querySelector("[data-profile-role]");

    return {
      role: page ? page.getAttribute("data-profile-role") || "" : "",
      formId: page ? page.getAttribute("data-profile-form-id") || "profileForm" : "profileForm",
      messageId: page ? page.getAttribute("data-profile-message-id") || "profileMessage" : "profileMessage"
    };
  }

  function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');

    if (meta && meta.content) {
      return meta.content;
    }

    if (window.frappe && window.frappe.csrf_token) {
      return window.frappe.csrf_token;
    }

    const match = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  async function postForm(method, formData) {
    const response = await fetch("/api/method/" + method, {
      method: "POST",
      body: formData,
      credentials: "same-origin",
      headers: {
        "X-Frappe-CSRF-Token": getCsrfToken()
      }
    });

    const data = await response.json();

    if (!response.ok || data.exc) {
      console.error(data);
      throw new Error(data.message || "Could not save.");
    }

    return data.message || data;
  }

  async function postJson(method, payload) {
    const response = await fetch("/api/method/" + method, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-Frappe-CSRF-Token": getCsrfToken()
      },
      body: JSON.stringify(payload || {})
    });

    const data = await response.json();

    if (!response.ok || data.exc) {
      console.error(data);
      throw new Error(data.message || "Could not save.");
    }

    return data.message || data;
  }

  function initTabs() {
    const buttons = document.querySelectorAll(".dashboard-tab-btn");
    const panels = document.querySelectorAll(".dashboard-tab-panel");

    buttons.forEach(function (button) {
      if (button.dataset.profileTabBound === "1") return;
      button.dataset.profileTabBound = "1";

      button.addEventListener("click", function () {
        const tab = button.getAttribute("data-tab");

        buttons.forEach(function (btn) {
          btn.classList.remove("is-active");
        });

        panels.forEach(function (panel) {
          const isActive = panel.getAttribute("data-tab-panel") === tab;
          panel.classList.toggle("is-active", isActive);
          panel.style.display = isActive ? "" : "none";
        });

        button.classList.add("is-active");
      });
    });
  }

  function setProfileEditMode(isEditing) {
    document.querySelectorAll(".js-profile-editable").forEach(function (field) {
      field.readOnly = !isEditing;
    });

    document.querySelectorAll(".js-profile-editable-file").forEach(function (field) {
      field.disabled = !isEditing;
    });

    document.querySelectorAll(".js-bank-editable").forEach(function (field) {
      field.readOnly = !isEditing;
    });

    const photoWrap = document.querySelector(".js-profile-photo-wrap");
    if (photoWrap) {
      photoWrap.style.display = isEditing ? "" : "none";
    }

    const actions = document.querySelector(".js-profile-save-actions");
    if (actions) {
      actions.style.display = isEditing ? "" : "none";
    }

    const bankActions = document.querySelector(".js-bank-save-actions");
    if (bankActions) {
      bankActions.style.display = isEditing ? "" : "none";
    }

    const editBtn = el("editProfileBtn");
    if (editBtn) {
      editBtn.textContent = isEditing ? "Save" : "Edit Profile";
      editBtn.classList.toggle("is-save-mode", isEditing);
    }
  }

  function initProfileEdit() {
    const config = getProfileConfig();
    const editBtn = el("editProfileBtn");
    const cancelBtn = el("cancelProfileEditBtn");

    if (editBtn && editBtn.dataset.profileEditBound !== "1") {
      editBtn.dataset.profileEditBound = "1";

      editBtn.addEventListener("click", function (event) {
        event.preventDefault();

        if (editBtn.classList.contains("is-save-mode")) {
          const form = el(config.formId);

          if (form) {
            form.requestSubmit();
          }

          const bankForm = el("bankingDetailsForm");
          if (bankForm) {
            bankForm.requestSubmit();
          }

          return;
        }

        setProfileEditMode(true);
      });
    }

    if (cancelBtn && cancelBtn.dataset.profileCancelBound !== "1") {
      cancelBtn.dataset.profileCancelBound = "1";

      cancelBtn.addEventListener("click", function () {
        window.location.reload();
      });
    }
  }

  function initProfileForm() {
    const config = getProfileConfig();
    const form = el(config.formId);
    const message = el(config.messageId);

    if (!form || form.dataset.profileFormBound === "1") {
      return;
    }

    form.dataset.profileFormBound = "1";

    form.addEventListener("submit", async function (event) {
      event.preventDefault();

      if (message) {
        message.textContent = "Saving...";
      }

      try {
        const formData = new FormData(form);
        formData.append("role", config.role);

        const result = await postForm(
          "dashboard.api.shared.profile.update_my_profile",
          formData
        );

        if (message) {
          message.textContent = result.message || "Profile saved.";
        }

        setTimeout(function () {
          window.location.reload();
        }, 700);

      } catch (error) {
        if (message) {
          message.textContent = error.message || "Could not save profile.";
        }
      }
    });
  }

  function initBankingDetailsForm() {
    const config = getProfileConfig();
    const form = el("bankingDetailsForm");
    const message = el("bankingDetailsMessage");

    if (!form || form.dataset.bankingDetailsBound === "1") {
      return;
    }

    form.dataset.bankingDetailsBound = "1";

    form.addEventListener("submit", async function (event) {
      event.preventDefault();

      if (!form.getAttribute("data-can-edit-directly")) {
        return;
      }

      if (message) {
        message.textContent = "Saving banking details...";
      }

      try {
        const formData = new FormData(form);

        const result = await postJson(
          "dashboard.api.shared.profile.update_my_banking_details",
          {
            role: config.role,
            account_name: formData.get("account_name"),
            bank: formData.get("bank"),
            bank_account_no: formData.get("bank_account_no"),
            branch_code: formData.get("branch_code"),
            iban: formData.get("iban")
          }
        );

        if (message) {
          message.textContent = result.message || "Banking details updated.";
        }

      } catch (error) {
        if (message) {
          message.textContent = error.message || "Could not save banking details.";
        }
      }
    });
  }

  function initBankingChangeRequest() {
    const config = getProfileConfig();

    const openBtn = el("requestBankingChangeBtn");
    const cancelBtn = el("cancelBankingChangeBtn");
    const panel = el("bankingChangeRequestPanel");
    const form = el("bankingChangeRequestForm");
    const message = el("bankingChangeRequestMessage");

    if (openBtn && panel && openBtn.dataset.bankingOpenBound !== "1") {
      openBtn.dataset.bankingOpenBound = "1";

      openBtn.addEventListener("click", function () {
        panel.style.display = "";
        openBtn.style.display = "none";
      });
    }

    if (cancelBtn && panel && openBtn && cancelBtn.dataset.bankingCancelBound !== "1") {
      cancelBtn.dataset.bankingCancelBound = "1";

      cancelBtn.addEventListener("click", function () {
        panel.style.display = "none";
        openBtn.style.display = "";

        if (form) {
          form.reset();
        }

        if (message) {
          message.textContent = "";
        }
      });
    }

    if (!form || form.dataset.bankingFormBound === "1") {
      return;
    }

    form.dataset.bankingFormBound = "1";

    form.addEventListener("submit", async function (event) {
      event.preventDefault();

      if (message) {
        message.textContent = "Submitting...";
      }

      try {
        const formData = new FormData(form);

        const result = await postJson(
          "dashboard.api.shared.profile.request_my_banking_change",
          {
            role: config.role,
            account_name: formData.get("account_name"),
            bank: formData.get("bank"),
            bank_account_no: formData.get("bank_account_no"),
            branch_code: formData.get("branch_code"),
            iban: formData.get("iban"),
            banking_change_reason: formData.get("banking_change_reason")
          }
        );

        if (message) {
          message.textContent = result.message || "Request submitted.";
        }

        setTimeout(function () {
          window.location.reload();
        }, 900);

      } catch (error) {
        if (message) {
          message.textContent = error.message || "Could not submit request.";
        }
      }
    });
  }

  function initLegalForms() {
    const config = getProfileConfig();

    document.querySelectorAll(".legal-record-form").forEach(function (form) {
      if (form.dataset.legalFormBound === "1") {
        return;
      }

      form.dataset.legalFormBound = "1";

      form.addEventListener("submit", async function (event) {
        event.preventDefault();

        const message = form.querySelector(".legal-record-message");
        const recordType = form.getAttribute("data-record-type");

        if (message) {
          message.textContent = "Saving...";
        }

        try {
          const formData = new FormData(form);

          formData.append("role", config.role);
          formData.append("record_type", recordType);

          const result = await postForm(
            "dashboard.api.shared.profile.add_my_legal_record",
            formData
          );

          if (message) {
            message.textContent = result.message || "Record added.";
          }

          setTimeout(function () {
            window.location.reload();
          }, 800);

        } catch (error) {
          if (message) {
            message.textContent = error.message || "Could not add record.";
          }
        }
      });
    });
  }

  function initLegalToggleButtons() {
    document.querySelectorAll(".legal-toggle-btn").forEach(function (button) {
      if (button.dataset.legalToggleBound === "1") {
        return;
      }

      button.dataset.legalToggleBound = "1";

      button.addEventListener("click", function () {
        const targetType = button.getAttribute("data-target-type");

        document.querySelectorAll(".legal-add-section").forEach(function (section) {
          const form = section.querySelector(".legal-record-form");
          const recordType = form ? form.getAttribute("data-record-type") : "";

          if (recordType === targetType) {
            const isHidden = section.style.display === "none";
            section.style.display = isHidden ? "" : "none";
          } else {
            section.style.display = "none";
          }
        });
      });
    });
  }

  function init() {
    const page = document.querySelector("[data-profile-role]");

    if (!page) {
      return;
    }

    initTabs();
    initProfileEdit();
    initProfileForm();
    initBankingDetailsForm();
    initBankingChangeRequest();
    initLegalForms();
    initLegalToggleButtons();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
