(function () {
  "use strict";

  var el = Dashboard.el;

  const SHARED_API = "dashboard.api.shared.leads";
  const DECLINE_STATUSES = ["Declined"];

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
      throw new Error(data.message || "There was a problem saving.");
    }

    return data.message || {};
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
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
    const banner = el("leadFormMessage");
    if (!banner) {
      if (isError) console.error(message);
      return;
    }

    banner.textContent = message || "";
    banner.style.display = message ? "" : "none";
    banner.classList.toggle("dashboard-form-message-error", !!isError);
  }

  function toggleDeclineField() {
    const status = getValue("lead_status");
    const field = el("leadDeclineReasonField");
    if (!field) return;

    field.style.display = DECLINE_STATUSES.indexOf(status) !== -1 ? "" : "none";
  }

  function renderNotes(notes) {
    const list = el("leadNotesList");
    if (!list) return;

    if (!notes || !notes.length) {
      list.innerHTML = '<div class="dashboard-empty">No notes yet.</div>';
      return;
    }

    list.innerHTML = notes.map((note) => {
      const when = note.added_on ? new Date(note.added_on).toLocaleString("en-GB") : "";

      return `
        <div class="dashboard-lead-note">
          <div class="dashboard-lead-note-text">${escapeHtml(note.note)}</div>
          <div class="dashboard-lead-note-meta">${escapeHtml(note.added_by || "")} ${when ? "· " + escapeHtml(when) : ""}</div>
        </div>
      `;
    }).join("");
  }

  function populateForm(lead) {
    setValue("lead_contact_name", lead.contact_name);
    setValue("lead_contact_email", lead.contact_email);
    setValue("lead_contact_mobile", lead.contact_mobile);
    setValue("lead_client_name", lead.client_name);
    setValue("lead_client_age", lead.client_age);
    setValue("lead_postal_code", lead.postal_code);
    setValue("lead_enquiry_reason", lead.enquiry_reason);
    setValue("lead_how_heard", lead.how_heard);

    const consentField = el("lead_consent_given");
    if (consentField) consentField.checked = !!lead.consent_given;

    if (el("lead_status")) {
      setValue("lead_status", lead.status || "New");
      setValue("lead_decline_reason", lead.decline_reason || "");
      toggleDeclineField();
    }

    const intakeInfo = el("leadIntakeInfo");
    if (intakeInfo) {
      if (lead.intake_completed_on) {
        intakeInfo.textContent = `Intake form completed ${new Date(lead.intake_completed_on).toLocaleString("en-GB")}`;
      } else if (lead.intake_sent_on) {
        intakeInfo.textContent = `Intake form sent ${new Date(lead.intake_sent_on).toLocaleString("en-GB")} - not yet completed`;
      } else {
        intakeInfo.textContent = "Intake form not sent yet";
      }
    }

    renderNotes(lead.notes || []);

    const bookBtn = el("bookLeadCallBtn");
    if (bookBtn) {
      const baseUrl = getValue("leadBaseUrl") || "/coach_db";
      const params = new URLSearchParams({
        book_lead: lead.name,
        book_lead_name: lead.contact_name || lead.client_name || "",
      });
      bookBtn.href = `${baseUrl}/calendar?${params.toString()}`;
    }

    const title = el("leadPageTitle");
    if (title) title.textContent = lead.client_name || "Lead";

    const baseUrl = getValue("leadBaseUrl") || "/coach_db";
    const sendBtn = el("sendIntakeFormBtn");
    const convertBtn = el("convertLeadBtn");
    const viewClientBtn = el("viewConvertedClientBtn");

    if (lead.status === "Converted" && lead.converted_client) {
      if (sendBtn) sendBtn.style.display = "none";
      if (convertBtn) convertBtn.style.display = "none";
      if (viewClientBtn) {
        viewClientBtn.style.display = "";
        viewClientBtn.href = `${baseUrl}/client_details?name=${encodeURIComponent(lead.converted_client)}`;
      }
    } else {
      if (viewClientBtn) viewClientBtn.style.display = "none";
      if (sendBtn) sendBtn.style.display = "";
      if (convertBtn) convertBtn.style.display = lead.intake_completed_on ? "" : "none";
    }
  }

  async function loadLead() {
    const name = getValue("leadDocname");
    if (!name) return;

    try {
      const lead = await apiPost(`${SHARED_API}.get_lead`, { name });
      populateForm(lead);
    } catch (error) {
      showMessage(error.message || "Could not load this lead.", true);
    }
  }

  function collectFormPayload() {
    return {
      contact_name: getValue("lead_contact_name").trim(),
      contact_email: getValue("lead_contact_email").trim(),
      contact_mobile: getValue("lead_contact_mobile").trim(),
      client_name: getValue("lead_client_name").trim(),
      client_age: getValue("lead_client_age").trim(),
      postal_code: getValue("lead_postal_code").trim(),
      enquiry_reason: getValue("lead_enquiry_reason").trim(),
      how_heard: getValue("lead_how_heard").trim(),
      consent_given: el("lead_consent_given") && el("lead_consent_given").checked ? 1 : 0,
    };
  }

  function getDashboardType() {
    const path = window.location.pathname || "";
    if (path.indexOf("/franchisor_db") !== -1) return "franchisor";
    return "coach";
  }

  async function saveLead() {
    const isNew = getValue("leadIsNew") === "1";
    const baseUrl = getValue("leadBaseUrl") || "/coach_db";
    const payload = collectFormPayload();

    if (!payload.contact_name) {
      showMessage("Please enter the contact's name.", true);
      return;
    }

    if (!payload.client_name) {
      showMessage("Please enter the client's (young person's) name.", true);
      return;
    }

    const saveBtn = el("saveLeadBtn");
    if (saveBtn) saveBtn.disabled = true;

    try {
      if (isNew) {
        payload.dashboard_type = getDashboardType();

        const coachField = el("lead_coach");
        if (coachField) payload.coach = coachField.value;

        const result = await apiPost(`${SHARED_API}.create_lead`, payload);
        window.location.href = `${baseUrl}/lead_details?name=${encodeURIComponent(result.name)}`;
        return;
      }

      payload.name = getValue("leadDocname");
      await apiPost(`${SHARED_API}.update_lead`, payload);

      const statusField = el("lead_status");
      if (statusField) {
        await apiPost(`${SHARED_API}.update_lead_status`, {
          name: payload.name,
          status: statusField.value,
          decline_reason: getValue("lead_decline_reason").trim(),
        });
      }

      showMessage("Saved.", false);
      loadLead();
    } catch (error) {
      showMessage(error.message || "Could not save this lead.", true);
    } finally {
      if (saveBtn) saveBtn.disabled = false;
    }
  }

  async function sendIntakeForm() {
    const name = getValue("leadDocname");
    const sendBtn = el("sendIntakeFormBtn");
    if (sendBtn) sendBtn.disabled = true;

    try {
      const result = await apiPost(`${SHARED_API}.send_intake_form`, { name });
      showMessage(
        result.email_sent
          ? "Intake form sent."
          : `Could not send the email, but here's the link to share directly: ${result.intake_url}`,
        !result.email_sent
      );
      loadLead();
    } catch (error) {
      showMessage(error.message || "Could not send the intake form.", true);
    } finally {
      if (sendBtn) sendBtn.disabled = false;
    }
  }

  async function convertLead() {
    const name = getValue("leadDocname");

    if (!window.confirm("Create a Client and Contact record from this lead's details?")) {
      return;
    }

    const convertBtn = el("convertLeadBtn");
    if (convertBtn) convertBtn.disabled = true;

    try {
      await apiPost(`${SHARED_API}.convert_lead_to_client`, { name });
      showMessage("Converted to a Client.", false);
      loadLead();
    } catch (error) {
      showMessage(error.message || "Could not convert this lead.", true);
    } finally {
      if (convertBtn) convertBtn.disabled = false;
    }
  }

  async function addNote() {
    const name = getValue("leadDocname");
    const noteField = el("leadNewNote");
    const note = noteField ? noteField.value.trim() : "";

    if (!note) return;

    const addBtn = el("addLeadNoteBtn");
    if (addBtn) addBtn.disabled = true;

    try {
      const result = await apiPost(`${SHARED_API}.add_lead_note`, { name, note });
      renderNotes(result.notes || []);
      if (noteField) noteField.value = "";
    } catch (error) {
      showMessage(error.message || "Could not add note.", true);
    } finally {
      if (addBtn) addBtn.disabled = false;
    }
  }

  function init() {
    const form = el("leadDetailsForm");
    if (!form) return;

    const saveBtn = el("saveLeadBtn");
    if (saveBtn) saveBtn.addEventListener("click", saveLead);

    const addNoteBtn = el("addLeadNoteBtn");
    if (addNoteBtn) addNoteBtn.addEventListener("click", addNote);

    const sendBtn = el("sendIntakeFormBtn");
    if (sendBtn) sendBtn.addEventListener("click", sendIntakeForm);

    const convertBtn = el("convertLeadBtn");
    if (convertBtn) convertBtn.addEventListener("click", convertLead);

    const statusField = el("lead_status");
    if (statusField) statusField.addEventListener("change", toggleDeclineField);

    if (getValue("leadIsNew") !== "1") {
      loadLead();
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
