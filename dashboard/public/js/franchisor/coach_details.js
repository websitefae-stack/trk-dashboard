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

  function initFranchiseExpiry() {
    const btn = document.getElementById("saveCoachFranchiseExpiryBtn");
    const input = document.getElementById("coachFranchiseExpiryInput");
    const status = document.getElementById("coachFranchiseExpiryStatus");
    const form = document.getElementById("franchisorCoachForm");
    if (!btn || !input || !form) return;

    btn.addEventListener("click", async function () {
      const coachName = form.querySelector('input[name="coach_name"]').value;
      if (status) status.textContent = "Saving...";
      btn.disabled = true;

      try {
        const formData = new FormData();
        formData.append("custom_franchise_agreement_expiry_date", input.value || "");

        await postForm(
          "dashboard.api.franchisor.accounts.update_coach?coach_name=" + encodeURIComponent(coachName),
          formData
        );

        if (status) status.textContent = "Saved - reload the page to see the reminder banner.";
      } catch (error) {
        if (status) status.textContent = error.message || "Could not save.";
      } finally {
        btn.disabled = false;
      }
    });
  }

  function init() {
    const form = document.getElementById("franchisorCoachForm");
    const message = document.getElementById("franchisorCoachMessage");

    initFranchiseExpiry();

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
