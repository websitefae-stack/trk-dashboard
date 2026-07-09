(function () {
  "use strict";

  const SHARED_API = "dashboard.api.shared.leads";

  function el(id) {
    return document.getElementById(id);
  }

  function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta && meta.content ? meta.content : "";
  }

  async function apiPost(method, args) {
    const response = await fetch(`/api/method/${method}`, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-Frappe-CSRF-Token": getCsrfToken(),
      },
      body: JSON.stringify(args || {}),
    });

    const data = await response.json();

    if (!response.ok || data.exc) {
      throw new Error(data.message || "There was a problem.");
    }

    return data.message || {};
  }

  function getValue(id) {
    const field = el(id);
    return field ? field.value || "" : "";
  }

  function setValue(id, value) {
    const field = el(id);
    if (field) field.value = value ?? "";
  }

  function showMessage(message, isError) {
    const banner = el("intakeFormMessage");
    if (!banner) return;

    banner.textContent = message || "";
    banner.style.display = message ? "" : "none";
    banner.classList.toggle("dashboard-form-message-error", !!isError);
  }

  async function loadLead(lead) {
    try {
      const data = await apiPost(`${SHARED_API}.get_intake_lead`, { lead });

      if (data.already_done) {
        el("intakeForm").style.display = "none";
        showMessage("This intake form has already been completed. Thank you!", false);
        return;
      }

      setValue("intake_contact_name", data.contact_name);
      setValue("intake_contact_email", data.contact_email);
      setValue("intake_contact_mobile", data.contact_mobile);
      setValue("intake_client_name", data.client_name);
      setValue("intake_client_age", data.client_age);
      setValue("intake_postal_code", data.postal_code);
      setValue("intake_enquiry_reason", data.enquiry_reason);
      setValue("intake_how_heard", data.how_heard);

      const consentField = el("intake_consent_given");
      if (consentField) consentField.checked = !!data.consent_given;
    } catch (error) {
      el("intakeForm").style.display = "none";
      showMessage(error.message || "This intake link is invalid or has expired.", true);
    }
  }

  async function submitForm() {
    const lead = getValue("intakeLead");

    const payload = {
      lead: lead,
      contact_name: getValue("intake_contact_name").trim(),
      contact_email: getValue("intake_contact_email").trim(),
      contact_mobile: getValue("intake_contact_mobile").trim(),
      client_name: getValue("intake_client_name").trim(),
      client_age: getValue("intake_client_age").trim(),
      postal_code: getValue("intake_postal_code").trim(),
      enquiry_reason: getValue("intake_enquiry_reason").trim(),
      how_heard: getValue("intake_how_heard").trim(),
      consent_given: el("intake_consent_given") && el("intake_consent_given").checked ? 1 : 0,
    };

    if (!payload.contact_name) {
      showMessage("Please enter your name.", true);
      return;
    }

    if (!payload.client_name) {
      showMessage("Please enter the young person's name.", true);
      return;
    }

    const submitBtn = el("submitIntakeBtn");
    if (submitBtn) submitBtn.disabled = true;

    try {
      await apiPost(`${SHARED_API}.submit_intake`, payload);
      el("intakeForm").style.display = "none";
      showMessage("Thank you - your intake form has been submitted.", false);
    } catch (error) {
      showMessage(error.message || "Could not submit this form.", true);
    } finally {
      if (submitBtn) submitBtn.disabled = false;
    }
  }

  function init() {
    const form = el("intakeForm");
    if (!form) return;

    const lead = getValue("intakeLead");

    if (!lead) {
      form.style.display = "none";
      showMessage("This intake link is missing some information. Please contact us for a new link.", true);
      return;
    }

    loadLead(lead);

    const submitBtn = el("submitIntakeBtn");
    if (submitBtn) submitBtn.addEventListener("click", submitForm);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
