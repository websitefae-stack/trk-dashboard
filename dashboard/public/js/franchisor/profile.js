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
          const form = el("coachProfileForm");
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
    const form = el("coachProfileForm");
    const message = el("coachProfileMessage");

    if (!form) return;

    form.addEventListener("submit", async function (event) {
      event.preventDefault();

      if (message) {
        message.textContent = "Saving...";
      }

      try {
        const formData = new FormData(form);

        const result = await postForm(
          "dashboard.api.coach.profile.update_my_coach_profile",
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

  function init() {
    initTabs();
    initProfileEdit();
    initProfileForm();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
