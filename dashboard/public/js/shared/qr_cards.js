/**
 * "QR Codes" tool (franchisor_db/qr_cards) - composes a branded,
 * downloadable QR code card (logo, title, QR code, destination URL,
 * optional corner graphic) entirely in the browser: the QR itself comes
 * from the same vendored qrcodejs library already used elsewhere in this
 * app (see utils.js's Dashboard.renderQrCodes for the Links/Your Logins
 * version), drawn onto a <canvas> alongside the rest of the card, then
 * exported as a PNG via canvas.toBlob(). Saved logos (QR Card Template)
 * are managed here too, so a brand's logo/corner graphic only has to be
 * uploaded once and is then just picked from a dropdown for every card.
 */
(function () {
  "use strict";

  var el = Dashboard.el;
  var SHARED_API = "dashboard.api.shared.qr_cards";

  var CARD_WIDTH = 1080;
  var CARD_HEIGHT = 1920;

  var templates = [];

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function getCsrfToken() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    return meta && meta.content ? meta.content : "";
  }

  async function apiPost(method, args) {
    var response = await fetch("/api/method/" + method, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-Frappe-CSRF-Token": getCsrfToken(),
      },
      body: JSON.stringify(args || {}),
    });

    var data = await response.json();

    if (!response.ok || data.exc) {
      throw new Error(Dashboard.extractErrorMessage(data, "There was a problem saving this."));
    }

    return data.message || {};
  }

  async function uploadFile(file) {
    var formData = new FormData();
    formData.append("file", file);
    formData.append("is_private", 0);

    var response = await fetch("/api/method/upload_file", {
      method: "POST",
      credentials: "same-origin",
      headers: { "X-Frappe-CSRF-Token": getCsrfToken() },
      body: formData,
    });

    var data = await response.json();

    if (!response.ok || data.exc) {
      throw new Error(Dashboard.extractErrorMessage(data, "Could not upload the file."));
    }

    return data.message && data.message.file_url;
  }

  function loadImage(url) {
    return new Promise(function (resolve, reject) {
      if (!url) {
        resolve(null);
        return;
      }
      var img = new Image();
      img.onload = function () { resolve(img); };
      img.onerror = function () { resolve(null); };
      img.src = url;
    });
  }

  // Splits text onto as many lines as it needs, each no wider than
  // maxWidth for the canvas context's currently-set font.
  function wrapText(ctx, text, maxWidth) {
    var words = (text || "").split(/\s+/).filter(Boolean);
    var lines = [];
    var current = "";

    words.forEach(function (word) {
      var attempt = current ? current + " " + word : word;
      if (ctx.measureText(attempt).width > maxWidth && current) {
        lines.push(current);
        current = word;
      } else {
        current = attempt;
      }
    });
    if (current) lines.push(current);

    return lines;
  }

  function renderQrToCanvas(text, size) {
    var holder = document.createElement("div");
    holder.style.position = "absolute";
    holder.style.left = "-9999px";
    document.body.appendChild(holder);

    /* eslint-disable no-new */
    new QRCode(holder, {
      text: text,
      width: size,
      height: size,
      correctLevel: QRCode.CorrectLevel.M,
    });

    var canvas = holder.querySelector("canvas");
    var result = null;
    if (canvas) {
      result = document.createElement("canvas");
      result.width = size;
      result.height = size;
      result.getContext("2d").drawImage(canvas, 0, 0, size, size);
    }

    document.body.removeChild(holder);
    return result;
  }

  async function generateCard() {
    var select = el("qrCardLogo");
    var template = templates.find(function (t) { return t.name === select.value; });
    var title = (el("qrCardTitle").value || "").trim();
    var url = (el("qrCardUrl").value || "").trim();

    if (!template) {
      window.alert("Please save and select a logo first.");
      return;
    }
    if (!title) {
      window.alert("Please enter a title.");
      return;
    }
    if (!url) {
      window.alert("Please enter a link.");
      return;
    }

    var canvas = el("qrCardCanvas");
    var ctx = canvas.getContext("2d");

    ctx.clearRect(0, 0, CARD_WIDTH, CARD_HEIGHT);
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, CARD_WIDTH, CARD_HEIGHT);

    var logoImg = await loadImage(template.logo);
    var cornerImg = await loadImage(template.corner_graphic);

    var cursorY = 110;

    if (logoImg) {
      var maxLogoWidth = CARD_WIDTH * 0.72;
      var maxLogoHeight = 300;
      var scale = Math.min(maxLogoWidth / logoImg.width, maxLogoHeight / logoImg.height, 1);
      var logoWidth = logoImg.width * scale;
      var logoHeight = logoImg.height * scale;
      ctx.drawImage(logoImg, (CARD_WIDTH - logoWidth) / 2, cursorY, logoWidth, logoHeight);
      cursorY += logoHeight + 70;
    }

    ctx.fillStyle = template.accent_color || "#0D5C63";
    ctx.font = "700 76px Comfortaa, Arial, sans-serif";
    ctx.textAlign = "center";
    var titleLines = wrapText(ctx, title, CARD_WIDTH * 0.84);
    titleLines.forEach(function (line, i) {
      ctx.fillText(line, CARD_WIDTH / 2, cursorY + i * 88);
    });
    cursorY += titleLines.length * 88 + 60;

    var qrSize = 700;
    var qrCanvas = renderQrToCanvas(url, qrSize);
    if (qrCanvas) {
      ctx.drawImage(qrCanvas, (CARD_WIDTH - qrSize) / 2, cursorY, qrSize, qrSize);
      cursorY += qrSize + 60;
    }

    ctx.fillStyle = "#333333";
    ctx.font = "400 34px Arial, sans-serif";
    var urlLines = wrapText(ctx, url, CARD_WIDTH * 0.8);
    urlLines.forEach(function (line, i) {
      ctx.fillText(line, CARD_WIDTH / 2, cursorY + i * 46);
    });

    if (cornerImg) {
      var cornerMaxWidth = CARD_WIDTH * 0.42;
      var cornerScale = Math.min(cornerMaxWidth / cornerImg.width, 1);
      var cornerWidth = cornerImg.width * cornerScale;
      var cornerHeight = cornerImg.height * cornerScale;
      ctx.drawImage(cornerImg, CARD_WIDTH - cornerWidth, CARD_HEIGHT - cornerHeight, cornerWidth, cornerHeight);
    }

    el("qrCardPreviewWrap").style.display = "";

    var downloadBtn = el("downloadQrCardBtn");
    downloadBtn.style.display = "";
    downloadBtn.href = canvas.toDataURL("image/png");
    downloadBtn.setAttribute(
      "download",
      (title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "") || "qr-card") + ".png"
    );
  }

  function renderLogoSelect() {
    var select = el("qrCardLogo");
    if (!select) return;

    var current = select.value;
    select.innerHTML = templates.length
      ? templates.map(function (t) { return '<option value="' + escapeHtml(t.name) + '">' + escapeHtml(t.template_name) + "</option>"; }).join("")
      : '<option value="">No saved logos yet - add one below</option>';

    if (current && templates.some(function (t) { return t.name === current; })) {
      select.value = current;
    }
  }

  function renderLogosList() {
    var list = el("qrCardLogosList");
    if (!list) return;

    if (!templates.length) {
      list.innerHTML = '<div class="dashboard-empty">No saved logos yet.</div>';
      return;
    }

    list.innerHTML = templates.map(function (t) {
      return (
        '<div class="dashboard-doc-list-meta" data-logo-name="' + escapeHtml(t.name) + '" style="display:flex; align-items:center; gap:12px; padding:8px 0; border-bottom:1px solid #eef3f3;">' +
          '<img src="' + escapeHtml(t.logo) + '" alt="" style="height:36px; max-width:120px; object-fit:contain;">' +
          '<span style="flex:1;">' + escapeHtml(t.template_name) + "</span>" +
          '<button type="button" class="dashboard-btn dashboard-btn-grey dashboard-qr-logo-delete">Delete</button>' +
        "</div>"
      );
    }).join("");

    list.querySelectorAll(".dashboard-qr-logo-delete").forEach(function (btn) {
      btn.addEventListener("click", async function () {
        var row = btn.closest("[data-logo-name]");
        var name = row && row.dataset.logoName;
        if (!name) return;
        if (!window.confirm("Delete this saved logo?")) return;

        btn.disabled = true;
        try {
          await apiPost(SHARED_API + ".delete_qr_card_template", { name: name });
          await loadTemplates();
        } catch (error) {
          window.alert(error.message || "Could not delete this logo.");
          btn.disabled = false;
        }
      });
    });
  }

  async function loadTemplates() {
    try {
      var rows = await apiPost(SHARED_API + ".get_qr_card_templates", {});
      templates = Array.isArray(rows) ? rows : [];
    } catch (error) {
      templates = [];
      window.alert(error.message || "Could not load saved logos.");
    }
    renderLogoSelect();
    renderLogosList();
  }

  function initAddLogoForm() {
    var btn = el("addLogoBtn");
    if (!btn) return;

    btn.addEventListener("click", async function () {
      var name = (el("newLogoName").value || "").trim();
      var color = el("newLogoColor").value || "#0d5c63";
      var fileInput = el("newLogoFile");
      var cornerInput = el("newLogoCornerFile");
      var file = fileInput.files && fileInput.files[0];
      var cornerFile = cornerInput.files && cornerInput.files[0];

      if (!name) {
        window.alert("Please enter a name for this logo.");
        return;
      }
      if (!file) {
        window.alert("Please choose a logo image.");
        return;
      }

      btn.disabled = true;
      btn.textContent = "Saving...";

      try {
        var logoUrl = await uploadFile(file);
        var cornerUrl = cornerFile ? await uploadFile(cornerFile) : null;

        await apiPost(SHARED_API + ".create_qr_card_template", {
          template_name: name,
          logo: logoUrl,
          corner_graphic: cornerUrl,
          accent_color: color,
        });

        el("newLogoName").value = "";
        fileInput.value = "";
        cornerInput.value = "";

        await loadTemplates();
      } catch (error) {
        window.alert(error.message || "Could not save this logo.");
      } finally {
        btn.disabled = false;
        btn.textContent = "Save Logo";
      }
    });
  }

  function initGenerate() {
    var btn = el("generateQrCardBtn");
    if (!btn) return;

    btn.addEventListener("click", async function () {
      btn.disabled = true;
      try {
        await generateCard();
      } catch (error) {
        window.alert(error.message || "Could not generate this card.");
      } finally {
        btn.disabled = false;
      }
    });
  }

  function init() {
    if (!el("qrCardLogosList")) return;

    loadTemplates();
    initAddLogoForm();
    initGenerate();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
