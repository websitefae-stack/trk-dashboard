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
    var id = "formLink_" + Math.random().toString(36).slice(2);

    return (
      '<div class="dashboard-card" style="margin-bottom:14px;">' +
        '<div class="dashboard-doc-list-title">' + escapeHtml(link.title) + "</div>" +
        (link.description
          ? '<div class="dashboard-doc-list-meta" style="margin-bottom:8px;">' + escapeHtml(link.description) + "</div>"
          : "") +
        '<div style="display:flex; gap:10px; align-items:center; flex-wrap:wrap; margin-top:8px;">' +
          '<input type="text" class="dashboard-input" id="' + id + '" value="' + escapeHtml(link.url) + '" readonly style="flex:1; min-width:220px;">' +
          '<button type="button" class="dashboard-btn dashboard-btn-light" data-copy-target="' + id + '">Copy Link</button>' +
          '<a class="dashboard-btn dashboard-btn-primary" href="' + escapeHtml(link.url) + '" target="_blank" rel="noopener noreferrer">Open</a>' +
        "</div>" +
      "</div>"
    );
  }

  function bindCopyButtons(container) {
    container.querySelectorAll("[data-copy-target]").forEach(function (button) {
      button.addEventListener("click", function () {
        var input = el(button.dataset.copyTarget);
        if (!input) return;

        input.select();
        input.setSelectionRange(0, input.value.length);

        var originalText = button.textContent;
        var restore = function () {
          button.textContent = originalText;
        };

        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(input.value).then(function () {
            button.textContent = "Copied!";
            window.setTimeout(restore, 1500);
          }).catch(function () {
            document.execCommand("copy");
            button.textContent = "Copied!";
            window.setTimeout(restore, 1500);
          });
        } else {
          document.execCommand("copy");
          button.textContent = "Copied!";
          window.setTimeout(restore, 1500);
        }
      });
    });
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

    var links = data.message || [];

    if (!links.length) {
      container.innerHTML = '<div class="dashboard-empty">No links are available to you yet.</div>';
      return;
    }

    container.innerHTML = links.map(renderLink).join("");
    bindCopyButtons(container);
  }

  function initLinksPage() {
    if (!el("linksPage")) return;
    loadFormLinks();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initLinksPage);
  } else {
    initLinksPage();
  }
})();
