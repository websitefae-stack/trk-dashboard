/**
 * Shared dashboard utilities.
 * Loaded first on every dashboard page (see shared_head.html).
 * All helpers live on window.Dashboard so they are available to every
 * subsequent script without polluting the global namespace further.
 *
 * Usage in any dashboard JS file:
 *   const el  = Dashboard.el;
 *   const qsa = Dashboard.qsa;
 *   const debounce = Dashboard.debounce;
 */
(function () {
  "use strict";

  window.Dashboard = window.Dashboard || {};

  /**
   * Shorthand for document.getElementById.
   * @param {string} id
   * @returns {HTMLElement|null}
   */
  Dashboard.el = function (id) {
    return document.getElementById(id);
  };

  /**
   * querySelectorAll returning a real Array.
   * @param {string} selector
   * @param {Element|Document} [root]
   * @returns {Element[]}
   */
  Dashboard.qsa = function (selector, root) {
    return Array.from((root || document).querySelectorAll(selector));
  };

  /**
   * Returns a debounced version of fn that fires after `wait` ms of quiet.
   * @param {Function} fn
   * @param {number} [wait=500]
   * @returns {Function}
   */
  Dashboard.debounce = function (fn, wait) {
    var timer = null;
    return function () {
      var args = arguments;
      clearTimeout(timer);
      timer = setTimeout(function () {
        fn.apply(null, args);
      }, wait || 500);
    };
  };

  /**
   * Inserts a one-line explainer right after a "From" sender <select> in
   * an email compose modal, the first time it's called for that element -
   * every send in this app goes out via the shared office account with
   * reply-to set to whoever's actually sending it (see
   * email_templates.get_email_sender_options() and every frappe.sendmail()
   * call across the API), which isn't obvious just from a dropdown with a
   * single "Office email" option in it. Safe to call every time a modal's
   * sender options are (re)loaded - a repeat call on the same element is a
   * no-op rather than stacking duplicate notes.
   * @param {HTMLElement|null} selectEl
   */
  Dashboard.attachSenderHint = function (selectEl) {
    if (!selectEl || !selectEl.parentNode) return;
    if (selectEl.parentNode.querySelector(".dashboard-sender-hint")) return;

    var hint = document.createElement("div");
    hint.className = "dashboard-field-hint dashboard-sender-hint";
    hint.textContent = "Sent from office@theresilienthub.co.uk, but replies go straight to your own email - let clients know to look for mail from office.";
    selectEl.insertAdjacentElement("afterend", hint);
  };

  /**
   * HTML for a small "Insert Image" / "Insert Link" toolbar, meant to sit
   * directly above a plain <textarea> email composer. The composer's own
   * plain_text_to_email_html() (Python) passes any line that already
   * looks like HTML straight through unescaped, so writing real <img>/<a>
   * markup into the textarea is already enough to make it render in the
   * sent email - these two buttons just insert that markup for you
   * instead of you having to type it by hand. Pair with
   * Dashboard.wireEmailComposerToolbar().
   * @returns {string}
   */
  Dashboard.emailComposerToolbarHtml = function () {
    return (
      '<div class="dashboard-email-toolbar" style="display:flex; gap:8px; margin-bottom:6px;">' +
      '<button type="button" class="dashboard-btn dashboard-btn-light dashboard-email-insert-image-btn" style="padding:4px 10px; font-size:12px;">Insert Image</button>' +
      '<button type="button" class="dashboard-btn dashboard-btn-light dashboard-email-insert-link-btn" style="padding:4px 10px; font-size:12px;">Insert Link</button>' +
      '<input type="file" accept="image/*" class="dashboard-email-image-input" style="display:none;">' +
      "</div>"
    );
  };

  /**
   * Wires up the buttons from Dashboard.emailComposerToolbarHtml() (must
   * already be in the DOM inside `root`) to insert markup into `textarea`
   * at the current cursor position - an uploaded image via
   * upload_school_pipeline_email_image, or a hand-typed link.
   * @param {Element|null} root - contains the toolbar buttons
   * @param {HTMLTextAreaElement|null} textarea - where markup gets inserted
   */
  Dashboard.wireEmailComposerToolbar = function (root, textarea) {
    if (!root || !textarea) return;

    var insertImageBtn = root.querySelector(".dashboard-email-insert-image-btn");
    var insertLinkBtn = root.querySelector(".dashboard-email-insert-link-btn");
    var fileInput = root.querySelector(".dashboard-email-image-input");

    function getCsrfToken() {
      var meta = document.querySelector('meta[name="csrf-token"]');
      return meta && meta.content ? meta.content : "";
    }

    function insertAtCursor(text) {
      var start = textarea.selectionStart != null ? textarea.selectionStart : textarea.value.length;
      var end = textarea.selectionEnd != null ? textarea.selectionEnd : textarea.value.length;
      var value = textarea.value;
      textarea.value = value.slice(0, start) + text + value.slice(end);
      var cursor = start + text.length;
      textarea.selectionStart = textarea.selectionEnd = cursor;
      textarea.focus();
    }

    if (insertImageBtn && fileInput) {
      insertImageBtn.addEventListener("click", function () {
        fileInput.click();
      });

      fileInput.addEventListener("change", function () {
        var file = fileInput.files && fileInput.files[0];
        if (!file) return;

        var formData = new FormData();
        formData.append("file", file);

        var originalLabel = insertImageBtn.textContent;
        insertImageBtn.disabled = true;
        insertImageBtn.textContent = "Uploading…";

        fetch("/api/method/dashboard.api.shared.school_pipeline.upload_school_pipeline_email_image", {
          method: "POST",
          credentials: "same-origin",
          headers: { "X-Frappe-CSRF-Token": getCsrfToken() },
          body: formData,
        })
          .then(function (response) {
            return response.json().then(function (data) {
              if (!response.ok || data.exc) {
                throw new Error(data.message || "Could not upload image.");
              }
              return data.message;
            });
          })
          .then(function (result) {
            insertAtCursor('<img src="' + result.url + '" style="max-width:100%;">');
          })
          .catch(function (error) {
            alert(error.message || "Could not upload image.");
          })
          .finally(function () {
            insertImageBtn.disabled = false;
            insertImageBtn.textContent = originalLabel;
            fileInput.value = "";
          });
      });
    }

    if (insertLinkBtn) {
      insertLinkBtn.addEventListener("click", function () {
        var url = prompt("Link URL (e.g. https://example.com):");
        if (!url) return;
        var text = prompt("Link text:", url) || url;
        insertAtCursor(
          '<a href="' + url.replace(/"/g, "&quot;") + '">' +
          text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;") +
          "</a>"
        );
      });
    }
  };
})();
