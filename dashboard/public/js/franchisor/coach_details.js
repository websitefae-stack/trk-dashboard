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

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
