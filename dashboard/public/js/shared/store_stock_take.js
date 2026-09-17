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

  // Only products/variations with tracked stock are worth listing at all -
  // a simple (non-variant) item is included when it isn't unlimited; a
  // variant template is included whenever it has has_variants, since
  // whether any individual variant is actually countable is only known
  // once get_stock_take_rows() expands it (see index.html's own note).
  function isCountable(product) {
    return product.has_variants || !product.unlimited_stock;
  }

  function renderProductList() {
    const container = el("stockTakeProductList");
    const search = el("stockTakeSearch").value.trim().toLowerCase();

    const filtered = products.filter((p) => isCountable(p) && (!search || p.item_name.toLowerCase().includes(search)));

    if (!filtered.length) {
      container.innerHTML = '<div class="dashboard-empty">No trackable-stock products found.</div>';
      return;
    }

    container.innerHTML = filtered.map((p) => `
      <label style="display:flex; align-items:center; gap:10px; padding:8px 6px; border-bottom:1px solid #F2F8F8; font-weight:normal;">
        <input type="checkbox" class="stock-take-product-check" value="${escapeHtml(p.name)}">
        <span>${escapeHtml(p.item_name)}${p.has_variants ? " (has variations)" : ""}</span>
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
        <td>${escapeHtml(row.item_name)}${row.variant_label ? ` <span class="dashboard-help">(${escapeHtml(row.variant_label)})</span>` : ""}</td>
        <td>${escapeHtml(row.sku || "—")}</td>
        <td>${row.current_stock_qty}</td>
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
        alert("Nothing to count in what you picked - every variation there is set to unlimited stock.");
        return;
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
