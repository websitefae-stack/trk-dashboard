/**
 * Store dashboard's Coupons page (see dashboard.api.shared.store_coupons) -
 * list/create/edit/delete discount codes customers can enter at checkout.
 */
(function () {
  "use strict";

  var el = Dashboard.el;

  const API = "dashboard.api.shared.store_coupons";

  let coupons = [];

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
        : '<tr><td colspan="6" class="dashboard-empty">No coupons yet.</td></tr>';
    } catch (error) {
      body.innerHTML = '<tr><td colspan="6" class="dashboard-empty">Could not load coupons.</td></tr>';
      countEl.textContent = "";
      console.error(error);
    }
  }

  function updateDiscountValueLabel() {
    const type = el("storeCouponDiscountType").value;
    el("storeCouponDiscountValueLabel").textContent = type === "Percentage" ? "Discount (%)" : "Discount (£)";
  }

  function openModal(coupon) {
    el("storeCouponModalTitle").textContent = coupon ? "Edit Coupon" : "Add Coupon";
    el("storeCouponName").value = coupon ? coupon.name : "";
    el("storeCouponCode").value = coupon ? coupon.code : "";
    el("storeCouponCode").disabled = !!coupon;
    el("storeCouponDiscountType").value = coupon ? coupon.discount_type : "Percentage";
    el("storeCouponDiscountValue").value = coupon ? coupon.discount_value : "";
    el("storeCouponExpiry").value = coupon && coupon.expiry_date ? coupon.expiry_date : "";
    el("storeCouponMaxUses").value = coupon ? coupon.max_uses || 0 : 0;
    el("storeCouponDescription").value = coupon ? coupon.description || "" : "";
    el("storeCouponActive").checked = coupon ? !!coupon.active : true;
    updateDiscountValueLabel();

    el("storeCouponModal").classList.add("is-open");
  }

  function closeModal() {
    el("storeCouponModal").classList.remove("is-open");
  }

  async function saveCoupon() {
    const name = el("storeCouponName").value;
    const isEdit = !!name;

    const btn = el("saveStoreCouponBtn");
    btn.disabled = true;
    btn.textContent = "Saving…";

    try {
      if (isEdit) {
        await apiPost(`${API}.update_coupon`, {
          name,
          discount_type: el("storeCouponDiscountType").value,
          discount_value: el("storeCouponDiscountValue").value,
          active: el("storeCouponActive").checked ? 1 : 0,
          expiry_date: el("storeCouponExpiry").value || null,
          max_uses: el("storeCouponMaxUses").value || 0,
          description: el("storeCouponDescription").value,
        });
      } else {
        await apiPost(`${API}.create_coupon`, {
          code: el("storeCouponCode").value,
          discount_type: el("storeCouponDiscountType").value,
          discount_value: el("storeCouponDiscountValue").value,
          active: el("storeCouponActive").checked ? 1 : 0,
          expiry_date: el("storeCouponExpiry").value || null,
          max_uses: el("storeCouponMaxUses").value || 0,
          description: el("storeCouponDescription").value,
        });
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

    el("storeCouponsBody").addEventListener("click", (event) => {
      const editBtn = event.target.closest("[data-edit-coupon]");
      if (editBtn) {
        const coupon = coupons.find((c) => c.name === editBtn.dataset.editCoupon);
        if (coupon) openModal(coupon);
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
