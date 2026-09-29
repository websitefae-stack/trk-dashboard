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

  function init() {
    const form = document.getElementById("franchisorCoachForm");
    const message = document.getElementById("franchisorCoachMessage");

    if (!form) return;

    form.addEventListener("submit", async function (event) {
      event.preventDefault();

      if (message) message.textContent = "Saving...";

      try {
        const formData = new FormData(form);
        const coachName = formData.get("coach_name");

        formData.append("coach_name", coachName);

        if (formData.get("coach_name_field") !== null) {
          formData.append("coach_name", coachName);
        }

        const result = await postForm(
          "dashboard.api.franchisor.accounts.update_coach?coach_name=" + encodeURIComponent(coachName),
          formData
        );

        if (message) message.textContent = result.message || "Saved.";
      } catch (error) {
        if (message) message.textContent = error.message || "Could not save.";
      }
    });
  }

  function initRecognitions() {
    const form = document.getElementById("addCoachRecognitionForm");
    const message = document.getElementById("coachRecognitionMessage");
    const list = document.getElementById("coachRecognitionsList");

    if (!form) return;

    form.addEventListener("submit", async function (event) {
      event.preventDefault();

      const submitBtn = form.querySelector('button[type="submit"]');
      if (submitBtn) submitBtn.disabled = true;
      if (message) message.textContent = "Adding...";

      try {
        await postForm("dashboard.api.shared.profile.add_coach_recognition", new FormData(form));
        // Simplest reliable way to show the new row in place, same as
        // client_details.js's own file-upload handler - this page has
        // no client-side render function for recognitions to update
        // in place instead.
        window.location.reload();
      } catch (error) {
        if (message) message.textContent = error.message || "Could not add recognition.";
        if (submitBtn) submitBtn.disabled = false;
      }
    });

    if (list) {
      list.addEventListener("click", async function (event) {
        const btn = event.target.closest("[data-delete-recognition]");
        if (!btn) return;

        if (!window.confirm("Delete this recognition?")) return;

        btn.disabled = true;

        try {
          const formData = new FormData();
          formData.append("coach", form.querySelector('[name="coach"]').value);
          formData.append("row_name", btn.dataset.deleteRecognition);

          await postForm("dashboard.api.shared.profile.delete_coach_recognition", formData);
          window.location.reload();
        } catch (error) {
          if (message) message.textContent = error.message || "Could not delete recognition.";
          btn.disabled = false;
        }
      });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      init();
      initRecognitions();
    });
  } else {
    init();
    initRecognitions();
  }
})();
