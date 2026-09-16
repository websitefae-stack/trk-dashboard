/**
 * Store Manager's Products page (see dashboard.api.shared.store_products) -
 * list, add, edit and quick-restock the items shown in the online store.
 */
(function () {
  "use strict";

  var el = Dashboard.el;

  const API = "dashboard.api.shared.store_products";

  let products = [];
  let itemGroups = [];
  let uploadedImageUrl = "";

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

  async function uploadFile(file) {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("is_private", 0);

    const response = await fetch("/api/method/upload_file", {
      method: "POST",
      credentials: "same-origin",
      headers: { "X-Frappe-CSRF-Token": getCsrfToken() },
      body: formData,
    });

    const data = await response.json();

    if (!response.ok || data.exc) {
      throw new Error(data.message || "Could not upload the image.");
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

  function formatPrice(price) {
    return "£" + Number(price || 0).toFixed(2);
  }

  const BRAND_LABELS = {
    custom_brand_hub: "Hub",
    custom_brand_kid: "Kid",
    custom_brand_teen: "Teen",
    custom_brand_people: "People",
    custom_brand_school: "School",
  };

  function brandsSummary(brands) {
    const shown = Object.keys(BRAND_LABELS).filter((key) => brands && brands[key]);
    if (!shown.length) return "—";
    return shown.map((key) => BRAND_LABELS[key]).join(", ");
  }

  function stockSummary(product) {
    if (product.unlimited_stock) return "Unlimited";
    return String(product.stock_qty || 0);
  }

  function renderRow(product) {
    const image = product.image
      ? `<img src="${escapeHtml(product.image)}" alt="" style="width:36px; height:36px; object-fit:cover; border-radius:6px; margin-right:8px; vertical-align:middle;">`
      : "";

    const stockInput = product.unlimited_stock
      ? `<span class="dashboard-doc-list-meta">Unlimited</span>`
      : `<input type="number" min="0" step="1" class="dashboard-input" style="width:80px;" value="${product.stock_qty || 0}" data-stock-input="${escapeHtml(product.name)}">
         <button type="button" class="dashboard-btn dashboard-btn-light" style="padding:4px 8px;" data-save-stock="${escapeHtml(product.name)}">Save</button>`;

    return `
      <tr data-product-row="${escapeHtml(product.name)}">
        <td>${image}${escapeHtml(product.item_name)}</td>
        <td>${escapeHtml(product.item_group || "—")}</td>
        <td>${formatPrice(product.price)}</td>
        <td>${stockInput}</td>
        <td>${escapeHtml(brandsSummary(product.brands))}</td>
        <td>${product.disabled ? '<span class="dashboard-badge dashboard-status-archived">Disabled</span>' : '<span class="dashboard-badge dashboard-status-active">Active</span>'}</td>
        <td><button type="button" class="dashboard-btn dashboard-btn-light" data-edit-product="${escapeHtml(product.name)}">Edit</button></td>
      </tr>
    `;
  }

  function renderProducts() {
    const body = el("storeProductsBody");
    if (!body) return;

    if (!products.length) {
      body.innerHTML = '<tr><td colspan="7" class="dashboard-empty">No products yet - click "Add Product" to create one.</td></tr>';
    } else {
      body.innerHTML = products.map(renderRow).join("");
    }

    const count = el("storeProductsCount");
    if (count) count.textContent = products.length + (products.length === 1 ? " product" : " products");
  }

  async function loadProducts() {
    try {
      products = await apiPost(API + ".get_store_products", {});
      renderProducts();
    } catch (error) {
      const body = el("storeProductsBody");
      if (body) body.innerHTML = '<tr><td colspan="7" class="dashboard-empty">Could not load products.</td></tr>';
      console.error(error);
    }
  }

  async function loadItemGroups() {
    try {
      itemGroups = await apiPost(API + ".get_item_groups", {});
      const datalist = el("storeProductGroupOptions");
      if (datalist) {
        datalist.innerHTML = itemGroups.map((name) => `<option value="${escapeHtml(name)}"></option>`).join("");
      }
    } catch (error) {
      console.error(error);
    }
  }

  function updateStockFieldVisibility() {
    const unlimited = el("storeProductUnlimited").checked;
    el("storeProductStockField").style.display = unlimited ? "none" : "";
  }

  function openModal(product) {
    uploadedImageUrl = product ? product.image || "" : "";

    el("storeProductModalTitle").textContent = product ? "Edit Product" : "Add Product";
    el("storeProductItemCode").value = product ? product.name : "";
    el("storeProductName").value = product ? product.item_name : "";
    el("storeProductDescription").value = product ? product.description : "";
    el("storeProductGroup").value = product ? product.item_group : "";
    el("storeProductPrice").value = product ? product.price : "";
    el("storeProductUnlimited").checked = !!(product && product.unlimited_stock);
    el("storeProductStockQty").value = product ? product.stock_qty || 0 : 0;
    el("storeProductDisabled").checked = !!(product && product.disabled);
    el("storeProductDisabledRow").style.display = product ? "" : "none";

    const preview = el("storeProductImagePreview");
    if (uploadedImageUrl) {
      preview.src = uploadedImageUrl;
      preview.style.display = "";
    } else {
      preview.style.display = "none";
    }
    el("storeProductImageFile").value = "";

    Object.keys(BRAND_LABELS).forEach((fieldname) => {
      const inputId = "storeProductBrand" + fieldname.replace("custom_brand_", "").replace(/^./, (c) => c.toUpperCase());
      const input = el(inputId);
      if (input) input.checked = !!(product && product.brands && product.brands[fieldname]);
    });

    updateStockFieldVisibility();

    el("storeProductModal").classList.add("is-open");
  }

  function closeModal() {
    el("storeProductModal").classList.remove("is-open");
  }

  function collectBrands() {
    return {
      custom_brand_hub: el("storeProductBrandHub").checked,
      custom_brand_kid: el("storeProductBrandKid").checked,
      custom_brand_teen: el("storeProductBrandTeen").checked,
      custom_brand_people: el("storeProductBrandPeople").checked,
      custom_brand_school: el("storeProductBrandSchool").checked,
    };
  }

  async function saveProduct() {
    const saveBtn = el("saveStoreProduct");
    const itemCode = el("storeProductItemCode").value;
    const itemName = el("storeProductName").value.trim();

    if (!itemName) {
      alert("Please enter a product name.");
      return;
    }

    saveBtn.disabled = true;
    saveBtn.textContent = "Saving…";

    try {
      const file = el("storeProductImageFile").files[0];
      if (file) {
        const uploaded = await uploadFile(file);
        uploadedImageUrl = uploaded.file_url || uploadedImageUrl;
      }

      const payload = {
        item_name: itemName,
        description: el("storeProductDescription").value,
        item_group: el("storeProductGroup").value,
        price: el("storeProductPrice").value || 0,
        unlimited_stock: el("storeProductUnlimited").checked,
        stock_qty: el("storeProductStockQty").value || 0,
        brands: collectBrands(),
        image: uploadedImageUrl,
      };

      if (itemCode) {
        payload.item_code = itemCode;
        payload.disabled = el("storeProductDisabled").checked;
        await apiPost(API + ".update_store_product", payload);
      } else {
        await apiPost(API + ".create_store_product", payload);
      }

      closeModal();
      await loadProducts();
    } catch (error) {
      alert(error.message || "Could not save the product.");
    } finally {
      saveBtn.disabled = false;
      saveBtn.textContent = "Save";
    }
  }

  async function saveStock(itemCode, button) {
    const row = document.querySelector(`[data-stock-input="${CSS.escape(itemCode)}"]`);
    if (!row) return;

    const qty = row.value;
    button.disabled = true;
    button.textContent = "Saving…";

    try {
      await apiPost(API + ".update_store_stock", { item_code: itemCode, stock_qty: qty });
      const product = products.find((p) => p.name === itemCode);
      if (product) product.stock_qty = parseInt(qty, 10) || 0;
      button.textContent = "Saved";
      window.setTimeout(() => {
        button.textContent = "Save";
        button.disabled = false;
      }, 1200);
    } catch (error) {
      alert(error.message || "Could not update stock.");
      button.disabled = false;
      button.textContent = "Save";
    }
  }

  function initSearch() {
    const input = el("storeProductsSearch");
    if (!input) return;

    input.addEventListener("input", Dashboard.debounce(async function () {
      const query = input.value.trim();
      try {
        products = await apiPost(API + ".get_store_products", { search: query });
        renderProducts();
      } catch (error) {
        console.error(error);
      }
    }, 250));
  }

  function initPage() {
    if (!el("storeProductsPage")) return;

    loadProducts();
    loadItemGroups();
    initSearch();

    el("addProductBtn").addEventListener("click", () => openModal(null));
    el("closeStoreProductModal").addEventListener("click", closeModal);
    el("cancelStoreProductModal").addEventListener("click", closeModal);
    el("saveStoreProduct").addEventListener("click", saveProduct);
    el("storeProductUnlimited").addEventListener("change", updateStockFieldVisibility);

    el("storeProductImageFile").addEventListener("change", function () {
      const file = this.files[0];
      if (!file) return;
      const preview = el("storeProductImagePreview");
      preview.src = URL.createObjectURL(file);
      preview.style.display = "";
    });

    document.addEventListener("click", function (event) {
      const editBtn = event.target.closest("[data-edit-product]");
      if (editBtn) {
        const product = products.find((p) => p.name === editBtn.dataset.editProduct);
        if (product) openModal(product);
        return;
      }

      const saveStockBtn = event.target.closest("[data-save-stock]");
      if (saveStockBtn) {
        saveStock(saveStockBtn.dataset.saveStock, saveStockBtn);
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initPage);
  } else {
    initPage();
  }
})();
