(function () {
  function el(id) {
    return document.getElementById(id);
  }

  function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta && meta.content ? meta.content : "";
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
      throw new Error(data.message || "Could not save.");
    }

    return data.message || data;
  }

  function initTabs() {
    const buttons = document.querySelectorAll(".dashboard-tab-btn");
    const panels = document.querySelectorAll(".dashboard-tab-panel");

    buttons.forEach(function (button) {
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
  
    const photoWrap = document.querySelector(".js-profile-photo-wrap");
    if (photoWrap) {
      photoWrap.style.display = isEditing ? "" : "none";
    }
  
    const actions = document.querySelector(".js-profile-save-actions");
    if (actions) {
      actions.style.display = isEditing ? "" : "none";
    }
  
    const editBtn = el("editProfileBtn");
    if (editBtn) {
      editBtn.textContent = isEditing ? "Save" : "Edit Profile";
      editBtn.classList.toggle("is-save-mode", isEditing);
    }
  }

  function initProfileEdit() {
    const editBtn = el("editProfileBtn");
    const cancelBtn = el("cancelProfileEditBtn");

    if (editBtn) {
      editBtn.addEventListener("click", function () {
        if (editBtn.classList.contains("is-save-mode")) {
          const form = el("sessionWorkerProfileForm");
          if (form) form.requestSubmit();
          return;
        }
    
        setProfileEditMode(true);
      });
    }

    if (cancelBtn) {
      cancelBtn.addEventListener("click", function () {
        window.location.reload();
      });
    }
  }

  function initProfileForm() {
    const form = el("sessionWorkerProfileForm");
    const message = el("sessionWorkerProfileMessage");

    if (!form) return;

    form.addEventListener("submit", async function (event) {
      event.preventDefault();

      if (message) {
        message.textContent = "Saving...";
      }

      try {
        const formData = new FormData(form);

        const result = await postForm(
          "dashboard.api.session_worker.profile.update_my_session_worker_profile",
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

  function initBankingChangeRequest() {
    const openBtn = el("requestBankingChangeBtn");
    const cancelBtn = el("cancelBankingChangeBtn");
    const panel = el("bankingChangeRequestPanel");
    const form = el("bankingChangeRequestForm");
    const message = el("bankingChangeRequestMessage");

    if (openBtn && panel) {
      openBtn.addEventListener("click", function () {
        panel.style.display = "";
        openBtn.style.display = "none";
      });
    }

    if (cancelBtn && panel && openBtn) {
      cancelBtn.addEventListener("click", function () {
        panel.style.display = "none";
        openBtn.style.display = "";
        if (form) form.reset();
      });
    }

    if (!form) return;

    form.addEventListener("submit", async function (event) {
      event.preventDefault();

      if (message) {
        message.textContent = "Submitting...";
      }

      try {
        const formData = new FormData(form);

        const result = await postJson(
          "dashboard.api.session_worker.profile.request_my_banking_change",
          {
            new_banking_details: formData.get("new_banking_details"),
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
    document.querySelectorAll(".legal-record-form").forEach(function (form) {
      form.addEventListener("submit", async function (event) {
        event.preventDefault();

        const message = form.querySelector(".legal-record-message");
        const recordType = form.getAttribute("data-record-type");

        if (message) {
          message.textContent = "Saving...";
        }

        try {
          const formData = new FormData(form);
          formData.append("record_type", recordType);

          const result = await postForm(
            "dashboard.api.session_worker.profile.add_my_legal_record",
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
    initTabs();
    initProfileEdit();
    initProfileForm();
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
