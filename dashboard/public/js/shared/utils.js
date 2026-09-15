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
   * HTML for a small rich text editor: a toolbar (style dropdown for
   * paragraph/heading/subheading, bold, italic, insert link, insert
   * image) over a bigger contenteditable body - used wherever a School
   * Pipeline email is composed. Pair with Dashboard.wireRichTextEditor().
   * @param {string} [placeholder]
   * @returns {string}
   */
  Dashboard.richTextEditorHtml = function (placeholder) {
    return (
      '<div class="dashboard-richtext">' +
      '<div class="dashboard-richtext-toolbar">' +
      '<select class="dashboard-richtext-heading-select">' +
      '<option value="">Style…</option>' +
      '<option value="P">Normal text</option>' +
      '<option value="H2">Heading</option>' +
      '<option value="H3">Subheading</option>' +
      "</select>" +
      '<button type="button" class="dashboard-richtext-btn dashboard-richtext-bold-btn" title="Bold"><b>B</b></button>' +
      '<button type="button" class="dashboard-richtext-btn dashboard-richtext-italic-btn" title="Italic"><i>I</i></button>' +
      '<button type="button" class="dashboard-richtext-btn dashboard-richtext-link-btn" title="Insert Link">Link</button>' +
      '<button type="button" class="dashboard-richtext-btn dashboard-richtext-image-btn" title="Insert Image">Image</button>' +
      '<input type="file" accept="image/*" class="dashboard-richtext-image-input" style="display:none;">' +
      "</div>" +
      '<div class="dashboard-richtext-body" contenteditable="true" data-placeholder="' +
      (placeholder || "Write your email…") +
      '"></div>' +
      "</div>"
    );
  };

  /**
   * Wires up the toolbar/body from Dashboard.richTextEditorHtml() (must
   * already be in the DOM inside `root`), and returns a small controller
   * so the caller never has to touch the contenteditable's innerHTML
   * directly.
   * @param {Element|null} root - the ".dashboard-richtext" wrapper
   * @returns {{getHtml: function, setHtml: function, isEmpty: function, focus: function}}
   */
  Dashboard.wireRichTextEditor = function (root) {
    var noop = { getHtml: function () { return ""; }, setHtml: function () {}, isEmpty: function () { return true; }, focus: function () {} };
    if (!root) return noop;

    var body = root.querySelector(".dashboard-richtext-body");
    if (!body) return noop;

    var headingSelect = root.querySelector(".dashboard-richtext-heading-select");
    var boldBtn = root.querySelector(".dashboard-richtext-bold-btn");
    var italicBtn = root.querySelector(".dashboard-richtext-italic-btn");
    var linkBtn = root.querySelector(".dashboard-richtext-link-btn");
    var imageBtn = root.querySelector(".dashboard-richtext-image-btn");
    var fileInput = root.querySelector(".dashboard-richtext-image-input");

    try {
      document.execCommand("defaultParagraphSeparator", false, "p");
    } catch (e) {
      // Some browsers don't support this - contenteditable still works,
      // it just may wrap lines in <div> instead of <p> (both render fine
      // in an email, and plain_text_to_email_html() on the Python side
      // already passes either straight through untouched).
    }

    function getCsrfToken() {
      var meta = document.querySelector('meta[name="csrf-token"]');
      return meta && meta.content ? meta.content : "";
    }

    function refreshEmptyState() {
      var isEmpty = body.textContent.trim() === "";
      body.classList.toggle("is-empty", isEmpty);
    }

    function saveSelectionRange() {
      var sel = window.getSelection();
      if (sel && sel.rangeCount > 0 && body.contains(sel.getRangeAt(0).commonAncestorContainer)) {
        return sel.getRangeAt(0);
      }
      return null;
    }

    function restoreSelectionRange(range) {
      body.focus();
      if (!range) return;
      var sel = window.getSelection();
      sel.removeAllRanges();
      sel.addRange(range);
    }

    function escapePastedText(value) {
      return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");
    }

    body.addEventListener("input", refreshEmptyState);
    body.addEventListener("blur", refreshEmptyState);
    refreshEmptyState();

    // Pasting plain text (e.g. an email drafted elsewhere and copied in)
    // otherwise lands as one unbroken run with no paragraph breaks at
    // all - the browser's default paste-into-contenteditable behaviour
    // doesn't reliably turn blank lines into separate blocks. This reads
    // the plain text off the clipboard directly and rebuilds it as one
    // <p> per paragraph (blank-line-separated, falling back to one per
    // line if there are no blank lines) instead.
    body.addEventListener("paste", function (e) {
      var clipboardData = e.clipboardData || window.clipboardData;
      if (!clipboardData) return;

      e.preventDefault();

      var text = clipboardData.getData("text/plain") || "";
      var paragraphs = text.split(/\r\n\s*\r\n|\n\s*\n/);
      if (paragraphs.length < 2) paragraphs = text.split(/\r\n|\n|\r/);

      var html = paragraphs
        .map(function (p) { return p.trim(); })
        .filter(function (p) { return p.length > 0; })
        .map(function (p) { return "<p>" + escapePastedText(p) + "</p>"; })
        .join("");

      document.execCommand("insertHTML", false, html || "<p></p>");
      refreshEmptyState();
    });

    if (headingSelect) {
      headingSelect.addEventListener("change", function () {
        var value = headingSelect.value;
        headingSelect.value = "";
        if (!value) return;
        body.focus();
        document.execCommand("formatBlock", false, value);
      });
    }

    if (boldBtn) {
      boldBtn.addEventListener("click", function () {
        body.focus();
        document.execCommand("bold");
      });
    }

    if (italicBtn) {
      italicBtn.addEventListener("click", function () {
        body.focus();
        document.execCommand("italic");
      });
    }

    if (linkBtn) {
      linkBtn.addEventListener("click", function () {
        var range = saveSelectionRange();
        var hasSelectedText = !!(range && !range.collapsed);
        var url = prompt("Link URL (e.g. https://example.com):");
        if (!url) return;

        restoreSelectionRange(range);

        if (hasSelectedText) {
          document.execCommand("createLink", false, url);
        } else {
          var text = prompt("Link text:", url) || url;
          var escapedText = text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
          document.execCommand("insertHTML", false, '<a href="' + url.replace(/"/g, "&quot;") + '">' + escapedText + "</a>");
        }
        refreshEmptyState();
      });
    }

    if (imageBtn && fileInput) {
      imageBtn.addEventListener("click", function () {
        fileInput.click();
      });

      fileInput.addEventListener("change", function () {
        var file = fileInput.files && fileInput.files[0];
        if (!file) return;

        var range = saveSelectionRange();
        var formData = new FormData();
        formData.append("file", file);

        var originalLabel = imageBtn.textContent;
        imageBtn.disabled = true;
        imageBtn.textContent = "Uploading…";

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
            restoreSelectionRange(range);
            document.execCommand("insertHTML", false, '<img src="' + result.url + '">');
            refreshEmptyState();
          })
          .catch(function (error) {
            alert(error.message || "Could not upload image.");
          })
          .finally(function () {
            imageBtn.disabled = false;
            imageBtn.textContent = originalLabel;
            fileInput.value = "";
          });
      });
    }

    return {
      getHtml: function () {
        return body.textContent.trim() === "" ? "" : body.innerHTML;
      },
      setHtml: function (html) {
        body.innerHTML = html || "";
        refreshEmptyState();
      },
      isEmpty: function () {
        return body.textContent.trim() === "";
      },
      focus: function () {
        body.focus();
      },
    };
  };
})();
