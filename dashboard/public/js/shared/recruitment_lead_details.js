(function () {
  "use strict";

  var el = Dashboard.el;

  const SHARED_API = "dashboard.api.shared.recruitment_leads";
  const DECLINE_STATUSES = ["Declined"];

  const STAGE1_MILESTONES_FRANCHISEE = [
    ["stage1_call_done", "Call With Ashley (Founder) / Franchise Call"],
    ["stage1_nda_done", "Sign NDA"],
    ["stage1_discovery_day_done", "Discovery Day"],
    ["stage1_intent_deposit_dbs_done", "Intent to Proceed"],
    ["stage1_deposit_invoice_done", "Deposit Invoice Done"],
    ["stage1_agreement_invoice_done", "Franchisee Intake + DBS/Insurance Submitted"],
    ["stage1_recruitment_questions_done", "Recruitment Questions Reviewed"],
    ["stage1_contract_sent_done", "Full Contract Signed"],
    ["stage1_final_invoice_done", "Final Invoice Raised"],
  ];

  const STAGE1_MILESTONES_SESSION_WORKER = [
    ["stage1_call_done", "Initial Call"],
    ["stage1_nda_done", "Sign NDA"],
    ["stage1_agreement_invoice_done", "Intake + DBS/Insurance Submitted"],
    ["fees_guide_done", "Fees and Expectations Guide"],
    ["sw_setup_done", "Set Up As Session Worker"],
  ];

  const STAGE1_ACTION_MILESTONES = new Set([
    "stage1_nda_done",
    "stage1_intent_deposit_dbs_done",
    "stage1_agreement_invoice_done",
    "stage1_contract_sent_done",
    "fees_guide_done",
    "sw_setup_done",
  ]);

  const EMAIL_ACTIONS = {
    nda: {
      title: "Send Non-Disclosure Agreement",
      defaultsMethod: `${SHARED_API}.get_nda_email_defaults`,
      sendMethod: `${SHARED_API}.send_nda_link`,
    },
    intent: {
      title: "Send Deposit and Intent to Proceed Agreement",
      defaultsMethod: `${SHARED_API}.get_intent_email_defaults`,
      sendMethod: `${SHARED_API}.send_intent_link`,
    },
    contract: {
      title: "Send Franchise Agreement",
      defaultsMethod: `${SHARED_API}.get_contract_email_defaults`,
      sendMethod: `${SHARED_API}.send_contract_link`,
    },
    intake: {
      title: "Send Intake + DBS Form",
      defaultsMethod: `${SHARED_API}.get_franchisee_intake_email_defaults`,
      sendMethod: `${SHARED_API}.send_franchisee_intake_form`,
    },
    fees_guide: {
      title: "Send Fees and Expectations Guide",
      defaultsMethod: `${SHARED_API}.get_fees_guide_email_defaults`,
      sendMethod: `${SHARED_API}.send_fees_guide_link`,
    },
  };

  let currentLead = null;
  let emailState = { kind: null, extraParams: null };

  function stage1ActionsId(fieldname) {
    return `rlStage1Actions_${fieldname}`;
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
      throw new Error(data.message || "There was a problem saving.");
    }

    return data.message || {};
  }

  async function apiPostForm(method, formData) {
    const response = await fetch(`/api/method/${method}`, {
      method: "POST",
      credentials: "same-origin",
      headers: { "X-Frappe-CSRF-Token": getCsrfToken() },
      body: formData,
    });

    const data = await response.json();

    if (!response.ok || data.exc) {
      throw new Error(data.message || "There was a problem.");
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

  function todayIso() {
    return new Date().toISOString().slice(0, 10);
  }

  function showMessage(message, isError) {
    const banner = el("rlFormMessage");
    if (!banner) {
      if (isError) console.error(message);
      return;
    }

    banner.textContent = message || "";
    banner.style.display = message ? "" : "none";
    banner.classList.toggle("dashboard-form-message-error", !!isError);
  }

  function toggleDeclineField() {
    const status = getValue("rl_status");
    const field = el("rlDeclineReasonField");
    if (!field) return;

    field.style.display = DECLINE_STATUSES.indexOf(status) !== -1 ? "" : "none";
  }

  // ---------------------------------------------------------------
  // Notes
  // ---------------------------------------------------------------

  function renderNotes(notes) {
    const list = el("rlNotesList");
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

  async function addNote() {
    const name = getValue("rlDocname");
    const textarea = el("rlNewNoteText");
    const dateInput = el("rlNewNoteDate");
    const btn = el("rlAddNoteBtn");
    if (!name || !textarea || !textarea.value.trim()) return;

    if (btn) { btn.disabled = true; btn.textContent = "Adding..."; }

    try {
      await apiPost(`${SHARED_API}.add_recruitment_lead_note`, {
        name,
        note: textarea.value.trim(),
        note_date: dateInput ? dateInput.value : "",
      });
      textarea.value = "";
      await loadLead();
    } catch (error) {
      window.alert(error.message || "Could not add this note.");
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = "Add"; }
    }
  }

  // ---------------------------------------------------------------
  // Stage 1 milestones
  // ---------------------------------------------------------------

  function renderStage1(lead) {
    const section = el("rlStage1Section");
    const list = el("rlStage1List");
    if (!section || !list) return;

    section.style.display = "";

    const isSessionWorker = lead.lead_type === "Session Worker";
    const titleEl = el("rlStage1Title");
    const hintEl = el("rlStage1Hint");
    if (titleEl) titleEl.textContent = isSessionWorker ? "Session Worker Onboarding" : "Stage 1 - Decide & Commit";
    if (hintEl) {
      hintEl.textContent = isSessionWorker
        ? "The pre-hire pipeline for a session worker, before a real Session Worker record exists."
        : "The pre-hire pipeline, before a real Coach record exists.";
    }

    const milestones = isSessionWorker ? STAGE1_MILESTONES_SESSION_WORKER : STAGE1_MILESTONES_FRANCHISEE;
    const stageData = lead.stage1 || {};

    list.innerHTML = milestones.map(([fieldname, label]) => {
      const milestone = stageData[fieldname] || { done: 0, date: "" };
      const checked = milestone.done ? "checked" : "";
      const dateValue = escapeHtml(milestone.date || "");
      const hasActions = STAGE1_ACTION_MILESTONES.has(fieldname);

      return `
        <div class="dashboard-lead-stage1-row${hasActions ? " dashboard-lead-stage1-row-wrap" : ""}" data-milestone="${escapeHtml(fieldname)}">
          <div class="dashboard-lead-stage1-row-main">
            <label class="dashboard-lead-stage1-label">
              <input type="checkbox" class="dashboard-lead-stage1-check" ${checked}>
              ${escapeHtml(label)}
            </label>
            <input type="date" class="dashboard-input dashboard-lead-stage1-date" value="${dateValue}"
              ${milestone.done ? "" : "disabled"}>
          </div>
          ${hasActions ? `<div class="dashboard-lead-stage1-actions" id="${stage1ActionsId(fieldname)}"></div>` : ""}
        </div>
      `;
    }).join("");

    list.querySelectorAll("[data-milestone]").forEach((row) => {
      row.querySelector(".dashboard-lead-stage1-check").addEventListener("change", () => saveStage1Milestone(row));
      row.querySelector(".dashboard-lead-stage1-date").addEventListener("change", () => saveStage1Milestone(row));
    });

    renderNdaBlock(lead);
    renderFranchiseeIntakeBlock(lead);

    if (isSessionWorker) {
      renderFeesGuideBlock(lead);
      renderSessionWorkerSetupBlock(lead);
    } else {
      renderIntentBlock(lead);
      renderContractBlock(lead);
    }
  }

  async function saveStage1Milestone(row) {
    const fieldname = row.dataset.milestone;
    const checkbox = row.querySelector(".dashboard-lead-stage1-check");
    const dateField = row.querySelector(".dashboard-lead-stage1-date");
    const name = getValue("rlDocname");
    if (!fieldname || !checkbox || !dateField || !name) return;

    dateField.disabled = !checkbox.checked;
    if (checkbox.checked && !dateField.value) dateField.value = todayIso();

    try {
      await apiPost(`${SHARED_API}.update_recruitment_pipeline`, {
        name,
        milestone: fieldname,
        done: checkbox.checked ? 1 : 0,
        milestone_date: dateField.value || "",
      });
    } catch (error) {
      window.alert(error.message || "Could not save this.");
    }
  }

  function signedViewAuditHtml(result) {
    const auditRows = [
      result.signed_at ? `Signed: ${escapeHtml(result.signed_at)}` : "",
      result.signer_ip ? `IP address: ${escapeHtml(result.signer_ip)}` : "",
      result.signer_user_agent ? `Browser/device: ${escapeHtml(result.signer_user_agent)}` : "",
    ].filter(Boolean);

    if (!auditRows.length) return "";

    return `<div style="margin-top:16px; padding:12px 14px; background:#F2F8F8; border-radius:10px; font-size:12px; color:#839898;">
      <strong style="display:block; margin-bottom:4px; color:#434B49;">Signing Record</strong>
      ${auditRows.join("<br>")}
    </div>`;
  }

  async function viewSignedDoc(title, method) {
    const name = getValue("rlDocname");
    if (!name) return;

    try {
      const result = await apiPost(method, { name });
      const titleEl = el("rlSignedViewTitle");
      const content = el("rlSignedViewModalContent");
      if (titleEl) titleEl.textContent = title;
      if (content) content.innerHTML = (result.signed_html || "") + signedViewAuditHtml(result);
      const modal = el("rlSignedViewModal");
      if (modal) modal.classList.add("show");
    } catch (error) {
      window.alert(error.message || "Could not load the signed document.");
    }
  }

  function linkRowHtml(inputId, copyBtnId, helpText) {
    return `
      <div id="${inputId}Result" style="flex-basis:100%; margin-top:8px; display:none;">
        <label style="display:block; font-size:12px; font-weight:600; margin-bottom:4px;">${helpText}</label>
        <div style="display:flex; gap:8px;">
          <input type="text" id="${inputId}" class="dashboard-input" readonly style="flex:1;">
          <button type="button" class="dashboard-btn dashboard-btn-secondary" id="${copyBtnId}">Copy</button>
        </div>
      </div>
    `;
  }

  function wireCopyButton(copyBtnId, inputId) {
    const copyBtn = el(copyBtnId);
    if (!copyBtn) return;
    copyBtn.addEventListener("click", () => {
      const input = el(inputId);
      if (!input) return;
      input.select();
      navigator.clipboard?.writeText(input.value).catch(() => {});
    });
  }

  // ---------------------------------------------------------------
  // NDA (shared by both lead types)
  // ---------------------------------------------------------------

  function renderNdaBlock(lead) {
    const block = el(stage1ActionsId("stage1_nda_done"));
    if (!block) return;

    if (lead.nda_signed) {
      block.innerHTML = `<button type="button" class="dashboard-btn dashboard-btn-light" id="rlViewSignedNdaBtn">View Signed NDA</button>`;
      const viewBtn = el("rlViewSignedNdaBtn");
      if (viewBtn) viewBtn.addEventListener("click", () => viewSignedDoc("Signed NDA", `${SHARED_API}.get_signed_nda`));
      return;
    }

    const sentStatusHtml = lead.nda_sent_at
      ? `<div class="dashboard-help" style="flex-basis:100%;">Sent ${escapeHtml(lead.nda_sent_at)}</div>` : "";

    block.innerHTML = `
      <button type="button" class="dashboard-btn dashboard-btn-primary" id="rlSendNdaBtn">${lead.nda_sent_at ? "Resend NDA" : "Send NDA"}</button>
      <button type="button" class="dashboard-btn dashboard-btn-light" id="rlGetNdaLinkBtn">${lead.nda_link_generated ? "Get NDA Sign Link Again" : "Generate NDA Sign Link"}</button>
      ${sentStatusHtml}
      ${linkRowHtml("rlNdaLinkInput", "rlCopyNdaLinkBtn", "Copy this link and send it to sign:")}
    `;

    el("rlSendNdaBtn")?.addEventListener("click", () => prepareEmail("nda"));
    el("rlGetNdaLinkBtn")?.addEventListener("click", async () => {
      const btn = el("rlGetNdaLinkBtn");
      if (btn) { btn.disabled = true; btn.textContent = "Generating..."; }
      try {
        const name = getValue("rlDocname");
        const result = await apiPost(`${SHARED_API}.get_nda_sign_url`, { name });
        setValue("rlNdaLinkInput", result.url || "");
        const resultBlock = el("rlNdaLinkInputResult");
        if (resultBlock) resultBlock.style.display = "";
      } catch (error) {
        window.alert(error.message || "Could not generate the sign link.");
      } finally {
        if (btn) { btn.disabled = false; btn.textContent = "Get NDA Sign Link Again"; }
      }
    });
    wireCopyButton("rlCopyNdaLinkBtn", "rlNdaLinkInput");
  }

  // ---------------------------------------------------------------
  // Intent to Proceed (Franchisee only)
  // ---------------------------------------------------------------

  function intentTermsPayload() {
    return {
      territory: getValue("rlIntentTerritoryInput"),
      deposit_amount: getValue("rlIntentDepositInput"),
      end_date: getValue("rlIntentEndDateInput"),
    };
  }

  function renderIntentBlock(lead) {
    const block = el(stage1ActionsId("stage1_intent_deposit_dbs_done"));
    if (!block) return;

    if (lead.intent_signed) {
      block.innerHTML = `<button type="button" class="dashboard-btn dashboard-btn-light" id="rlViewSignedIntentBtn">View Signed Agreement</button>`;
      el("rlViewSignedIntentBtn")?.addEventListener("click", () => viewSignedDoc("Signed Deposit & Intent to Proceed Agreement", `${SHARED_API}.get_signed_intent`));
      return;
    }

    const sendBtnLabel = lead.intent_sent_at ? "Resend Intent to Proceed" : "Send Intent to Proceed";
    const sentStatusHtml = lead.intent_sent_at
      ? `<div class="dashboard-help" style="flex-basis:100%;">Sent ${escapeHtml(lead.intent_sent_at)}</div>` : "";
    const linkRow = linkRowHtml("rlIntentLinkInput", "rlCopyIntentLinkBtn", "Copy this link and send it to the franchisee to sign:");

    if (lead.intent_link_generated) {
      block.innerHTML = `
        <button type="button" class="dashboard-btn dashboard-btn-primary" id="rlSendIntentBtn">${sendBtnLabel}</button>
        <button type="button" class="dashboard-btn dashboard-btn-light" id="rlGetIntentLinkBtn">Get Sign Link Again</button>
        ${sentStatusHtml}
        ${linkRow}
      `;
    } else {
      block.innerHTML = `
        <div style="display:flex; gap:10px; flex-wrap:wrap; flex-basis:100%;">
          <input type="text" id="rlIntentTerritoryInput" class="dashboard-input" placeholder="Territory (e.g. postcode areas)" style="flex:1; min-width:200px;">
          <input type="number" id="rlIntentDepositInput" class="dashboard-input" placeholder="Deposit Amount (£)" min="0" step="0.01" style="width:160px;">
          <input type="date" id="rlIntentEndDateInput" class="dashboard-input" style="width:160px;" title="Agreement End Date">
        </div>
        <button type="button" class="dashboard-btn dashboard-btn-primary" id="rlSendIntentBtn">${sendBtnLabel}</button>
        <button type="button" class="dashboard-btn dashboard-btn-light" id="rlGetIntentLinkBtn">Generate Sign Link</button>
        ${sentStatusHtml}
        ${linkRow}
      `;
    }

    el("rlSendIntentBtn")?.addEventListener("click", () => prepareEmail("intent", intentTermsPayload()));
    el("rlGetIntentLinkBtn")?.addEventListener("click", async () => {
      const btn = el("rlGetIntentLinkBtn");
      if (btn) { btn.disabled = true; btn.textContent = "Generating..."; }
      try {
        const name = getValue("rlDocname");
        const result = await apiPost(`${SHARED_API}.get_intent_sign_url`, { name, ...intentTermsPayload() });
        setValue("rlIntentLinkInput", result.url || "");
        const resultBlock = el("rlIntentLinkInputResult");
        if (resultBlock) resultBlock.style.display = "";
      } catch (error) {
        window.alert(error.message || "Could not generate the sign link.");
      } finally {
        if (btn) { btn.disabled = false; btn.textContent = "Get Sign Link Again"; }
      }
    });
    wireCopyButton("rlCopyIntentLinkBtn", "rlIntentLinkInput");
  }

  // ---------------------------------------------------------------
  // Franchise Agreement (Franchisee only)
  // ---------------------------------------------------------------

  function contractTermsPayload() {
    return {
      commencement_date: getValue("rlContractCommencementDateInput"),
      territory_description: getValue("rlContractTerritoryInput"),
      permitted_area: getValue("rlContractPermittedAreaInput"),
    };
  }

  function renderContractBlock(lead) {
    const block = el(stage1ActionsId("stage1_contract_sent_done"));
    if (!block) return;

    if (lead.contract_signed) {
      block.innerHTML = `<button type="button" class="dashboard-btn dashboard-btn-light" id="rlViewSignedContractBtn">View Signed Agreement</button>`;
      el("rlViewSignedContractBtn")?.addEventListener("click", () => viewSignedDoc("Signed Franchise Agreement", `${SHARED_API}.get_signed_contract`));
      return;
    }

    const sendBtnLabel = lead.contract_sent_at ? "Resend Franchise Agreement" : "Send Franchise Agreement";
    const sentStatusHtml = lead.contract_sent_at
      ? `<div class="dashboard-help" style="flex-basis:100%;">Sent ${escapeHtml(lead.contract_sent_at)}</div>` : "";
    const linkRow = linkRowHtml("rlContractLinkInput", "rlCopyContractLinkBtn", "Copy this link and send it to the franchisee to sign:");

    const territoryMapHtml = `
      <div style="flex-basis:100%; display:flex; align-items:center; gap:10px; flex-wrap:wrap;">
        <span class="dashboard-help">${lead.contract_territory_map ? "Territory map uploaded." : "No territory map uploaded yet - it appears in Schedule 2 of the agreement."}</span>
        ${lead.contract_territory_map ? `<a href="${escapeHtml(lead.contract_territory_map)}" target="_blank" rel="noopener">View current map</a>` : ""}
        <input type="file" id="rlContractTerritoryMapInput" accept="image/*">
        <button type="button" class="dashboard-btn dashboard-btn-light" id="rlUploadContractTerritoryMapBtn">${lead.contract_territory_map ? "Replace Map" : "Upload Map"}</button>
        <span class="dashboard-help" id="rlContractTerritoryMapStatus"></span>
      </div>
    `;

    if (lead.contract_link_generated) {
      const franchisorSignedHtml = lead.contract_franchisor_signature_name
        ? `<div class="dashboard-help" style="flex-basis:100%;">Generated by ${escapeHtml(lead.contract_franchisor_signature_name)} on ${escapeHtml(lead.contract_franchisor_signed_at)}.</div>`
        : "";
      block.innerHTML = `
        ${franchisorSignedHtml}
        <button type="button" class="dashboard-btn dashboard-btn-primary" id="rlSendContractBtn">${sendBtnLabel}</button>
        <button type="button" class="dashboard-btn dashboard-btn-light" id="rlGetContractLinkBtn">Get Sign Link Again</button>
        ${sentStatusHtml}
        ${linkRow}
        ${territoryMapHtml}
      `;
    } else {
      block.innerHTML = `
        ${territoryMapHtml}
        <div style="display:flex; gap:10px; flex-wrap:wrap; flex-basis:100%; margin-top:8px;">
          <input type="date" id="rlContractCommencementDateInput" class="dashboard-input" style="width:170px;" title="Commencement Date">
          <input type="text" id="rlContractTerritoryInput" class="dashboard-input" placeholder="Territory (postcode areas)" style="flex:1; min-width:200px;">
          <input type="text" id="rlContractPermittedAreaInput" class="dashboard-input" placeholder="Permitted Area (e.g. Hartford)" style="width:200px;">
        </div>
        <button type="button" class="dashboard-btn dashboard-btn-primary" id="rlSendContractBtn">${sendBtnLabel}</button>
        <button type="button" class="dashboard-btn dashboard-btn-light" id="rlGetContractLinkBtn">Generate Sign Link</button>
        ${sentStatusHtml}
        ${linkRow}
      `;
    }

    el("rlSendContractBtn")?.addEventListener("click", () => prepareEmail("contract", contractTermsPayload()));
    el("rlGetContractLinkBtn")?.addEventListener("click", async () => {
      const btn = el("rlGetContractLinkBtn");
      const originalLabel = btn ? btn.textContent : "";
      if (btn) { btn.disabled = true; btn.textContent = "Generating..."; }
      try {
        const name = getValue("rlDocname");
        const result = await apiPost(`${SHARED_API}.get_contract_sign_url`, { name, ...contractTermsPayload() });
        setValue("rlContractLinkInput", result.url || "");
        const resultBlock = el("rlContractLinkInputResult");
        if (resultBlock) resultBlock.style.display = "";
        await loadLead();
      } catch (error) {
        window.alert(error.message || "Could not generate the sign link.");
      } finally {
        if (btn) { btn.disabled = false; btn.textContent = originalLabel || "Get Sign Link Again"; }
      }
    });
    wireCopyButton("rlCopyContractLinkBtn", "rlContractLinkInput");

    el("rlUploadContractTerritoryMapBtn")?.addEventListener("click", async () => {
      const name = getValue("rlDocname");
      const fileInput = el("rlContractTerritoryMapInput");
      const uploadBtn = el("rlUploadContractTerritoryMapBtn");
      const statusEl = el("rlContractTerritoryMapStatus");
      if (!name || !fileInput) return;

      const file = fileInput.files && fileInput.files[0];
      if (!file) {
        if (statusEl) statusEl.textContent = "Choose an image first.";
        return;
      }

      if (uploadBtn) { uploadBtn.disabled = true; uploadBtn.textContent = "Uploading..."; }
      if (statusEl) statusEl.textContent = "";

      try {
        const formData = new FormData();
        formData.append("file", file);
        formData.append("name", name);
        await apiPostForm(`${SHARED_API}.upload_contract_territory_map`, formData);
        await loadLead();
      } catch (error) {
        if (statusEl) statusEl.textContent = error.message || "Could not upload this image.";
        if (uploadBtn) { uploadBtn.disabled = false; uploadBtn.textContent = "Upload Map"; }
      }
    });
  }

  // ---------------------------------------------------------------
  // Fees and Expectations Guide (Session Worker only)
  // ---------------------------------------------------------------

  function feesGuideTermsPayload() {
    return {
      rate_1to1: getValue("rlFeesGuideRate1to1Input"),
      rate_group: getValue("rlFeesGuideRateGroupInput"),
      rate_workshop: getValue("rlFeesGuideRateWorkshopInput"),
      invoicing_frequency: getValue("rlFeesGuideInvoicingFrequencyInput"),
      effective_date: getValue("rlFeesGuideEffectiveDateInput"),
    };
  }

  function renderFeesGuideBlock(lead) {
    const block = el(stage1ActionsId("fees_guide_done"));
    if (!block) return;

    if (lead.fees_guide_signed) {
      block.innerHTML = `<button type="button" class="dashboard-btn dashboard-btn-light" id="rlViewSignedFeesGuideBtn">View Signed Guide</button>`;
      el("rlViewSignedFeesGuideBtn")?.addEventListener("click", () => viewSignedDoc("Signed Fees and Expectations Guide", `${SHARED_API}.get_signed_fees_guide`));
      return;
    }

    const sendBtnLabel = lead.fees_guide_sent_at ? "Resend Fees and Expectations Guide" : "Send Fees and Expectations Guide";
    const sentStatusHtml = lead.fees_guide_sent_at
      ? `<div class="dashboard-help" style="flex-basis:100%;">Sent ${escapeHtml(lead.fees_guide_sent_at)}</div>` : "";
    const linkRow = linkRowHtml("rlFeesGuideLinkInput", "rlCopyFeesGuideLinkBtn", "Copy this link and send it to the worker to sign:");

    if (lead.fees_guide_link_generated) {
      block.innerHTML = `
        <button type="button" class="dashboard-btn dashboard-btn-primary" id="rlSendFeesGuideBtn">${sendBtnLabel}</button>
        <button type="button" class="dashboard-btn dashboard-btn-light" id="rlGetFeesGuideLinkBtn">Get Sign Link Again</button>
        ${sentStatusHtml}
        ${linkRow}
      `;
    } else {
      block.innerHTML = `
        <div style="display:flex; gap:10px; flex-wrap:wrap; flex-basis:100%;">
          <input type="number" id="rlFeesGuideRate1to1Input" class="dashboard-input" placeholder="1:1 Session Rate (£)" min="0" step="0.01" style="width:170px;">
          <input type="number" id="rlFeesGuideRateGroupInput" class="dashboard-input" placeholder="Group Session Rate (£)" min="0" step="0.01" style="width:170px;">
          <input type="number" id="rlFeesGuideRateWorkshopInput" class="dashboard-input" placeholder="Workshop Rate (£)" min="0" step="0.01" style="width:170px;">
        </div>
        <div style="display:flex; gap:10px; flex-wrap:wrap; flex-basis:100%; margin-top:8px;">
          <select id="rlFeesGuideInvoicingFrequencyInput" class="dashboard-input" style="width:170px;">
            <option value="">Invoicing Frequency...</option>
            <option value="Weekly">Weekly</option>
            <option value="Fortnightly">Fortnightly</option>
            <option value="Monthly">Monthly</option>
          </select>
          <input type="date" id="rlFeesGuideEffectiveDateInput" class="dashboard-input" style="width:170px;" title="Effective From">
        </div>
        <button type="button" class="dashboard-btn dashboard-btn-primary" id="rlSendFeesGuideBtn">${sendBtnLabel}</button>
        <button type="button" class="dashboard-btn dashboard-btn-light" id="rlGetFeesGuideLinkBtn">Generate Sign Link</button>
        ${sentStatusHtml}
        ${linkRow}
      `;
    }

    el("rlSendFeesGuideBtn")?.addEventListener("click", () => prepareEmail("fees_guide", feesGuideTermsPayload()));
    el("rlGetFeesGuideLinkBtn")?.addEventListener("click", async () => {
      const btn = el("rlGetFeesGuideLinkBtn");
      if (btn) { btn.disabled = true; btn.textContent = "Generating..."; }
      try {
        const name = getValue("rlDocname");
        const result = await apiPost(`${SHARED_API}.get_fees_guide_sign_url`, { name, ...feesGuideTermsPayload() });
        setValue("rlFeesGuideLinkInput", result.url || "");
        const resultBlock = el("rlFeesGuideLinkInputResult");
        if (resultBlock) resultBlock.style.display = "";
      } catch (error) {
        window.alert(error.message || "Could not generate the sign link.");
      } finally {
        if (btn) { btn.disabled = false; btn.textContent = "Get Sign Link Again"; }
      }
    });
    wireCopyButton("rlCopyFeesGuideLinkBtn", "rlFeesGuideLinkInput");
  }

  // ---------------------------------------------------------------
  // Intake + DBS/Insurance form (shared)
  // ---------------------------------------------------------------

  function renderFranchiseeIntakeBlock(lead) {
    const block = el(stage1ActionsId("stage1_agreement_invoice_done"));
    if (!block) return;

    if (lead.franchisee_intake_submitted) {
      const isFranchisee = lead.lead_type === "Franchisee";
      const alreadyConverted = (isFranchisee && lead.status === "Converted" && lead.converted_client)
        || (!isFranchisee && lead.converted_session_worker);

      let convertHtml = "";
      if (isFranchisee) {
        convertHtml = alreadyConverted
          ? `<a class="dashboard-btn dashboard-btn-light" href="/franchisor_db/client_details?name=${encodeURIComponent(lead.converted_client)}">View Client</a>`
          : `<button type="button" class="dashboard-btn dashboard-btn-primary" id="rlConvertBtn">Convert to Client</button>`;
      }

      const reopenHtml = alreadyConverted
        ? "" : `<button type="button" class="dashboard-btn dashboard-btn-light" id="rlReopenIntakeBtn">Reopen Intake Form</button>`;

      block.innerHTML = `
        <div id="rlIntakeSummary" class="dashboard-help" style="flex-basis:100%;">Loading…</div>
        <div id="rlSaferRecruitmentChecklistContainer" style="flex-basis:100%; margin-top:10px;">Loading checklist…</div>
        ${reopenHtml}
        ${convertHtml}
        <div id="rlConvertStatus" class="dashboard-help" style="flex-basis:100%;"></div>
      `;
      loadIntakeSummary();
      loadSaferRecruitmentChecklist();

      el("rlConvertBtn")?.addEventListener("click", convertLeadToClient);
      el("rlReopenIntakeBtn")?.addEventListener("click", reopenIntake);
      return;
    }

    const linkRow = linkRowHtml("rlIntakeLinkInput", "rlCopyIntakeLinkBtn", "Copy this link and send it to fill in:");

    block.innerHTML = `
      <button type="button" class="dashboard-btn dashboard-btn-primary" id="rlSendIntakeBtn">${lead.franchisee_intake_sent_at ? "Resend Intake Form" : "Send Intake Form"}</button>
      <button type="button" class="dashboard-btn dashboard-btn-light" id="rlGetIntakeLinkBtn">${lead.franchisee_intake_link_generated ? "Get Form Link Again" : "Generate Form Link"}</button>
      <div class="dashboard-help" style="flex-basis:100%;">${lead.franchisee_intake_sent_at ? `Sent ${escapeHtml(lead.franchisee_intake_sent_at)}` : ""}</div>
      ${linkRow}
    `;

    el("rlSendIntakeBtn")?.addEventListener("click", () => prepareEmail("intake"));
    el("rlGetIntakeLinkBtn")?.addEventListener("click", async () => {
      const btn = el("rlGetIntakeLinkBtn");
      if (btn) { btn.disabled = true; btn.textContent = "Generating..."; }
      try {
        const name = getValue("rlDocname");
        const result = await apiPost(`${SHARED_API}.get_franchisee_intake_url`, { name });
        setValue("rlIntakeLinkInput", result.url || "");
        const resultBlock = el("rlIntakeLinkInputResult");
        if (resultBlock) resultBlock.style.display = "";
      } catch (error) {
        window.alert(error.message || "Could not generate the form link.");
      } finally {
        if (btn) { btn.disabled = false; btn.textContent = "Get Form Link Again"; }
      }
    });
    wireCopyButton("rlCopyIntakeLinkBtn", "rlIntakeLinkInput");
  }

  async function reopenIntake() {
    const name = getValue("rlDocname");
    const btn = el("rlReopenIntakeBtn");
    const statusEl = el("rlConvertStatus");
    if (!name) return;

    if (!window.confirm("Reopen this intake form? They'll be able to use their existing link to go back in and finish or correct it - nothing already submitted is lost.")) {
      return;
    }

    if (btn) { btn.disabled = true; btn.textContent = "Reopening..."; }

    try {
      await apiPost(`${SHARED_API}.reopen_franchisee_intake`, { name });
      await loadLead();
    } catch (error) {
      if (statusEl) statusEl.textContent = error.message || "Could not reopen this.";
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = "Reopen Intake Form"; }
    }
  }

  async function loadIntakeSummary() {
    const name = getValue("rlDocname");
    const summary = el("rlIntakeSummary");
    if (!name || !summary) return;

    try {
      const result = await apiPost(`${SHARED_API}.get_franchisee_intake`, { name });

      const rows = [
        ["Name", `${result.first_name} ${result.last_name}`.trim()],
        ["Phone", result.phone],
        ["Gender", result.gender],
        ["Date of Birth", result.dob],
        ["ID Document", result.id_document_type],
        ["Right to Work Status", result.right_to_work_status],
        ["Visa Expiry", result.right_to_work_expiry],
        ["Address History", result.address_history],
        ["Overseas Checks", result.overseas_checks],
        ["Work History", result.work_history],
        ["Work Locations / Areas", result.work_locations],
        ["Qualifications / Training", result.qualifications],
        ["Reference 1", result.reference1_details],
        ["Reference 2", result.reference2_details],
        ["DBS Number", result.dbs_number],
        ["DBS Date Received", result.dbs_date_received],
        ["DBS Expiry Date", result.dbs_expiry_date],
        ["Public Liability Insurer", result.public_liability_insurer],
        ["Professional Indemnity Insurer", result.indemnity_insurer],
        ["Insurance Renewal Date", result.insurance_renewal_date],
        ["Submitted", result.submitted_at],
      ].filter(([, value]) => value);

      const rowsHtml = rows.map(([label, value]) => `
        <div class="dashboard-field-value-row">
          <div class="dashboard-field-value-label">${escapeHtml(label)}</div>
          <div class="dashboard-field-value-text">${escapeHtml(value)}</div>
        </div>
      `).join("");

      const fileLinks = [
        result.dbs_certificate ? `<a href="${escapeHtml(result.dbs_certificate)}" target="_blank" rel="noopener" class="dashboard-btn dashboard-btn-light">View DBS Certificate</a>` : "",
        result.additional_document ? `<a href="${escapeHtml(result.additional_document)}" target="_blank" rel="noopener" class="dashboard-btn dashboard-btn-light">View Additional Document</a>` : "",
      ].filter(Boolean).join(" ");

      summary.innerHTML = rowsHtml + `<div style="margin-top:10px; display:flex; gap:8px;">${fileLinks}</div>`;
    } catch (error) {
      summary.textContent = error.message || "Could not load the submitted intake form.";
    }
  }

  // ---------------------------------------------------------------
  // Safer Recruitment Checklist
  // ---------------------------------------------------------------

  const SAFER_RECRUITMENT_STATUS_OPTIONS = ["Pending", "Complete", "N/A"];

  async function loadSaferRecruitmentChecklist() {
    const name = getValue("rlDocname");
    const container = el("rlSaferRecruitmentChecklistContainer");
    if (!name || !container) return;

    try {
      const result = await apiPost(`${SHARED_API}.get_safer_recruitment_checklist`, { name });
      renderSaferRecruitmentChecklist(result.rows || [], result.outstanding_actions || "");
    } catch (error) {
      container.textContent = error.message || "Could not load the Safer Recruitment Checklist.";
    }
  }

  function saferRecruitmentChecklistRowHtml(row) {
    return `
      <tr data-checklist-row="${escapeHtml(row.item_key)}">
        <td>${escapeHtml(row.item_label)}</td>
        <td>
          <select class="dashboard-input" data-checklist-field="status" style="min-width:110px;">
            ${SAFER_RECRUITMENT_STATUS_OPTIONS.map((opt) => `<option value="${opt}" ${row.status === opt ? "selected" : ""}>${opt}</option>`).join("")}
          </select>
        </td>
        <td><input type="date" class="dashboard-input" data-checklist-field="checked_date" value="${escapeHtml(row.checked_date || "")}" style="min-width:140px;"></td>
        <td><input type="text" class="dashboard-input" data-checklist-field="notes" value="${escapeHtml(row.notes || "")}" placeholder="Notes / expiry">
          ${row.checked_by ? `<div class="dashboard-help" style="margin-top:2px;">Checked by ${escapeHtml(row.checked_by)}</div>` : ""}
        </td>
      </tr>
    `;
  }

  function saferRecruitmentChecklistTableHtml(rowList) {
    const sections = [];
    const sectionIndex = {};
    rowList.forEach((row) => {
      if (!(row.section in sectionIndex)) {
        sectionIndex[row.section] = sections.length;
        sections.push({ section: row.section, rows: [] });
      }
      sections[sectionIndex[row.section]].rows.push(row);
    });

    const rowsHtml = sections.map((group) => `
      <tr><td colspan="4" style="font-weight:700; padding-top:12px; border:none;">${escapeHtml(group.section)}</td></tr>
      ${group.rows.map(saferRecruitmentChecklistRowHtml).join("")}
    `).join("");

    return `
      <div class="dashboard-table-wrap">
        <table class="dashboard-table">
          <thead><tr><th>Requirement</th><th>Status</th><th>Date</th><th>Notes</th></tr></thead>
          <tbody>${rowsHtml}</tbody>
        </table>
      </div>
    `;
  }

  function renderSaferRecruitmentChecklist(rows, outstandingActions) {
    const container = el("rlSaferRecruitmentChecklistContainer");
    if (!container) return;

    const isReviewed = (row) => row.status && row.status !== "Pending";
    const completeCount = rows.filter(isReviewed).length;

    const pendingRows = rows.filter((row) => !isReviewed(row));
    const reviewedRows = rows.filter(isReviewed).slice().sort((a, b) => {
      const dateA = a.checked_date || "";
      const dateB = b.checked_date || "";
      if (dateA === dateB) return 0;
      if (!dateA) return 1;
      if (!dateB) return -1;
      return dateA < dateB ? -1 : 1;
    });

    const pendingHtml = pendingRows.length
      ? saferRecruitmentChecklistTableHtml(pendingRows)
      : `<p class="dashboard-help">Everything's been reviewed - see completed/not applicable items below.</p>`;

    const reviewedHtml = reviewedRows.length
      ? `
        <details style="margin-top:14px;">
          <summary style="cursor:pointer; font-weight:600;">✓ ${reviewedRows.length} completed / not applicable</summary>
          ${saferRecruitmentChecklistTableHtml(reviewedRows)}
        </details>
      `
      : "";

    container.innerHTML = `
      <details ${completeCount < rows.length ? "open" : ""} style="width:100%;">
        <summary style="cursor:pointer; font-weight:600;">
          Safer Recruitment Checklist - ${completeCount} of ${rows.length} reviewed
        </summary>
        <p class="dashboard-help">Go through every item below and mark it off before converting this lead.</p>
        ${pendingHtml}
        ${reviewedHtml}
        <div style="margin-top:10px;">
          <label style="display:block; font-weight:600; font-size:13px; margin-bottom:4px;">Outstanding Actions &amp; Conditions</label>
          <textarea id="rlSaferRecruitmentOutstandingActions" class="dashboard-textarea" rows="3" placeholder="Any follow-up actions or conditions before this can proceed">${escapeHtml(outstandingActions)}</textarea>
          <button type="button" class="dashboard-btn dashboard-btn-light" id="rlSaveSaferRecruitmentOutstandingActionsBtn" style="margin-top:6px;">Save</button>
          <span class="dashboard-help" id="rlSaferRecruitmentOutstandingActionsStatus"></span>
        </div>
      </details>
    `;

    container.querySelectorAll("[data-checklist-row]").forEach((rowEl) => {
      const itemKey = rowEl.dataset.checklistRow;
      rowEl.querySelectorAll("[data-checklist-field]").forEach((fieldEl) => {
        fieldEl.addEventListener("change", () => saveSaferRecruitmentChecklistItem(itemKey, rowEl));
      });
    });

    el("rlSaveSaferRecruitmentOutstandingActionsBtn")?.addEventListener("click", saveSaferRecruitmentOutstandingActions);
  }

  async function saveSaferRecruitmentChecklistItem(itemKey, rowEl) {
    const name = getValue("rlDocname");
    if (!name) return;

    const status = rowEl.querySelector('[data-checklist-field="status"]').value;
    const checkedDate = rowEl.querySelector('[data-checklist-field="checked_date"]').value;
    const notes = rowEl.querySelector('[data-checklist-field="notes"]').value;

    try {
      await apiPost(`${SHARED_API}.update_safer_recruitment_checklist_item`, {
        name, item_key: itemKey, status, checked_date: checkedDate, notes,
      });
      await loadSaferRecruitmentChecklist();
    } catch (error) {
      window.alert(error.message || "Could not save this checklist item.");
    }
  }

  async function saveSaferRecruitmentOutstandingActions() {
    const name = getValue("rlDocname");
    const textarea = el("rlSaferRecruitmentOutstandingActions");
    const statusEl = el("rlSaferRecruitmentOutstandingActionsStatus");
    const btn = el("rlSaveSaferRecruitmentOutstandingActionsBtn");
    if (!name || !textarea) return;

    if (btn) { btn.disabled = true; btn.textContent = "Saving..."; }

    try {
      await apiPost(`${SHARED_API}.update_safer_recruitment_outstanding_actions`, {
        name, outstanding_actions: textarea.value,
      });
      if (statusEl) statusEl.textContent = "Saved.";
    } catch (error) {
      if (statusEl) statusEl.textContent = error.message || "Could not save this.";
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = "Save"; }
    }
  }

  // ---------------------------------------------------------------
  // Set up as Session Worker
  // ---------------------------------------------------------------

  function renderSessionWorkerSetupBlock(lead) {
    const block = el(stage1ActionsId("sw_setup_done"));
    if (!block) return;

    if (lead.converted_session_worker) {
      block.innerHTML = `
        <a class="dashboard-btn dashboard-btn-light" href="/app/session-worker/${encodeURIComponent(lead.converted_session_worker)}" target="_blank" rel="noopener">
          View Session Worker Record
        </a>
      `;
      return;
    }

    block.innerHTML = `
      <button type="button" class="dashboard-btn dashboard-btn-primary" id="rlOpenSessionWorkerSetupBtn">Open New Session Worker Form</button>
      <div style="display:flex; gap:8px; align-items:center; flex-basis:100%; margin-top:8px;">
        <input type="text" id="rlSessionWorkerLinkInput" class="dashboard-input" placeholder="Session Worker record name, once created" style="flex:1;">
        <button type="button" class="dashboard-btn dashboard-btn-secondary" id="rlSaveSessionWorkerLinkBtn">Save</button>
      </div>
      <div id="rlSessionWorkerSetupStatus" class="dashboard-help" style="flex-basis:100%;"></div>
    `;

    el("rlOpenSessionWorkerSetupBtn")?.addEventListener("click", async () => {
      const name = getValue("rlDocname");
      const btn = el("rlOpenSessionWorkerSetupBtn");
      if (!name) return;
      if (btn) { btn.disabled = true; btn.textContent = "Opening..."; }
      try {
        const result = await apiPost(`${SHARED_API}.get_session_worker_setup_url`, { name });
        if (result.url) window.open(result.url, "_blank", "noopener");
      } catch (error) {
        window.alert(error.message || "Could not open the New Session Worker form.");
      } finally {
        if (btn) { btn.disabled = false; btn.textContent = "Open New Session Worker Form"; }
      }
    });

    el("rlSaveSessionWorkerLinkBtn")?.addEventListener("click", async () => {
      const name = getValue("rlDocname");
      const input = el("rlSessionWorkerLinkInput");
      const statusEl = el("rlSessionWorkerSetupStatus");
      const btn = el("rlSaveSessionWorkerLinkBtn");
      if (!name || !input) return;

      const sessionWorker = input.value.trim();
      if (!sessionWorker) {
        if (statusEl) statusEl.textContent = "Enter the Session Worker record's name first.";
        return;
      }

      if (btn) { btn.disabled = true; btn.textContent = "Saving..."; }
      if (statusEl) statusEl.textContent = "";

      try {
        await apiPost(`${SHARED_API}.set_session_worker_link`, { name, session_worker: sessionWorker });
        await loadLead();
      } catch (error) {
        if (statusEl) statusEl.textContent = error.message || "Could not save this.";
      } finally {
        if (btn) { btn.disabled = false; btn.textContent = "Save"; }
      }
    });
  }

  // ---------------------------------------------------------------
  // Convert to Client
  // ---------------------------------------------------------------

  async function convertLeadToClient() {
    const name = getValue("rlDocname");
    const baseUrl = getValue("rlBaseUrl") || "/franchisor_db";
    if (!window.confirm("Create a Client and Contact record from this lead's details?")) return;

    const btn = el("rlConvertBtn");
    if (btn) btn.disabled = true;

    try {
      const result = await apiPost(`${SHARED_API}.convert_recruitment_lead_to_client`, { name });
      if (result && result.client) {
        window.location.href = `${baseUrl}/client_details?name=${encodeURIComponent(result.client)}`;
        return;
      }
      await loadLead();
    } catch (error) {
      const statusEl = el("rlConvertStatus");
      if (statusEl) statusEl.textContent = error.message || "Could not convert this lead.";
    } finally {
      if (btn) btn.disabled = false;
    }
  }

  // ---------------------------------------------------------------
  // Email compose modal (shared by NDA/Intent/Contract/Intake/Fees Guide)
  // ---------------------------------------------------------------

  function openEmailModal() {
    const modal = el("rlEmailModal");
    if (modal) modal.classList.add("show");
  }

  function closeEmailModal() {
    const modal = el("rlEmailModal");
    if (modal) modal.classList.remove("show");
  }

  async function prepareEmail(kind, extraParams) {
    const action = EMAIL_ACTIONS[kind];
    if (!action) return;

    const name = getValue("rlDocname");
    emailState = { kind, extraParams: extraParams || {} };

    const titleEl = el("rlEmailTitle");
    if (titleEl) titleEl.textContent = action.title;

    try {
      const defaults = await apiPost(action.defaultsMethod, { name, ...emailState.extraParams });

      setValue("rlEmailRecipient", defaults.recipient || "");
      setValue("rlEmailSubject", defaults.subject || "");
      setValue("rlEmailMessage", defaults.message || "");
      setValue("rlEmailCc", "");
      const statusField = el("rlEmailStatus");
      if (statusField) statusField.textContent = "";

      openEmailModal();
    } catch (error) {
      showMessage(error.message || "Could not load this email.", true);
    }
  }

  async function confirmSendEmail() {
    const { kind, extraParams } = emailState;
    const action = EMAIL_ACTIONS[kind];
    if (!action) return;

    const name = getValue("rlDocname");
    const statusField = el("rlEmailStatus");
    const submitBtn = el("rlEmailSubmit");

    if (submitBtn) { submitBtn.disabled = true; submitBtn.textContent = "Sending..."; }
    if (statusField) statusField.textContent = "";

    try {
      await apiPost(action.sendMethod, {
        name,
        ...(extraParams || {}),
        subject: getValue("rlEmailSubject").trim(),
        message: getValue("rlEmailMessage").trim(),
        cc: getValue("rlEmailCc").trim(),
      });

      showMessage("Sent.", false);
      closeEmailModal();
      await loadLead();
    } catch (error) {
      if (statusField) statusField.textContent = error.message || "Could not send this email.";
    } finally {
      if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = "Send"; }
    }
  }

  function initEmailModal() {
    el("rlEmailModalClose")?.addEventListener("click", closeEmailModal);
    el("rlEmailCancel")?.addEventListener("click", closeEmailModal);
    el("rlEmailSubmit")?.addEventListener("click", confirmSendEmail);
  }

  function initSignedViewModal() {
    el("rlSignedViewModalClose")?.addEventListener("click", () => el("rlSignedViewModal")?.classList.remove("show"));
  }

  // ---------------------------------------------------------------
  // Load / populate / save
  // ---------------------------------------------------------------

  function populateForm(lead) {
    currentLead = lead;

    setValue("rl_contact_name", lead.contact_name);
    setValue("rl_contact_email", lead.contact_email);
    setValue("rl_contact_mobile", lead.contact_mobile);
    setValue("rl_postal_code", lead.postal_code);
    setValue("rl_location_address", lead.location_address);
    setValue("rl_how_heard", lead.how_heard);

    const consentField = el("rl_consent_given");
    if (consentField) consentField.checked = !!lead.consent_given;

    if (el("rl_status")) {
      setValue("rl_status", lead.status || "New");
      setValue("rl_decline_reason", lead.decline_reason || "");
      toggleDeclineField();
    }

    const coachField = el("rl_coach");
    if (coachField) coachField.value = lead.coach || "";

    const typeBadge = el("rlTypeBadge");
    if (typeBadge) {
      if (lead.lead_type) {
        typeBadge.textContent = lead.lead_type;
        typeBadge.style.display = "";
      } else {
        typeBadge.style.display = "none";
      }
    }

    renderNotes(lead.notes || []);
    renderStage1(lead);
  }

  async function loadLead() {
    const name = getValue("rlDocname");
    if (!name) return;

    try {
      const lead = await apiPost(`${SHARED_API}.get_recruitment_lead`, { name });
      populateForm(lead);
    } catch (error) {
      showMessage(error.message || "Could not load this lead.", true);
    }
  }

  function collectFormPayload() {
    return {
      contact_name: getValue("rl_contact_name").trim(),
      contact_email: getValue("rl_contact_email").trim(),
      contact_mobile: getValue("rl_contact_mobile").trim(),
      postal_code: getValue("rl_postal_code").trim(),
      location_address: getValue("rl_location_address").trim(),
      how_heard: getValue("rl_how_heard").trim(),
      consent_given: el("rl_consent_given")?.checked ? 1 : 0,
    };
  }

  async function saveLead() {
    const isNew = getValue("rlIsNew") === "1";
    const baseUrl = getValue("rlBaseUrl") || "/franchisor_db";
    const payload = collectFormPayload();

    if (!payload.contact_name) {
      showMessage("Please enter the contact's name.", true);
      return;
    }

    const saveBtn = el("rlSaveBtn");
    if (saveBtn) saveBtn.disabled = true;

    try {
      if (isNew) {
        payload.lead_type = getValue("rl_lead_type");
        payload.coach = getValue("rl_coach");

        const result = await apiPost(`${SHARED_API}.create_recruitment_lead`, payload);
        window.location.href = `${baseUrl}/recruitment_lead_details?name=${encodeURIComponent(result.name)}`;
        return;
      }

      payload.name = getValue("rlDocname");
      payload.coach = getValue("rl_coach");

      await apiPost(`${SHARED_API}.update_recruitment_lead`, payload);

      const statusField = el("rl_status");
      if (statusField) {
        await apiPost(`${SHARED_API}.update_recruitment_lead_status`, {
          name: payload.name,
          status: statusField.value,
          decline_reason: getValue("rl_decline_reason").trim(),
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

  async function deleteLead() {
    const name = getValue("rlDocname");
    if (!name) return;

    if (!window.confirm("Delete this lead? This cannot be undone.")) return;

    const deleteBtn = el("rlDeleteBtn");
    if (deleteBtn) { deleteBtn.disabled = true; deleteBtn.textContent = "Deleting..."; }

    try {
      await apiPost(`${SHARED_API}.delete_recruitment_lead`, { name });
      const baseUrl = getValue("rlBaseUrl") || "/franchisor_db";
      window.location.href = `${baseUrl}/recruitment_leads`;
    } catch (error) {
      showMessage(error.message || "Could not delete this lead.", true);
      if (deleteBtn) { deleteBtn.disabled = false; deleteBtn.textContent = "Delete Lead"; }
    }
  }

  function init() {
    const form = el("rlDetailsForm");
    if (!form) return;

    initEmailModal();
    initSignedViewModal();

    el("rlSaveBtn")?.addEventListener("click", saveLead);
    el("rlDeleteBtn")?.addEventListener("click", deleteLead);
    el("rlAddNoteBtn")?.addEventListener("click", addNote);
    el("rl_status")?.addEventListener("change", toggleDeclineField);

    const isNew = getValue("rlIsNew") === "1";
    if (!isNew) {
      loadLead();
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
