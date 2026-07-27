(function () {
  "use strict";

  function getCsrfToken() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    return meta && meta.content ? meta.content : "";
  }

  async function submitResponse(token, payload) {
    var response = await fetch("/api/method/dashboard.api.shared.client_document_share.submit_client_response", {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-Frappe-CSRF-Token": getCsrfToken()
      },
      body: JSON.stringify(Object.assign({ token: token }, payload))
    });

    var data = await response.json();

    if (!response.ok || data.exc) {
      throw new Error(data.message || "Something went wrong. Please try again.");
    }

    return data.message || {};
  }

  function renderThankYou(area) {
    area.innerHTML =
      '<div class="client-document-portal-done">Thank you - this has already been completed.</div>';
  }

  function renderDownloadButton(area, token) {
    var link = document.createElement("a");
    link.className = "client-document-portal-btn";
    link.href = "/api/method/dashboard.api.shared.client_document_share.download_shared_document?token=" + encodeURIComponent(token);
    link.textContent = "Download Document";
    area.appendChild(link);
  }

  function renderAcknowledge(area, token, extraLabel) {
    var wrap = document.createElement("div");
    wrap.className = "client-document-portal-action";

    var button = document.createElement("button");
    button.type = "button";
    button.className = "client-document-portal-btn";
    button.textContent = extraLabel || "I acknowledge I have received this document";

    var error = document.createElement("div");
    error.className = "client-document-portal-error";

    button.addEventListener("click", async function () {
      button.disabled = true;
      button.textContent = "Submitting...";
      error.textContent = "";

      try {
        await submitResponse(token, { action: "acknowledge" });
        area.innerHTML = "";
        renderThankYou(area);
      } catch (err) {
        error.textContent = err.message;
        button.disabled = false;
        button.textContent = extraLabel || "I acknowledge I have received this document";
      }
    });

    wrap.appendChild(button);
    wrap.appendChild(error);
    area.appendChild(wrap);
  }

  function renderSignaturePad(area, token) {
    var wrap = document.createElement("div");
    wrap.className = "client-document-portal-action";

    var nameLabel = document.createElement("label");
    nameLabel.textContent = "Type your full name";
    nameLabel.className = "client-document-portal-label";

    var nameInput = document.createElement("input");
    nameInput.type = "text";
    nameInput.className = "client-document-portal-input";
    nameInput.placeholder = "Full name";

    var canvasLabel = document.createElement("label");
    canvasLabel.textContent = "Sign below";
    canvasLabel.className = "client-document-portal-label";

    var canvas = document.createElement("canvas");
    canvas.className = "client-document-portal-signature-pad";
    canvas.width = 400;
    canvas.height = 150;

    var ctx = canvas.getContext("2d");
    ctx.lineWidth = 2;
    ctx.lineCap = "round";
    ctx.strokeStyle = "#434B49";

    var drawing = false;
    var hasDrawn = false;

    function pointerPosition(event) {
      var rect = canvas.getBoundingClientRect();
      var point = event.touches ? event.touches[0] : event;
      return {
        x: (point.clientX - rect.left) * (canvas.width / rect.width),
        y: (point.clientY - rect.top) * (canvas.height / rect.height)
      };
    }

    function start(event) {
      drawing = true;
      hasDrawn = true;
      var pos = pointerPosition(event);
      ctx.beginPath();
      ctx.moveTo(pos.x, pos.y);
      event.preventDefault();
    }

    function move(event) {
      if (!drawing) return;
      var pos = pointerPosition(event);
      ctx.lineTo(pos.x, pos.y);
      ctx.stroke();
      event.preventDefault();
    }

    function stop() {
      drawing = false;
    }

    canvas.addEventListener("mousedown", start);
    canvas.addEventListener("mousemove", move);
    window.addEventListener("mouseup", stop);
    canvas.addEventListener("touchstart", start, { passive: false });
    canvas.addEventListener("touchmove", move, { passive: false });
    canvas.addEventListener("touchend", stop);

    var clearButton = document.createElement("button");
    clearButton.type = "button";
    clearButton.className = "client-document-portal-btn-light";
    clearButton.textContent = "Clear Signature";
    clearButton.addEventListener("click", function () {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      hasDrawn = false;
    });

    var submitButton = document.createElement("button");
    submitButton.type = "button";
    submitButton.className = "client-document-portal-btn";
    submitButton.textContent = "Submit Signature";

    var error = document.createElement("div");
    error.className = "client-document-portal-error";

    submitButton.addEventListener("click", async function () {
      error.textContent = "";

      if (!nameInput.value.trim()) {
        error.textContent = "Please type your full name.";
        return;
      }

      if (!hasDrawn) {
        error.textContent = "Please sign in the box above.";
        return;
      }

      submitButton.disabled = true;
      submitButton.textContent = "Submitting...";

      try {
        await submitResponse(token, {
          action: "sign",
          typed_name: nameInput.value.trim(),
          signature: canvas.toDataURL("image/png")
        });
        area.innerHTML = "";
        renderThankYou(area);
      } catch (err) {
        error.textContent = err.message;
        submitButton.disabled = false;
        submitButton.textContent = "Submit Signature";
      }
    });

    wrap.appendChild(nameLabel);
    wrap.appendChild(nameInput);
    wrap.appendChild(canvasLabel);
    wrap.appendChild(canvas);

    var canvasActions = document.createElement("div");
    canvasActions.className = "client-document-portal-signature-actions";
    canvasActions.appendChild(clearButton);
    canvasActions.appendChild(submitButton);
    wrap.appendChild(canvasActions);

    wrap.appendChild(error);
    area.appendChild(wrap);
  }

  function init() {
    var area = document.getElementById("clientDocumentActionArea");
    if (!area) return;

    var token = area.dataset.token;
    var actionRequired = area.dataset.actionRequired || "None";
    var hasFile = area.dataset.hasFile === "1";
    var alreadyCompleted = area.dataset.alreadyCompleted === "1";

    if (alreadyCompleted) {
      renderThankYou(area);
      return;
    }

    if (hasFile) {
      renderDownloadButton(area, token);
    }

    if (actionRequired === "Acknowledge") {
      renderAcknowledge(area, token);
    } else if (actionRequired === "Sign") {
      renderSignaturePad(area, token);
    } else if (actionRequired === "Download and Return") {
      renderAcknowledge(area, token, "I confirm I have completed and returned this document");
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
