(function () {
  const optionCache = {};
  let isSaving = false;
  let currentClientDefaults = null;

  const SHARED_API = "dashboard.api.shared.invoices";

  const TRAVEL_ITEM_CODE = "TRA002";
  const PARENT_CHECKIN_ITEM_CODE = "PAR001";
  const FREE_MILES_ONE_WAY = 10;
  const TRAVEL_RATE_PER_MILE = 0.45;

  function el(id) {
    return document.getElementById(id);
  }

  function qsa(selector, root) {
    return Array.from((root || document).querySelectorAll(selector));
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

  function openEmailModal() {
    if (getDocstatus() !== 1) {
      showError("Only submitted invoices can be emailed.");
      return;
    }

    forceEmailTemplate();

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
      updateReadOnlyText("invoice_bank_display", data.bank_display_text || "");
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

  function setFieldState(field) {
    const metaReadonly = String(field.dataset.metaReadonly || "0") === "1";
    const tag = (field.tagName || "").toUpperCase();

    if (metaReadonly || !isEditable()) {
      if (tag === "SELECT") field.disabled = true;
      else field.readOnly = true;
      return;
    }

    if (tag === "SELECT") field.disabled = false;
    else field.readOnly = false;
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

  function clearResolvedFields() {
    updateReadOnlyText("invoice_company", "");
    updateReadOnlyText("invoice_price_list", "");
    updateReadOnlyText("invoice_coach_label", "");
    updateReadOnlyText("invoice_contact_email", "");
    updateReadOnlyText("invoice_bank_display", "");
    updateFieldValue("invoice_contact_email_hidden", "");
  }

  function applyContextToPage(context) {
    if (!context) return;

    updateReadOnlyText("invoice_company", context.company || "");
    updateReadOnlyText("invoice_price_list", context.price_list || "");
    updateReadOnlyText("invoice_coach_label", context.coach_label || "");
    updateReadOnlyText("invoice_contact_email", context.contact_email || "");
    updateReadOnlyText("invoice_bank_display", context.bank_display_text || "");
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

    const result = await apiPost(SHARED_API + ".resolve_invoice_context", {
      client_name: clientName,
      customer_name: customerName
    });

    const context = result.message || result;
    applyContextToPage(context);
    return context;
  }

  async function refreshItemRowDefaults(row, options) {
    const itemCode = row.querySelector("[data-item-field='item_code']")?.value || "";

    if (!itemCode) {
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

    if (rateField) {
      rateField.value = details.rate != null ? details.rate : 0;
    }

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
      if (itemCode === PARENT_CHECKIN_ITEM_CODE) return;

      total += qty;
    });

    return total;
  }

  async function updateTravelRow() {
    if (!isEditable()) return;
    if (!currentClientDefaults) return;

    const travelCharged = Number(currentClientDefaults.travel_charged || 0);
    const oneWayMiles = Number(currentClientDefaults.travel_miles_one_way || 0);

    if (!travelCharged || !oneWayMiles || oneWayMiles <= FREE_MILES_ONE_WAY) {
      removeTravelRow();
      return;
    }

    const totalSessions = getBillableSessionCount();

    if (!totalSessions || totalSessions <= 0) {
      removeTravelRow();
      return;
    }

    const chargeableOneWay = oneWayMiles - FREE_MILES_ONE_WAY;
    const chargeableReturnMiles = chargeableOneWay * 2;
    const travelQty = chargeableReturnMiles * totalSessions;

    const description = [
      "Travel: ",
      oneWayMiles,
      " miles each way, less ",
      FREE_MILES_ONE_WAY,
      " free miles each way = ",
      chargeableOneWay,
      " chargeable miles each way (",
      chargeableReturnMiles,
      " miles return) x £",
      TRAVEL_RATE_PER_MILE,
      " x ",
      totalSessions,
      " sessions"
    ].join("");

    let travelRow = getTravelRow();

    if (!travelRow) {
      await addItemRow({
        item_code: TRAVEL_ITEM_CODE,
        description: description,
        qty: travelQty,
        rate: TRAVEL_RATE_PER_MILE,
        amount: travelQty * TRAVEL_RATE_PER_MILE
      });
      return;
    }

    const descriptionField = travelRow.querySelector("[data-item-field='description']");
    const qtyField = travelRow.querySelector("[data-item-field='qty']");
    const rateField = travelRow.querySelector("[data-item-field='rate']");

    if (descriptionField) descriptionField.value = description;
    if (qtyField) qtyField.value = travelQty;
    if (rateField) rateField.value = TRAVEL_RATE_PER_MILE;

    recalcTotals();
  }

  async function addItemRow(data) {
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
      await refreshItemRowDefaults(row, { preserveDescription: !!data?.description });
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

  function forceEmailTemplate() {
    const customerName = selectedCustomerText() || el("invoice_customer")?.value || "Billing Contact";
    const invoiceNumber = el("invoice_name")?.value || "";
    const amountDue = el("invoice_outstanding_amount")?.value || "0.00";
    const dueDate = el("invoice_due_date")?.value || "";
    const bankDetails = (el("invoice_bank_display")?.value || "Bank details available on request.").trim();
    const coachName = el("invoice_coach_label")?.value || "Coach";
    const companyLabel = el("invoice_company")?.value || "The Resilient Kid";
    const coachEmail = el("emailReplyTo")?.value || "";
    const coachPhone = el("coachPhoneValue")?.value || "";

    const subjectField = el("emailSubject");
    if (subjectField) subjectField.value = `Invoice ${invoiceNumber}`;

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

    const messageField = el("emailMessage");
    if (messageField) messageField.value = messageLines.join("\n");
  }

  function closePaymentModal() {
    const modal = el("invoicePaymentModal");
  
    if (modal) {
      modal.hidden = true;
      modal.style.display = "none";
    }
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
  
    const modal = el("invoicePaymentModal");
  
    if (modal) {
      modal.hidden = false;
      modal.style.display = "flex";
    }
  
    const amountField = el("paymentAmount");
    if (amountField) {
      amountField.value = parseMoneyValue(el("invoice_outstanding_amount")?.value || "0").toFixed(2);
    }
  
    const referenceField = el("paymentReference");
    if (referenceField && !referenceField.value) {
      referenceField.value = docname;
    }
  
    const select = el("paymentBankAccount");
  
    if (select) {
      select.innerHTML = "";
  
      const loading = document.createElement("option");
      loading.value = "";
      loading.textContent = "Loading bank accounts...";
      select.appendChild(loading);
    }
  
    try {
      const result = await apiPost(SHARED_API + ".get_payment_bank_accounts", {
        invoice_name: docname
      });
  
      const data = result.message || {};
  
      if (select) {
        select.innerHTML = "";
  
        const blank = document.createElement("option");
        blank.value = "";
        blank.textContent = "Select bank account";
        select.appendChild(blank);
  
        (data.bank_accounts || []).forEach((row) => {
          const option = document.createElement("option");
          option.value = row.name;
          option.textContent = row.label || row.name;
  
          if (row.name === data.default_bank_account) {
            option.selected = true;
          }
  
          select.appendChild(option);
        });
      }
    } catch (error) {
      if (select) {
        select.innerHTML = "";
  
        const option = document.createElement("option");
        option.value = "";
        option.textContent = "Could not load bank accounts";
        select.appendChild(option);
      }
  
      showError(error.message || "Could not load bank accounts.");
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
        bank_account: el("paymentBankAccount")?.value || "",
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

      window.history.replaceState({}, "", `${getDashboardBasePath()}/invoice_details?name=${encodeURIComponent(payload.name)}`);
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

    applyContextToPage({
      company: payload.company,
      price_list: payload.price_list,
      coach_label: payload.coach_label,
      contact_email: payload.contact_email,
      bank_display_text: payload.bank_display_text
    });

    forceEmailTemplate();
    updateActionState();
  }

  async function saveDraft() {
    if (isSaving || !isEditable()) return;

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
        message: el("emailMessage")?.value || ""
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
      await refreshInvoiceContext();
      await refreshAllItemRates();
      await updateTravelRow();
      forceEmailTemplate();
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
    closePaymentModal();
  
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
  
    if (new URLSearchParams(window.location.search).get("payment") === "1") {
      openPaymentModal();
    }
  
    try {
      await loadAllLinkOptions();
      await restrictCustomerToClientBillingContact();
  
      const existingRows = JSON.parse(el("invoiceInitialItems")?.textContent || "[]");
      const body = el("invoiceItemsBody");
      if (body) body.innerHTML = "";
  
      if (existingRows.length) {
        for (const row of existingRows) {
          await addItemRow(row);
        }
      } else {
        await addItemRow({ qty: 1, rate: 0, amount: 0 });
      }
  
      await refreshInvoiceContext();
      await updateTravelRow();
  
      updateStatusBadge(el("invoice_status")?.value || "Draft");
      recalcTotals();
      forceEmailTemplate();
      updateActionState();
      await initPartyWatchers();
  
      el("addInvoiceItem")?.addEventListener("click", async function () {
        await addItemRow({ qty: 1, rate: 0, amount: 0 });
        await updateTravelRow();
      });
    } catch (error) {
      console.error("Invoice details init failed", error);
      updateActionState();
    }
  
    el("saveInvoiceDraft")?.addEventListener("click", function (event) {
      event.preventDefault();
      saveDraft();
    });
  
    el("submitInvoice")?.addEventListener("click", function (event) {
      event.preventDefault();
      submitInvoice();
    });
  }
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
