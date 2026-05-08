window.TRKProfile = (function () {
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
          const active =
            panel.getAttribute("data-tab-panel") === tab;

          panel.classList.toggle("is-active", active);
          panel.style.display = active ? "" : "none";
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
      editBtn.textContent = isEditing
        ? "Save"
        : "Edit Profile";

      editBtn.classList.toggle(
        "is-save-mode",
        isEditing
      );
    }
  }

  return {
    initTabs,
    setProfileEditMode,
    postForm,
    postJson,
    el
  };
})();
