/**
 * Store Manager's Products page (see dashboard.api.shared.store_products) -
 * list, add, edit and quick-restock the items shown in the online store,
 * plus variant products (e.g. a hoodie in several sizes/wordings) and
 * each plain product's optional digital download file / course unlock.
 */
(function () {
  "use strict";

  var el = Dashboard.el;

  const API = "dashboard.api.shared.store_products";

  let products = [];
  let lmsCourses = [];
  let uploadedImageUrl = "";
  let uploadedDigitalFileUrl = "";
  let generatedVariants = [];
  let imageKeyAttribute = "";
  let variantImagesByValue = {};

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

  async function uploadFile(file, isPrivate) {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("is_private", isPrivate ? 1 : 0);

    const response = await fetch("/api/method/upload_file", {
      method: "POST",
      credentials: "same-origin",
      headers: { "X-Frappe-CSRF-Token": getCsrfToken() },
      body: formData,
    });

    const data = await response.json();

    if (!response.ok || data.exc) {
      throw new Error(data.message || "Could not upload the file.");
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

  function brandInputId(fieldname) {
    return "storeProductBrand" + fieldname.replace("custom_brand_", "").replace(/^./, (c) => c.toUpperCase());
  }

  // ---------------------------------------------------------------
  // Product list
  // ---------------------------------------------------------------

  function renderRow(product) {
    const image = product.image
      ? `<img src="${escapeHtml(product.image)}" alt="" style="width:36px; height:36px; object-fit:cover; border-radius:6px; margin-right:8px; vertical-align:middle;">`
      : "";

    let priceCell;
    let stockCell;
    let actionsCell;

    if (product.has_variants) {
      priceCell = '<span class="dashboard-doc-list-meta">Varies</span>';
      stockCell = '<span class="dashboard-doc-list-meta">See variants</span>';
      actionsCell = (
        `<button type="button" class="dashboard-btn dashboard-btn-light" data-edit-product="${escapeHtml(product.name)}">Edit</button> ` +
        `<button type="button" class="dashboard-btn dashboard-btn-light" data-manage-variants="${escapeHtml(product.name)}">Manage Variants</button>`
      );
    } else {
      priceCell = formatPrice(product.price);
      stockCell = product.unlimited_stock
        ? `<span class="dashboard-doc-list-meta">Unlimited</span>`
        : `<input type="number" min="0" step="1" class="dashboard-input" style="width:80px;" value="${product.stock_qty || 0}" data-stock-input="${escapeHtml(product.name)}">
           <button type="button" class="dashboard-btn dashboard-btn-light" style="padding:4px 8px;" data-save-stock="${escapeHtml(product.name)}">Save</button>`;
      actionsCell = `<button type="button" class="dashboard-btn dashboard-btn-light" data-edit-product="${escapeHtml(product.name)}">Edit</button>`;
    }

    return `
      <tr data-product-row="${escapeHtml(product.name)}">
        <td>${image}${escapeHtml(product.item_name)}</td>
        <td>${escapeHtml(product.item_group || "—")}</td>
        <td>${priceCell}</td>
        <td>${stockCell}</td>
        <td>${escapeHtml(brandsSummary(product.brands))}</td>
        <td>${product.disabled ? '<span class="dashboard-badge dashboard-status-archived">Disabled</span>' : '<span class="dashboard-badge dashboard-status-active">Active</span>'}</td>
        <td>${actionsCell}</td>
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
      const itemGroups = await apiPost(API + ".get_item_groups", {});
      const datalist = el("storeProductGroupOptions");
      if (datalist) {
        datalist.innerHTML = itemGroups.map((name) => `<option value="${escapeHtml(name)}"></option>`).join("");
      }
    } catch (error) {
      console.error(error);
    }
  }

  async function loadLmsCourses() {
    try {
      lmsCourses = await apiPost(API + ".get_lms_courses", {});
      const select = el("storeProductUnlocksCourse");
      if (select) {
        select.innerHTML = '<option value="">— None —</option>' +
          lmsCourses.map((c) => `<option value="${escapeHtml(c.name)}">${escapeHtml(c.title || c.name)}</option>`).join("");
      }
    } catch (error) {
      console.error(error);
    }
  }

  // ---------------------------------------------------------------
  // Add/Edit product modal
  // ---------------------------------------------------------------

  function updateStockFieldVisibility() {
    const unlimited = el("storeProductUnlimited").checked;
    el("storeProductStockField").style.display = unlimited ? "none" : "";
  }

  function updateVariationsVisibility() {
    const hasVariations = el("storeProductHasVariations").checked;
    el("storeProductPriceField").style.display = hasVariations ? "none" : "";
    el("storeSimpleProductFields").style.display = hasVariations ? "none" : "";
    el("storeVariationsFields").style.display = hasVariations ? "" : "none";
  }

  function updateDigitalFieldVisibility() {
    el("storeProductDigitalFileWrap").style.display = el("storeProductIsDigital").checked ? "" : "none";
  }

  function updateUnlocksCourseFieldVisibility() {
    el("storeProductUnlocksCourseWrap").style.display = el("storeProductUnlocksCourseEnabled").checked ? "" : "none";
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

  let attributeRowCount = 0;

  function addAttributeRow() {
    const container = el("storeAttributesList");
    const index = attributeRowCount++;

    const row = document.createElement("div");
    row.className = "store-attribute-row";
    row.style.marginBottom = "14px";
    row.innerHTML = `
      <label>Attribute ${index + 1} name</label>
      <input type="text" class="dashboard-input" data-attribute-name placeholder="e.g. Size">
      <label>Attribute ${index + 1} values (comma separated)</label>
      <input type="text" class="dashboard-input" data-attribute-values placeholder="e.g. Small, Medium, Large, XL">
      ${index > 0 ? '<button type="button" class="dashboard-btn dashboard-btn-light" data-remove-attribute style="margin-top:6px;">Remove Attribute</button>' : ""}
    `;
    container.appendChild(row);

    const removeBtn = row.querySelector("[data-remove-attribute]");
    if (removeBtn) {
      removeBtn.addEventListener("click", function () {
        row.remove();
      });
    }
  }

  function resetVariationBuilder() {
    el("storeAttributesList").innerHTML = "";
    attributeRowCount = 0;
    addAttributeRow();

    el("storeVariationsBasePrice").value = "";
    generatedVariants = [];
    imageKeyAttribute = "";
    variantImagesByValue = {};
    el("storeVariantsGeneratedWrap").style.display = "none";
    el("storeVariantsGeneratedBody").innerHTML = "";
    el("storeVariantImagesSection").style.display = "none";
    el("storeVariantImagesBody").innerHTML = "";
    el("storeVariantImageAttribute").innerHTML = "";
  }

  function openModal(product) {
    uploadedImageUrl = product ? product.image || "" : "";
    uploadedDigitalFileUrl = product ? product.digital_file || "" : "";

    const isVariantTemplate = !!(product && product.has_variants);

    el("storeProductModalTitle").textContent = product ? "Edit Product" : "Add Product";
    el("storeProductItemCode").value = product ? product.name : "";
    el("storeProductName").value = product ? product.item_name : "";
    el("storeProductDescription").value = product ? product.description : "";
    el("storeProductShortDescription").value = product ? product.short_description || "" : "";
    el("storeProductShortDescriptionCount").textContent = el("storeProductShortDescription").value.length;
    el("storeProductGroup").value = product ? product.item_group : "";
    el("storeProductPrice").value = product ? product.price : "";
    // A new product defaults to unlimited (stock quantity stays hidden
    // until you actually untick this to say it's a fixed quantity) - an
    // existing product keeps showing whatever it was actually saved as.
    el("storeProductUnlimited").checked = product ? !!product.unlimited_stock : true;
    el("storeProductStockQty").value = product ? product.stock_qty || 0 : 0;
    el("storeProductDisabled").checked = !!(product && product.disabled);
    el("storeProductDisabledRow").style.display = product ? "" : "none";
    el("storeProductUnlocksCourse").value = product ? product.unlocks_course || "" : "";
    el("storeProductUnlocksCourseEnabled").checked = !!(product && product.unlocks_course);
    updateUnlocksCourseFieldVisibility();

    el("storeProductIsDigital").checked = !!(product && product.digital_file);
    updateDigitalFieldVisibility();

    const digitalLink = el("storeProductDigitalFileLink");
    if (uploadedDigitalFileUrl) {
      digitalLink.href = uploadedDigitalFileUrl;
      digitalLink.style.display = "";
    } else {
      digitalLink.style.display = "none";
    }
    el("storeProductDigitalFileInput").value = "";

    const preview = el("storeProductImagePreview");
    if (uploadedImageUrl) {
      preview.src = uploadedImageUrl;
      preview.style.display = "";
    } else {
      preview.style.display = "none";
    }
    el("storeProductImageFile").value = "";

    Object.keys(BRAND_LABELS).forEach((fieldname) => {
      const input = el(brandInputId(fieldname));
      if (input) input.checked = !!(product && product.brands && product.brands[fieldname]);
    });

    // Variations can only be set up when creating a new product - once a
    // template exists, its attributes are fixed and price/stock moves to
    // Manage Variants instead.
    resetVariationBuilder();
    el("storeProductHasVariations").checked = false;
    el("storeVariationsToggleRow").style.display = product ? "none" : "";
    updateVariationsVisibility();

    if (isVariantTemplate) {
      el("storeProductPriceField").style.display = "none";
      el("storeSimpleProductFields").style.display = "none";
    }

    updateStockFieldVisibility();

    el("storeProductModal").classList.add("is-open");
  }

  function closeModal() {
    el("storeProductModal").classList.remove("is-open");
  }

  // General N-way cartesian product - one attribute gives one combo per
  // value, two gives every pairing, and so on for however many
  // attributes were added.
  function buildCombinations(lists) {
    let combos = [{}];

    lists.forEach((attr) => {
      const next = [];
      combos.forEach((combo) => {
        attr.values.forEach((value) => {
          next.push(Object.assign({}, combo, { [attr.attribute]: value }));
        });
      });
      combos = next;
    });

    return combos;
  }

  function renderGeneratedVariants() {
    const basePrice = el("storeVariationsBasePrice").value || 0;

    const body = el("storeVariantsGeneratedBody");
    body.innerHTML = generatedVariants.map((combo, index) => {
      const label = Object.values(combo).join(" / ");
      return `
        <tr>
          <td>${escapeHtml(label)}</td>
          <td><input type="number" min="0" step="0.01" class="dashboard-input" style="width:90px;" value="${basePrice}" data-variant-price="${index}"></td>
          <td><input type="number" min="0" step="1" class="dashboard-input" style="width:70px;" value="0" data-variant-stock="${index}"></td>
          <td style="text-align:center;"><input type="checkbox" data-variant-unlimited="${index}"></td>
        </tr>
      `;
    }).join("");

    el("storeVariantsGeneratedWrap").style.display = generatedVariants.length ? "" : "none";
  }

  // Reads every currently added attribute row (however many there are).
  function attributeValueLists() {
    const rows = Array.from(document.querySelectorAll("#storeAttributesList .store-attribute-row"));

    return rows.map((row) => ({
      attribute: row.querySelector("[data-attribute-name]").value.trim(),
      values: row.querySelector("[data-attribute-values]").value.split(",").map((v) => v.trim()).filter(Boolean),
    })).filter((attr) => attr.attribute && attr.values.length);
  }

  // One photo per value of a single chosen attribute (e.g. one per
  // Style), reused across every combination that shares that value -
  // avoids needing a separate photo for every Size x Style pair.
  function renderVariantImageRows() {
    const lists = attributeValueLists();
    const select = el("storeVariantImageAttribute");
    select.innerHTML = lists.map((a) => `<option value="${escapeHtml(a.attribute)}">${escapeHtml(a.attribute)}</option>`).join("");

    // Default to the last (most likely visually distinct, e.g. Style
    // over Size) attribute when there's more than one.
    imageKeyAttribute = lists[lists.length - 1].attribute;
    select.value = imageKeyAttribute;

    variantImagesByValue = {};
    renderVariantImageValueRows();
    el("storeVariantImagesSection").style.display = "";
  }

  function renderVariantImageValueRows() {
    const lists = attributeValueLists();
    const chosen = lists.find((a) => a.attribute === imageKeyAttribute) || lists[0];
    const body = el("storeVariantImagesBody");

    body.innerHTML = (chosen ? chosen.values : []).map((value) => `
      <div style="display:flex; align-items:center; gap:10px; margin-bottom:8px;">
        <span style="min-width:120px;">${escapeHtml(value)}</span>
        <input type="file" accept="image/*" data-variant-image-value="${escapeHtml(value)}">
        <img data-variant-image-value-preview="${escapeHtml(value)}" alt="" style="display:none; width:36px; height:36px; object-fit:cover; border-radius:6px;">
      </div>
    `).join("");
  }

  function generateVariants() {
    const lists = attributeValueLists();

    if (!lists.length) {
      alert("Enter at least one attribute's name and values.");
      return;
    }

    generatedVariants = buildCombinations(lists);
    renderGeneratedVariants();
    renderVariantImageRows();
  }

  async function uploadVariantImagesByValue() {
    const inputs = document.querySelectorAll("[data-variant-image-value]");

    for (const input of inputs) {
      const file = input.files[0];
      if (!file) continue;

      const value = input.dataset.variantImageValue;
      const uploaded = await uploadFile(file, false);
      variantImagesByValue[value] = uploaded.file_url || "";
    }
  }

  function collectVariantSpecs() {
    return generatedVariants.map((combo, index) => {
      const priceInput = document.querySelector(`[data-variant-price="${index}"]`);
      const stockInput = document.querySelector(`[data-variant-stock="${index}"]`);
      const unlimitedInput = document.querySelector(`[data-variant-unlimited="${index}"]`);
      const keyValue = combo[imageKeyAttribute];

      return {
        attribute_values: combo,
        price: priceInput ? priceInput.value : 0,
        stock_qty: stockInput ? stockInput.value : 0,
        unlimited_stock: unlimitedInput ? unlimitedInput.checked : false,
        image: keyValue ? (variantImagesByValue[keyValue] || "") : "",
      };
    });
  }

  async function saveProduct() {
    const saveBtn = el("saveStoreProduct");
    const itemCode = el("storeProductItemCode").value;
    const itemName = el("storeProductName").value.trim();
    const hasVariations = !itemCode && el("storeProductHasVariations").checked;

    if (!itemName) {
      alert("Please enter a product name.");
      return;
    }

    if (hasVariations && !generatedVariants.length) {
      alert('Click "Generate Combinations" before saving a product with variations.');
      return;
    }

    saveBtn.disabled = true;
    saveBtn.textContent = "Saving…";

    try {
      const imageFile = el("storeProductImageFile").files[0];
      if (imageFile) {
        const uploaded = await uploadFile(imageFile, false);
        uploadedImageUrl = uploaded.file_url || uploadedImageUrl;
      }

      if (hasVariations) {
        await uploadVariantImagesByValue();

        await apiPost(API + ".create_variant_store_product", {
          item_name: itemName,
          description: el("storeProductDescription").value,
          short_description: el("storeProductShortDescription").value,
          item_group: el("storeProductGroup").value,
          brands: collectBrands(),
          image: uploadedImageUrl,
          attributes: attributeValueLists(),
          variants: collectVariantSpecs(),
        });
      } else {
        const isDigital = el("storeProductIsDigital").checked;
        const unlocksCourseEnabled = el("storeProductUnlocksCourseEnabled").checked;

        if (isDigital) {
          const digitalFile = el("storeProductDigitalFileInput").files[0];
          if (digitalFile) {
            const uploaded = await uploadFile(digitalFile, true);
            uploadedDigitalFileUrl = uploaded.file_url || uploadedDigitalFileUrl;
          }
        } else {
          uploadedDigitalFileUrl = "";
        }

        const payload = {
          item_name: itemName,
          description: el("storeProductDescription").value,
          short_description: el("storeProductShortDescription").value,
          item_group: el("storeProductGroup").value,
          brands: collectBrands(),
          image: uploadedImageUrl,
        };

        const isVariantTemplate = itemCode && products.some((p) => p.name === itemCode && p.has_variants);

        if (!isVariantTemplate) {
          payload.price = el("storeProductPrice").value || 0;
          payload.unlimited_stock = el("storeProductUnlimited").checked;
          payload.stock_qty = el("storeProductStockQty").value || 0;
          payload.digital_file = isDigital ? uploadedDigitalFileUrl : "";
          payload.unlocks_course = unlocksCourseEnabled ? el("storeProductUnlocksCourse").value : "";
        }

        if (itemCode) {
          payload.item_code = itemCode;
          payload.disabled = el("storeProductDisabled").checked;
          await apiPost(API + ".update_store_product", payload);
        } else {
          await apiPost(API + ".create_store_product", payload);
        }
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

  // ---------------------------------------------------------------
  // Manage Variants modal (existing variant templates only)
  // ---------------------------------------------------------------

  function renderVariantRow(variant) {
    const label = Object.values(variant.attributes || {}).join(" / ") || variant.item_name;
    const preview = variant.image
      ? `<img src="${escapeHtml(variant.image)}" alt="" data-existing-variant-image-preview="${escapeHtml(variant.name)}" style="width:36px; height:36px; object-fit:cover; border-radius:6px; display:block; margin-bottom:4px;">`
      : `<img alt="" data-existing-variant-image-preview="${escapeHtml(variant.name)}" style="width:36px; height:36px; object-fit:cover; border-radius:6px; display:none; margin-bottom:4px;">`;

    return `
      <tr data-variant-row="${escapeHtml(variant.name)}">
        <td>${escapeHtml(label)}</td>
        <td>
          ${preview}
          <input type="file" accept="image/*" data-existing-variant-image-input="${escapeHtml(variant.name)}">
        </td>
        <td><input type="number" min="0" step="0.01" class="dashboard-input" style="width:90px;" value="${variant.price || 0}" data-existing-variant-price="${escapeHtml(variant.name)}"></td>
        <td><input type="number" min="0" step="1" class="dashboard-input" style="width:70px;" value="${variant.stock_qty || 0}" data-existing-variant-stock="${escapeHtml(variant.name)}" ${variant.unlimited_stock ? "disabled" : ""}></td>
        <td style="text-align:center;"><input type="checkbox" data-existing-variant-unlimited="${escapeHtml(variant.name)}" ${variant.unlimited_stock ? "checked" : ""}></td>
        <td style="text-align:center;"><input type="checkbox" data-existing-variant-active="${escapeHtml(variant.name)}" ${variant.disabled ? "" : "checked"}></td>
        <td><button type="button" class="dashboard-btn dashboard-btn-light" data-save-variant="${escapeHtml(variant.name)}">Save</button></td>
      </tr>
    `;
  }

  async function openVariantsModal(templateItemCode) {
    el("storeVariantsTemplateCode").value = templateItemCode;
    const body = el("storeVariantsBody");
    body.innerHTML = '<tr><td colspan="7" class="dashboard-empty">Loading…</td></tr>';
    el("storeVariantsModal").classList.add("is-open");

    try {
      const variants = await apiPost(API + ".get_product_variants", { template_item_code: templateItemCode });
      body.innerHTML = variants.length
        ? variants.map(renderVariantRow).join("")
        : '<tr><td colspan="7" class="dashboard-empty">No variants found.</td></tr>';
    } catch (error) {
      body.innerHTML = '<tr><td colspan="7" class="dashboard-empty">Could not load variants.</td></tr>';
      console.error(error);
    }
  }

  function closeVariantsModal() {
    el("storeVariantsModal").classList.remove("is-open");
  }

  async function saveVariantRow(itemCode, button) {
    const priceInput = document.querySelector(`[data-existing-variant-price="${CSS.escape(itemCode)}"]`);
    const stockInput = document.querySelector(`[data-existing-variant-stock="${CSS.escape(itemCode)}"]`);
    const unlimitedInput = document.querySelector(`[data-existing-variant-unlimited="${CSS.escape(itemCode)}"]`);
    const activeInput = document.querySelector(`[data-existing-variant-active="${CSS.escape(itemCode)}"]`);
    const imageInput = document.querySelector(`[data-existing-variant-image-input="${CSS.escape(itemCode)}"]`);

    button.disabled = true;
    button.textContent = "Saving…";

    try {
      let imageUrl = "";
      const imageFile = imageInput ? imageInput.files[0] : null;
      if (imageFile) {
        const uploaded = await uploadFile(imageFile, false);
        imageUrl = uploaded.file_url || "";
      }

      await apiPost(API + ".update_variant", {
        item_code: itemCode,
        price: priceInput ? priceInput.value : 0,
        stock_qty: stockInput ? stockInput.value : 0,
        unlimited_stock: unlimitedInput ? unlimitedInput.checked : false,
        disabled: activeInput ? !activeInput.checked : false,
        image: imageUrl,
      });
      button.textContent = "Saved";
      window.setTimeout(() => {
        button.textContent = "Save";
        button.disabled = false;
      }, 1200);
    } catch (error) {
      alert(error.message || "Could not save this variant.");
      button.disabled = false;
      button.textContent = "Save";
    }
  }

  // ---------------------------------------------------------------
  // Init
  // ---------------------------------------------------------------

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
    loadLmsCourses();
    initSearch();

    el("addProductBtn").addEventListener("click", () => openModal(null));
    el("closeStoreProductModal").addEventListener("click", closeModal);
    el("cancelStoreProductModal").addEventListener("click", closeModal);
    el("saveStoreProduct").addEventListener("click", saveProduct);
    el("storeProductUnlimited").addEventListener("change", updateStockFieldVisibility);
    el("storeProductHasVariations").addEventListener("change", updateVariationsVisibility);
    el("storeProductIsDigital").addEventListener("change", updateDigitalFieldVisibility);
    el("storeProductUnlocksCourseEnabled").addEventListener("change", updateUnlocksCourseFieldVisibility);
    el("generateVariantsBtn").addEventListener("click", generateVariants);
    el("addAttributeBtn").addEventListener("click", addAttributeRow);

    // Changing the starting price after combinations are already
    // generated fills every row instead of only affecting ones
    // generated afterwards.
    el("storeVariationsBasePrice").addEventListener("input", function () {
      document.querySelectorAll("[data-variant-price]").forEach((input) => {
        input.value = this.value;
      });
    });

    el("closeStoreVariantsModal").addEventListener("click", closeVariantsModal);
    el("closeStoreVariantsModalBtn").addEventListener("click", closeVariantsModal);

    el("storeProductImageFile").addEventListener("change", function () {
      const file = this.files[0];
      if (!file) return;
      const preview = el("storeProductImagePreview");
      preview.src = URL.createObjectURL(file);
      preview.style.display = "";
    });

    el("storeProductShortDescription").addEventListener("input", function () {
      el("storeProductShortDescriptionCount").textContent = this.value.length;
    });

    el("storeVariantImageAttribute").addEventListener("change", function () {
      imageKeyAttribute = this.value;
      renderVariantImageValueRows();
    });

    document.addEventListener("change", function (event) {
      const variantImageInput = event.target.closest("[data-variant-image-value]");
      if (variantImageInput) {
        const file = variantImageInput.files[0];
        if (!file) return;

        const preview = document.querySelector(
          `[data-variant-image-value-preview="${CSS.escape(variantImageInput.dataset.variantImageValue)}"]`
        );
        if (preview) {
          preview.src = URL.createObjectURL(file);
          preview.style.display = "";
        }
        return;
      }

      const existingUnlimited = event.target.closest("[data-existing-variant-unlimited]");
      if (existingUnlimited) {
        const stockInput = document.querySelector(
          `[data-existing-variant-stock="${CSS.escape(existingUnlimited.dataset.existingVariantUnlimited)}"]`
        );
        if (stockInput) stockInput.disabled = existingUnlimited.checked;
        return;
      }

      const newVariantUnlimited = event.target.closest("[data-variant-unlimited]");
      if (newVariantUnlimited) {
        const stockInput = document.querySelector(
          `[data-variant-stock="${newVariantUnlimited.dataset.variantUnlimited}"]`
        );
        if (stockInput) stockInput.disabled = newVariantUnlimited.checked;
      }
    });

    document.addEventListener("click", function (event) {
      const editBtn = event.target.closest("[data-edit-product]");
      if (editBtn) {
        const product = products.find((p) => p.name === editBtn.dataset.editProduct);
        if (product) openModal(product);
        return;
      }

      const manageVariantsBtn = event.target.closest("[data-manage-variants]");
      if (manageVariantsBtn) {
        openVariantsModal(manageVariantsBtn.dataset.manageVariants);
        return;
      }

      const saveStockBtn = event.target.closest("[data-save-stock]");
      if (saveStockBtn) {
        saveStock(saveStockBtn.dataset.saveStock, saveStockBtn);
        return;
      }

      const saveVariantBtn = event.target.closest("[data-save-variant]");
      if (saveVariantBtn) {
        saveVariantRow(saveVariantBtn.dataset.saveVariant, saveVariantBtn);
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initPage);
  } else {
    initPage();
  }
})();
