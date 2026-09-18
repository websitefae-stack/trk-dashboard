(function () {
  "use strict";

  var el = Dashboard.el;

  const API = "dashboard.api.shared.school_pipeline";

  let schoolName;
  let oneOffMessageEditor;
  let currentSchool = null;

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

    return data.message;
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  // ---------- Contacts (always read/written as a whole - see save_school's
  // own docstring: it rewrites the entire child table on every call, so
  // every save here must always include every contact row, not just the
  // one that changed) ----------

  function contactRowHtml(contact) {
    const responded = contact.responded ? "checked" : "";
    return `
      <div class="dashboard-school-contact-row" data-row-name="${escapeHtml(contact.name || "")}">
        <input type="text" class="dashboard-input school-contact-name" placeholder="Name" value="${escapeHtml(contact.contact_name || "")}">
        <select class="dashboard-select school-contact-role">
          <option value="" ${!contact.role ? "selected" : ""}>Role</option>
          <option value="SENCO" ${contact.role === "SENCO" ? "selected" : ""}>SENCO</option>
          <option value="Head" ${contact.role === "Head" ? "selected" : ""}>Head</option>
          <option value="Deputy Head" ${contact.role === "Deputy Head" ? "selected" : ""}>Deputy Head</option>
          <option value="Reception" ${contact.role === "Reception" ? "selected" : ""}>Reception</option>
          <option value="Other" ${contact.role === "Other" ? "selected" : ""}>Other</option>
        </select>
        <input type="email" class="dashboard-input school-contact-email" placeholder="Email" value="${escapeHtml(contact.email || "")}">
        <button type="button" class="dashboard-btn dashboard-btn-light school-contact-remove">Remove</button>
      </div>
      <div style="display:flex; align-items:center; gap:8px; margin: 2px 0 10px 0;">
        <label style="display:flex; align-items:center; gap:6px;">
          <input type="checkbox" class="school-contact-responded" ${responded}> Responded
        </label>
        <input type="hidden" class="school-contact-note" value="${escapeHtml(contact.response_note || "")}">
      </div>
    `;
  }

  function wireContactRemoveButtons(wrap) {
    wrap.querySelectorAll(".school-contact-remove").forEach((btn) => {
      btn.onclick = function () {
        const row = btn.closest(".dashboard-school-contact-row");
        row?.nextElementSibling?.remove();
        row?.remove();
      };
    });
  }

  function renderContacts(contacts) {
    const wrap = el("schoolContactsList");
    if (!wrap) return;

    wrap.innerHTML = (contacts || []).map(contactRowHtml).join("");
    wireContactRemoveButtons(wrap);
  }

  function readContactsFromForm() {
    return Array.from(document.querySelectorAll(".dashboard-school-contact-row")).map((row) => {
      const responseArea = row.nextElementSibling;
      return {
        contact_name: row.querySelector(".school-contact-name")?.value.trim() || "",
        role: row.querySelector(".school-contact-role")?.value || "",
        email: row.querySelector(".school-contact-email")?.value.trim() || "",
        responded: responseArea?.querySelector(".school-contact-responded")?.checked ? 1 : 0,
        response_note: responseArea?.querySelector(".school-contact-note")?.value || "",
      };
    }).filter((c) => c.contact_name && c.email);
  }

  async function saveSchool(overrides) {
    const payload = Object.assign({
      school_name: currentSchool.school_name,
      website: el("schoolWebsiteInput")?.value.trim() || "",
      address: el("schoolAddressInput")?.value.trim() || "",
      telephone: el("schoolTelephoneInput")?.value.trim() || "",
      area: el("schoolAreaInput")?.value.trim() || "",
      notes: currentSchool.notes || "",
      contacts: readContactsFromForm(),
    }, overrides || {});

    await apiPost(`${API}.save_school`, {
      docname: schoolName,
      data: JSON.stringify(payload),
    });

    await loadSchool();
  }

  function formatNoteDate() {
    const now = new Date();
    const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    return `${now.getDate()} ${months[now.getMonth()]} ${now.getFullYear()}`;
  }

  function renderNotesLog(notes) {
    const wrap = el("schoolNotesLog");
    if (!wrap) return;

    if (!notes || !notes.trim()) {
      wrap.innerHTML = `<div class="dashboard-field-hint">No notes yet.</div>`;
      return;
    }

    wrap.innerHTML = notes
      .split("\n")
      .filter((line) => line.trim())
      .map((line) => `<div class="dashboard-school-note-line">${escapeHtml(line)}</div>`)
      .join("");
  }

  async function addSchoolNote() {
    const input = el("schoolNewNoteInput");
    const noteText = (input?.value || "").trim();
    if (!noteText) return;

    const existing = (currentSchool.notes || "").trim();
    const newLine = `${noteText} - ${formatNoteDate()}`;
    const updatedNotes = existing ? `${existing}\n${newLine}` : newLine;

    await saveSchool({ notes: updatedNotes });

    if (input) input.value = "";
  }

  // ---------- Enrollment ----------

  async function loadSequenceOptions() {
    const select = el("enrollSequenceSelect");
    if (!select) return;

    try {
      const sequences = await apiPost(`${API}.get_sequences`, {});
      select.innerHTML = '<option value="">Choose a sequence…</option>' +
        sequences.filter((s) => s.is_active).map((s) => `<option value="${escapeHtml(s.name)}">${escapeHtml(s.sequence_name)}</option>`).join("");
    } catch (error) {
      // Non-fatal.
    }
  }

  async function loadClientLinkOptions() {
    const select = el("convertClientSelect");
    if (!select) return;

    try {
      const clients = await apiPost("dashboard.api.shared.leads.get_client_link_options", {});
      select.innerHTML = '<option value="">Choose an existing client…</option>' +
        clients.map((c) => `<option value="${escapeHtml(c.value)}">${escapeHtml(c.label)}</option>`).join("");
    } catch (error) {
      // Non-fatal - the button still works to create a new client.
    }
  }

  function renderEnrollments(enrollments) {
    const body = el("enrollmentHistoryBody");
    if (!body) return;

    if (!enrollments || !enrollments.length) {
      body.innerHTML = `<tr><td colspan="6" class="dashboard-empty">No sequences run yet.</td></tr>`;
      return;
    }

    body.innerHTML = enrollments.map((row) => `
      <tr>
        <td>${escapeHtml(row.sequence)}</td>
        <td>${escapeHtml(row.status)}</td>
        <td>${row.current_step} / ${row.total_steps}</td>
        <td>${row.start_date || "—"}</td>
        <td>${row.status === "Active" ? (row.next_send_date || "—") : "—"}</td>
        <td class="dashboard-action-cell">
          ${row.status === "Active" ? `
            <button type="button" class="dashboard-link-btn enrollment-send-now-btn" data-name="${escapeHtml(row.name)}">Send Now</button>
            <button type="button" class="dashboard-link-btn enrollment-cancel-btn" data-name="${escapeHtml(row.name)}">Cancel</button>
          ` : "—"}
        </td>
      </tr>
    `).join("");

    body.querySelectorAll(".enrollment-send-now-btn").forEach((btn) => {
      btn.addEventListener("click", async function () {
        btn.disabled = true;
        try {
          await apiPost(`${API}.send_next_step_now`, { enrollment: btn.dataset.name });
          await loadSchool();
        } catch (error) {
          alert(error.message || "Could not send this step.");
          btn.disabled = false;
        }
      });
    });

    body.querySelectorAll(".enrollment-cancel-btn").forEach((btn) => {
      btn.addEventListener("click", async function () {
        if (!confirm("Cancel this enrollment? The school can then be enrolled again from the top of the sequence.")) return;
        btn.disabled = true;
        try {
          await apiPost(`${API}.cancel_enrollment`, { enrollment: btn.dataset.name });
          await loadSchool();
        } catch (error) {
          alert(error.message || "Could not cancel this enrollment.");
          btn.disabled = false;
        }
      });
    });
  }

  // ---------- One-off email ----------

  function renderContactChoices(contacts, containerId, checkboxClass) {
    const wrap = el(containerId);
    if (!wrap) return;

    if (!contacts || !contacts.length) {
      wrap.innerHTML = `<div class="dashboard-field-hint">Add a contact above first.</div>`;
      return;
    }

    wrap.innerHTML = contacts.map((c) => `
      <label style="display:flex; align-items:center; gap:8px; margin-bottom:4px;">
        <input type="checkbox" class="${checkboxClass}" value="${escapeHtml(c.email)}">
        ${escapeHtml(c.contact_name)}${c.role ? ` (${escapeHtml(c.role)})` : ""} - ${escapeHtml(c.email)}
      </label>
    `).join("");
  }

  function renderOneOffContactChoices(contacts) {
    renderContactChoices(contacts, "oneOffContactChoices", "one-off-contact-checkbox");
  }

  function renderIntakeFormContactChoices(contacts) {
    renderContactChoices(contacts, "intakeFormContactChoices", "intake-form-contact-checkbox");
  }

  // ---------- Timeline ----------

  function renderTimeline(timeline) {
    const wrap = el("schoolTimeline");
    if (!wrap) return;

    if (!timeline || !timeline.length) {
      wrap.innerHTML = `<div class="dashboard-empty">Nothing sent yet.</div>`;
      return;
    }

    wrap.innerHTML = timeline.map((item, index) => {
      const isReceived = item.sent_or_received === "Received";

      // A sent email's content is HTML we generated ourselves via
      // wrap_branded_email_html() - safe to show as real HTML. A
      // received email's content is HTML from whoever replied, which
      // must never be dropped into the page as live markup (a crafted
      // reply could otherwise run script in this session) - it's shown
      // as escaped, pre-wrapped plain text instead.
      const bodyHtml = isReceived
        ? `<div class="dashboard-school-timeline-body-plain">${escapeHtml(item.content || "(no content)")}</div>`
        : (item.content || "<em>(no content)</em>");

      return `
        <div class="dashboard-school-timeline-item ${isReceived ? "dashboard-school-timeline-received" : "dashboard-school-timeline-sent"}" data-timeline-index="${index}">
          <div class="dashboard-school-timeline-meta">
            ${isReceived ? "Received" : "Sent"} · ${item.communication_date || ""} ${isReceived ? `from ${escapeHtml(item.sender || "")}` : `to ${escapeHtml(item.recipients || "")}`}
          </div>
          <div class="dashboard-school-timeline-subject">
            <strong>${escapeHtml(item.subject || "(no subject)")}</strong>
            <span class="dashboard-school-timeline-toggle">Show</span>
          </div>
          <div class="dashboard-school-timeline-body" style="display:none;">${bodyHtml}</div>
        </div>
      `;
    }).join("");

    wrap.querySelectorAll(".dashboard-school-timeline-item").forEach((row) => {
      row.addEventListener("click", function () {
        const body = row.querySelector(".dashboard-school-timeline-body");
        const toggle = row.querySelector(".dashboard-school-timeline-toggle");
        if (!body) return;
        const showing = body.style.display !== "none";
        body.style.display = showing ? "none" : "block";
        if (toggle) toggle.textContent = showing ? "Show" : "Hide";
      });
    });
  }

  // ---------- Load ----------

  async function loadSchool() {
    try {
      currentSchool = await apiPost(`${API}.get_school`, { name: schoolName });

      const title = el("schoolPageTitle");
      if (title) title.textContent = currentSchool.school_name;

      const subtitle = el("schoolPageSubtitle");
      if (subtitle) subtitle.textContent = `Stage: ${currentSchool.stage}`;

      if (el("schoolStageSelect")) el("schoolStageSelect").value = currentSchool.stage;
      if (el("schoolWebsiteInput")) el("schoolWebsiteInput").value = currentSchool.website || "";
      if (el("schoolAddressInput")) el("schoolAddressInput").value = currentSchool.address || "";
      if (el("schoolTelephoneInput")) el("schoolTelephoneInput").value = currentSchool.telephone || "";
      if (el("schoolAreaInput")) el("schoolAreaInput").value = currentSchool.area || "";
      renderNotesLog(currentSchool.notes);

      const linkedView = el("schoolLinkedClientView");
      const convertView = el("schoolConvertView");
      const viewClientBtn = el("viewLinkedClientBtn");

      if (currentSchool.linked_client) {
        if (linkedView) linkedView.style.display = "block";
        if (convertView) convertView.style.display = "none";
        if (viewClientBtn) viewClientBtn.href = `/franchisor_db/client_details?name=${encodeURIComponent(currentSchool.linked_client)}`;
      } else {
        if (linkedView) linkedView.style.display = "none";
        if (convertView) convertView.style.display = "block";
      }

      renderContacts(currentSchool.contacts);
      renderEnrollments(currentSchool.enrollments);
      renderOneOffContactChoices(currentSchool.contacts);
      renderIntakeFormContactChoices(currentSchool.contacts);
      renderTimeline(currentSchool.timeline);
    } catch (error) {
      const title = el("schoolPageTitle");
      if (title) title.textContent = "Could not load this school";
    }
  }

  // ---------- Event bindings ----------

  function bindEvents() {
    el("saveSchoolDetailsBtn")?.addEventListener("click", async function () {
      try {
        await saveSchool();
      } catch (error) {
        alert(error.message || "Could not save.");
      }
    });

    el("saveContactsBtn")?.addEventListener("click", async function () {
      try {
        await saveSchool();
      } catch (error) {
        alert(error.message || "Could not save contacts.");
      }
    });

    el("addSchoolNoteBtn")?.addEventListener("click", async function () {
      try {
        await addSchoolNote();
      } catch (error) {
        alert(error.message || "Could not add this note.");
      }
    });

    el("addContactRowBtn")?.addEventListener("click", function () {
      const wrap = el("schoolContactsList");
      if (!wrap) return;
      wrap.insertAdjacentHTML("beforeend", contactRowHtml({}));
      wireContactRemoveButtons(wrap);
    });

    el("schoolStageSelect")?.addEventListener("change", async function () {
      try {
        await apiPost(`${API}.set_school_stage`, { school: schoolName, stage: el("schoolStageSelect").value });
      } catch (error) {
        alert(error.message || "Could not update stage.");
      }
    });

    el("createNewClientBtn")?.addEventListener("click", async function () {
      if (!confirm(`Create a new Client for "${currentSchool.school_name}" and carry over all contacts?`)) return;

      try {
        const result = await apiPost(`${API}.convert_school_to_client`, { school: schoolName });
        window.location.href = `/franchisor_db/client_details?name=${encodeURIComponent(result.client)}`;
      } catch (error) {
        alert(error.message || "Could not create a client.");
      }
    });

    el("linkExistingClientBtn")?.addEventListener("click", async function () {
      const selectedClient = el("convertClientSelect")?.value || "";
      if (!selectedClient) {
        alert("Choose a client to link to first.");
        return;
      }

      const selectedClientLabel = el("convertClientSelect").options[el("convertClientSelect").selectedIndex].text;

      if (!confirm(`Link "${currentSchool.school_name}" to the existing client "${selectedClientLabel}" and carry over all contacts?`)) return;

      try {
        const result = await apiPost(`${API}.convert_school_to_client`, {
          school: schoolName,
          client: selectedClient,
        });
        window.location.href = `/franchisor_db/client_details?name=${encodeURIComponent(result.client)}`;
      } catch (error) {
        alert(error.message || "Could not link this client.");
      }
    });

    el("copyIntakeFormLinkBtn")?.addEventListener("click", async function () {
      const link = el("schoolIntakeFormLink")?.value || "";
      const btn = el("copyIntakeFormLinkBtn");
      try {
        await navigator.clipboard.writeText(link);
        if (btn) {
          const original = btn.textContent;
          btn.textContent = "Copied!";
          setTimeout(function () { btn.textContent = original; }, 1500);
        }
      } catch (error) {
        el("schoolIntakeFormLink")?.select();
      }
    });

    el("sendIntakeFormBtn")?.addEventListener("click", async function () {
      const emails = Array.from(document.querySelectorAll(".intake-form-contact-checkbox:checked")).map((cb) => cb.value);

      if (!emails.length) {
        alert("Choose at least one contact to send it to.");
        return;
      }

      const link = el("schoolIntakeFormLink")?.value || "";
      const btn = el("sendIntakeFormBtn");
      const originalText = btn.textContent;
      btn.disabled = true;
      btn.textContent = "Sending…";

      try {
        await apiPost(`${API}.send_one_off_school_email`, {
          school: schoolName,
          contact_emails: emails,
          subject: `Getting started with The Resilient Hub - ${currentSchool.school_name}`,
          message:
            `<p>Hi {{ contact_name }},</p>` +
            `<p>Thanks for your interest in The Resilient Hub. Please fill in this short form so we can get in touch about next steps:</p>` +
            `<p><a href="${link}">${link}</a></p>`,
        });
        await loadSchool();
      } catch (error) {
        alert(error.message || "Could not send the intake form.");
      } finally {
        btn.disabled = false;
        btn.textContent = originalText;
      }
    });

    el("enrollSchoolBtn")?.addEventListener("click", async function () {
      const sequence = el("enrollSequenceSelect")?.value;
      if (!sequence) {
        alert("Choose a sequence first.");
        return;
      }

      try {
        await apiPost(`${API}.enroll_schools`, {
          school_names: [schoolName],
          sequence,
          start_date: el("enrollStartDate")?.value || undefined,
        });
        await loadSchool();
      } catch (error) {
        alert(error.message || "Could not enrol this school.");
      }
    });

    el("sendOneOffBtn")?.addEventListener("click", async function () {
      const emails = Array.from(document.querySelectorAll(".one-off-contact-checkbox:checked")).map((cb) => cb.value);
      const subject = el("oneOffSubject")?.value.trim() || "";
      const message = oneOffMessageEditor ? oneOffMessageEditor.getHtml() : "";

      if (!emails.length) {
        alert("Choose at least one contact.");
        return;
      }
      if (!subject || !message) {
        alert("Subject and message are required.");
        return;
      }

      try {
        await apiPost(`${API}.send_one_off_school_email`, { school: schoolName, contact_emails: emails, subject, message });
        el("oneOffSubject").value = "";
        if (oneOffMessageEditor) oneOffMessageEditor.setHtml("");
        await loadSchool();
      } catch (error) {
        alert(error.message || "Could not send this email.");
      }
    });
  }

  function init() {
    const docnameInput = el("schoolDocname");
    if (!docnameInput) return;

    schoolName = docnameInput.value;

    bindEvents();
    const oneOffContainer = el("oneOffMessageEditor");
    if (oneOffContainer) {
      oneOffContainer.innerHTML = Dashboard.richTextEditorHtml();
      oneOffMessageEditor = Dashboard.wireRichTextEditor(oneOffContainer.querySelector(".dashboard-richtext"));
    }
    loadSchool();
    loadSequenceOptions();
    loadClientLinkOptions();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
