/**
 * "Links" page - shareable public URLs for every Forms-module Web Form
 * the current user is allowed to see (dashboard.api.shared.form_reports.
 * get_form_links), so a link like the Care Languages Quiz doesn't have to
 * be dug up and re-shared by hand every time someone asks for it. Reuses
 * the exact same Form Visibility Rule that already gates the Reports
 * section, so nothing needs configuring twice here.
 */
(function () {
  "use strict";

  var el = Dashboard.el;

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function renderLink(link) {
    return (
      '<div class="dashboard-card dashboard-link-card">' +
        '<h3 class="dashboard-form-link-title">' + escapeHtml(link.title) + "</h3>" +
        (link.description
          ? '<div class="dashboard-doc-list-meta" style="margin-bottom:8px;">' + escapeHtml(link.description) + "</div>"
          : "") +
        '<div class="dashboard-login-qr" data-qr-value="' + escapeHtml(link.url) + '" data-qr-label="' + escapeHtml(link.title) + '"></div>' +
        '<a href="#" class="dashboard-login-qr-download" download>Download QR code (JPG)</a>' +
        '<div class="dashboard-link-card-actions">' +
          '<button type="button" class="dashboard-btn dashboard-btn-light" data-copy-value="' + escapeHtml(link.url) + '">Copy Link</button>' +
          '<a class="dashboard-btn dashboard-btn-primary" href="' + escapeHtml(link.url) + '" target="_blank" rel="noopener noreferrer">Open</a>' +
        "</div>" +
      "</div>"
    );
  }

  function bindCopyButtons(container) {
    container.querySelectorAll("[data-copy-value]").forEach(function (button) {
      button.addEventListener("click", function () {
        var value = button.dataset.copyValue;
        if (!value) return;

        var originalText = button.textContent;
        var restore = function () {
          button.textContent = originalText;
        };

        var fallbackCopy = function () {
          var temp = document.createElement("textarea");
          temp.value = value;
          temp.style.position = "fixed";
          temp.style.opacity = "0";
          document.body.appendChild(temp);
          temp.select();
          document.execCommand("copy");
          document.body.removeChild(temp);
        };

        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(value).then(function () {
            button.textContent = "Copied!";
            window.setTimeout(restore, 1500);
          }).catch(function () {
            fallbackCopy();
            button.textContent = "Copied!";
            window.setTimeout(restore, 1500);
          });
        } else {
          fallbackCopy();
          button.textContent = "Copied!";
          window.setTimeout(restore, 1500);
        }
      });
    });
  }

  var allLinksCache = [];

  function renderLinks(links, emptyMessage) {
    var container = el("formLinksList");
    if (!container) return;

    if (!links.length) {
      container.innerHTML = '<div class="dashboard-empty">' + escapeHtml(emptyMessage) + "</div>";
      return;
    }

    container.innerHTML = '<div class="dashboard-links-grid">' + links.map(renderLink).join("") + "</div>";
    bindCopyButtons(container);
    Dashboard.renderQrCodes({ root: container, format: "jpeg" });
  }

  function initLinksSearch() {
    var input = el("formLinksSearch");
    if (!input) return;

    input.addEventListener("input", Dashboard.debounce(function () {
      var query = input.value.trim().toLowerCase();

      var filtered = query
        ? allLinksCache.filter(function (link) {
            return (link.title || "").toLowerCase().indexOf(query) !== -1
              || (link.description || "").toLowerCase().indexOf(query) !== -1;
          })
        : allLinksCache;

      renderLinks(filtered, query ? "No links match your search." : "No links are available to you yet.");
    }, 200));
  }

  async function loadFormLinks() {
    var container = el("formLinksList");
    if (!container) return;

    container.innerHTML = '<div class="dashboard-empty">Loading links...</div>';

    var response;
    try {
      response = await fetch("/api/method/dashboard.api.shared.form_reports.get_form_links", {
        method: "GET",
        credentials: "same-origin"
      });
    } catch (error) {
      container.innerHTML = '<div class="dashboard-empty">Could not load links right now.</div>';
      return;
    }

    var data = await response.json();

    if (!response.ok || data.exc) {
      container.innerHTML = '<div class="dashboard-empty">Could not load links right now.</div>';
      return;
    }

    allLinksCache = data.message || [];
    renderLinks(allLinksCache, "No links are available to you yet.");
  }

  function initLinksPage() {
    if (!el("linksPage")) return;
    loadFormLinks();
    initLinksSearch();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initLinksPage);
  } else {
    initLinksPage();
  }
})();
