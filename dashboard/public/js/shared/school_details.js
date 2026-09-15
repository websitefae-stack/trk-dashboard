(function () {
  "use strict";

  var el = Dashboard.el;

  const API = "dashboard.api.shared.school_pipeline";

  let schoolName;
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
        <input type="text" class="dashboard-input school-contact-note" placeholder="Response note" value="${escapeHtml(contact.response_note || "")}" style="flex:1;">
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

  async function saveSchool() {
    const payload = {
      school_name: currentSchool.school_name,
      website: el("schoolWebsiteInput")?.value.trim() || "",
      notes: el("schoolNotesInput")?.value || "",
      contacts: readContactsFromForm(),
    };

    await apiPost(`${API}.save_school`, {
      docname: schoolName,
      data: JSON.stringify(payload),
    });

    await loadSchool();
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

  function renderEnrollments(enrollments) {
    const body = el("enrollmentHistoryBody");
    if (!body) return;

    if (!enrollments || !enrollments.length) {
      body.innerHTML = `<tr><td colspan="5" class="dashboard-empty">No sequences run yet.</td></tr>`;
      return;
    }

    body.innerHTML = enrollments.map((row) => `
      <tr>
        <td>${escapeHtml(row.sequence)}</td>
        <td>${escapeHtml(row.status)}</td>
        <td>${row.current_step} / ${row.total_steps}</td>
        <td>${row.start_date || "—"}</td>
        <td>${row.status === "Active" ? (row.next_send_date || "—") : "—"}</td>
      </tr>
    `).join("");
  }

  // ---------- One-off email ----------

  function renderOneOffContactChoices(contacts) {
    const wrap = el("oneOffContactChoices");
    if (!wrap) return;

    if (!contacts || !contacts.length) {
      wrap.innerHTML = `<div class="dashboard-field-hint">Add a contact above first.</div>`;
      return;
    }

    wrap.innerHTML = contacts.map((c) => `
      <label style="display:flex; align-items:center; gap:8px; margin-bottom:4px;">
        <input type="checkbox" class="one-off-contact-checkbox" value="${escapeHtml(c.email)}">
        ${escapeHtml(c.contact_name)}${c.role ? ` (${escapeHtml(c.role)})` : ""} - ${escapeHtml(c.email)}
      </label>
    `).join("");
  }

  // ---------- Timeline ----------

  function renderTimeline(timeline) {
    const wrap = el("schoolTimeline");
    if (!wrap) return;

    if (!timeline || !timeline.length) {
      wrap.innerHTML = `<div class="dashboard-empty">Nothing sent yet.</div>`;
      return;
    }

    wrap.innerHTML = timeline.map((item) => {
      const isReceived = item.sent_or_received === "Received";
      return `
        <div class="dashboard-school-timeline-item ${isReceived ? "dashboard-school-timeline-received" : "dashboard-school-timeline-sent"}">
          <div class="dashboard-school-timeline-meta">
            ${isReceived ? "Received" : "Sent"} · ${item.communication_date || ""} ${isReceived ? `from ${escapeHtml(item.sender || "")}` : `to ${escapeHtml(item.recipients || "")}`}
          </div>
          <div><strong>${escapeHtml(item.subject || "(no subject)")}</strong></div>
        </div>
      `;
    }).join("");
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
      if (el("schoolNotesInput")) el("schoolNotesInput").value = currentSchool.notes || "";

      const clientNote = el("schoolLinkedClientNote");
      const convertBtn = el("convertToClientBtn");
      if (currentSchool.linked_client) {
        if (clientNote) {
          clientNote.style.display = "block";
          clientNote.innerHTML = `Linked to Client <a href="/franchisor_db/client_details?name=${encodeURIComponent(currentSchool.linked_client)}">${escapeHtml(currentSchool.linked_client)}</a>.`;
        }
        if (convertBtn) convertBtn.textContent = "View Client";
      } else if (clientNote) {
        clientNote.style.display = "none";
      }

      renderContacts(currentSchool.contacts);
      renderEnrollments(currentSchool.enrollments);
      renderOneOffContactChoices(currentSchool.contacts);
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

    el("convertToClientBtn")?.addEventListener("click", async function () {
      if (currentSchool?.linked_client) {
        window.location.href = `/franchisor_db/client_details?name=${encodeURIComponent(currentSchool.linked_client)}`;
        return;
      }

      if (!confirm(`Create a new Client for "${currentSchool.school_name}" and carry over all contacts?`)) return;

      try {
        const result = await apiPost(`${API}.convert_school_to_client`, { school: schoolName });
        window.location.href = `/franchisor_db/client_details?name=${encodeURIComponent(result.client)}`;
      } catch (error) {
        alert(error.message || "Could not convert to a client.");
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
      const message = el("oneOffMessage")?.value.trim() || "";

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
        el("oneOffMessage").value = "";
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
    loadSchool();
    loadSequenceOptions();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
