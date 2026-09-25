/**
 * Store dashboard's Stock Take page (see dashboard.api.shared.
 * store_products' get_stock_take_rows/stock_take_update) - pick which
 * products to count, expand each into its actually-countable variants,
 * enter what's actually on the shelf, save updates every one at once.
 */
(function () {
  "use strict";

  var el = Dashboard.el;

  const API = "dashboard.api.shared.store_products";

  let products = [];

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

  function renderProductList() {
    const container = el("stockTakeProductList");
    const search = el("stockTakeSearch").value.trim().toLowerCase();
    const brandField = el("stockTakeBrandFilter") ? el("stockTakeBrandFilter").value : "";
    const visibility = el("stockTakeVisibilityFilter") ? el("stockTakeVisibilityFilter").value : "";
    const status = el("stockTakeStatusFilter") ? el("stockTakeStatusFilter").value : "";

    const filtered = products.filter((p) => {
      if (search && !p.item_name.toLowerCase().includes(search)) return false;
      if (brandField && !(p.brands && p.brands[brandField])) return false;
      if (visibility && (p.visibility || "Everyone") !== visibility) return false;
      if (status === "active" && p.disabled) return false;
      if (status === "archived" && !p.disabled) return false;
      return true;
    });

    if (!filtered.length) {
      container.innerHTML = '<div class="dashboard-empty">No products found.</div>';
      return;
    }

    container.innerHTML = filtered.map((p) => `
      <label style="display:flex; align-items:center; gap:10px; padding:8px 6px; border-bottom:1px solid #F2F8F8; font-weight:normal;">
        <input type="checkbox" class="stock-take-product-check" value="${escapeHtml(p.name)}">
        <span>${escapeHtml(p.item_name)}${p.has_variants ? " (has variations)" : ""}${(!p.has_variants && p.unlimited_stock) ? " (Always Available)" : ""}</span>
      </label>
    `).join("");
  }

  async function loadProducts() {
    const container = el("stockTakeProductList");

    try {
      products = await apiPost(`${API}.get_store_products`, {});
      renderProductList();
    } catch (error) {
      container.innerHTML = '<div class="dashboard-empty">Could not load products.</div>';
      console.error(error);
    }
  }

  function renderSheetRow(row) {
    return `
      <tr data-stock-take-row="${escapeHtml(row.item_code)}">
        <td>
          ${escapeHtml(row.item_name)}${row.variant_label ? ` <span class="dashboard-help">(${escapeHtml(row.variant_label)})</span>` : ""}
          ${row.unlimited_stock ? '<div class="dashboard-help">Currently Always Available - saving a count here switches it to tracked stock.</div>' : ""}
        </td>
        <td>${escapeHtml(row.sku || "—")}</td>
        <td>${row.unlimited_stock ? "Unlimited" : row.current_stock_qty}</td>
        <td><input type="number" min="0" step="1" class="dashboard-input" style="width:110px;" value="${row.current_stock_qty}" data-stock-take-input="${escapeHtml(row.item_code)}"></td>
      </tr>
    `;
  }

  async function buildCountSheet() {
    const checked = Array.from(document.querySelectorAll(".stock-take-product-check:checked")).map((c) => c.value);

    if (!checked.length) {
      alert("Choose at least one product to count.");
      return;
    }

    const btn = el("buildStockTakeBtn");
    btn.disabled = true;
    btn.textContent = "Loading…";

    try {
      const rows = await apiPost(`${API}.get_stock_take_rows`, { item_codes: checked });

      if (!rows.length) {
        alert("Nothing to count in what you picked.");
        return;
      }

      const unlimitedCount = rows.filter((row) => row.unlimited_stock).length;

      if (unlimitedCount) {
        const warned = window.confirm(
          `${unlimitedCount} item${unlimitedCount === 1 ? " is" : "s are"} currently set to "Always Available" (unlimited stock).\n\n` +
          "Entering a count for it here will switch it to tracked stock, so once you save, it'll only show as " +
          "available on the store while that count is above zero - even if you later bring in new stock, you'll " +
          "need to update the count again for it to show as available.\n\n" +
          "Continue with the count for these items?"
        );

        if (!warned) return;
      }

      el("stockTakeSheetBody").innerHTML = rows.map(renderSheetRow).join("");
      el("stockTakeSheetCount").textContent = `${rows.length} row${rows.length === 1 ? "" : "s"}`;
      el("stockTakeSaveStatus").textContent = "";
      el("stockTakePickerCard").style.display = "none";
      el("stockTakeSheetCard").style.display = "";
    } catch (error) {
      alert(error.message || "Could not build the count sheet.");
    } finally {
      btn.disabled = false;
      btn.textContent = "Build Count Sheet";
    }
  }

  function startOver() {
    el("stockTakeSheetCard").style.display = "none";
    el("stockTakePickerCard").style.display = "";
    el("stockTakeSheetBody").innerHTML = "";
  }

  async function saveStockTake() {
    const updates = Array.from(document.querySelectorAll("[data-stock-take-input]")).map((input) => ({
      item_code: input.dataset.stockTakeInput,
      stock_qty: input.value,
    }));

    const btn = el("saveStockTakeBtn");
    const statusEl = el("stockTakeSaveStatus");

    btn.disabled = true;
    btn.textContent = "Saving…";
    statusEl.textContent = "";

    try {
      const result = await apiPost(`${API}.stock_take_update`, { updates });
      statusEl.textContent = `Saved - updated stock for ${result.updated} item${result.updated === 1 ? "" : "s"}.`;
    } catch (error) {
      statusEl.textContent = error.message || "Could not save this stock take.";
    } finally {
      btn.disabled = false;
      btn.textContent = "Save Stock Take";
    }
  }

  function initPage() {
    if (!el("storeStockTakePage")) return;

    loadProducts();

    let searchTimer = null;
    el("stockTakeSearch").addEventListener("input", () => {
      window.clearTimeout(searchTimer);
      searchTimer = window.setTimeout(renderProductList, 150);
    });

    ["stockTakeBrandFilter", "stockTakeVisibilityFilter", "stockTakeStatusFilter"].forEach((id) => {
      const select = el(id);
      if (select) select.addEventListener("change", renderProductList);
    });

    el("buildStockTakeBtn").addEventListener("click", buildCountSheet);
    el("cancelStockTakeBtn").addEventListener("click", startOver);
    el("saveStockTakeBtn").addEventListener("click", saveStockTake);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initPage);
  } else {
    initPage();
  }
})();
