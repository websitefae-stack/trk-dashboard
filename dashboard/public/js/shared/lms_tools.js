/**
 * Franchisor-facing LMS admin tools (franchisor_db/lms_tools) - not
 * tied to onboarding. The chapter-sharing tool used to live inside the
 * onboarding Manage Step List screen; moved here so it can be used for
 * any two courses, not only when reusing a module happens to also be
 * an onboarding step's Go link. See lms_tools.py's own docstring.
 */
(function () {
  "use strict";

  var el = Dashboard.el;
  var ONBOARDING_API = "dashboard.api.shared.onboarding";
  var LMS_TOOLS_API = "dashboard.api.shared.lms_tools";

  function getCsrfToken() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    return meta && meta.content ? meta.content : "";
  }

  function extractErrorMessage(data) {
    if (!data) return "";

    if (typeof data._server_messages === "string" && data._server_messages) {
      try {
        var parsed = JSON.parse(data._server_messages);
        if (Array.isArray(parsed) && parsed.length) {
          var first = JSON.parse(parsed[0]);
          if (first && first.message) return first.message;
        }
      } catch (error) {
        console.error("Could not parse server messages:", error);
      }
    }

    if (typeof data.message === "string" && data.message) return data.message;
    if (data.exception) return String(data.exception);

    return "";
  }

  async function apiGet(method, args) {
    var params = new URLSearchParams(args || {});
    var response = await fetch("/api/method/" + method + "?" + params.toString(), {
      method: "GET",
      credentials: "same-origin"
    });

    var data = await response.json();

    if (!response.ok || data.exc) {
      throw new Error(extractErrorMessage(data) || "There was a problem loading this.");
    }

    return data.message;
  }

  async function apiPost(method, args) {
    var response = await fetch("/api/method/" + method, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-Frappe-CSRF-Token": getCsrfToken()
      },
      body: JSON.stringify(args || {})
    });

    var data = await response.json();

    if (!response.ok || data.exc) {
      throw new Error(extractErrorMessage(data) || "There was a problem saving this.");
    }

    return data.message;
  }

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function renderShareTool(chapters, courses) {
    // Deliberately NOT derived from `chapters` - that only ever lists
    // courses that already have a chapter in them, so a brand new,
    // still-empty course would never show up to pick as a destination.
    var courseOptions = (courses || []).map(function (c) {
      return '<option value="' + escapeHtml(c.name) + '">' + escapeHtml(c.title || c.name) + "</option>";
    }).join("");

    var chapterOptions = (chapters || []).map(function (c) {
      return '<option value="' + escapeHtml(c.chapter_name) + '">' +
        escapeHtml(c.chapter_title) + " (currently in " + escapeHtml(c.course_title) + ")</option>";
    }).join("");

    return (
      '<div style="display:flex; gap:10px; flex-wrap:wrap; align-items:flex-end;">' +
        '<div>' +
          '<label class="dashboard-field-label">Module (chapter) to share</label>' +
          '<select class="dashboard-select" id="lmsShareChapterSelect">' + chapterOptions + "</select>" +
        "</div>" +
        '<div>' +
          '<label class="dashboard-field-label">Add it to this course</label>' +
          '<select class="dashboard-select" id="lmsShareCourseSelect">' + courseOptions + "</select>" +
        "</div>" +
        '<button type="button" class="dashboard-btn dashboard-btn-primary" id="lmsShareChapterBtn">Share</button>' +
      "</div>" +
      '<div class="dashboard-doc-list-meta" id="lmsShareChapterResult" style="margin-top:8px;"></div>'
    );
  }

  function bindShareTool() {
    var btn = el("lmsShareChapterBtn");
    if (!btn) return;

    btn.addEventListener("click", async function () {
      var chapterSelect = el("lmsShareChapterSelect");
      var courseSelect = el("lmsShareCourseSelect");
      var result = el("lmsShareChapterResult");
      if (!chapterSelect || !courseSelect) return;

      btn.disabled = true;
      btn.textContent = "Sharing...";
      if (result) result.textContent = "";

      try {
        var response = await apiPost(LMS_TOOLS_API + ".link_existing_chapter_to_course", {
          course: courseSelect.value,
          chapter_name: chapterSelect.value,
        });
        if (result) {
          result.textContent = response.already_linked
            ? "That module is already in this course."
            : "Done - that module (and its lessons) now shows under this course too.";
        }
      } catch (error) {
        if (result) result.textContent = error.message || "Could not share this module.";
      } finally {
        btn.disabled = false;
        btn.textContent = "Share";
      }
    });
  }

  async function loadShareTool() {
    var body = el("lmsShareToolBody");
    if (!body) return;

    try {
      var chapters = await apiGet(ONBOARDING_API + ".get_lms_chapters", {});
      var courses = await apiGet(LMS_TOOLS_API + ".get_lms_courses", {});
    } catch (error) {
      body.innerHTML = '<div class="dashboard-empty">' + escapeHtml(error.message) + "</div>";
      return;
    }

    if (!chapters.length) {
      body.innerHTML = '<div class="dashboard-empty">No LMS chapters found yet - create at least one course with a module in it first.</div>';
      return;
    }

    body.innerHTML = renderShareTool(chapters, courses);
    bindShareTool();
  }

  function init() {
    if (!el("lmsToolsPage")) return;
    loadShareTool();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
