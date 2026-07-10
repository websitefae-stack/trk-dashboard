(function () {
  "use strict";

  const SHARED_API = "dashboard.api.shared.leads";

  // Detail fields (beyond the always-present contact_name/contact_email/
  // contact_mobile/client_name/client_age/postal_code/enquiry_reason/
  // how_heard/consent_given) - mirrors INTAKE_TEXT_FIELDS/INTAKE_DATE_FIELDS/
  // INTAKE_CHECK_FIELDS in dashboard/api/shared/leads.py.
  const TEXT_FIELDS = [
    "young_person_first_name", "young_person_last_name", "young_person_preferred_name",
    "young_person_mobile", "young_person_email", "young_person_pronouns", "young_person_sex",
    "young_person_gender_identity", "young_person_address_line_1", "young_person_address_line_2",
    "young_person_city", "young_person_postalcode",
    "primary_caregiver_full_name", "primary_caregiver_mobile", "primary_caregiver_email",
    "primary_relationship_to_client", "siblings",
    "secondary_caregiver_full_name", "secondary_caregiver_mobile", "secondary_caregiver_email",
    "secondary_relationship", "account_responsible_person",
    "adult_first_name", "adult_last_name", "adult_preferred_name", "adult_address_1", "adult_address_2",
    "adult_city", "adult_postalcode", "adult_mobile", "adult_email", "adult_pronouns", "adult_sex",
    "adult_gender_identity", "adult_account_responsible_person",
    "next_of_kin_name", "next_of_kin_email", "next_of_kin_mobile",
    "school_name", "school_contact_name", "school_contact_role", "school_contact_email", "school_mobile",
    "school_address_line_1", "school_address_line_2", "school_city", "school_postalcode", "school_support_required",
    "company_name", "company_contact_name", "company_contact_role", "company_contact_email", "company_mobile",
    "company_address_line_1", "company_address_line_2", "company_city", "company_postalcode", "company_support_required",
    "billing_contact_full_name", "billing_contact_email", "billing_contact_mobile",
    "billing_contact_address_line_1", "billing_contact_address_line_2", "billing_contact_city", "billing_contact_postal_code",
    "support_required", "allergies", "neurodiverse_status", "neurodiverse_information", "doctor_details",
    "main_therapy_location", "new_therapy_location_details",
    "education_establishment", "year_group_teacher", "sendco_involved", "education_contact",
    "signature_name",
  ];

  const DATE_FIELDS = ["young_person_date_of_birth", "adult_date_of_birth", "date_signed"];

  const CHECK_FIELDS = [
    "billing_contact_next_kin", "school_billing_same_as_contact", "company_billing_same_as_contact",
    "therapy_location_not_listed", "agreement_confirmed",
  ];

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
    if (!field) return "";
    if (field.type === "checkbox") return field.checked ? 1 : 0;
    return field.value || "";
  }

  function setValue(id, value) {
    const field = el(id);
    if (!field) return;
    if (field.type === "checkbox") {
      field.checked = !!value;
      return;
    }
    field.value = value ?? "";
  }

  function updateDateDisplay(id) {
    const field = el(id);
    const display = el(`${id}_display`);
    if (!field || !display) return;

    if (!field.value) {
      display.textContent = "";
      return;
    }

    // <input type="date"> renders its own text using the visitor's browser/
    // OS locale, not anything this code controls - this label guarantees
    // day/month/year regardless of what the native picker shows.
    const date = new Date(`${field.value}T00:00:00`);
    display.textContent = isNaN(date.getTime())
      ? ""
      : date.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
  }

  function showMessage(message, isError) {
    const banner = el("intakeFormMessage");
    if (!banner) return;

    banner.textContent = message || "";
    banner.style.display = message ? "" : "none";
    banner.classList.toggle("dashboard-form-message-error", !!isError);
  }

  const YOUNG_PERSON_TYPES = ["Kid", "Teen", "Uni Student"];

  function updateSectionVisibility() {
    const clientType = getValue("intake_client_type");
    const isYoungPerson = YOUNG_PERSON_TYPES.includes(clientType);
    const isAdult = clientType === "Adult";
    const isSchool = clientType === "School";
    const isCompany = clientType === "Company";

    const sections = {
      section_young_person: isYoungPerson,
      section_caregivers: isYoungPerson,
      section_adult: isAdult,
      section_next_of_kin: isAdult,
      section_school: isSchool,
      section_company: isCompany,
      section_support: isYoungPerson || isAdult,
      section_education: isYoungPerson,
    };

    Object.keys(sections).forEach((id) => {
      const section = el(id);
      if (section) section.style.display = sections[id] ? "" : "none";
    });

    const ageField = el("intake_client_age_field");
    if (ageField) ageField.style.display = (isSchool || isCompany) ? "none" : "";

    const clientNameLabel = el("intake_client_name_label");
    if (clientNameLabel) {
      clientNameLabel.textContent = isSchool ? "School Name"
        : isCompany ? "Company / Organisation Name"
        : isAdult ? "Client Name"
        : "Young Person's Name";
    }
  }

  async function loadTherapyLocationOptions() {
    const select = el("main_therapy_location");
    if (!select) return;

    try {
      const data = await apiPost(`${SHARED_API}.get_intake_form_options`, {});
      (data.therapy_locations || []).forEach((option) => {
        const opt = document.createElement("option");
        opt.value = option.value;
        opt.textContent = option.label;
        select.appendChild(opt);
      });
    } catch (error) {
      console.error("Could not load therapy locations:", error);
    }
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
      setValue("intake_consent_given", !!data.consent_given);
      setValue("intake_client_type", data.client_type);

      TEXT_FIELDS.concat(DATE_FIELDS).forEach((fieldname) => setValue(fieldname, data[fieldname]));
      CHECK_FIELDS.forEach((fieldname) => setValue(fieldname, !!data[fieldname]));

      if (!getValue("date_signed")) {
        const today = new Date().toISOString().slice(0, 10);
        setValue("date_signed", today);
      }

      DATE_FIELDS.forEach(updateDateDisplay);

      updateSectionVisibility();
      const newLocationField = el("new_therapy_location_details_field");
      if (newLocationField) newLocationField.style.display = getValue("therapy_location_not_listed") ? "" : "none";
    } catch (error) {
      el("intakeForm").style.display = "none";
      showMessage(error.message || "This intake link is invalid or has expired.", true);
    }
  }

  async function submitForm() {
    const lead = getValue("intakeLead");

    const payload = {
      lead: lead,
      contact_name: getValue("intake_contact_name").toString().trim(),
      contact_email: getValue("intake_contact_email").toString().trim(),
      contact_mobile: getValue("intake_contact_mobile").toString().trim(),
      client_name: getValue("intake_client_name").toString().trim(),
      client_age: getValue("intake_client_age").toString().trim(),
      postal_code: getValue("intake_postal_code").toString().trim(),
      enquiry_reason: getValue("intake_enquiry_reason").toString().trim(),
      how_heard: getValue("intake_how_heard").toString().trim(),
      consent_given: getValue("intake_consent_given"),
      client_type: getValue("intake_client_type"),
    };

    TEXT_FIELDS.concat(DATE_FIELDS).forEach((fieldname) => {
      const value = getValue(fieldname);
      payload[fieldname] = typeof value === "string" ? value.trim() : value;
    });

    CHECK_FIELDS.forEach((fieldname) => {
      payload[fieldname] = getValue(fieldname);
    });

    if (!payload.contact_name) {
      showMessage("Please enter your name.", true);
      return;
    }

    if (!payload.client_name) {
      showMessage("Please enter the client's name.", true);
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
    loadTherapyLocationOptions();

    const clientTypeField = el("intake_client_type");
    if (clientTypeField) clientTypeField.addEventListener("change", updateSectionVisibility);

    const notListedField = el("therapy_location_not_listed");
    if (notListedField) {
      notListedField.addEventListener("change", function () {
        const newLocationField = el("new_therapy_location_details_field");
        if (newLocationField) newLocationField.style.display = notListedField.checked ? "" : "none";
      });
    }

    DATE_FIELDS.forEach((fieldname) => {
      const field = el(fieldname);
      if (field) field.addEventListener("change", () => updateDateDisplay(fieldname));
    });

    const submitBtn = el("submitIntakeBtn");
    if (submitBtn) submitBtn.addEventListener("click", submitForm);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
