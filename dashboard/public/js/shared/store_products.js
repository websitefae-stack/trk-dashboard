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
  // Each row is {url} for an already-uploaded photo or {file} for one
  // picked but not yet uploaded - both render as a thumbnail, only
  // {file} rows get uploaded (turning into {url}) at save time.
  let galleryItems = [];
  let generatedVariants = [];
  // Which attribute(s) actually change what a photo looks like (e.g.
  // Colour + Print Colour + Slogan, but not Size) - one photo is then
  // needed per unique combination of just those, reused across every
  // value of whichever attributes were left unticked.
  let imageKeyAttributes = [];
  let variantImagesByCombo = {};
  let descriptionEditor = null;

  // Manage Variants modal (editing an existing variant product) - its
  // own equivalent of the three above, since it's a separate flow with
  // its own state: the variants currently loaded, which attributes the
  // bulk photo picker is grouping by, and any photo already uploaded
  // and applied to a row (via that bulk picker) but not yet saved.
  let currentManageVariants = [];
  let manageVariantsImageAttributes = [];
  let pendingVariantImageUrls = {};

  // A separator unlikely to ever appear inside an attribute value itself
  // (a colour name, a slogan, ...) - joins the chosen key attributes'
  // values into one lookup key for variantImagesByCombo.
  const COMBO_KEY_SEPARATOR = "␟";

  function comboKeyFor(combo, attributes) {
    return attributes.map((attribute) => combo[attribute] || "").join(COMBO_KEY_SEPARATOR);
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

  function renderLogoOptionRow(choice) {
    const preview = choice.image
      ? `<img src="${escapeHtml(choice.image)}" alt="" data-logo-option-preview="${escapeHtml(choice.key)}" style="width:80px; height:80px; object-fit:contain; border-radius:8px; border:1px solid #E6EFEF; display:block; margin-bottom:6px;">`
      : `<img alt="" data-logo-option-preview="${escapeHtml(choice.key)}" style="width:80px; height:80px; object-fit:contain; border-radius:8px; border:1px solid #E6EFEF; display:none; margin-bottom:6px;">`;

    return `
      <div style="width:120px;">
        ${preview}
        <div style="font-weight:700; margin-bottom:4px;">${escapeHtml(choice.label)}</div>
        <input type="file" accept="image/*" data-logo-option-input="${escapeHtml(choice.key)}">
        <span class="dashboard-help" data-logo-option-status="${escapeHtml(choice.key)}"></span>
      </div>
    `;
  }

  async function loadLogoOptions() {
    const list = el("logoOptionsList");
    if (!list) return;

    try {
      const options = await apiPost("dashboard.api.shared.webshop_purchase.get_logo_choice_options", {});
      list.innerHTML = options.map(renderLogoOptionRow).join("");
    } catch (error) {
      list.innerHTML = '<p class="dashboard-help">Could not load logo options.</p>';
      console.error(error);
    }
  }

  async function saveLogoOption(key, input) {
    const file = input.files[0];
    if (!file) return;

    const statusEl = document.querySelector(`[data-logo-option-status="${CSS.escape(key)}"]`);
    if (statusEl) statusEl.textContent = "Uploading…";

    try {
      const uploaded = await uploadFile(file, false);
      const url = uploaded.file_url || "";

      await apiPost("dashboard.api.shared.store_products.save_logo_choice_options", {
        [`${key.toLowerCase()}_logo`]: url,
      });

      const preview = document.querySelector(`[data-logo-option-preview="${CSS.escape(key)}"]`);
      if (preview) {
        preview.src = url;
        preview.style.display = "";
      }
      if (statusEl) statusEl.textContent = "Saved.";
    } catch (error) {
      if (statusEl) statusEl.textContent = error.message || "Could not upload.";
    }
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

  function updatePersonalizationFieldVisibility() {
    el("storeProductPersonalizationLabelField").style.display = el("storeProductPersonalizationEnabled").checked ? "" : "none";
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
    imageKeyAttributes = [];
    variantImagesByCombo = {};
    el("storeVariantsGeneratedWrap").style.display = "none";
    el("storeVariantsGeneratedBody").innerHTML = "";
    el("storeVariantImagesSection").style.display = "none";
    el("storeVariantImagesBody").innerHTML = "";
    el("storeVariantImageAttributesList").innerHTML = "";
  }

  function renderGalleryList() {
    const container = el("storeProductGalleryList");
    if (!container) return;

    container.innerHTML = galleryItems.map((item, index) => {
      const src = item.url || (item.objectUrl || (item.objectUrl = URL.createObjectURL(item.file)));
      return `
        <div style="position:relative;">
          <img src="${src}" alt="" style="width:60px; height:60px; object-fit:cover; border-radius:8px; display:block;">
          <button type="button" data-remove-gallery-item="${index}"
            style="position:absolute; top:-6px; right:-6px; width:20px; height:20px; border-radius:50%; border:none; background:#C0392B; color:#fff; font-size:12px; line-height:1; cursor:pointer;">×</button>
        </div>
      `;
    }).join("");
  }

  async function openModal(product) {
    uploadedImageUrl = product ? product.image || "" : "";
    uploadedDigitalFileUrl = product ? product.digital_file || "" : "";

    galleryItems = [];
    renderGalleryList();
    if (product) {
      try {
        const urls = await apiPost(`${API}.get_product_gallery`, { item_code: product.name });
        galleryItems = (urls || []).map((url) => ({ url }));
        renderGalleryList();
      } catch (error) {
        console.error("Could not load gallery photos", error);
      }
    }

    const isVariantTemplate = !!(product && product.has_variants);

    el("storeProductModalTitle").textContent = product ? "Edit Product" : "Add Product";
    el("storeProductItemCode").value = product ? product.name : "";
    el("storeProductName").value = product ? product.item_name : "";
    el("storeProductSku").value = product ? product.sku || "" : "";
    if (descriptionEditor) descriptionEditor.setHtml(product ? product.description || "" : "");
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

    el("storeProductPersonalizationEnabled").checked = !!(product && product.personalization_enabled);
    el("storeProductPersonalizationLabel").value = product ? product.personalization_label || "" : "";
    updatePersonalizationFieldVisibility();

    el("storeProductLogoChoiceEnabled").checked = !!(product && product.logo_choice_enabled);

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
          <td><input type="text" class="dashboard-input" style="width:110px;" value="" data-variant-sku="${index}" placeholder="Optional"></td>
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

  // One photo per unique combination of whichever attribute(s) are
  // ticked below as "changes the photo" (e.g. Colour + Print Colour +
  // Slogan), reused across every value of any attribute left unticked
  // (e.g. Size) - avoids needing a separate photo for every single
  // generated combination.
  function renderVariantImageRows() {
    const lists = attributeValueLists();
    const checklist = el("storeVariantImageAttributesList");

    // Defaults to every attribute ticked - most products only have one
    // or two, where "all of them" is usually right; untick whichever
    // ones don't actually change the photo (e.g. Size).
    imageKeyAttributes = lists.map((a) => a.attribute);

    checklist.innerHTML = lists.map((a) => `
      <label style="display:flex; align-items:center; gap:6px; font-weight:normal;">
        <input type="checkbox" data-variant-image-attribute="${escapeHtml(a.attribute)}" checked>
        ${escapeHtml(a.attribute)}
      </label>
    `).join("");

    variantImagesByCombo = {};
    renderVariantImageGroupRows();
    el("storeVariantImagesSection").style.display = "";
  }

  function renderVariantImageGroupRows() {
    const body = el("storeVariantImagesBody");

    if (!imageKeyAttributes.length) {
      body.innerHTML = '<p class="dashboard-help">Tick at least one attribute above to upload photos for it.</p>';
      return;
    }

    const seen = new Set();
    const groups = [];

    generatedVariants.forEach((combo) => {
      const key = comboKeyFor(combo, imageKeyAttributes);
      if (seen.has(key)) return;
      seen.add(key);
      groups.push({ key, label: imageKeyAttributes.map((attribute) => combo[attribute]).join(" / ") });
    });

    body.innerHTML = groups.map((group) => `
      <div style="display:flex; align-items:center; gap:10px; margin-bottom:8px;">
        <span style="min-width:180px;">${escapeHtml(group.label)}</span>
        <input type="file" accept="image/*" data-variant-image-combo="${escapeHtml(group.key)}">
        <img data-variant-image-combo-preview="${escapeHtml(group.key)}" alt="" style="display:none; width:36px; height:36px; object-fit:cover; border-radius:6px;">
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

  async function uploadVariantImagesByCombo() {
    const inputs = document.querySelectorAll("[data-variant-image-combo]");

    for (const input of inputs) {
      const file = input.files[0];
      if (!file) continue;

      const key = input.dataset.variantImageCombo;
      const uploaded = await uploadFile(file, false);
      variantImagesByCombo[key] = uploaded.file_url || "";
    }
  }

  function collectVariantSpecs() {
    return generatedVariants.map((combo, index) => {
      const skuInput = document.querySelector(`[data-variant-sku="${index}"]`);
      const priceInput = document.querySelector(`[data-variant-price="${index}"]`);
      const stockInput = document.querySelector(`[data-variant-stock="${index}"]`);
      const unlimitedInput = document.querySelector(`[data-variant-unlimited="${index}"]`);
      const key = comboKeyFor(combo, imageKeyAttributes);

      return {
        attribute_values: combo,
        sku: skuInput ? skuInput.value : "",
        price: priceInput ? priceInput.value : 0,
        stock_qty: stockInput ? stockInput.value : 0,
        unlimited_stock: unlimitedInput ? unlimitedInput.checked : false,
        image: variantImagesByCombo[key] || "",
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

      for (const item of galleryItems) {
        if (item.file && !item.url) {
          const uploaded = await uploadFile(item.file, false);
          item.url = uploaded.file_url || "";
        }
      }
      const galleryUrls = galleryItems.map((item) => item.url).filter(Boolean);
      const personalizationEnabled = el("storeProductPersonalizationEnabled").checked;
      const personalizationLabel = el("storeProductPersonalizationLabel").value;
      const logoChoiceEnabled = el("storeProductLogoChoiceEnabled").checked;

      if (hasVariations) {
        await uploadVariantImagesByCombo();

        await apiPost(API + ".create_variant_store_product", {
          item_name: itemName,
          sku: el("storeProductSku").value,
          description: descriptionEditor ? descriptionEditor.getHtml() : "",
          short_description: el("storeProductShortDescription").value,
          item_group: el("storeProductGroup").value,
          brands: collectBrands(),
          image: uploadedImageUrl,
          gallery_images: galleryUrls,
          personalization_enabled: personalizationEnabled,
          personalization_label: personalizationLabel,
          logo_choice_enabled: logoChoiceEnabled,
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
          sku: el("storeProductSku").value,
          description: descriptionEditor ? descriptionEditor.getHtml() : "",
          short_description: el("storeProductShortDescription").value,
          item_group: el("storeProductGroup").value,
          brands: collectBrands(),
          image: uploadedImageUrl,
          gallery_images: galleryUrls,
          personalization_enabled: personalizationEnabled,
          personalization_label: personalizationLabel,
          logo_choice_enabled: logoChoiceEnabled,
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
        <td><input type="text" class="dashboard-input" style="width:110px;" value="${escapeHtml(variant.sku || "")}" data-existing-variant-sku="${escapeHtml(variant.name)}" placeholder="Optional"></td>
        <td><input type="number" min="0" step="0.01" class="dashboard-input" style="width:90px;" value="${variant.price || 0}" data-existing-variant-price="${escapeHtml(variant.name)}"></td>
        <td><input type="number" min="0" step="1" class="dashboard-input" style="width:70px;" value="${variant.stock_qty || 0}" data-existing-variant-stock="${escapeHtml(variant.name)}" ${variant.unlimited_stock ? "disabled" : ""}></td>
        <td style="text-align:center;"><input type="checkbox" data-existing-variant-unlimited="${escapeHtml(variant.name)}" ${variant.unlimited_stock ? "checked" : ""}></td>
        <td style="text-align:center;"><input type="checkbox" data-existing-variant-active="${escapeHtml(variant.name)}" ${variant.disabled ? "" : "checked"}></td>
        <td>
          <button type="button" class="dashboard-btn dashboard-btn-light" data-save-variant="${escapeHtml(variant.name)}">Save</button>
          <button type="button" class="dashboard-btn dashboard-btn-light" style="color:#B3261E;" data-delete-variant="${escapeHtml(variant.name)}">Delete</button>
        </td>
      </tr>
    `;
  }

  // Every attribute name/value actually used across the currently
  // loaded variants (e.g. Size, Colour, Print Colour, Slogan) - the
  // checklist for the bulk photo picker is built from this, same idea
  // as attributeValueLists() for the create-time version above.
  function manageVariantsAttributeLists() {
    const byAttribute = {};

    currentManageVariants.forEach((variant) => {
      Object.entries(variant.attributes || {}).forEach(([attribute, value]) => {
        byAttribute[attribute] = byAttribute[attribute] || [];
        if (byAttribute[attribute].indexOf(value) === -1) byAttribute[attribute].push(value);
      });
    });

    return Object.keys(byAttribute).map((attribute) => ({ attribute, values: byAttribute[attribute] }));
  }

  function renderManageVariantsImageAttributes() {
    const lists = manageVariantsAttributeLists();
    const section = el("manageVariantsImagesSection");

    if (!lists.length) {
      section.style.display = "none";
      return;
    }

    manageVariantsImageAttributes = lists.map((a) => a.attribute);

    el("manageVariantsImageAttributesList").innerHTML = lists.map((a) => `
      <label style="display:flex; align-items:center; gap:6px; font-weight:normal;">
        <input type="checkbox" data-manage-variants-image-attribute="${escapeHtml(a.attribute)}" checked>
        ${escapeHtml(a.attribute)}
      </label>
    `).join("");

    renderManageVariantsImageGroups();
    section.style.display = "";
  }

  function renderManageVariantsImageGroups() {
    const body = el("manageVariantsImagesBody");

    if (!manageVariantsImageAttributes.length) {
      body.innerHTML = '<p class="dashboard-help">Tick at least one attribute above to upload photos for it.</p>';
      return;
    }

    const seen = new Set();
    const groups = [];

    currentManageVariants.forEach((variant) => {
      const key = comboKeyFor(variant.attributes || {}, manageVariantsImageAttributes);
      if (seen.has(key)) return;
      seen.add(key);
      groups.push({ key, label: manageVariantsImageAttributes.map((a) => variant.attributes[a]).join(" / ") });
    });

    body.innerHTML = groups.map((group) => `
      <div style="display:flex; align-items:center; gap:10px; margin-bottom:8px;">
        <span style="min-width:180px;">${escapeHtml(group.label)}</span>
        <input type="file" accept="image/*" data-manage-variants-image-combo="${escapeHtml(group.key)}">
        <button type="button" class="dashboard-btn dashboard-btn-light" data-apply-variant-image-combo="${escapeHtml(group.key)}">Apply to matching variants</button>
        <span class="dashboard-help" data-manage-variants-image-status="${escapeHtml(group.key)}"></span>
      </div>
    `).join("");
  }

  async function applyManageVariantsImageCombo(key, button) {
    const input = document.querySelector(`[data-manage-variants-image-combo="${CSS.escape(key)}"]`);
    const statusEl = document.querySelector(`[data-manage-variants-image-status="${CSS.escape(key)}"]`);
    const file = input ? input.files[0] : null;

    if (!file) {
      alert("Choose a photo first.");
      return;
    }

    button.disabled = true;
    if (statusEl) statusEl.textContent = "Uploading…";

    try {
      const uploaded = await uploadFile(file, false);
      const url = uploaded.file_url || "";
      let matched = 0;

      currentManageVariants.forEach((variant) => {
        if (comboKeyFor(variant.attributes || {}, manageVariantsImageAttributes) !== key) return;

        matched += 1;
        pendingVariantImageUrls[variant.name] = url;

        const preview = document.querySelector(`[data-existing-variant-image-preview="${CSS.escape(variant.name)}"]`);
        if (preview) {
          preview.src = url;
          preview.style.display = "";
        }
      });

      if (statusEl) statusEl.textContent = `Applied to ${matched} variant${matched === 1 ? "" : "s"} - click Save/Save All to keep it.`;
    } catch (error) {
      if (statusEl) statusEl.textContent = error.message || "Could not upload.";
    } finally {
      button.disabled = false;
    }
  }

  function renderAddVariantAttributes() {
    const container = el("addVariantAttributesList");
    if (!container) return;

    const lists = manageVariantsAttributeLists();

    container.innerHTML = lists.map((a) => {
      const listId = "addVariantValues_" + a.attribute.replace(/[^a-zA-Z0-9]/g, "");
      return `
        <div>
          <label style="display:block; font-weight:normal; margin-bottom:2px;">${escapeHtml(a.attribute)}</label>
          <input type="text" class="dashboard-input" style="width:140px;" list="${listId}" data-add-variant-attribute="${escapeHtml(a.attribute)}" placeholder="${escapeHtml(a.attribute)}">
          <datalist id="${listId}">${a.values.map((v) => `<option value="${escapeHtml(v)}"></option>`).join("")}</datalist>
        </div>
      `;
    }).join("");
  }

  function bulkAddVariantsAttributeInputs() {
    return Array.from(document.querySelectorAll("[data-bulk-add-variant-attribute]"));
  }

  function renderBulkAddVariantsAttributes() {
    const container = el("bulkAddVariantsAttributesList");
    if (!container) return;

    const lists = manageVariantsAttributeLists();

    container.innerHTML = lists.map((a) => `
      <div>
        <label style="display:block; font-weight:normal; margin-bottom:2px;">${escapeHtml(a.attribute)}</label>
        <input type="text" class="dashboard-input" style="width:100%;"
          data-bulk-add-variant-attribute="${escapeHtml(a.attribute)}"
          placeholder="Comma separated, e.g. ${escapeHtml(a.values.slice(0, 3).join(", ") || "Red, Blue, Green")}">
      </div>
    `).join("");

    updateBulkAddVariantsCount();
  }

  function parseBulkAddVariantsValues() {
    const values = {};

    bulkAddVariantsAttributeInputs().forEach((input) => {
      values[input.dataset.bulkAddVariantAttribute] = input.value
        .split(",")
        .map((v) => v.trim())
        .filter(Boolean);
    });

    return values;
  }

  function updateBulkAddVariantsCount() {
    const countEl = el("bulkAddVariantsCount");
    if (!countEl) return;

    const values = parseBulkAddVariantsValues();
    const lists = Object.values(values);

    if (!lists.length || lists.some((list) => !list.length)) {
      countEl.textContent = "";
      return;
    }

    const total = lists.reduce((acc, list) => acc * list.length, 1);
    countEl.textContent = `${total} combination${total === 1 ? "" : "s"} (existing ones are skipped automatically).`;
  }

  async function bulkAddVariants() {
    const templateItemCode = el("storeVariantsTemplateCode").value;
    const values = parseBulkAddVariantsValues();
    const missing = Object.entries(values).filter(([, list]) => !list.length).map(([attr]) => attr);

    const statusEl = el("bulkAddVariantsStatus");

    if (missing.length) {
      statusEl.textContent = `Add at least one value for: ${missing.join(", ")}.`;
      return;
    }

    const btn = el("bulkAddVariantsBtn");
    btn.disabled = true;
    statusEl.textContent = "Adding…";

    try {
      const result = await apiPost(API + ".add_product_variants_bulk", {
        template_item_code: templateItemCode,
        attribute_value_lists: JSON.stringify(values),
        price: el("bulkAddVariantsPrice").value,
        stock_qty: el("bulkAddVariantsStock").value,
        unlimited_stock: el("bulkAddVariantsUnlimited").checked,
      });

      await openVariantsModal(templateItemCode);

      const parts = [`Added ${result.created_count} new variant${result.created_count === 1 ? "" : "s"}.`];
      if (result.skipped_count) parts.push(`${result.skipped_count} already existed and were skipped.`);
      const refreshedStatusEl = el("bulkAddVariantsStatus");
      if (refreshedStatusEl) refreshedStatusEl.textContent = parts.join(" ");

      const content = el("bulkAddVariantsContent");
      if (content) content.style.display = "";
      const icon = el("bulkAddVariantsToggleIcon");
      if (icon) icon.textContent = "▾";
    } catch (error) {
      statusEl.textContent = error.message || "Could not add these variants.";
    } finally {
      btn.disabled = false;
    }
  }

  async function addNewVariant() {
    const templateItemCode = el("storeVariantsTemplateCode").value;
    const attributeInputs = Array.from(document.querySelectorAll("[data-add-variant-attribute]"));
    const attributeValues = {};
    const missing = [];

    attributeInputs.forEach((input) => {
      const value = input.value.trim();
      if (value) {
        attributeValues[input.dataset.addVariantAttribute] = value;
      } else {
        missing.push(input.dataset.addVariantAttribute);
      }
    });

    const statusEl = el("addVariantStatus");

    if (missing.length) {
      statusEl.textContent = `Fill in: ${missing.join(", ")}.`;
      return;
    }

    const btn = el("addVariantBtn");
    btn.disabled = true;
    statusEl.textContent = "Adding…";

    try {
      let imageUrl = "";
      const imageFile = el("addVariantImage").files[0];
      if (imageFile) {
        const uploaded = await uploadFile(imageFile, false);
        imageUrl = uploaded.file_url || "";
      }

      await apiPost(API + ".add_product_variant", {
        template_item_code: templateItemCode,
        attribute_values: JSON.stringify(attributeValues),
        price: el("addVariantPrice").value,
        stock_qty: el("addVariantStock").value,
        unlimited_stock: el("addVariantUnlimited").checked,
        sku: el("addVariantSku").value,
        image: imageUrl,
      });

      await openVariantsModal(templateItemCode);
      el("addVariantStatus").textContent = "Added.";
    } catch (error) {
      statusEl.textContent = error.message || "Could not add this variant.";
    } finally {
      btn.disabled = false;
    }
  }

  async function openVariantsModal(templateItemCode) {
    el("storeVariantsTemplateCode").value = templateItemCode;
    const body = el("storeVariantsBody");
    body.innerHTML = '<tr><td colspan="8" class="dashboard-empty">Loading…</td></tr>';
    el("manageVariantsImagesSection").style.display = "none";
    el("manageVariantsImagesContent").style.display = "none";
    el("manageVariantsImagesToggleIcon").textContent = "▸";
    pendingVariantImageUrls = {};
    el("addVariantSku").value = "";
    el("addVariantPrice").value = "";
    el("addVariantStock").value = "";
    el("addVariantUnlimited").checked = false;
    el("addVariantImage").value = "";
    el("addVariantStatus").textContent = "";
    el("bulkAddVariantsPrice").value = "";
    el("bulkAddVariantsStock").value = "";
    el("bulkAddVariantsUnlimited").checked = false;
    el("bulkAddVariantsStatus").textContent = "";
    el("storeVariantsModal").classList.add("is-open");

    try {
      const variants = await apiPost(API + ".get_product_variants", { template_item_code: templateItemCode });
      currentManageVariants = variants;
      body.innerHTML = variants.length
        ? variants.map(renderVariantRow).join("")
        : '<tr><td colspan="8" class="dashboard-empty">No variants found.</td></tr>';
      renderManageVariantsImageAttributes();
      renderAddVariantAttributes();
      renderBulkAddVariantsAttributes();
    } catch (error) {
      body.innerHTML = '<tr><td colspan="8" class="dashboard-empty">Could not load variants.</td></tr>';
      console.error(error);
    }
  }

  function closeVariantsModal() {
    el("storeVariantsModal").classList.remove("is-open");
    currentManageVariants = [];
    pendingVariantImageUrls = {};
  }

  async function saveOneVariant(itemCode) {
    const skuInput = document.querySelector(`[data-existing-variant-sku="${CSS.escape(itemCode)}"]`);
    const priceInput = document.querySelector(`[data-existing-variant-price="${CSS.escape(itemCode)}"]`);
    const stockInput = document.querySelector(`[data-existing-variant-stock="${CSS.escape(itemCode)}"]`);
    const unlimitedInput = document.querySelector(`[data-existing-variant-unlimited="${CSS.escape(itemCode)}"]`);
    const activeInput = document.querySelector(`[data-existing-variant-active="${CSS.escape(itemCode)}"]`);
    const imageInput = document.querySelector(`[data-existing-variant-image-input="${CSS.escape(itemCode)}"]`);

    // A photo already applied via the bulk "Apply to matching variants"
    // picker above wins over this row's own file input - it's already
    // uploaded, no need to ask the browser to pick a file too.
    let imageUrl = pendingVariantImageUrls[itemCode] || "";

    if (!imageUrl) {
      const imageFile = imageInput ? imageInput.files[0] : null;
      if (imageFile) {
        const uploaded = await uploadFile(imageFile, false);
        imageUrl = uploaded.file_url || "";
      }
    }

    await apiPost(API + ".update_variant", {
      item_code: itemCode,
      sku: skuInput ? skuInput.value : "",
      price: priceInput ? priceInput.value : 0,
      stock_qty: stockInput ? stockInput.value : 0,
      unlimited_stock: unlimitedInput ? unlimitedInput.checked : false,
      disabled: activeInput ? !activeInput.checked : false,
      image: imageUrl,
    });

    delete pendingVariantImageUrls[itemCode];
  }

  async function saveVariantRow(itemCode, button) {
    button.disabled = true;
    button.textContent = "Saving…";

    try {
      await saveOneVariant(itemCode);
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

  async function deleteVariantRow(itemCode, button) {
    const row = document.querySelector(`[data-variant-row="${CSS.escape(itemCode)}"]`);
    const label = row ? row.querySelector("td")?.textContent : itemCode;

    if (!confirm(`Delete "${label}"? This permanently removes it - it can't be undone. If it's ever been ordered, deleting it will be blocked; mark it inactive instead in that case.`)) {
      return;
    }

    button.disabled = true;
    button.textContent = "Deleting…";

    try {
      await apiPost(API + ".delete_variant", { item_code: itemCode });
      currentManageVariants = currentManageVariants.filter((v) => v.name !== itemCode);
      delete pendingVariantImageUrls[itemCode];
      if (row) row.remove();
      if (!currentManageVariants.length) {
        el("storeVariantsBody").innerHTML = '<tr><td colspan="8" class="dashboard-empty">No variants found.</td></tr>';
      }
      renderManageVariantsImageAttributes();
      renderAddVariantAttributes();
    } catch (error) {
      alert(error.message || "Could not delete this variant.");
      button.disabled = false;
      button.textContent = "Delete";
    }
  }

  async function saveAllVariants() {
    const rows = Array.from(document.querySelectorAll("[data-variant-row]"));
    if (!rows.length) return;

    const saveAllBtn = el("saveAllVariantsBtn");
    const statusEl = el("saveAllVariantsStatus");

    saveAllBtn.disabled = true;
    const failed = [];

    for (let i = 0; i < rows.length; i++) {
      const itemCode = rows[i].dataset.variantRow;
      const rowButton = document.querySelector(`[data-save-variant="${CSS.escape(itemCode)}"]`);

      statusEl.textContent = `Saving ${i + 1} of ${rows.length}…`;
      if (rowButton) { rowButton.disabled = true; rowButton.textContent = "Saving…"; }

      try {
        await saveOneVariant(itemCode);
        if (rowButton) rowButton.textContent = "Saved";
      } catch (error) {
        failed.push(itemCode);
        if (rowButton) rowButton.textContent = "Save";
      } finally {
        if (rowButton) rowButton.disabled = false;
      }
    }

    saveAllBtn.disabled = false;
    statusEl.textContent = failed.length
      ? `Saved ${rows.length - failed.length} of ${rows.length} - ${failed.length} failed, see above.`
      : `Saved all ${rows.length} variant${rows.length === 1 ? "" : "s"}.`;

    window.setTimeout(() => { statusEl.textContent = ""; }, 4000);
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

    const descriptionContainer = el("storeProductDescriptionEditor");
    if (descriptionContainer) {
      descriptionContainer.innerHTML = Dashboard.richTextEditorHtml("Describe this product…");
      descriptionEditor = Dashboard.wireRichTextEditor(descriptionContainer.querySelector(".dashboard-richtext"));
    }

    loadProducts();
    loadItemGroups();
    loadLmsCourses();
    loadLogoOptions();
    initSearch();

    el("logoOptionsToggle").addEventListener("click", function () {
      const content = el("logoOptionsContent");
      const isOpen = content.style.display !== "none";
      content.style.display = isOpen ? "none" : "";
      el("logoOptionsToggleIcon").textContent = isOpen ? "▸" : "▾";
    });

    el("logoOptionsList").addEventListener("change", function (event) {
      const input = event.target.closest("[data-logo-option-input]");
      if (input) saveLogoOption(input.dataset.logoOptionInput, input);
    });

    el("addProductBtn").addEventListener("click", () => openModal(null));
    el("closeStoreProductModal").addEventListener("click", closeModal);
    el("cancelStoreProductModal").addEventListener("click", closeModal);
    el("saveStoreProduct").addEventListener("click", saveProduct);
    el("storeProductUnlimited").addEventListener("change", updateStockFieldVisibility);
    el("storeProductHasVariations").addEventListener("change", updateVariationsVisibility);
    el("storeProductIsDigital").addEventListener("change", updateDigitalFieldVisibility);
    el("storeProductUnlocksCourseEnabled").addEventListener("change", updateUnlocksCourseFieldVisibility);
    el("storeProductPersonalizationEnabled").addEventListener("change", updatePersonalizationFieldVisibility);
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
    el("saveAllVariantsBtn").addEventListener("click", saveAllVariants);

    el("manageVariantsImagesToggle").addEventListener("click", function () {
      const content = el("manageVariantsImagesContent");
      const icon = el("manageVariantsImagesToggleIcon");
      const isOpen = content.style.display !== "none";

      content.style.display = isOpen ? "none" : "";
      icon.textContent = isOpen ? "▸" : "▾";
    });

    el("bulkAddVariantsToggle").addEventListener("click", function () {
      const content = el("bulkAddVariantsContent");
      const icon = el("bulkAddVariantsToggleIcon");
      const isOpen = content.style.display !== "none";

      content.style.display = isOpen ? "none" : "";
      icon.textContent = isOpen ? "▸" : "▾";
    });

    el("bulkAddVariantsAttributesList").addEventListener("input", updateBulkAddVariantsCount);
    el("bulkAddVariantsBtn").addEventListener("click", bulkAddVariants);

    el("manageVariantsImageAttributesList").addEventListener("change", function (event) {
      const checkbox = event.target.closest("[data-manage-variants-image-attribute]");
      if (!checkbox) return;

      if (
        Object.keys(pendingVariantImageUrls).length &&
        !window.confirm("Changing which attributes affect the photo will clear any photos applied below that haven't been saved yet. Continue?")
      ) {
        checkbox.checked = !checkbox.checked;
        return;
      }

      manageVariantsImageAttributes = Array.from(
        document.querySelectorAll("#manageVariantsImageAttributesList [data-manage-variants-image-attribute]:checked")
      ).map((input) => input.dataset.manageVariantsImageAttribute);

      pendingVariantImageUrls = {};
      renderManageVariantsImageGroups();
    });

    el("manageVariantsImagesBody").addEventListener("click", function (event) {
      const button = event.target.closest("[data-apply-variant-image-combo]");
      if (!button) return;

      applyManageVariantsImageCombo(button.dataset.applyVariantImageCombo, button);
    });

    el("storeProductImageFile").addEventListener("change", function () {
      const file = this.files[0];
      if (!file) return;
      const preview = el("storeProductImagePreview");
      preview.src = URL.createObjectURL(file);
      preview.style.display = "";
    });

    el("storeProductGalleryFile").addEventListener("change", function () {
      Array.from(this.files || []).forEach((file) => galleryItems.push({ file }));
      this.value = "";
      renderGalleryList();
    });

    el("storeProductGalleryList").addEventListener("click", function (event) {
      const btn = event.target.closest("[data-remove-gallery-item]");
      if (!btn) return;
      const index = parseInt(btn.dataset.removeGalleryItem, 10);
      const removed = galleryItems.splice(index, 1)[0];
      if (removed && removed.objectUrl) URL.revokeObjectURL(removed.objectUrl);
      renderGalleryList();
    });

    el("storeProductShortDescription").addEventListener("input", function () {
      el("storeProductShortDescriptionCount").textContent = this.value.length;
    });

    el("storeVariantImageAttributesList").addEventListener("change", function (event) {
      const checkbox = event.target.closest("[data-variant-image-attribute]");
      if (!checkbox) return;

      if (
        Object.keys(variantImagesByCombo).length &&
        !window.confirm("Changing which attributes affect the photo will clear the photos already picked below. Continue?")
      ) {
        checkbox.checked = !checkbox.checked;
        return;
      }

      imageKeyAttributes = Array.from(
        document.querySelectorAll("#storeVariantImageAttributesList [data-variant-image-attribute]:checked")
      ).map((input) => input.dataset.variantImageAttribute);

      variantImagesByCombo = {};
      renderVariantImageGroupRows();
    });

    document.addEventListener("change", function (event) {
      const variantImageInput = event.target.closest("[data-variant-image-combo]");
      if (variantImageInput) {
        const file = variantImageInput.files[0];
        if (!file) return;

        const preview = document.querySelector(
          `[data-variant-image-combo-preview="${CSS.escape(variantImageInput.dataset.variantImageCombo)}"]`
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
        return;
      }

      const deleteVariantBtn = event.target.closest("[data-delete-variant]");
      if (deleteVariantBtn) {
        deleteVariantRow(deleteVariantBtn.dataset.deleteVariant, deleteVariantBtn);
      }
    });

    el("addVariantBtn").addEventListener("click", addNewVariant);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initPage);
  } else {
    initPage();
  }
})();
