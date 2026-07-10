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
      const dateText = note.note_date
        ? new Date(`${note.note_date}T00:00:00`).toLocaleDateString("en-GB")
        : "";
      const addedText = note.added_on ? new Date(note.added_on).toLocaleString("en-GB") : "";

      const metaBits = [];
      if (dateText) metaBits.push(dateText);
      if (note.added_by) metaBits.push(note.added_by);
      if (addedText) metaBits.push(`added ${addedText}`);

      return `
        <div class="dashboard-lead-note">
          <div class="dashboard-lead-note-text">${escapeHtml(note.note)}</div>
          <div class="dashboard-lead-note-meta">${escapeHtml(metaBits.join(" · "))}</div>
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
    setValue("lead_location_address", lead.location_address);

    const consentField = el("lead_consent_given");
    if (consentField) consentField.checked = !!lead.consent_given;

    if (el("lead_status")) {
      setValue("lead_status", lead.status || "New");
      setValue("lead_decline_reason", lead.decline_reason || "");
      toggleDeclineField();
      setValue("lead_coach", lead.coach || "");
    }

    const typeBadge = el("leadAppointmentTypeBadge");
    if (typeBadge) {
      if (lead.appointment_type) {
        typeBadge.textContent = lead.appointment_type;
        typeBadge.style.display = "";
      } else {
        typeBadge.style.display = "none";
      }
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

    const callSection = el("leadCallSection");
    if (callSection) {
      if (lead.call && lead.call.date) {
        callSection.style.display = "";

        const dateTimeEl = el("leadCallDateTime");
        if (dateTimeEl) {
          const dateText = new Date(`${lead.call.date}T00:00:00`).toLocaleDateString("en-GB", {
            weekday: "long", day: "numeric", month: "long", year: "numeric"
          });
          const timeText = lead.call.start_time
            ? `${lead.call.start_time}${lead.call.end_time ? " - " + lead.call.end_time : ""}`
            : "";
          dateTimeEl.textContent = [dateText, timeText].filter(Boolean).join(" at ");
        }

        const locationEl = el("leadCallLocation");
        if (locationEl) {
          if (lead.call.online_link) {
            locationEl.innerHTML = `<a href="${escapeHtml(lead.call.online_link)}" target="_blank" rel="noopener noreferrer">${escapeHtml(lead.call.online_link)}</a>`;
          } else {
            locationEl.textContent = lead.call.location || "—";
          }
        }
      } else {
        callSection.style.display = "none";
      }
    }

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
    const linkExistingSection = el("leadLinkExistingSection");

    if (lead.status === "Converted" && lead.converted_client) {
      if (sendBtn) sendBtn.style.display = "none";
      if (convertBtn) convertBtn.style.display = "none";
      if (linkExistingSection) linkExistingSection.style.display = "none";
      if (viewClientBtn) {
        viewClientBtn.style.display = "";
        viewClientBtn.href = `${baseUrl}/client_details?name=${encodeURIComponent(lead.converted_client)}`;
      }
    } else {
      if (viewClientBtn) viewClientBtn.style.display = "none";

      // Same button slot changes from "Send Intake Form" to "Convert to
      // Client" - Send Intake Form disappears as soon as it's been sent
      // (nothing to resend), Convert to Client appears once it's done.
      const intakeSent = !!lead.intake_sent_on;
      const intakeDone = !!lead.intake_completed_on;
      if (sendBtn) sendBtn.style.display = intakeSent ? "none" : "";

      if (!lead.is_client_conversion) {
        // e.g. Franchisee Call - turns into a Franchisee, not a Client;
        // that conversion flow doesn't exist yet, so don't offer the
        // Client-shaped conversion actions for it.
        if (convertBtn) convertBtn.style.display = "none";
        if (linkExistingSection) linkExistingSection.style.display = "none";
      } else {
        if (convertBtn) convertBtn.style.display = intakeDone ? "" : "none";
        if (linkExistingSection) {
          linkExistingSection.style.display = "";
          loadClientLinkOptions();
        }
      }
    }
  }

  async function loadClientLinkOptions() {
    const clientSelect = el("lead_link_client");
    if (!clientSelect || clientSelect.dataset.loaded === "1") return;

    clientSelect.dataset.loaded = "1";

    try {
      const options = await apiPost(`${SHARED_API}.get_client_link_options`, {});
      (options || []).forEach((option) => {
        const opt = document.createElement("option");
        opt.value = option.value;
        opt.textContent = option.label;
        clientSelect.appendChild(opt);
      });
    } catch (error) {
      console.error("Could not load clients:", error);
    }
  }

  async function loadContactOptionsForClient(client) {
    const contactSelect = el("lead_link_contact");
    if (!contactSelect) return;

    contactSelect.innerHTML = '<option value="">— No contact —</option>';
    if (!client) return;

    try {
      const options = await apiPost(`${SHARED_API}.get_client_contact_options`, { client });
      (options || []).forEach((option) => {
        const opt = document.createElement("option");
        opt.value = option.value;
        opt.textContent = option.label;
        contactSelect.appendChild(opt);
      });
    } catch (error) {
      console.error("Could not load contacts:", error);
    }
  }

  async function linkExistingClient() {
    const name = getValue("leadDocname");
    const client = getValue("lead_link_client");
    const contact = getValue("lead_link_contact");

    if (!client) {
      showMessage("Please select a client to link this lead to.", true);
      return;
    }

    const linkBtn = el("linkExistingClientBtn");
    if (linkBtn) linkBtn.disabled = true;

    try {
      await apiPost(`${SHARED_API}.link_lead_to_existing_client`, { name, client, contact });
      showMessage("Linked to existing client.", false);
      loadLead();
    } catch (error) {
      showMessage(error.message || "Could not link this lead.", true);
    } finally {
      if (linkBtn) linkBtn.disabled = false;
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
      location_address: getValue("lead_location_address").trim(),
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

        const appointmentTypeField = el("lead_appointment_type");
        if (appointmentTypeField) payload.appointment_type = appointmentTypeField.value;

        const result = await apiPost(`${SHARED_API}.create_lead`, payload);
        window.location.href = `${baseUrl}/lead_details?name=${encodeURIComponent(result.name)}`;
        return;
      }

      payload.name = getValue("leadDocname");

      const coachField = el("lead_coach");
      if (coachField) payload.coach = coachField.value;

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

  function openIntakeEmailModal() {
    const modal = el("intakeEmailModal");
    if (modal) modal.classList.add("show");
  }

  function closeIntakeEmailModal() {
    const modal = el("intakeEmailModal");
    if (modal) modal.classList.remove("show");
  }

  async function prepareIntakeEmail() {
    const name = getValue("leadDocname");
    const emailField = el("lead_contact_email");
    const email = emailField ? emailField.value.trim() : "";

    if (!email) {
      showMessage("Add a contact email above before sending the intake form.", true);
      if (emailField) emailField.focus();
      return;
    }

    const sendBtn = el("sendIntakeFormBtn");
    if (sendBtn) sendBtn.disabled = true;

    try {
      // get_intake_email_defaults reads the saved record, not the live
      // form - if a coach types an email and opens this without a
      // separate Save first, it would otherwise still see the old
      // (possibly blank) value. Persist the current form first, same as
      // the Save button does.
      const payload = collectFormPayload();
      payload.name = name;
      await apiPost(`${SHARED_API}.update_lead`, payload);

      const defaults = await apiPost(`${SHARED_API}.get_intake_email_defaults`, { name });

      const recipientField = el("intakeEmailRecipient");
      const subjectField = el("intakeEmailSubject");
      const messageField = el("intakeEmailMessage");
      const statusField = el("intakeEmailStatus");

      if (recipientField) recipientField.value = defaults.recipient || "";
      if (subjectField) subjectField.value = defaults.subject || "";
      if (messageField) messageField.value = defaults.message || "";
      if (statusField) statusField.textContent = "";

      openIntakeEmailModal();
    } catch (error) {
      showMessage(error.message || "Could not load the intake form email.", true);
    } finally {
      if (sendBtn) sendBtn.disabled = false;
    }
  }

  async function confirmSendIntakeForm() {
    const name = getValue("leadDocname");
    const subjectField = el("intakeEmailSubject");
    const messageField = el("intakeEmailMessage");
    const statusField = el("intakeEmailStatus");
    const submitBtn = el("intakeEmailSubmit");

    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.textContent = "Sending...";
    }

    if (statusField) statusField.textContent = "";

    try {
      const result = await apiPost(`${SHARED_API}.send_intake_form`, {
        name,
        subject: subjectField ? subjectField.value.trim() : "",
        message: messageField ? messageField.value.trim() : "",
      });

      showMessage(
        result.email_sent
          ? "Intake form sent."
          : `Could not send the email, but here's the link to share directly: ${result.intake_url}`,
        !result.email_sent
      );
      closeIntakeEmailModal();
      loadLead();
    } catch (error) {
      if (statusField) statusField.textContent = error.message || "Could not send the intake form.";
    } finally {
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.textContent = "Send";
      }
    }
  }

  function initIntakeEmailModal() {
    const openBtn = el("sendIntakeFormBtn");
    if (openBtn) openBtn.addEventListener("click", prepareIntakeEmail);

    const closeBtn = el("intakeEmailModalClose");
    if (closeBtn) closeBtn.addEventListener("click", closeIntakeEmailModal);

    const cancelBtn = el("intakeEmailCancel");
    if (cancelBtn) cancelBtn.addEventListener("click", closeIntakeEmailModal);

    const submitBtn = el("intakeEmailSubmit");
    if (submitBtn) submitBtn.addEventListener("click", confirmSendIntakeForm);
  }

  async function convertLead() {
    const name = getValue("leadDocname");
    const baseUrl = getValue("leadBaseUrl") || "/coach_db";

    if (!window.confirm("Create a Client and Contact record from this lead's details?")) {
      return;
    }

    const convertBtn = el("convertLeadBtn");
    if (convertBtn) convertBtn.disabled = true;

    try {
      const result = await apiPost(`${SHARED_API}.convert_lead_to_client`, { name });

      // The Contact is created automatically alongside it - nothing to
      // review there. Land straight on the new Client record so it can be
      // checked over and any extra details filled in and saved.
      if (result && result.client) {
        window.location.href = `${baseUrl}/client_details?name=${encodeURIComponent(result.client)}`;
        return;
      }

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
    const noteDate = getValue("leadNewNoteDate");

    if (!note) return;

    const addBtn = el("addLeadNoteBtn");
    if (addBtn) addBtn.disabled = true;

    try {
      const result = await apiPost(`${SHARED_API}.add_lead_note`, { name, note, note_date: noteDate });
      renderNotes(result.notes || []);
      if (noteField) noteField.value = "";
      setValue("leadNewNoteDate", todayIso());
    } catch (error) {
      showMessage(error.message || "Could not add note.", true);
    } finally {
      if (addBtn) addBtn.disabled = false;
    }
  }

  function todayIso() {
    const now = new Date();
    const offset = now.getTimezoneOffset();
    return new Date(now.getTime() - offset * 60000).toISOString().slice(0, 10);
  }

  function init() {
    const form = el("leadDetailsForm");
    if (!form) return;

    const saveBtn = el("saveLeadBtn");
    if (saveBtn) saveBtn.addEventListener("click", saveLead);

    const addNoteBtn = el("addLeadNoteBtn");
    if (addNoteBtn) addNoteBtn.addEventListener("click", addNote);

    initIntakeEmailModal();

    const convertBtn = el("convertLeadBtn");
    if (convertBtn) convertBtn.addEventListener("click", convertLead);

    const linkBtn = el("linkExistingClientBtn");
    if (linkBtn) linkBtn.addEventListener("click", linkExistingClient);

    const linkClientSelect = el("lead_link_client");
    if (linkClientSelect) {
      linkClientSelect.addEventListener("change", function () {
        loadContactOptionsForClient(linkClientSelect.value);
      });
    }

    const statusField = el("lead_status");
    if (statusField) statusField.addEventListener("change", toggleDeclineField);

    const noteDateField = el("leadNewNoteDate");
    if (noteDateField && !noteDateField.value) noteDateField.value = todayIso();

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
