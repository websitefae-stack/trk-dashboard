(function () {
  const optionCache = {};
  let isSaving = false;
  let currentClientDefaults = null;

  const SHARED_API = "dashboard.api.shared.invoices";

  const TRAVEL_ITEM_CODE = "TRA002";
  const FREE_MILES_ONE_WAY = 10;
  const TRAVEL_RATE_PER_MILE = 0.55;

  var el = Dashboard.el;
  var qsa = Dashboard.qsa;

  function formatDisplayDate(value) {
    if (!value) return "";

    const date = new Date(String(value).slice(0, 10) + "T00:00:00");
    if (isNaN(date.getTime())) return String(value);

    return date.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
  }

  function getDashboardBasePath() {
    const path = window.location.pathname || "";
    if (path.startsWith("/franchisor_db")) return "/franchisor_db";
    return "/coach_db";
  }

  function getCsrfToken() {
    const hidden = el("csrfToken");
    return hidden && hidden.value ? hidden.value : "";
  }

  function getDocstatus() {
    return parseInt(el("invoiceDocstatus")?.value || "0", 10);
  }

  function isEditable() {
    return getDocstatus() === 0;
  }

  function parseServerMessages(serverMessages) {
    if (!serverMessages) return "";

    try {
      const decoded = JSON.parse(serverMessages);
      if (!Array.isArray(decoded) || !decoded.length) return "";

      return decoded.map((msg) => {
        try {
          const parsed = JSON.parse(msg);
          return parsed.message || msg;
        } catch (e) {
          return msg;
        }
      }).join("<br>");
    } catch (e) {
      return "";
    }
  }

  function showSuccess(message) {
    if (window.frappe && typeof window.frappe.show_alert === "function") {
      window.frappe.show_alert({ message: message, indicator: "green" });
      return;
    }
    console.log(message);
  }

  function showError(messageHtml) {
    if (window.frappe && typeof window.frappe.msgprint === "function") {
      window.frappe.msgprint(messageHtml);
      return;
    }

    const temp = document.createElement("div");
    temp.innerHTML = messageHtml;
    window.alert(temp.textContent || "There was a problem.");
  }

  async function apiPost(method, args) {
    const body = new URLSearchParams();

    Object.entries(args || {}).forEach(([key, value]) => {
      if (typeof value === "string") {
        body.append(key, value);
      } else {
        body.append(key, JSON.stringify(value));
      }
    });

    const response = await fetch(`/api/method/${method}`, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Frappe-CSRF-Token": getCsrfToken()
      },
      body: body.toString()
    });

    let data = {};
    try {
      data = await response.json();
    } catch (e) {
      throw new Error("Could not read server response.");
    }

    if (!response.ok || data.exc) {
      const serverMessage = parseServerMessages(data._server_messages);
      throw new Error(serverMessage || data.message || "There was a problem with the request.");
    }

    return data;
  }

  function isDetailPage() {
    return !!el("invoiceDetailsForm");
  }

  function closeEmailModal() {
    const modal = el("invoiceEmailModal");
    if (modal) {
      modal.hidden = true;
      modal.style.display = "none";
    }
  }

  function closeStatementModal() {
    const modal = el("invoiceStatementModal");
    if (modal) {
      modal.hidden = true;
      modal.style.display = "none";
    }
  }

  function getInvoiceClientName() {
    return el("invoice_custom_client")?.value || "";
  }

  async function openStatementModal() {
    const client = getInvoiceClientName();

    if (!client) {
      showError("This invoice has no client linked yet.");
      return;
    }

    const statusEl = el("statementStatus");
    const previewBox = el("statementPreview");
    const recipientSelect = el("statementRecipient");
    const senderSelect = el("statementSender");
    const subjectField = el("statementSubject");
    const messageField = el("statementMessage");
    const ccField = el("statementCc");

    if (statusEl) statusEl.textContent = "Loading...";
    if (previewBox) {
      previewBox.hidden = true;
      previewBox.innerHTML = "";
    }
    if (recipientSelect) recipientSelect.innerHTML = '<option value="">Loading...</option>';
    if (subjectField) subjectField.value = "";
    if (messageField) messageField.value = "";
    if (ccField) ccField.value = "";

    const modal = el("invoiceStatementModal");
    if (modal) {
      modal.hidden = false;
      modal.style.display = "flex";
    }

    try {
      const [emailOptionsResult, senderOptionsResult, defaultsResult] = await Promise.all([
        apiPost(SHARED_API + ".get_client_email_options", { client_name: client }),
        apiPost("dashboard.api.shared.email_templates.get_email_sender_options", {}),
        apiPost(SHARED_API + ".get_client_statement_email_defaults", { client_name: client })
      ]);

      const emailOptions = emailOptionsResult.message || emailOptionsResult || [];
      const senderOptions = senderOptionsResult.message || senderOptionsResult || [];
      const defaults = defaultsResult.message || defaultsResult || {};

      if (recipientSelect) {
        recipientSelect.innerHTML = "";

        if (!emailOptions.length) {
          const opt = document.createElement("option");
          opt.value = "";
          opt.textContent = "No email on file";
          recipientSelect.appendChild(opt);
        } else {
          emailOptions.forEach((opt) => {
            const option = document.createElement("option");
            option.value = opt.value;
            option.textContent = opt.label;
            recipientSelect.appendChild(option);
          });
        }
      }

      if (senderSelect) {
        senderSelect.innerHTML = "";
        senderOptions.forEach((opt) => {
          const option = document.createElement("option");
          option.value = opt.value;
          option.textContent = opt.label;
          senderSelect.appendChild(option);
        });
      }

      if (subjectField) subjectField.value = defaults.subject || "";
      if (messageField) messageField.value = defaults.message || "";
      if (statusEl) statusEl.textContent = "";
    } catch (error) {
      if (statusEl) statusEl.textContent = "";
      showError(error.message || "Could not load statement details.");
      closeStatementModal();
    }
  }

  async function previewStatementEmail() {
    const messageField = el("statementMessage");
    const previewBox = el("statementPreview");
    const previewBtn = el("previewStatementEmail");

    if (!messageField || !previewBox) return;

    if (previewBtn) {
      previewBtn.disabled = true;
      previewBtn.textContent = "Loading...";
    }

    try {
      const result = await apiPost("dashboard.api.shared.email_templates.preview_email_html", {
        message: messageField.value
      });

      const data = result.message || result || {};
      previewBox.innerHTML = data.html || "";
      previewBox.hidden = false;
    } catch (error) {
      showError(error.message || "Could not build a preview.");
    } finally {
      if (previewBtn) {
        previewBtn.disabled = false;
        previewBtn.textContent = "Preview";
      }
    }
  }

  async function sendStatementEmail() {
    const client = getInvoiceClientName();
    const recipientSelect = el("statementRecipient");
    const senderSelect = el("statementSender");
    const subjectField = el("statementSubject");
    const messageField = el("statementMessage");
    const ccField = el("statementCc");
    const statusEl = el("statementStatus");
    const sendBtn = el("sendStatementEmail");

    const recipient = recipientSelect ? recipientSelect.value : "";
    const subject = subjectField ? subjectField.value.trim() : "";
    const message = messageField ? messageField.value.trim() : "";

    if (!recipient) {
      showError("Select an email address to send to.");
      return;
    }

    if (sendBtn) {
      sendBtn.disabled = true;
      sendBtn.textContent = "Sending...";
    }

    if (statusEl) statusEl.textContent = "";

    try {
      await apiPost(SHARED_API + ".send_client_email", {
        client_name: client,
        recipient: recipient,
        subject: subject,
        message: message,
        sender: senderSelect ? senderSelect.value : "",
        cc: ccField ? ccField.value.trim() : ""
      });

      showSuccess("Statement sent");
      closeStatementModal();
    } catch (error) {
      showError(error.message || "Could not send the statement.");
    } finally {
      if (sendBtn) {
        sendBtn.disabled = false;
        sendBtn.textContent = "Send Statement";
      }
    }
  }

  async function loadEmailSenderOptions() {
    const select = el("emailSender");
    if (!select) return;

    try {
      const result = await apiPost("dashboard.api.shared.email_templates.get_email_sender_options", {});
      const options = (result.message || result) || [];

      select.innerHTML = "";
      options.forEach((opt) => {
        const option = document.createElement("option");
        option.value = opt.value;
        option.textContent = opt.label;
        select.appendChild(option);
      });
    } catch (error) {
      console.error("Could not load sender options", error);
    }
  }

  async function openEmailModal() {
    if (getDocstatus() !== 1) {
      showError("Only submitted invoices can be emailed.");
      return;
    }

    await forceEmailTemplate();
    await loadEmailSenderOptions();

    const ccField = el("emailCc");
    if (ccField) ccField.value = "";

    const modal = el("invoiceEmailModal");
    if (modal) {
      modal.hidden = false;
      modal.style.display = "flex";
    }
  }

  async function getOptionsForDoctype(doctype) {
    if (!doctype) return [];
    if (optionCache[doctype]) return optionCache[doctype];

    const result = await apiPost(SHARED_API + ".get_link_options", {
      doctype: doctype,
      limit_page_length: 1000
    });

    optionCache[doctype] = result.message || [];
    return optionCache[doctype];
  }

  async function populateSelect(select) {
    if (!select) return;

    const doctype = select.dataset.linkDoctype;
    const currentValue = select.value || select.dataset.currentValue || "";
    const options = await getOptionsForDoctype(doctype);

    select.innerHTML = "";

    const blank = document.createElement("option");
    blank.value = "";
    blank.textContent = "";
    select.appendChild(blank);

    options.forEach((row) => {
      const option = document.createElement("option");
      option.value = row.name;
      option.textContent = row.label || row.name;
      option.dataset.description = row.description || "";
      option.dataset.uom = row.uom || "";
      if (row.name === currentValue) option.selected = true;
      select.appendChild(option);
    });

    if (currentValue && !options.some((row) => row.name === currentValue)) {
      const fallback = document.createElement("option");
      fallback.value = currentValue;
      fallback.textContent = currentValue;
      fallback.selected = true;
      select.appendChild(fallback);
    }

    select.dataset.currentValue = currentValue;
  }

  async function loadAllLinkOptions() {
    const selects = qsa("select[data-link-doctype]");

    for (const select of selects) {
      if (select.id === "invoice_customer") continue;
      await populateSelect(select);
    }
  }

  function setSingleCustomerOption(customerName, label) {
    const customerField = el("invoice_customer");
    if (!customerField) return;

    customerField.innerHTML = "";

    const blank = document.createElement("option");
    blank.value = "";
    blank.textContent = "";
    customerField.appendChild(blank);

    if (customerName) {
      const option = document.createElement("option");
      option.value = customerName;
      option.textContent = label || customerName;
      option.selected = true;
      customerField.appendChild(option);

      customerField.value = customerName;
      customerField.dataset.currentValue = customerName;
    } else {
      customerField.value = "";
      customerField.dataset.currentValue = "";
    }
  }

  async function restrictCustomerToClientBillingContact() {
    const clientName = el("invoice_custom_client")?.value || "";

    if (!clientName) {
      currentClientDefaults = null;
      setSingleCustomerOption("", "");
      clearResolvedFields();
      renderOpenPackageWarning([]);
      removeTravelRow();
      return null;
    }

    try {
      const result = await apiPost(SHARED_API + ".get_client_invoice_defaults", {
        client_name: clientName
      });

      const data = result.message || {};
      currentClientDefaults = data;

      setSingleCustomerOption(
        data.billing_contact || "",
        data.billing_contact_label || data.billing_contact || ""
      );

      updateReadOnlyText("invoice_price_list", data.price_list || "");
      updateReadOnlyText("invoice_company", data.company || "");
      updateReadOnlyText("invoice_coach_label", data.coach_label || "");
      updateReadOnlyText("invoice_contact_email", data.contact_email || "");

      const storedBankField = el("invoice_stored_bank_account");
      const storedBankAccount = storedBankField ? storedBankField.value : "";

      if (storedBankAccount) {
        // Only applies once, to seed the previously-saved override on initial
        // page load - once consumed, later client changes fall back to that
        // (possibly different) client's own default instead of reapplying it.
        data.bank_account = storedBankAccount;
        storedBankField.value = "";
      }

      updateBankAccountField(data);
      updateFieldValue("invoice_contact_email_hidden", data.contact_email || "");

      const emailRecipient = el("emailRecipient");
      if (emailRecipient) emailRecipient.value = data.contact_email || "";

      renderOpenPackageWarning(data.open_balances || []);
      await updateTravelRow();

      return data;
    } catch (error) {
      console.error("Could not load client invoice defaults", error);
      showError(error.message || "Could not load the client's billing defaults.");
      return null;
    }
  }

  function renderOpenPackageWarning(rows) {
    const box = el("openPackageWarning");
    if (!box) return;

    if (!rows || !rows.length) {
      box.hidden = true;
      box.innerHTML = "";
      return;
    }

    let html = `
      <strong>This client still has available package sessions.</strong><br>
      Please review before creating a new invoice.
      <table style="width:100%;margin-top:10px;font-size:13px;">
        <thead>
          <tr>
            <th style="text-align:left;">Service Item</th>
            <th style="text-align:left;">Available</th>
            <th style="text-align:left;">Invoice</th>
            <th style="text-align:left;">Balance</th>
          </tr>
        </thead>
        <tbody>
    `;

    rows.forEach((row) => {
      html += `
        <tr>
          <td>${row.service_item || ""}</td>
          <td>${row.qty_available || 0}</td>
          <td>${row.sales_invoice || ""}</td>
          <td>${row.name || ""}</td>
        </tr>
      `;
    });

    html += `</tbody></table>`;

    box.innerHTML = html;
    box.hidden = false;
  }

  function syncDateDisplay(field, showAsText) {
    if (field.type !== "date") return;

    const display = el(`${field.id}_display`);
    if (!display) return;

    if (showAsText) {
      display.textContent = formatDisplayDate(field.value) || "—";
      display.style.display = "";
      field.style.display = "none";
    } else {
      display.style.display = "none";
      field.style.display = "";
    }
  }

  function setFieldState(field) {
    const metaReadonly = String(field.dataset.metaReadonly || "0") === "1";
    const tag = (field.tagName || "").toUpperCase();

    if (metaReadonly || !isEditable()) {
      if (tag === "SELECT") field.disabled = true;
      else field.readOnly = true;
      syncDateDisplay(field, true);
      return;
    }

    if (tag === "SELECT") field.disabled = false;
    else field.readOnly = false;
    syncDateDisplay(field, false);
  }

  function updateStatusBadge(statusText) {
    const badge = el("invoiceStatusBadge");
    if (!badge) return;

    badge.textContent = statusText || "Draft";
    badge.className = "dashboard-badge";

    if (statusText === "Paid") {
      badge.classList.add("dashboard-status-active");
    } else if (statusText === "Draft" || statusText === "Partly Paid") {
      badge.classList.add("dashboard-status-onhold");
    } else {
      badge.classList.add("dashboard-status-archived");
    }
  }

  function updateActionState() {
    const editable = isEditable();
    const submitted = getDocstatus() === 1;
    const cancelled = getDocstatus() === 2;
    const hasName = !!(el("invoiceDocname")?.value || "");

    qsa("[data-invoice-field='1']").forEach((field) => setFieldState(field));

    qsa(".invoice-item-remove").forEach((button) => {
      button.disabled = !editable;
      button.style.display = editable ? "" : "none";
    });

    const addRow = el("addInvoiceItem");
    if (addRow) {
      addRow.disabled = !editable;
      addRow.style.display = editable ? "" : "none";
    }

    const saveBtn = el("saveInvoiceDraft");
    if (saveBtn) {
      saveBtn.disabled = isSaving || !editable;
      saveBtn.style.display = editable ? "" : "none";
      saveBtn.textContent = isSaving ? "Saving..." : "Save Draft";
    }

    const submitBtn = el("submitInvoice");
    if (submitBtn) {
      submitBtn.disabled = isSaving || !editable;
      submitBtn.style.display = editable ? "" : "none";
    }

    const emailBtn = el("openEmailInvoice");
    if (emailBtn) {
      emailBtn.style.display = submitted && hasName ? "" : "none";
    }
    
    const paymentBtn = el("openAllocatePayment");
    if (paymentBtn) {
      const outstanding = parseMoneyValue(el("invoice_outstanding_amount")?.value || "0");
      paymentBtn.style.display = submitted && hasName && outstanding > 0 ? "" : "none";
    }
    
    if (!submitted || cancelled) {
      closeEmailModal();
      closePaymentModal();
    }

    document.body.classList.toggle("dashboard-detail-edit-mode", editable);
  }

  function money(value) {
    const num = Number(value || 0);
    return num.toFixed(2);
  }

  function updateFieldValue(id, value) {
    const field = el(id);
    if (!field) return;

    field.value = value == null ? "" : value;

    if ((field.tagName || "").toUpperCase() === "SELECT") {
      field.dataset.currentValue = field.value || "";
    }
  }

  function updateReadOnlyText(id, value) {
    const field = el(id);
    if (!field) return;
    field.value = value == null ? "" : value;
  }

  function populateBankAccountOptions(select, options, value) {
    select.innerHTML = "";

    (options || []).forEach((row) => {
      const option = document.createElement("option");
      option.value = row.value;
      option.textContent = row.label || row.value;
      option.dataset.displayText = row.display_text || "";
      option.dataset.company = row.company || "";
      if (row.value === value) option.selected = true;
      select.appendChild(option);
    });

    if (value && !(options || []).some((row) => row.value === value)) {
      const fallback = document.createElement("option");
      fallback.value = value;
      fallback.textContent = value;
      fallback.selected = true;
      select.appendChild(fallback);
    }

    select.value = value || select.value;
  }

  function updateBankAccountField(data) {
    const field = el("invoice_bank_account_field");
    const select = el("invoice_bank_account_select");
    const allowOverride = !!(data && data.allow_bank_override);

    if (field) field.style.display = allowOverride ? "" : "none";

    if (select) {
      if (allowOverride) {
        populateBankAccountOptions(select, data.bank_account_options || [], data.bank_account || "");
        select.dataset.clientDefault = data.client_bank_account || data.bank_account || "";
        select.dataset.alwaysConfirm = data.always_confirm_bank_account ? "1" : "";
      } else {
        select.innerHTML = "";
        select.dataset.clientDefault = "";
        select.dataset.alwaysConfirm = "";
      }
    }

    updateReadOnlyText("invoice_bank_display", data?.bank_display_text || "");
  }

  function confirmBankAccountOverrideIfNeeded() {
    const field = el("invoice_bank_account_field");
    const select = el("invoice_bank_account_select");

    if (!field || field.style.display === "none" || !select) return true;

    const selectedValue = select.value || "";
    const defaultValue = select.dataset.clientDefault || "";
    const alwaysConfirm = select.dataset.alwaysConfirm === "1";

    if (!selectedValue) return true;

    const option = select.options[select.selectedIndex];
    const label = (option && option.textContent ? option.textContent.trim() : "") || selectedValue;

    // Interbusiness invoices (coach-to-coach, or to HQ) always get a
    // confirmation on which bank account receives the payment - even when
    // it's the account already selected by default (e.g. HQ's own
    // account), since this is still money moving between businesses.
    if (alwaysConfirm) {
      return window.confirm(
        `This invoice will pay into ${label}'s bank account. ` +
        `Any payment received against it will be recorded against ${label}'s account. Continue?`
      );
    }

    if (selectedValue === defaultValue) return true;

    return window.confirm(
      `You have selected ${label}'s bank account for this invoice instead of the client's usual account. ` +
      `Any payment received against this invoice will be recorded against ${label}'s account. Continue?`
    );
  }

  function updateInvoiceBackButton(clientName) {
    const button = el("invoiceBackButton");
    if (!button) return;

    if (clientName) {
      button.href = getDashboardBasePath() + "/client_details?name=" + encodeURIComponent(clientName);
      button.textContent = "Back to Client";
    } else {
      button.href = getDashboardBasePath() + "/invoices";
      button.textContent = "Back to Invoices";
    }

    updateFieldValue("invoiceReturnClient", clientName || "");
  }

  function clearResolvedFields() {
    updateReadOnlyText("invoice_company", "");
    updateReadOnlyText("invoice_price_list", "");
    updateReadOnlyText("invoice_coach_label", "");
    updateReadOnlyText("invoice_contact_email", "");
    updateBankAccountField(null);
    updateFieldValue("invoice_contact_email_hidden", "");
    updateInvoiceBackButton("");
  }

  function applyContextToPage(context) {
    if (!context) return;

    updateInvoiceBackButton(context.client_name || el("invoice_custom_client")?.value || "");

    updateReadOnlyText("invoice_company", context.company || "");
    updateReadOnlyText("invoice_price_list", context.price_list || "");
    updateReadOnlyText("invoice_coach_label", context.coach_label || "");
    updateReadOnlyText("invoice_contact_email", context.contact_email || "");
    updateBankAccountField(context);
    updateFieldValue("invoice_contact_email_hidden", context.contact_email || "");

    const emailRecipient = el("emailRecipient");
    if (emailRecipient) emailRecipient.value = context.contact_email || "";
  }

  async function refreshInvoiceContext() {
    const clientName = el("invoice_custom_client")?.value || "";
    const customerName = el("invoice_customer")?.value || "";
    const invoiceName = el("invoiceDocname")?.value || "";

    if (!clientName && !invoiceName) {
      clearResolvedFields();
      return null;
    }

    try {
      const result = await apiPost(SHARED_API + ".resolve_invoice_context", {
        client_name: clientName,
        customer_name: customerName
      });

      const context = result.message || result;
      applyContextToPage(context);
      return context;
    } catch (error) {
      // Never let this take down the rest of init() (button/change-event
      // bindings still need to run even if this particular refresh fails).
      console.error("Could not resolve invoice context", error);
      return null;
    }
  }

  async function refreshItemRowDefaults(row, options) {
    const itemCode = row.querySelector("[data-item-field='item_code']")?.value || "";

    if (!itemCode) {
      row.dataset.bundleSessionCount = "0";
      recalcItemRow(row);
      await updateTravelRow();
      return;
    }

    const result = await apiPost(SHARED_API + ".get_item_details_for_invoice", {
      item_code: itemCode,
      company: el("invoice_company")?.value || "",
      customer: el("invoice_customer")?.value || "",
      price_list: el("invoice_price_list")?.value || ""
    });

    const details = result.message || result;
    const descriptionField = row.querySelector("[data-item-field='description']");
    const rateField = row.querySelector("[data-item-field='rate']");

    if (descriptionField) {
      if (!(options && options.preserveDescription) || !descriptionField.value.trim()) {
        descriptionField.value = details.description || "";
      }
    }

    if (rateField && !(options && options.preserveRate)) {
      rateField.value = details.rate != null ? details.rate : 0;
    }

    row.dataset.bundleSessionCount = String(details.bundle_session_count || 0);

    recalcTotals();
    await updateTravelRow();
  }

  async function refreshAllItemRates() {
    const rows = qsa("#invoiceItemsBody tr");

    for (const row of rows) {
      await refreshItemRowDefaults(row, { preserveDescription: true });
    }
  }

  function recalcItemRow(row) {
    const qty = Number(row.querySelector("[data-item-field='qty']")?.value || 0);
    const rate = Number(row.querySelector("[data-item-field='rate']")?.value || 0);
    const amountField = row.querySelector("[data-item-field='amount']");
    const amount = qty * rate;

    if (amountField) amountField.value = money(amount);
  }

  function recalcTotals() {
    let total = 0;

    qsa("#invoiceItemsBody tr").forEach((row) => {
      recalcItemRow(row);
      total += Number(row.querySelector("[data-item-field='amount']")?.value || 0);
    });

    const grandTotal = el("invoice_grand_total");
    if (grandTotal && isEditable()) grandTotal.value = money(total);
  }

  function getItemRows() {
    return qsa("#invoiceItemsBody tr");
  }

  function getTravelRow() {
    return getItemRows().find((row) => {
      return row.querySelector("[data-item-field='item_code']")?.value === TRAVEL_ITEM_CODE;
    });
  }

  function removeTravelRow() {
    const row = getTravelRow();
    if (row) {
      row.remove();
      recalcTotals();
      updateActionState();
    }
  }

  function getBillableSessionCount() {
    let total = 0;

    getItemRows().forEach((row) => {
      const itemCode = row.querySelector("[data-item-field='item_code']")?.value || "";
      const qty = Number(row.querySelector("[data-item-field='qty']")?.value || 0);

      if (!itemCode) return;
      if (itemCode === TRAVEL_ITEM_CODE) return;

      const sessionsPerItem = Number(row.dataset.bundleSessionCount || 0);
      total += sessionsPerItem * qty;
    });

    return total;
  }

  async function updateTravelRow() {
    if (!isEditable()) return;
    if (!currentClientDefaults) return;

    const travelCharged = Number(currentClientDefaults.travel_charged || 0);
    const ratePerSession = Number(currentClientDefaults.travel_charge_per_session || 0);

    if (!travelCharged || !ratePerSession) {
      // Not a standing charge for this client (box unticked, or no rate set
      // yet) - leave the invoice alone. A travel line added manually here
      // must not be touched.
      return;
    }

    const totalSessions = getBillableSessionCount();

    if (!totalSessions || totalSessions <= 0) {
      removeTravelRow();
      return;
    }

    const description =
      "Travel charge for " +
      totalSessions +
      " session" +
      (totalSessions === 1 ? "" : "s") +
      " at this client's agreed rate of £" +
      ratePerSession +
      " per session. (Travel is charged at £" +
      TRAVEL_RATE_PER_MILE +
      " per mile, with the first " +
      FREE_MILES_ONE_WAY +
      " miles each way free.)";

    let travelRow = getTravelRow();

    if (!travelRow) {
      await addItemRow({
        item_code: TRAVEL_ITEM_CODE,
        description: description,
        qty: totalSessions,
        rate: ratePerSession,
        amount: totalSessions * ratePerSession
      });
      return;
    }

    const descriptionField = travelRow.querySelector("[data-item-field='description']");
    const qtyField = travelRow.querySelector("[data-item-field='qty']");
    const rateField = travelRow.querySelector("[data-item-field='rate']");

    if (descriptionField) descriptionField.value = description;
    if (qtyField) qtyField.value = totalSessions;
    if (rateField) rateField.value = ratePerSession;

    recalcTotals();
  }

  async function addItemRow(data, rowOptions) {
    const body = el("invoiceItemsBody");
    if (!body) return;

    const row = document.createElement("tr");

    row.innerHTML = `
      <td>
        <select
          class="dashboard-select"
          data-item-field="item_code"
          data-link-doctype="Item"
          data-current-value="${(data?.item_code || "").replace(/"/g, "&quot;")}"
          data-invoice-field="1"
        >
          <option value=""></option>
        </select>
      </td>
      <td>
        <textarea class="dashboard-textarea" data-item-field="description" rows="2">${data?.description || ""}</textarea>
      </td>
      <td>
        <input type="number" step="0.01" class="dashboard-input" data-item-field="qty" value="${data?.qty || 1}">
      </td>
      <td>
        <input type="number" step="0.01" class="dashboard-input" data-item-field="rate" value="${data?.rate || 0}">
      </td>
      <td>
        <input type="text" class="dashboard-input" data-item-field="amount" value="${money(data?.amount || 0)}" readonly>
      </td>
      <td class="dashboard-text-right">
        <button type="button" class="dashboard-btn dashboard-btn-light invoice-item-remove">Remove</button>
      </td>
    `;

    body.appendChild(row);

    const itemSelect = row.querySelector("[data-item-field='item_code']");
    await populateSelect(itemSelect);

    itemSelect.addEventListener("change", async function () {
      await refreshItemRowDefaults(row, { preserveDescription: false });
    });

    row.querySelector("[data-item-field='qty']").addEventListener("input", async function () {
      recalcTotals();
      await updateTravelRow();
    });

    row.querySelector("[data-item-field='rate']").addEventListener("input", function () {
      recalcTotals();
    });

    row.querySelector(".invoice-item-remove").addEventListener("click", async function () {
      if (!isEditable()) return;
      row.remove();
      recalcTotals();
      await updateTravelRow();
      updateActionState();
    });

    qsa("textarea, input, select", row).forEach((field) => {
      if (field.dataset.itemField === "amount") return;
      setFieldState(field);
    });

    if (data?.item_code) {
      await refreshItemRowDefaults(row, {
        preserveDescription: !!data?.description,
        preserveRate: !!(rowOptions && rowOptions.preserveExistingRate)
      });
    } else {
      recalcTotals();
    }

    updateActionState();
  }

  function collectInvoiceData() {
    return {
      customer: el("invoice_customer")?.value || "",
      custom_client: el("invoice_custom_client")?.value || "",
      posting_date: el("invoice_posting_date")?.value || "",
      due_date: el("invoice_due_date")?.value || "",
      bank_account: el("invoice_bank_account_select")?.value || "",
      items: qsa("#invoiceItemsBody tr").map((row) => ({
        item_code: row.querySelector("[data-item-field='item_code']")?.value || "",
        description: row.querySelector("[data-item-field='description']")?.value || "",
        qty: row.querySelector("[data-item-field='qty']")?.value || 0,
        rate: row.querySelector("[data-item-field='rate']")?.value || 0,
        amount: row.querySelector("[data-item-field='amount']")?.value || 0
      }))
    };
  }

  function selectedCustomerText() {
    const field = el("invoice_customer");
    if (!field) return "";
    const option = field.options[field.selectedIndex];
    return (option && option.textContent ? option.textContent : "").trim();
  }

  function localDefaultEmailTemplate() {
    const customerName = selectedCustomerText() || el("invoice_customer")?.value || "Billing Contact";
    const invoiceNumber = el("invoice_name")?.value || "";
    const amountDue = el("invoice_outstanding_amount")?.value || "0.00";
    const dueDate = formatDisplayDate(el("invoice_due_date")?.value || "");
    const bankDetails = (el("invoice_bank_display")?.value || "Bank details available on request.").trim();
    const coachName = el("invoice_coach_label")?.value || "Coach";
    const companyLabel = el("invoice_company")?.value || "The Resilient Kid";
    const coachEmail = el("emailReplyTo")?.value || "";
    const coachPhone = el("coachPhoneValue")?.value || "";

    const messageLines = [
      `Hi ${customerName},`,
      "",
      "I hope you’re doing well.",
      "",
      "Please find attached your invoice.",
      "",
      `Invoice number: ${invoiceNumber}`,
      `Amount due: £${amountDue}`,
      `Payment due by: ${dueDate}`,
      "",
      "Payment details:",
      bankDetails,
      "",
      "Warm regards,",
      coachName,
      companyLabel
    ];

    if (coachEmail) messageLines.push("", coachEmail);
    if (coachPhone) messageLines.push(coachPhone);

    return { subject: `Invoice ${invoiceNumber}`, message: messageLines.join("\n") };
  }

  // Pulls the default subject/message from the "Invoice Email" Email
  // Template (desk -> Email Template) when the invoice is already saved,
  // so editing that template changes what pre-fills here. Falls back to
  // the local, DOM-only defaults for a new/unsaved invoice or if that
  // call fails, so the compose modal always has something sensible in it.
  async function forceEmailTemplate() {
    const subjectField = el("emailSubject");
    const messageField = el("emailMessage");
    const docname = el("invoiceDocname")?.value || "";

    const local = localDefaultEmailTemplate();
    if (subjectField) subjectField.value = local.subject;
    if (messageField) messageField.value = local.message;

    if (!docname) return;

    try {
      const result = await apiPost(SHARED_API + ".get_invoice_email_defaults", { docname: docname });
      const defaults = result.message || result;

      if (defaults && defaults.subject && subjectField) subjectField.value = defaults.subject;
      if (defaults && defaults.message && messageField) messageField.value = defaults.message;
    } catch (error) {
      // Local defaults above already stand - a broken template render
      // must never leave the compose modal empty.
    }
  }

  function closePaymentModal() {
    const modal = el("invoicePaymentModal");

    if (modal) {
      modal.hidden = true;
      modal.style.display = "none";
    }
  }

  function closeIncomeOwnerModal() {
    const modal = el("invoiceIncomeOwnerModal");

    if (modal) {
      modal.hidden = true;
      modal.style.display = "none";
    }
  }

  // Franchise-type clients (see always_confirm_bank_account) represent
  // another coach or HQ - an interbusiness invoice, where "who does this
  // money belong to" has to be picked deliberately every time rather than
  // silently defaulting to whichever bank account the client record
  // happens to carry (almost always HQ's own). Coaches kept leaving the
  // default bank account/company in place - a native window.confirm() at
  // save time (see confirmBankAccountOverrideIfNeeded()) wasn't enough of
  // a speed bump, since the default was already sitting there selected
  // and "OK" is easy to click without reading it. This opens the moment a
  // Franchise client is picked, before anything else about the invoice
  // can be filled in, and forces one explicit named choice.
  function openIncomeOwnerModal(context) {
    const modal = el("invoiceIncomeOwnerModal");
    const choicesBox = el("incomeOwnerChoices");
    const messageField = el("incomeOwnerModalMessage");
    const bankSelect = el("invoice_bank_account_select");

    if (!modal || !choicesBox || !bankSelect) return;

    const options = context.bank_account_options || [];
    if (!options.length) return;

    const clientLabel = context.client_label || "this client";

    if (messageField) {
      messageField.textContent =
        `You are about to invoice ${clientLabel}. This is money moving between businesses, so pick whose invoice ` +
        `this actually is - it decides which bank account gets paid and which company appears on it.`;
    }

    choicesBox.innerHTML = "";

    options.forEach((option) => {
      const isDefault = option.value === (context.bank_account || context.client_bank_account || "");

      const heading = isDefault
        ? `${option.label || "HQ"} (this client's default)`
        : option.is_self
        ? `${option.label} (you)`
        : option.label;

      const subtext = isDefault
        ? "This invoice's income belongs to HQ, not any individual coach."
        : option.is_self
        ? "This invoice's income belongs to you - it'll show on your own dashboard and pay into your own account."
        : `This invoice's income belongs to ${option.label}, not HQ.`;

      const button = document.createElement("button");
      button.type = "button";
      button.className = "invoice-income-owner-choice";
      button.dataset.bankAccount = option.value;

      const strong = document.createElement("strong");
      strong.textContent = `Invoice as ${heading}`;
      const span = document.createElement("span");
      span.textContent = subtext;

      button.appendChild(strong);
      button.appendChild(span);

      button.addEventListener("click", function () {
        bankSelect.value = option.value;
        bankSelect.dispatchEvent(new Event("change"));
        closeIncomeOwnerModal();
      });

      choicesBox.appendChild(button);
    });

    modal.hidden = false;
    modal.style.display = "flex";
  }

  function parseMoneyValue(value) {
    return Number(String(value || "0").replace(/[£,]/g, "") || 0);
  }
  
  async function openPaymentModal() {
    const docname = el("invoiceDocname")?.value || "";
  
    if (!docname) {
      showError("Please save and submit the invoice first.");
      return;
    }
  
    const amountField = el("paymentAmount");
    if (amountField) {
      amountField.value = parseMoneyValue(el("invoice_outstanding_amount")?.value || "0").toFixed(2);
    }
  
    const referenceField = el("paymentReference");
    if (referenceField && !referenceField.value) {
      referenceField.value = docname;
    }
  
    const modal = el("invoicePaymentModal");
  
    if (modal) {
      modal.hidden = false;
      modal.style.display = "flex";
    }
  }
  async function allocatePayment() {
    const docname = el("invoiceDocname")?.value || "";
  
    if (!docname) {
      showError("Invoice is required.");
      return;
    }
  
    const button = el("submitAllocatePayment");
  
    if (button) {
      button.disabled = true;
      button.textContent = "Allocating...";
    }
  
    try {
      const result = await apiPost(SHARED_API + ".allocate_invoice_payment", {
        invoice_name: docname,
        posting_date: el("paymentPostingDate")?.value || "",
        amount: el("paymentAmount")?.value || "",
        reference_no: el("paymentReference")?.value || ""
      });
  
      const data = result.message || {};
  
      updateReadOnlyText("invoice_paid_amount", money(data.paid_amount || 0));
      updateReadOnlyText("invoice_outstanding_amount", money(data.outstanding_amount || 0));
      updateFieldValue("invoice_status", data.status || "");
      updateStatusBadge(data.status || "");
  
      closePaymentModal();
      updateActionState();
      showSuccess("Payment allocated");
    } catch (error) {
      showError(error.message || "Could not allocate payment.");
    } finally {
      if (button) {
        button.disabled = false;
        button.textContent = "Allocate Payment";
      }
    }
  }

  function applyInvoiceResponse(payload) {
    if (!payload) return;

    if (payload.name) {
      updateFieldValue("invoiceDocname", payload.name);
      updateReadOnlyText("invoice_name", payload.name);

      const title = el("invoicePageTitle");
      if (title) title.textContent = payload.name;

      const returnClient = payload.custom_client || el("invoiceReturnClient")?.value || "";
      const clientQuery = returnClient ? "&client=" + encodeURIComponent(returnClient) : "";

      window.history.replaceState(
        {},
        "",
        `${getDashboardBasePath()}/invoice_details?name=${encodeURIComponent(payload.name)}${clientQuery}`
      );
    }

    updateFieldValue("invoiceDocstatus", payload.docstatus);
    updateReadOnlyText("invoice_posting_date", payload.posting_date);
    updateReadOnlyText("invoice_due_date", payload.due_date);
    updateReadOnlyText("invoice_naming_series", payload.naming_series || "");
    updateReadOnlyText("invoice_grand_total", money(payload.grand_total));
    updateReadOnlyText("invoice_outstanding_amount", money(payload.outstanding_amount));
    updateReadOnlyText("invoice_paid_amount", money(payload.paid_amount));
    updateFieldValue("invoice_status", payload.status);
    updateStatusBadge(payload.status || "Draft");

    updateFieldValue("invoice_customer", payload.customer || "");
    updateFieldValue("invoice_custom_client", payload.custom_client || "");
    updateInvoiceBackButton(payload.custom_client || "");

    applyContextToPage({
      client_name: payload.custom_client || "",
      company: payload.company,
      price_list: payload.price_list,
      coach_label: payload.coach_label,
      contact_email: payload.contact_email,
      bank_account: payload.bank_account,
      client_bank_account: payload.client_bank_account,
      bank_display_text: payload.bank_display_text,
      allow_bank_override: payload.allow_bank_override,
      bank_account_options: payload.bank_account_options,
      always_confirm_bank_account: payload.always_confirm_bank_account
    });

    forceEmailTemplate();
    updateActionState();
  }

  async function saveDraft() {
    if (isSaving || !isEditable()) return;
    if (!confirmBankAccountOverrideIfNeeded()) return;

    isSaving = true;
    updateActionState();

    try {
      await updateTravelRow();

      const result = await apiPost(SHARED_API + ".save_draft_invoice", {
        docname: el("invoiceDocname")?.value || "",
        data: JSON.stringify(collectInvoiceData())
      });

      applyInvoiceResponse(result.message || result);
      showSuccess("Invoice draft saved");
    } catch (error) {
      showError(error.message || "Could not save invoice draft.");
    } finally {
      isSaving = false;
      updateActionState();
    }
  }

  async function submitInvoice() {
    if (isSaving || !isEditable()) return;
    if (!confirmBankAccountOverrideIfNeeded()) return;

    const confirmed = window.confirm(
      "Once submitted, this invoice can no longer be edited by coaches. Do you want to submit it now?"
    );

    if (!confirmed) return;

    isSaving = true;
    updateActionState();

    try {
      await updateTravelRow();

      const result = await apiPost(SHARED_API + ".submit_invoice", {
        docname: el("invoiceDocname")?.value || "",
        data: JSON.stringify(collectInvoiceData())
      });

      applyInvoiceResponse(result.message || result);
      closeEmailModal();
      showSuccess("Invoice submitted");
    } catch (error) {
      showError(error.message || "Could not submit invoice.");
    } finally {
      isSaving = false;
      updateActionState();
    }
  }

  async function sendEmail() {
    const docname = el("invoiceDocname")?.value || "";

    if (!docname) {
      showError("Please save the invoice first.");
      return;
    }

    if (getDocstatus() !== 1) {
      showError("Only submitted invoices can be emailed.");
      return;
    }

    const sendBtn = el("sendInvoiceEmail");
    if (sendBtn) {
      sendBtn.disabled = true;
      sendBtn.textContent = "Sending...";
    }

    try {
      await apiPost(SHARED_API + ".send_invoice_email", {
        docname: docname,
        recipient: el("emailRecipient")?.value || "",
        reply_to: el("emailReplyTo")?.value || "",
        subject: el("emailSubject")?.value || "",
        message: el("emailMessage")?.value || "",
        sender: el("emailSender")?.value || "",
        cc: el("emailCc")?.value || ""
      });

      closeEmailModal();
      showSuccess("Invoice email sent");
    } catch (error) {
      showError(error.message || "Could not send invoice email.");
    } finally {
      if (sendBtn) {
        sendBtn.disabled = false;
        sendBtn.textContent = "Send Email";
      }
    }
  }

  async function initPartyWatchers() {
    const customerField = el("invoice_customer");
    const clientField = el("invoice_custom_client");

    async function handleClientChange() {
      await restrictCustomerToClientBillingContact();
      const context = await refreshInvoiceContext();
      await refreshAllItemRates();
      await updateTravelRow();
      forceEmailTemplate();

      if (context && context.always_confirm_bank_account) {
        openIncomeOwnerModal(context);
      }
    }

    async function handleCustomerChange() {
      await refreshInvoiceContext();
      await refreshAllItemRates();
      forceEmailTemplate();
    }

    if (customerField) customerField.addEventListener("change", handleCustomerChange);
    if (clientField) clientField.addEventListener("change", handleClientChange);
  }

  async function init() {
  if (!isDetailPage()) return;

  closeEmailModal();
  closeStatementModal();
  closePaymentModal();
  closeIncomeOwnerModal();

  el("closeInvoiceIncomeOwnerModal")?.addEventListener("click", function (event) {
    event.preventDefault();

    const clientField = el("invoice_custom_client");
    if (clientField) {
      clientField.value = "";
      clientField.dispatchEvent(new Event("change"));
    }

    closeIncomeOwnerModal();
  });

  el("openAllocatePayment")?.addEventListener("click", function (event) {
    event.preventDefault();
    openPaymentModal();
  });

  el("closeAllocatePayment")?.addEventListener("click", function (event) {
    event.preventDefault();
    closePaymentModal();
  });

  el("submitAllocatePayment")?.addEventListener("click", function (event) {
    event.preventDefault();
    allocatePayment();
  });

  el("openEmailInvoice")?.addEventListener("click", function (event) {
    event.preventDefault();
    openEmailModal();
  });

  el("closeInvoiceEmailModal")?.addEventListener("click", function (event) {
    event.preventDefault();
    closeEmailModal();
  });

  el("sendInvoiceEmail")?.addEventListener("click", function (event) {
    event.preventDefault();
    sendEmail();
  });

  el("openStatementModal")?.addEventListener("click", function (event) {
    event.preventDefault();
    openStatementModal();
  });

  el("closeInvoiceStatementModal")?.addEventListener("click", function (event) {
    event.preventDefault();
    closeStatementModal();
  });

  el("previewStatementEmail")?.addEventListener("click", function (event) {
    event.preventDefault();
    previewStatementEmail();
  });

  el("sendStatementEmail")?.addEventListener("click", function (event) {
    event.preventDefault();
    sendStatementEmail();
  });

  el("saveInvoiceDraft")?.addEventListener("click", function (event) {
    event.preventDefault();
    saveDraft();
  });

  el("submitInvoice")?.addEventListener("click", function (event) {
    event.preventDefault();
    submitInvoice();
  });

  el("addInvoiceItem")?.addEventListener("click", async function () {
    await addItemRow({ qty: 1, rate: 0, amount: 0 });
    await updateTravelRow();
  });

  el("invoice_bank_account_select")?.addEventListener("change", function () {
    const option = this.options[this.selectedIndex];
    updateReadOnlyText("invoice_bank_display", (option && option.dataset.displayText) || "");

    // The Company field only used to update after the invoice was saved
    // and the server recomputed it - picking a different coach's bank
    // account here now shows that coach's own company immediately,
    // instead of leaving the previous (often HQ's) company showing until
    // save.
    const company = option && option.dataset.company;
    if (company) updateReadOnlyText("invoice_company", company);
  });

  await loadAllLinkOptions();

  const existingRows = JSON.parse(el("invoiceInitialItems")?.textContent || "[]");
  const body = el("invoiceItemsBody");
  if (body) body.innerHTML = "";

  if (existingRows.length) {
    for (const row of existingRows) {
      // These rows come from a saved invoice - the rate may have been
      // typed in by hand (e.g. a negotiated Franchise Fee amount with no
      // matching Item Price) rather than looked up from the current price
      // list, so it must survive exactly as saved instead of being
      // silently refetched and overwritten (often with 0, if nothing
      // matches the current price list).
      await addItemRow(row, { preserveExistingRate: true });
    }
  } else {
    await addItemRow({ qty: 1, rate: 0, amount: 0 });
  }

  // refreshInvoiceContext() always recomputes bank details from the
  // client's own default, so it must run before
  // restrictCustomerToClientBillingContact() - otherwise it would clobber
  // the one-time seeding of a previously-saved bank account override.
  await refreshInvoiceContext();
  await restrictCustomerToClientBillingContact();
  await updateTravelRow();

  updateStatusBadge(el("invoice_status")?.value || "Draft");
  recalcTotals();
  forceEmailTemplate();
  updateActionState();
  await initPartyWatchers();

  if (new URLSearchParams(window.location.search).get("payment") === "1") {
    openPaymentModal();
  }

  if (new URLSearchParams(window.location.search).get("email") === "1") {
    await openEmailModal();
  }

  if (new URLSearchParams(window.location.search).get("statement") === "1") {
    await openStatementModal();
  }
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
})();
