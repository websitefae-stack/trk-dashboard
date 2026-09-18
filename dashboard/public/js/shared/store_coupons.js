/**
 * Store dashboard's Coupons page (see dashboard.api.shared.store_coupons) -
 * list/create/edit/delete discount codes customers can enter at checkout,
 * either store-wide or restricted to specific products.
 */
(function () {
  "use strict";

  var el = Dashboard.el;

  const API = "dashboard.api.shared.store_coupons";
  const PRODUCTS_API = "dashboard.api.shared.store_products";

  let coupons = [];
  let products = null; // lazy-loaded, cached - [{name, item_name}, ...]

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

  function formatDiscount(coupon) {
    return coupon.discount_type === "Percentage"
      ? `${coupon.discount_value}%`
      : `£${Number(coupon.discount_value).toFixed(2)}`;
  }

  function formatDate(value) {
    if (!value) return "—";
    const date = new Date(value);
    return isNaN(date.getTime()) ? value : date.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
  }

  function formatScope(coupon) {
    if (coupon.scope !== "Specific Items") return "Entire Store";
    const count = coupon.item_count || 0;
    return `${count} item${count === 1 ? "" : "s"}`;
  }

  function renderRow(coupon) {
    const usesLabel = coupon.max_uses ? `${coupon.times_used} / ${coupon.max_uses}` : `${coupon.times_used}`;
    const expired = coupon.expiry_date && new Date(coupon.expiry_date) < new Date(new Date().toDateString());
    const usedUp = coupon.max_uses && coupon.times_used >= coupon.max_uses;

    let statusLabel = "Active";
    let statusClass = "dashboard-status-active";
    if (!coupon.active) {
      statusLabel = "Inactive";
      statusClass = "dashboard-status-archived";
    } else if (expired) {
      statusLabel = "Expired";
      statusClass = "dashboard-status-onhold";
    } else if (usedUp) {
      statusLabel = "Fully redeemed";
      statusClass = "dashboard-status-onhold";
    }

    return `
      <tr>
        <td style="font-weight:700;">${escapeHtml(coupon.code)}</td>
        <td>${formatDiscount(coupon)}</td>
        <td>${formatScope(coupon)}</td>
        <td>${formatDate(coupon.expiry_date)}</td>
        <td>${usesLabel}</td>
        <td><span class="dashboard-badge ${statusClass}">${statusLabel}</span></td>
        <td>
          <button type="button" class="dashboard-btn dashboard-btn-light" data-edit-coupon="${escapeHtml(coupon.name)}">Edit</button>
          <button type="button" class="dashboard-btn dashboard-btn-light" data-delete-coupon="${escapeHtml(coupon.name)}">Delete</button>
        </td>
      </tr>
    `;
  }

  async function loadCoupons() {
    const body = el("storeCouponsBody");
    const countEl = el("storeCouponsCount");

    try {
      coupons = await apiPost(`${API}.get_coupons`, {});

      countEl.textContent = `${coupons.length} coupon${coupons.length === 1 ? "" : "s"}`;
      body.innerHTML = coupons.length
        ? coupons.map(renderRow).join("")
        : '<tr><td colspan="7" class="dashboard-empty">No coupons yet.</td></tr>';
    } catch (error) {
      body.innerHTML = '<tr><td colspan="7" class="dashboard-empty">Could not load coupons.</td></tr>';
      countEl.textContent = "";
      console.error(error);
    }
  }

  function updateDiscountValueLabel() {
    const type = el("storeCouponDiscountType").value;
    el("storeCouponDiscountValueLabel").textContent = type === "Percentage" ? "Discount (%)" : "Discount (£)";
  }

  async function ensureProductsLoaded() {
    if (products) return products;

    const list = el("storeCouponItemsList");
    try {
      products = await apiPost(`${PRODUCTS_API}.get_store_products`, {});
    } catch (error) {
      products = [];
      list.innerHTML = '<div class="dashboard-empty">Could not load products.</div>';
    }
    return products;
  }

  function renderItemsChecklist(selectedCodes) {
    const list = el("storeCouponItemsList");
    const selected = new Set(selectedCodes || []);

    if (!products.length) {
      list.innerHTML = '<div class="dashboard-empty">No products found.</div>';
      return;
    }

    list.innerHTML = products.map((product) => `
      <label style="display:flex; align-items:center; gap:10px; padding:6px 4px; font-weight:normal;">
        <input type="checkbox" class="store-coupon-item-check" value="${escapeHtml(product.name)}" ${selected.has(product.name) ? "checked" : ""}>
        <span>${escapeHtml(product.item_name)}${product.has_variants ? " (has variations)" : ""}</span>
      </label>
    `).join("");
  }

  async function updateScopeVisibility(selectedCodes) {
    const scope = el("storeCouponScope").value;
    const section = el("storeCouponItemsSection");

    if (scope !== "Specific Items") {
      section.style.display = "none";
      return;
    }

    section.style.display = "";
    await ensureProductsLoaded();
    renderItemsChecklist(selectedCodes);
  }

  async function openModal(coupon) {
    el("storeCouponModalTitle").textContent = coupon ? "Edit Coupon" : "Add Coupon";
    el("storeCouponName").value = coupon ? coupon.name : "";
    el("storeCouponCode").value = coupon ? coupon.code : "";
    el("storeCouponCode").disabled = !!coupon;
    el("storeCouponDiscountType").value = coupon ? coupon.discount_type : "Percentage";
    el("storeCouponDiscountValue").value = coupon ? coupon.discount_value : "";
    el("storeCouponScope").value = coupon ? coupon.scope || "Entire Store" : "Entire Store";
    el("storeCouponExpiry").value = coupon && coupon.expiry_date ? coupon.expiry_date : "";
    el("storeCouponMaxUses").value = coupon ? coupon.max_uses || 0 : 0;
    el("storeCouponDescription").value = coupon ? coupon.description || "" : "";
    el("storeCouponActive").checked = coupon ? !!coupon.active : true;
    updateDiscountValueLabel();

    const selectedCodes = coupon && coupon.items ? coupon.items.map((row) => row.item) : [];
    await updateScopeVisibility(selectedCodes);

    el("storeCouponModal").classList.add("is-open");
  }

  async function openEditModal(name) {
    try {
      const coupon = await apiPost(`${API}.get_coupon`, { name });
      openModal(coupon);
    } catch (error) {
      alert(error.message || "Could not load this coupon.");
    }
  }

  function closeModal() {
    el("storeCouponModal").classList.remove("is-open");
  }

  function checkedItemCodes() {
    return Array.from(document.querySelectorAll(".store-coupon-item-check:checked")).map((c) => c.value);
  }

  async function saveCoupon() {
    const name = el("storeCouponName").value;
    const isEdit = !!name;
    const scope = el("storeCouponScope").value;
    const items = scope === "Specific Items" ? checkedItemCodes() : [];

    if (scope === "Specific Items" && !items.length) {
      alert("Choose at least one item this coupon applies to, or set \"Applies To\" back to Entire Store.");
      return;
    }

    const payload = {
      discount_type: el("storeCouponDiscountType").value,
      discount_value: el("storeCouponDiscountValue").value,
      active: el("storeCouponActive").checked ? 1 : 0,
      scope,
      items: JSON.stringify(items),
      expiry_date: el("storeCouponExpiry").value || null,
      max_uses: el("storeCouponMaxUses").value || 0,
      description: el("storeCouponDescription").value,
    };

    const btn = el("saveStoreCouponBtn");
    btn.disabled = true;
    btn.textContent = "Saving…";

    try {
      if (isEdit) {
        payload.name = name;
        await apiPost(`${API}.update_coupon`, payload);
      } else {
        payload.code = el("storeCouponCode").value;
        await apiPost(`${API}.create_coupon`, payload);
      }

      closeModal();
      loadCoupons();
    } catch (error) {
      alert(error.message || "Could not save this coupon.");
    } finally {
      btn.disabled = false;
      btn.textContent = "Save Coupon";
    }
  }

  async function deleteCoupon(name) {
    if (!window.confirm("Delete this coupon? This can't be undone.")) return;

    try {
      await apiPost(`${API}.delete_coupon`, { name });
      loadCoupons();
    } catch (error) {
      alert(error.message || "Could not delete this coupon.");
    }
  }

  function initPage() {
    if (!el("storeCouponsPage")) return;

    loadCoupons();

    el("addCouponBtn").addEventListener("click", () => openModal(null));
    el("closeStoreCouponModal").addEventListener("click", closeModal);
    el("cancelStoreCouponModal").addEventListener("click", closeModal);
    el("saveStoreCouponBtn").addEventListener("click", saveCoupon);
    el("storeCouponDiscountType").addEventListener("change", updateDiscountValueLabel);
    el("storeCouponScope").addEventListener("change", () => updateScopeVisibility(checkedItemCodes()));

    el("storeCouponsBody").addEventListener("click", (event) => {
      const editBtn = event.target.closest("[data-edit-coupon]");
      if (editBtn) {
        openEditModal(editBtn.dataset.editCoupon);
        return;
      }

      const deleteBtn = event.target.closest("[data-delete-coupon]");
      if (deleteBtn) {
        deleteCoupon(deleteBtn.dataset.deleteCoupon);
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initPage);
  } else {
    initPage();
  }
})();
