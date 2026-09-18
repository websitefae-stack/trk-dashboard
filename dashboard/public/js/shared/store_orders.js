/**
 * Store dashboard's Orders page (see dashboard.api.shared.store_orders) -
 * every paid Webshop Checkout, worked through Paid -> Packed -> Shipped.
 */
(function () {
  "use strict";

  var el = Dashboard.el;

  const API = "dashboard.api.shared.store_orders";

  let orders = [];
  let currentOrder = null;

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
      throw new Error(data.message || "There was a problem loading this.");
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

  function formatMoney(amount, currency) {
    try {
      return new Intl.NumberFormat("en-GB", { style: "currency", currency: currency || "GBP" }).format(amount || 0);
    } catch (error) {
      return `${currency || "GBP"} ${Number(amount || 0).toFixed(2)}`;
    }
  }

  function formatDate(value) {
    if (!value) return "—";
    const date = new Date(value);
    return isNaN(date.getTime()) ? value : date.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
  }

  function formatDateTime(value) {
    if (!value) return "—";
    const date = new Date(value);
    return isNaN(date.getTime()) ? value : date.toLocaleString("en-GB");
  }

  function statusBadgeClass(status) {
    if (status === "Shipped") return "dashboard-status-active";
    if (status === "Packed") return "dashboard-status-archived";
    return "dashboard-status-onhold"; // Paid - needs packing
  }

  function renderRow(order) {
    return `
      <tr>
        <td>
          <div style="font-weight:700;">${escapeHtml(order.full_name)}</div>
          <div class="dashboard-help">${escapeHtml(order.email)}</div>
        </td>
        <td>${formatDate(order.creation)}</td>
        <td>${order.item_count}</td>
        <td>${formatMoney(order.total, order.currency)}</td>
        <td><span class="dashboard-badge ${statusBadgeClass(order.status)}">${escapeHtml(order.status)}</span></td>
        <td>
          <button type="button" class="dashboard-btn dashboard-btn-light" data-view-order="${escapeHtml(order.name)}">View</button>
        </td>
      </tr>
    `;
  }

  async function loadOrders() {
    const body = el("storeOrdersBody");
    const countEl = el("storeOrdersCount");
    const search = el("storeOrdersSearch") ? el("storeOrdersSearch").value.trim() : "";
    const status = el("storeOrdersStatusFilter") ? el("storeOrdersStatusFilter").value : "";

    try {
      orders = await apiPost(`${API}.get_store_orders`, { search, status });

      countEl.textContent = `${orders.length} order${orders.length === 1 ? "" : "s"}`;
      body.innerHTML = orders.length
        ? orders.map(renderRow).join("")
        : '<tr><td colspan="6" class="dashboard-empty">No orders found.</td></tr>';
    } catch (error) {
      body.innerHTML = '<tr><td colspan="6" class="dashboard-empty">Could not load orders.</td></tr>';
      countEl.textContent = "";
      console.error(error);
    }
  }

  function renderOrderItem(item) {
    return `
      <div style="display:flex; gap:12px; align-items:center; padding:10px 0; border-bottom:1px solid #F2F8F8;">
        ${item.image
          ? `<img src="${escapeHtml(item.image)}" alt="" style="width:48px; height:48px; object-fit:cover; border-radius:8px;">`
          : `<div style="width:48px; height:48px; border-radius:8px; background:#F2F8F8;"></div>`}
        <div style="flex:1;">
          <div style="font-weight:700;">${escapeHtml(item.item_name)}</div>
          ${item.variant_label ? `<div class="dashboard-help">${escapeHtml(item.variant_label)}</div>` : ""}
          ${item.sku ? `<div class="dashboard-help">SKU: ${escapeHtml(item.sku)}</div>` : ""}
          ${item.personalization ? `<div style="color:#C0392B; font-weight:700; margin-top:2px;">Personalize: ${escapeHtml(item.personalization)}</div>` : ""}
        </div>
        <div style="text-align:right; white-space:nowrap;">
          <div>${item.qty} × ${formatMoney(item.rate, item.currency)}</div>
          <div style="font-weight:700;">${formatMoney(item.amount, item.currency)}</div>
        </div>
      </div>
    `;
  }

  function renderOrderModal(order) {
    currentOrder = order;

    el("storeOrderModalTitle").textContent = order.full_name;

    const addressLines = [order.address_line1, order.address_line2, order.city, order.postcode, order.country]
      .filter(Boolean)
      .map(escapeHtml)
      .join("<br>");

    el("storeOrderModalBody").innerHTML = `
      <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:16px;">
        <div>
          <span class="dashboard-badge ${statusBadgeClass(order.status)}">${escapeHtml(order.status)}</span>
          <div class="dashboard-help" style="margin-top:6px;">Ordered ${formatDateTime(order.creation)}</div>
          ${order.packed_on ? `<div class="dashboard-help">Packed ${formatDateTime(order.packed_on)}</div>` : ""}
          ${order.shipped_on ? `<div class="dashboard-help">Shipped ${formatDateTime(order.shipped_on)}${order.tracking_number ? " - Tracking: " + escapeHtml(order.tracking_number) : ""}</div>` : ""}
        </div>
        ${order.invoice ? `<a class="dashboard-btn dashboard-btn-light" href="/app/sales-invoice/${escapeHtml(order.invoice)}" target="_blank" rel="noopener noreferrer">View Invoice</a>` : ""}
      </div>

      <div class="dashboard-detail-grid dashboard-detail-grid-2" style="margin-bottom:16px;">
        <div class="dashboard-detail-field">
          <label>Contact</label>
          <div class="dashboard-field-value">
            ${escapeHtml(order.full_name)}<br>
            ${escapeHtml(order.email)}
            ${order.phone ? "<br>" + escapeHtml(order.phone) : ""}
          </div>
        </div>
        <div class="dashboard-detail-field">
          <label>Delivery / Billing Address</label>
          <div class="dashboard-field-value">${addressLines || "—"}</div>
        </div>
      </div>

      <label>Items</label>
      <div>${(order.items || []).map(renderOrderItem).join("")}</div>

      <div style="display:flex; justify-content:space-between; padding-top:12px; margin-top:6px; font-weight:700; font-size:16px;">
        <span>Total</span>
        <span>${formatMoney(order.total, order.currency)}</span>
      </div>

      ${order.status !== "Shipped" ? `
        <div class="dashboard-detail-field" style="margin-top:16px;">
          <label for="storeOrderTrackingNumber">Tracking Number (optional)</label>
          <input type="text" id="storeOrderTrackingNumber" class="dashboard-input" placeholder="e.g. a Royal Mail/courier tracking code" value="${escapeHtml(order.tracking_number || "")}">
        </div>
      ` : ""}
    `;

    const footButtons = [];

    if (order.status === "Paid") {
      footButtons.push('<button type="button" class="dashboard-btn dashboard-btn-primary" id="markOrderPackedBtn">Mark as Packed</button>');
    }

    if (order.status === "Paid" || order.status === "Packed") {
      footButtons.push('<button type="button" class="dashboard-btn dashboard-btn-primary" id="markOrderShippedBtn">Mark as Shipped</button>');
    }

    el("storeOrderModalFoot").innerHTML = footButtons.join("");

    const packedBtn = el("markOrderPackedBtn");
    if (packedBtn) packedBtn.addEventListener("click", markPacked);

    const shippedBtn = el("markOrderShippedBtn");
    if (shippedBtn) shippedBtn.addEventListener("click", markShipped);
  }

  async function openOrderModal(name) {
    el("storeOrderModal").classList.add("is-open");
    el("storeOrderModalTitle").textContent = "Order";
    el("storeOrderModalBody").innerHTML = '<div class="dashboard-empty">Loading…</div>';
    el("storeOrderModalFoot").innerHTML = "";

    try {
      const order = await apiPost(`${API}.get_store_order`, { name });
      renderOrderModal(order);
    } catch (error) {
      el("storeOrderModalBody").innerHTML = `<div class="dashboard-empty">${escapeHtml(error.message || "Could not load this order.")}</div>`;
    }
  }

  function closeOrderModal() {
    el("storeOrderModal").classList.remove("is-open");
    currentOrder = null;
  }

  async function markPacked() {
    if (!currentOrder) return;
    const btn = el("markOrderPackedBtn");
    if (btn) { btn.disabled = true; btn.textContent = "Saving…"; }

    try {
      await apiPost(`${API}.mark_order_packed`, { name: currentOrder.name });
      await openOrderModal(currentOrder.name);
      loadOrders();
    } catch (error) {
      alert(error.message || "Could not mark this order as packed.");
      if (btn) { btn.disabled = false; btn.textContent = "Mark as Packed"; }
    }
  }

  async function markShipped() {
    if (!currentOrder) return;
    const btn = el("markOrderShippedBtn");
    const trackingInput = el("storeOrderTrackingNumber");
    if (btn) { btn.disabled = true; btn.textContent = "Saving…"; }

    try {
      await apiPost(`${API}.mark_order_shipped`, {
        name: currentOrder.name,
        tracking_number: trackingInput ? trackingInput.value.trim() : "",
      });
      await openOrderModal(currentOrder.name);
      loadOrders();
    } catch (error) {
      alert(error.message || "Could not mark this order as shipped.");
      if (btn) { btn.disabled = false; btn.textContent = "Mark as Shipped"; }
    }
  }

  function initPage() {
    if (!el("storeOrdersPage")) return;

    loadOrders();

    let searchTimer = null;
    el("storeOrdersSearch").addEventListener("input", () => {
      window.clearTimeout(searchTimer);
      searchTimer = window.setTimeout(loadOrders, 300);
    });

    el("storeOrdersStatusFilter").addEventListener("change", loadOrders);

    el("storeOrdersBody").addEventListener("click", (event) => {
      const btn = event.target.closest("[data-view-order]");
      if (!btn) return;
      openOrderModal(btn.dataset.viewOrder);
    });

    el("closeStoreOrderModal").addEventListener("click", closeOrderModal);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initPage);
  } else {
    initPage();
  }
})();
