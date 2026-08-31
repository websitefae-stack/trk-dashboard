(function () {
  "use strict";

  var el = Dashboard.el;

  const SHARED_API = "dashboard.api.shared.leads";
  const DECLINE_STATUSES = ["Declined"];

  // Set by populateForm() - deleteLead() reads it back to warn about a
  // linked appointment before deleting, without a redundant extra fetch.
  let currentLead = null;

  // Mirrors leads.STAGE1_MILESTONES's order/fieldnames exactly - a
  // (fieldname, label) pair per Stage 1 - Decide & Commit milestone.
  const STAGE1_MILESTONES = [
    ["stage1_call_done", "Call With Ashley (Founder) / Franchise Call"],
    ["stage1_nda_done", "Sign NDA"],
    ["stage1_discovery_day_done", "Discovery Day"],
    ["stage1_intent_deposit_dbs_done", "Intent to Proceed + Deposit + DBS/Insurance Submitted"],
    ["stage1_agreement_invoice_done", "Franchisee Agreement Signed + Final Invoice Paid"],
  ];

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

  function renderStage1(lead) {
    const section = el("leadStage1Section");
    const list = el("leadStage1List");
    if (!section || !list) return;

    if (!lead.is_franchise_lead || !lead.stage1) {
      section.style.display = "none";
      return;
    }

    section.style.display = "";

    list.innerHTML = STAGE1_MILESTONES.map(([fieldname, label]) => {
      const milestone = lead.stage1[fieldname] || { done: 0, date: "" };
      const checked = milestone.done ? "checked" : "";
      const dateValue = escapeHtml(milestone.date || "");

      return `
        <div class="dashboard-lead-stage1-row" data-milestone="${escapeHtml(fieldname)}">
          <label class="dashboard-lead-stage1-label">
            <input type="checkbox" class="dashboard-lead-stage1-check" ${checked}>
            ${escapeHtml(label)}
          </label>
          <input type="date" class="dashboard-input dashboard-lead-stage1-date" value="${dateValue}"
            ${milestone.done ? "" : "disabled"}>
        </div>
      `;
    }).join("");

    renderNdaBlock(lead);
  }

  async function saveStage1Milestone(row) {
    const fieldname = row.dataset.milestone;
    const checkbox = row.querySelector(".dashboard-lead-stage1-check");
    const dateField = row.querySelector(".dashboard-lead-stage1-date");
    const name = getValue("leadDocname");
    if (!fieldname || !checkbox || !dateField || !name) return;

    dateField.disabled = !checkbox.checked;

    if (checkbox.checked && !dateField.value) {
      dateField.value = todayIso();
    }

    try {
      await apiPost(`${SHARED_API}.update_franchise_pipeline`, {
        name,
        milestone: fieldname,
        done: checkbox.checked ? 1 : 0,
        milestone_date: dateField.value || "",
      });
    } catch (error) {
      window.alert(error.message || "Could not save this.");
    }
  }

  function renderNdaBlock(lead) {
    const block = el("leadNdaBlock");
    if (!block) return;

    if (lead.nda_signed) {
      block.innerHTML = `
        <button type="button" class="dashboard-btn dashboard-btn-light" id="viewSignedNdaBtn">View Signed NDA</button>
      `;
      const viewBtn = el("viewSignedNdaBtn");
      if (viewBtn) viewBtn.addEventListener("click", viewSignedNda);
      return;
    }

    block.innerHTML = `
      <button type="button" class="dashboard-btn dashboard-btn-light" id="getNdaLinkBtn">
        ${lead.nda_link_generated ? "Get NDA Sign Link Again" : "Generate NDA Sign Link"}
      </button>
      <div id="ndaLinkResult" style="margin-top:10px; display:none;">
        <label style="display:block; font-size:12px; font-weight:600; margin-bottom:4px;">
          Copy this link and send it to the franchisee to sign:
        </label>
        <div style="display:flex; gap:8px;">
          <input type="text" id="ndaLinkInput" class="dashboard-input" readonly style="flex:1;">
          <button type="button" class="dashboard-btn dashboard-btn-secondary" id="copyNdaLinkBtn">Copy</button>
        </div>
      </div>
    `;

    const getLinkBtn = el("getNdaLinkBtn");
    if (getLinkBtn) getLinkBtn.addEventListener("click", getNdaSignLink);

    const copyBtn = el("copyNdaLinkBtn");
    if (copyBtn) {
      copyBtn.addEventListener("click", () => {
        const input = el("ndaLinkInput");
        if (!input) return;
        input.select();
        navigator.clipboard?.writeText(input.value).catch(() => {});
      });
    }
  }

  async function getNdaSignLink() {
    const name = getValue("leadDocname");
    const btn = el("getNdaLinkBtn");
    if (!name) return;

    if (btn) { btn.disabled = true; btn.textContent = "Generating..."; }

    try {
      const result = await apiPost(`${SHARED_API}.get_nda_sign_url`, { name });
      const resultBlock = el("ndaLinkResult");
      const input = el("ndaLinkInput");
      if (input) input.value = result.url || "";
      if (resultBlock) resultBlock.style.display = "";
    } catch (error) {
      window.alert(error.message || "Could not generate the sign link.");
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = "Get NDA Sign Link Again"; }
    }
  }

  async function viewSignedNda() {
    const name = getValue("leadDocname");
    if (!name) return;

    try {
      const result = await apiPost(`${SHARED_API}.get_signed_nda`, { name });
      const content = el("ndaViewModalContent");
      if (content) {
        const auditRows = [
          result.signed_at ? `Signed: ${escapeHtml(result.signed_at)}` : "",
          result.signer_ip ? `IP address: ${escapeHtml(result.signer_ip)}` : "",
          result.signer_user_agent ? `Browser/device: ${escapeHtml(result.signer_user_agent)}` : "",
        ].filter(Boolean);

        const auditBlock = auditRows.length
          ? `<div style="margin-top:16px; padding:12px 14px; background:#F2F8F8; border-radius:10px; font-size:12px; color:#839898;">
              <strong style="display:block; margin-bottom:4px; color:#434B49;">Signing Record</strong>
              ${auditRows.join("<br>")}
            </div>`
          : "";

        content.innerHTML = (result.signed_html || "") + auditBlock;
      }
      const modal = el("ndaViewModal");
      if (modal) modal.classList.add("show");
    } catch (error) {
      window.alert(error.message || "Could not load the signed NDA.");
    }
  }

  function renderIntakeAnswers(answers) {
    const section = el("leadIntakeAnswersSection");
    const list = el("leadIntakeAnswersList");
    if (!section || !list) return;

    if (!answers || !answers.length) {
      section.style.display = "none";
      return;
    }

    section.style.display = "";
    list.innerHTML = answers.map((row) => `
      <div class="dashboard-field-value-row">
        <div class="dashboard-field-value-label">${escapeHtml(row.label)}</div>
        <div class="dashboard-field-value-text">${escapeHtml(row.value)}</div>
      </div>
    `).join("");
  }

  function populateForm(lead) {
    currentLead = lead;

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
        let text = `Intake form completed ${new Date(lead.intake_completed_on).toLocaleString("en-GB")}`;
        if (!lead.is_client_conversion) {
          text += " - this appointment type doesn't create a Client on conversion, so no Convert/Link button shows here.";
        }
        intakeInfo.textContent = text;
      } else if (lead.intake_sent_on) {
        let text = `Intake form sent ${new Date(lead.intake_sent_on).toLocaleString("en-GB")} - not yet completed`;
        if (lead.intake_email_status === "Failed") {
          text += " - the email failed to send, please resend it";
        }
        intakeInfo.textContent = text;
      } else {
        intakeInfo.textContent = "Intake form not sent yet";
      }
    }

    renderIntakeAnswers(lead.intake_answers || []);
    renderNotes(lead.notes || []);
    renderStage1(lead);

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
    const deleteBtn = el("deleteLeadBtn");

    if (lead.status === "Converted" && lead.converted_client) {
      if (sendBtn) sendBtn.style.display = "none";
      if (convertBtn) convertBtn.style.display = "none";
      if (linkExistingSection) linkExistingSection.style.display = "none";
      // Converted leads already have a real client record built from
      // them - deletion is blocked on the backend too, but hiding the
      // button here avoids offering an action that will just fail.
      if (deleteBtn) deleteBtn.style.display = "none";
      if (viewClientBtn) {
        viewClientBtn.style.display = "";
        viewClientBtn.href = `${baseUrl}/client_details?name=${encodeURIComponent(lead.converted_client)}`;
      }
    } else {
      if (viewClientBtn) viewClientBtn.style.display = "none";
      if (deleteBtn) deleteBtn.style.display = "";

      // Send/Resend Intake Form stays available at every stage right up
      // until conversion actually succeeds - never sent yet, sent and
      // still waiting, or completed (possibly incompletely - the parent
      // skipped questions, or conversion turned up mistakes) all need a
      // way to get a fresh submission back out to the parent, without
      // requiring the lead to be un-sent or un-completed first.
      const intakeSent = !!lead.intake_sent_on;
      const intakeDone = !!lead.intake_completed_on;
      if (sendBtn) {
        sendBtn.style.display = "";
        sendBtn.textContent = intakeSent ? "Resend Intake Form" : "Send Intake Form";
      }

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

  function openLinkClientDiffModal() {
    const modal = el("linkClientDiffModal");
    if (modal) modal.classList.add("show");
  }

  function closeLinkClientDiffModal() {
    const modal = el("linkClientDiffModal");
    if (modal) modal.classList.remove("show");
  }

  function renderDiffRows(rows) {
    const container = el("linkClientDiffRows");
    if (!container) return;

    container.innerHTML = rows.map((row) => `
      <div class="trk-lead-diff-row" data-fieldname="${escapeHtml(row.fieldname)}">
        <div class="trk-lead-diff-label">${escapeHtml(row.label)}</div>
        <label class="trk-lead-diff-option">
          <input type="radio" name="diff_${escapeHtml(row.fieldname)}" value="keep" checked>
          Keep: <span class="trk-lead-diff-value">${escapeHtml(row.current_value) || "(blank)"}</span>
        </label>
        <label class="trk-lead-diff-option trk-lead-diff-option-new">
          <input type="radio" name="diff_${escapeHtml(row.fieldname)}" value="use_new">
          Use new: <span class="trk-lead-diff-value">${escapeHtml(row.new_value)}</span>
        </label>
      </div>
    `).join("");
  }

  function collectFieldChoices() {
    const choices = {};
    document.querySelectorAll("#linkClientDiffRows .trk-lead-diff-row").forEach((row) => {
      const fieldname = row.dataset.fieldname;
      const selected = row.querySelector("input[type=radio]:checked");
      choices[fieldname] = selected ? selected.value : "keep";
    });
    return choices;
  }

  async function finishLinkingClient(name, client, contact, fieldChoices) {
    await apiPost(`${SHARED_API}.link_lead_to_existing_client`, {
      name,
      client,
      contact,
      field_choices: fieldChoices ? JSON.stringify(fieldChoices) : undefined,
    });
    showMessage("Linked to existing client.", false);
    closeLinkClientDiffModal();
    loadLead();
  }

  let pendingLinkClient = null;

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
      const diff = await apiPost(`${SHARED_API}.get_lead_client_diff`, { name, client });
      const rows = (diff && diff.rows) || [];

      if (!rows.length) {
        await finishLinkingClient(name, client, contact, null);
        return;
      }

      pendingLinkClient = { name, client, contact };
      renderDiffRows(rows);
      openLinkClientDiffModal();
    } catch (error) {
      showMessage(error.message || "Could not link this lead.", true);
    } finally {
      if (linkBtn) linkBtn.disabled = false;
    }
  }

  async function confirmLinkClientDiff() {
    if (!pendingLinkClient) return;

    const confirmBtn = el("linkClientDiffConfirm");
    if (confirmBtn) confirmBtn.disabled = true;

    try {
      const { name, client, contact } = pendingLinkClient;
      await finishLinkingClient(name, client, contact, collectFieldChoices());
      pendingLinkClient = null;
    } catch (error) {
      showMessage(error.message || "Could not link this lead.", true);
    } finally {
      if (confirmBtn) confirmBtn.disabled = false;
    }
  }

  function initLinkClientDiffModal() {
    const closeBtn = el("linkClientDiffClose");
    if (closeBtn) closeBtn.addEventListener("click", closeLinkClientDiffModal);

    const cancelBtn = el("linkClientDiffCancel");
    if (cancelBtn) cancelBtn.addEventListener("click", closeLinkClientDiffModal);

    const confirmBtn = el("linkClientDiffConfirm");
    if (confirmBtn) confirmBtn.addEventListener("click", confirmLinkClientDiff);
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
      const senderField = el("intakeEmailSender");
      const ccField = el("intakeEmailCc");

      if (recipientField) recipientField.value = defaults.recipient || "";
      if (subjectField) subjectField.value = defaults.subject || "";
      if (messageField) messageField.value = defaults.message || "";
      if (statusField) statusField.textContent = "";
      if (ccField) ccField.value = "";

      if (senderField) {
        try {
          const senderOptions = await apiPost("dashboard.api.shared.email_templates.get_email_sender_options", {});
          senderField.innerHTML = "";
          (senderOptions || []).forEach((opt) => {
            const option = document.createElement("option");
            option.value = opt.value;
            option.textContent = opt.label;
            senderField.appendChild(option);
          });
          Dashboard.attachSenderHint(senderField);
        } catch (error) {
          console.error("Could not load sender options", error);
        }
      }

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
      const senderField = el("intakeEmailSender");
      const ccField = el("intakeEmailCc");

      const result = await apiPost(`${SHARED_API}.send_intake_form`, {
        name,
        subject: subjectField ? subjectField.value.trim() : "",
        message: messageField ? messageField.value.trim() : "",
        sender: senderField ? senderField.value : "",
        cc: ccField ? ccField.value.trim() : "",
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
      updateNoteDateDisplay();
    } catch (error) {
      showMessage(error.message || "Could not add note.", true);
    } finally {
      if (addBtn) addBtn.disabled = false;
    }
  }

  async function deleteLead() {
    const name = getValue("leadDocname");
    if (!name) return;

    let confirmMessage = "Delete this lead? This cannot be undone.";
    if (currentLead && currentLead.call && currentLead.call.date) {
      const dateText = new Date(`${currentLead.call.date}T00:00:00`).toLocaleDateString("en-GB", {
        day: "numeric", month: "long", year: "numeric"
      });
      confirmMessage = `Delete this lead? This will also delete the linked appointment on ${dateText}. This cannot be undone.`;
    }

    if (!window.confirm(confirmMessage)) {
      return;
    }

    const deleteBtn = el("deleteLeadBtn");
    if (deleteBtn) {
      deleteBtn.disabled = true;
      deleteBtn.textContent = "Deleting...";
    }

    try {
      await apiPost(`${SHARED_API}.delete_lead`, { name });
      const baseUrl = getValue("leadBaseUrl") || "/coach_db";
      window.location.href = `${baseUrl}/leads`;
    } catch (error) {
      showMessage(error.message || "Could not delete this lead.", true);
      if (deleteBtn) {
        deleteBtn.disabled = false;
        deleteBtn.textContent = "Delete Lead";
      }
    }
  }

  function todayIso() {
    const now = new Date();
    const offset = now.getTimezoneOffset();
    return new Date(now.getTime() - offset * 60000).toISOString().slice(0, 10);
  }

  function updateNoteDateDisplay() {
    const field = el("leadNewNoteDate");
    const display = el("leadNewNoteDateDisplay");
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

  function init() {
    const form = el("leadDetailsForm");
    if (!form) return;

    const saveBtn = el("saveLeadBtn");
    if (saveBtn) saveBtn.addEventListener("click", saveLead);

    const addNoteBtn = el("addLeadNoteBtn");
    if (addNoteBtn) addNoteBtn.addEventListener("click", addNote);

    initIntakeEmailModal();
    initLinkClientDiffModal();

    const convertBtn = el("convertLeadBtn");
    if (convertBtn) convertBtn.addEventListener("click", convertLead);

    const deleteBtn = el("deleteLeadBtn");
    if (deleteBtn) deleteBtn.addEventListener("click", deleteLead);

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

    const stage1List = el("leadStage1List");
    if (stage1List) {
      stage1List.addEventListener("change", function (event) {
        const row = event.target.closest(".dashboard-lead-stage1-row");
        if (row) saveStage1Milestone(row);
      });
    }

    const ndaViewModalClose = el("ndaViewModalClose");
    if (ndaViewModalClose) {
      ndaViewModalClose.addEventListener("click", () => {
        const modal = el("ndaViewModal");
        if (modal) modal.classList.remove("show");
      });
    }

    const noteDateField = el("leadNewNoteDate");
    if (noteDateField && !noteDateField.value) noteDateField.value = todayIso();
    updateNoteDateDisplay();
    if (noteDateField) noteDateField.addEventListener("change", updateNoteDateDisplay);

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
