(function () {
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

  function setEditMode(isEditing) {
    const form = document.getElementById("coachSessionWorkerForm");
    const editBtn = document.getElementById("editDetailsBtn");
    const saveBtn = document.querySelector(".js-save-edit-btn");
    const cancelBtn = document.querySelector(".js-cancel-edit-btn");

    if (!form) return;

    form.classList.toggle("dashboard-edit-locked", !isEditing);

    form.querySelectorAll("input, select, textarea").forEach(function (field) {
      if (field.type === "hidden") return;
      field.disabled = !isEditing;
    });

    if (editBtn) editBtn.style.display = isEditing ? "none" : "";
    if (saveBtn) saveBtn.style.display = isEditing ? "" : "none";
    if (cancelBtn) cancelBtn.style.display = isEditing ? "" : "none";
  }

  function init() {
    const form = document.getElementById("coachSessionWorkerForm");
    const message = document.getElementById("coachSessionWorkerMessage");
    const editBtn = document.getElementById("editDetailsBtn");
    const cancelBtn = document.getElementById("cancelDetailsEditBtn");

    if (!form) return;

    setEditMode(false);

    if (editBtn) {
      editBtn.addEventListener("click", function () {
        setEditMode(true);
      });
    }

    if (cancelBtn) {
      cancelBtn.addEventListener("click", function () {
        window.location.reload();
      });
    }

    form.addEventListener("submit", async function (event) {
      event.preventDefault();

      if (message) message.textContent = "Saving...";

      try {
        const formData = new FormData(form);
        const sessionWorkerName = formData.get("session_worker_name");

        const result = await postForm(
          "dashboard.api.coach.session_workers.update_linked_session_worker?session_worker_name=" + encodeURIComponent(sessionWorkerName),
          formData
        );

        if (message) message.textContent = result.message || "Saved.";
        setEditMode(false);
      } catch (error) {
        if (message) message.textContent = error.message || "Could not save.";
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
