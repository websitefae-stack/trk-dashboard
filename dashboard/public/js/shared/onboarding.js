/**
 * Coach Onboarding Journey - Tier 1.
 *
 * Two pages share this file:
 *  - coach_db/onboarding: a coach's own journey, grouped by stage. They
 *    can mark their own (Coach-owned) steps Done; HQ-owned steps are
 *    read-only status here.
 *  - franchisor_db/onboarding: an overview of every coach currently
 *    onboarding, with a drill-down into one coach's full journey where
 *    HQ can update any step's status (including marking HQ-owned steps
 *    done, or moving something to Waiting on HQ / Ready for You).
 */
(function () {
  "use strict";

  var el = Dashboard.el;
  var API = "dashboard.api.shared.onboarding";

  var STATUS_CLASS = {
    "Not Started": "doc-status-new",
    "In Progress": "doc-status-new",
    "Waiting on HQ": "doc-status-overdue",
    "Ready for You": "doc-status-overdue",
    "Done": "doc-status-completed",
    // The Policies stage reads its status straight from Coach Document
    // Requirement (see _dynamic_policies_stage on the server) rather
    // than the usual 5 onboarding statuses, so its own status values
    // need their own badge colours here too.
    "Not Viewed": "doc-status-new",
    "Viewed": "doc-status-new",
    "Completed": "doc-status-completed",
    "Overdue": "doc-status-overdue",
    "Superseded": "doc-status-superseded"
  };

  var HQ_STATUSES = ["Not Started", "In Progress", "Waiting on HQ", "Ready for You", "Done"];

  function getCsrfToken() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    return meta && meta.content ? meta.content : "";
  }

  // Same approach as calendar.js/calendar_details.js etc. - a bare
  // data.message check missed most real errors, since an unhandled
  // Python exception's actual text usually lands in _server_messages
  // or data.exception instead, not data.message. Without this, every
  // real failure just showed the same generic fallback text, which
  // made diagnosing anything reported here far harder than it needed
  // to be.
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

  function formatDateTime(value) {
    if (!value) return "";
    var date = new Date(String(value).replace(" ", "T"));
    if (Number.isNaN(date.getTime())) return String(value);
    return date.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" }) +
      " at " + date.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
  }

  // -------------------------------------------------------------------
  // Shared rendering - used by both the coach's own page and (in HQ
  // mode) the franchisor drill-down.
  // -------------------------------------------------------------------

  function renderStepRow(step, hqMode) {
    var lockedNote = step.is_locked
      ? '<div class="dashboard-doc-list-meta">Unlocks once an earlier step is done</div>'
      : "";

    var goLink = (!step.is_locked && step.link_url)
      ? '<a class="dashboard-btn dashboard-btn-light" href="' + escapeHtml(step.link_url) + '" target="_blank" rel="noopener noreferrer">Go</a>'
      : "";

    var actionCell;

    // An LMS-based step (a course module the coach completes elsewhere)
    // isn't something to self-report Done from this dashboard - a
    // misclick here marks it complete with no actual course completion
    // behind it. Until real course-completion tracking exists, these are
    // Go-only for the coach; only HQ (the status dropdown below, in the
    // franchisor drill-down) can correct the status.
    var isLmsStep = step.owner_type === "Coach" && step.where_it_happens === "LMS";

    // Policies rows are a live mirror of Coach Document Requirement, not
    // a real Coach Onboarding Step - there's no step to "mark done" here
    // at all (that happens by acknowledging the actual document on the
    // Documents page), so this never gets the usual button/dropdown. The
    // status badge already says "Completed" - repeating the completion
    // date next to it here was just noise, so this is Go-only.
    if (step.read_only) {
      actionCell = "";
    } else if (hqMode) {
      var options = HQ_STATUSES.map(function (status) {
        return '<option value="' + status + '"' + (status === step.status ? " selected" : "") + '>' + status + "</option>";
      }).join("");
      actionCell = '<select class="dashboard-select dashboard-onboarding-status-select" data-step="' + escapeHtml(step.name) + '">' + options + "</select>";
    } else if (isLmsStep) {
      actionCell = step.status === "Done"
        ? '<span class="dashboard-doc-list-meta">' + escapeHtml(formatDateTime(step.completed_on)) + "</span>"
        : "";
    } else if (step.owner_type === "Coach" && step.status !== "Done" && !step.is_locked) {
      actionCell = '<button type="button" class="dashboard-btn dashboard-btn-primary dashboard-onboarding-mark-done" data-step="' + escapeHtml(step.name) + '">Mark Done</button>';
    } else if (step.status === "Done") {
      actionCell = '<span class="dashboard-doc-list-meta">' + escapeHtml(formatDateTime(step.completed_on)) + "</span>";
    } else {
      actionCell = '<span class="dashboard-doc-list-meta">Owned by ' + escapeHtml(step.owner_type) + "</span>";
    }

    return (
      '<tr class="' + (step.is_locked ? "dashboard-onboarding-row-locked" : "") + '">' +
        "<td>" +
          '<div class="dashboard-doc-list-title">' + escapeHtml(step.step_name) + "</div>" +
          (step.expected_result ? '<div class="dashboard-doc-list-meta">' + escapeHtml(step.expected_result) + "</div>" : "") +
          lockedNote +
        "</td>" +
        "<td>" + escapeHtml(step.owner_type) + "</td>" +
        "<td><span class=\"dashboard-badge " + (STATUS_CLASS[step.status] || "") + "\">" + escapeHtml(step.is_locked ? "Locked" : step.status) + "</span></td>" +
        '<td class="dashboard-text-right dashboard-doc-list-actions">' + goLink + actionCell + "</td>" +
      "</tr>"
    );
  }

  function isStepDone(step) {
    return step.status === "Done" || step.status === "Completed";
  }

  function renderStage(stage, hqMode, hideCompleted) {
    var allDone = stage.steps.length > 0 && stage.steps.every(isStepDone);
    var completeBadge = allDone
      ? '<span class="dashboard-badge doc-status-completed dashboard-onboarding-stage-complete-badge">All done</span>'
      : "";

    // Hiding completed steps is opt-out on the coach's own page (see
    // onboardingShowCompletedCheckbox) so a coach mid-journey sees only
    // what's still due instead of a long list dominated by everything
    // they already finished - HQ's drill-down never hides anything
    // (hideCompleted is only ever passed true from loadMyOnboarding).
    // allDone/the stage collapsing is worked out from the full list
    // either way, so this never leaves an open stage with an empty table
    // - if every step were hidden, allDone would be true and the whole
    // stage collapses instead.
    var visibleSteps = hideCompleted ? stage.steps.filter(function (step) { return !isStepDone(step); }) : stage.steps;
    var hiddenCount = stage.steps.length - visibleSteps.length;
    var hiddenNote = (hiddenCount > 0 && !allDone)
      ? '<div class="dashboard-doc-list-meta dashboard-onboarding-hidden-note">' +
          hiddenCount + " completed step" + (hiddenCount === 1 ? "" : "s") + " hidden</div>"
      : "";

    // A native <details>/<summary> collapses a stage automatically once
    // everything in it is done, without needing any JS to track open/
    // closed state - it just starts collapsed for a stage that already
    // was complete when the page loaded, and stays interactive (click
    // the title to reopen) for anyone who wants to double check it.
    return (
      '<details class="dashboard-card dashboard-onboarding-stage"' + (allDone ? "" : " open") + '>' +
        '<summary class="dashboard-onboarding-stage-title">' + escapeHtml(stage.stage) + completeBadge + '</summary>' +
        hiddenNote +
        '<table class="dashboard-table dashboard-doc-list-table">' +
          "<thead><tr><th>Step</th><th>Owner</th><th>Status</th><th class=\"dashboard-text-right\">Action</th></tr></thead>" +
          "<tbody>" + visibleSteps.map(function (step) { return renderStepRow(step, hqMode); }).join("") + "</tbody>" +
        "</table>" +
      "</details>"
    );
  }

  function renderProgress(data) {
    var card = el("onboardingProgressCard");
    var fill = el("onboardingProgressFill");
    var label = el("onboardingProgressLabel");
    var showCompletedRow = el("onboardingShowCompletedRow");
    if (!card || !fill || !label) return;

    if (!data.started || !data.total_steps) {
      card.style.display = "none";
      if (showCompletedRow) showCompletedRow.style.display = "none";
      return;
    }

    var pct = Math.round((data.done_steps / data.total_steps) * 100);
    card.style.display = "block";
    fill.style.width = pct + "%";
    label.textContent = data.done_steps + " of " + data.total_steps + " steps done (" + pct + "%)";

    // Only worth offering once there's actually something done to hide -
    // nothing to toggle on a fresh journey with 0 steps completed yet.
    if (showCompletedRow) showCompletedRow.style.display = data.done_steps > 0 ? "flex" : "none";
  }

  function bindStepActions(container, onChange) {
    container.querySelectorAll(".dashboard-onboarding-mark-done").forEach(function (btn) {
      btn.addEventListener("click", async function () {
        btn.disabled = true;
        btn.textContent = "Saving...";
        try {
          await apiPost(API + ".mark_step_done", { step_name: btn.dataset.step });
          onChange();
        } catch (error) {
          window.alert(error.message || "Could not update this step.");
          btn.disabled = false;
          btn.textContent = "Mark Done";
        }
      });
    });

    container.querySelectorAll(".dashboard-onboarding-status-select").forEach(function (select) {
      select.addEventListener("change", async function () {
        select.disabled = true;
        try {
          await apiPost(API + ".mark_step_done_for_coach", { step_name: select.dataset.step, status: select.value });
          onChange();
        } catch (error) {
          window.alert(error.message || "Could not update this step.");
        } finally {
          select.disabled = false;
        }
      });
    });
  }

  // -------------------------------------------------------------------
  // Coach's own page
  // -------------------------------------------------------------------

  // Hides completed steps by default so a long-in-progress journey shows
  // what's still due instead of a list dominated by everything already
  // finished - persisted per-browser (not per-account) since it's purely
  // a display preference, not something anyone else needs to see. Coach
  // page and franchisor drill-down use separate keys since they're
  // realistically different people/sessions and independently useful.
  var COACH_HIDE_COMPLETED_STORAGE_KEY = "trk_onboarding_show_completed";
  var HQ_HIDE_COMPLETED_STORAGE_KEY = "trk_onboarding_show_completed_hq";

  function getShowCompletedPreference(storageKey) {
    try {
      return window.localStorage.getItem(storageKey) === "1";
    } catch (error) {
      return false;
    }
  }

  function setShowCompletedPreference(storageKey, showCompleted) {
    try {
      window.localStorage.setItem(storageKey, showCompleted ? "1" : "0");
    } catch (error) {
      // Private browsing / storage blocked - the toggle still works for
      // this page view, it just won't be remembered next visit.
    }
  }

  var lastOnboardingData = null;

  function renderMyOnboardingStages() {
    var content = el("onboardingContent");
    if (!content || !lastOnboardingData) return;

    var hideCompleted = !getShowCompletedPreference(COACH_HIDE_COMPLETED_STORAGE_KEY);
    content.innerHTML = lastOnboardingData.stages
      .map(function (stage) { return renderStage(stage, false, hideCompleted); })
      .join("");
    bindStepActions(content, loadMyOnboarding);
  }

  async function loadMyOnboarding() {
    var content = el("onboardingContent");
    if (!content) return;

    var data;
    try {
      data = await apiGet(API + ".get_my_onboarding_steps", {});
    } catch (error) {
      content.innerHTML = '<div class="dashboard-empty">' + escapeHtml(error.message) + "</div>";
      return;
    }

    if (!data.started) {
      content.innerHTML = '<div class="dashboard-empty">Your onboarding journey hasn\'t started yet - reach out if you think this is a mistake.</div>';
      return;
    }

    lastOnboardingData = data;
    renderProgress(data);
    renderMyOnboardingStages();
  }

  function initCoachOnboardingPage() {
    if (!el("onboardingPage") || window.location.pathname.indexOf("/franchisor_db") !== -1) return;

    var checkbox = el("onboardingShowCompletedCheckbox");
    if (checkbox) {
      checkbox.checked = getShowCompletedPreference(COACH_HIDE_COMPLETED_STORAGE_KEY);
      checkbox.addEventListener("change", function () {
        setShowCompletedPreference(COACH_HIDE_COMPLETED_STORAGE_KEY, checkbox.checked);
        renderMyOnboardingStages();
      });
    }

    loadMyOnboarding();
  }

  // -------------------------------------------------------------------
  // Franchisor overview + drill-down
  // -------------------------------------------------------------------

  function renderOverviewRow(row) {
    var pct = row.total_steps ? Math.round((row.done_steps / row.total_steps) * 100) : 0;

    return (
      "<tr>" +
        "<td>" +
          '<a href="#" class="dashboard-onboarding-view-coach" data-coach="' + escapeHtml(row.coach) + '">' +
            escapeHtml(row.coach_label) +
          "</a>" +
        "</td>" +
        "<td>" + escapeHtml(row.current_stage) + "</td>" +
        "<td>" + row.done_steps + " / " + row.total_steps + " (" + pct + "%)</td>" +
        "<td>" + (row.waiting_on_hq
          ? '<span class="dashboard-badge doc-status-overdue">' + row.waiting_on_hq + " waiting on HQ</span>"
          : "&mdash;") +
        "</td>" +
      "</tr>"
    );
  }

  async function loadOverview() {
    var body = el("onboardingOverviewBody");
    var table = el("onboardingOverviewTable");
    var detail = el("onboardingOverviewDetail");
    var manager = el("onboardingStepManagerSection");
    if (!body) return;

    if (detail) detail.style.display = "none";
    if (manager) manager.style.display = "none";
    if (table) table.style.display = "";

    var rows;
    try {
      rows = await apiGet(API + ".get_all_coaches_onboarding_progress", {});
    } catch (error) {
      body.innerHTML = '<tr><td colspan="4"><div class="dashboard-empty">' + escapeHtml(error.message) + "</div></td></tr>";
      return;
    }

    if (!rows.length) {
      body.innerHTML = '<tr><td colspan="4"><div class="dashboard-empty">No coaches are currently onboarding.</div></td></tr>';
      return;
    }

    body.innerHTML = rows.map(renderOverviewRow).join("");

    body.querySelectorAll(".dashboard-onboarding-view-coach").forEach(function (link) {
      link.addEventListener("click", function (event) {
        event.preventDefault();
        loadCoachDetail(link.dataset.coach);
      });
    });
  }

  var lastCoachDetailData = null;
  var lastCoachDetailName = null;

  function renderCoachDetailStages() {
    var content = el("onboardingOverviewDetailContent");
    if (!content || !lastCoachDetailData) return;

    var hideCompleted = !getShowCompletedPreference(HQ_HIDE_COMPLETED_STORAGE_KEY);
    content.innerHTML = lastCoachDetailData.stages
      .map(function (stage) { return renderStage(stage, true, hideCompleted); })
      .join("");
    bindStepActions(content, function () { loadCoachDetail(lastCoachDetailName); });
  }

  async function loadCoachDetail(coachName) {
    var table = el("onboardingOverviewTable");
    var detail = el("onboardingOverviewDetail");
    var manager = el("onboardingStepManagerSection");
    var content = el("onboardingOverviewDetailContent");
    var title = el("onboardingOverviewDetailTitle");
    if (!detail || !content) return;

    if (table) table.style.display = "none";
    if (manager) manager.style.display = "none";
    detail.style.display = "block";
    if (title) title.textContent = "Onboarding - " + coachName;
    content.innerHTML = '<div class="dashboard-empty">Loading...</div>';

    var data;
    try {
      data = await apiGet(API + ".get_my_onboarding_steps", { coach: coachName });
    } catch (error) {
      content.innerHTML = '<div class="dashboard-empty">' + escapeHtml(error.message) + "</div>";
      return;
    }

    lastCoachDetailData = data;
    lastCoachDetailName = coachName;
    renderCoachDetailStages();
  }

  // -------------------------------------------------------------------
  // Step list manager - lets HQ add a "Go" link (or edit one) on any
  // step directly from the dashboard, without needing Desk access.
  // Edits the master Onboarding Step, and also updates the link on any
  // Coach Onboarding Step rows already created from it, so a coach
  // already partway through sees the corrected/added link immediately
  // rather than only coaches who start onboarding from now on.
  // -------------------------------------------------------------------

  function renderChapterOptions(chapters, step) {
    // chapter_name is the real Course Chapter document name - an exact,
    // unambiguous key regardless of course, unlike matching on title
    // text (which is how this used to work, and turned out unreliable).
    var courseGroups = {};
    var courseOrder = [];
    chapters.forEach(function (c) {
      if (!(c.course in courseGroups)) {
        courseGroups[c.course] = { title: c.course_title, chapters: [] };
        courseOrder.push(c.course);
      }
      courseGroups[c.course].chapters.push(c);
    });

    var optionsHtml = '<option value=""' + (step.lms_chapter ? "" : " selected") + '>— none —</option>';

    optionsHtml += courseOrder.map(function (courseName) {
      var group = courseGroups[courseName];
      var optionsForCourse = group.chapters.map(function (c) {
        var isSelected = c.chapter_name === step.lms_chapter;
        return '<option value="' + escapeHtml(c.chapter_name) + '" data-course="' + escapeHtml(c.course) + '"' +
          (isSelected ? " selected" : "") + ">" + escapeHtml(c.chapter_title) + "</option>";
      }).join("");
      return '<optgroup label="' + escapeHtml(group.title) + '">' + optionsForCourse + "</optgroup>";
    }).join("");

    return optionsHtml;
  }

  function findChapterEntry(chapters, chapterName) {
    return chapters.find(function (c) { return c.chapter_name === chapterName; });
  }

  function renderLessonOptions(lessons, selectedNumber) {
    if (!lessons || !lessons.length) {
      return '<option value="1">Lesson 1</option>';
    }
    return lessons.map(function (lesson) {
      var isSelected = String(lesson.idx) === String(selectedNumber);
      return '<option value="' + lesson.idx + '"' + (isSelected ? " selected" : "") + ">" +
        escapeHtml(lesson.idx + ". " + lesson.title) + "</option>";
    }).join("");
  }

  function renderStepManagerRow(step, chapters) {
    // An LMS step's Go link and Done status are worked out live from
    // actual course progress once HQ picks which chapter (and which
    // lesson Go should open) to watch (see _apply_lms_progress_overrides)
    // - dropdowns of the real chapters/lessons Frappe LMS actually has,
    // so there's nothing to mistype. Done still requires every lesson in
    // the chapter, regardless of which one Go points to.
    var isLmsStep = step.where_it_happens === "LMS";

    var linkCell;
    if (isLmsStep && chapters.length) {
      var currentChapter = step.lms_chapter ? findChapterEntry(chapters, step.lms_chapter) : null;

      linkCell = '<select class="dashboard-select dashboard-onboarding-lms-chapter-select" data-step="' +
          escapeHtml(step.name) + '">' + renderChapterOptions(chapters, step) + "</select>" +
          '<select class="dashboard-select dashboard-onboarding-lms-lesson-select" data-step="' +
          escapeHtml(step.name) + '" style="margin-top:6px;">' +
          renderLessonOptions(currentChapter ? currentChapter.lessons : [], step.lms_lesson_number || 1) +
          "</select>" +
          '<div class="dashboard-doc-list-meta">Go opens the lesson picked above; Done is automatic once every lesson in the chapter is complete</div>';
    } else if (isLmsStep) {
      linkCell = '<div class="dashboard-doc-list-meta">No LMS chapters found - check Frappe LMS is installed.</div>';
    } else {
      linkCell = '<input type="text" class="dashboard-input dashboard-onboarding-link-input" data-step="' +
          escapeHtml(step.name) + '" value="' + escapeHtml(step.link_url || "") +
          '" placeholder="/coach_db/... or https://...">';
    }

    return (
      "<tr>" +
        "<td>" +
          '<div class="dashboard-doc-list-title">' + escapeHtml(step.step_name) + "</div>" +
          (step.expected_result ? '<div class="dashboard-doc-list-meta">' + escapeHtml(step.expected_result) + "</div>" : "") +
        "</td>" +
        "<td>" + escapeHtml(step.owner_type) + "</td>" +
        "<td>" + linkCell + "</td>" +
        '<td class="dashboard-text-right">' +
          '<button type="button" class="dashboard-btn dashboard-btn-primary dashboard-onboarding-save-link" data-step="' +
            escapeHtml(step.name) + '" data-lms="' + (isLmsStep ? "1" : "0") + '">Save</button>' +
        "</td>" +
      "</tr>"
    );
  }

  function renderStepManagerStage(stage, chapters) {
    return (
      '<div class="dashboard-card dashboard-onboarding-stage">' +
        '<h3 class="dashboard-onboarding-stage-title">' + escapeHtml(stage.stage) + "</h3>" +
        '<table class="dashboard-table dashboard-doc-list-table">' +
          "<thead><tr><th>Step</th><th>Owner</th><th>Link URL / LMS Chapter</th><th class=\"dashboard-text-right\">Action</th></tr></thead>" +
          "<tbody>" + stage.steps.map(function (step) { return renderStepManagerRow(step, chapters); }).join("") + "</tbody>" +
        "</table>" +
      "</div>"
    );
  }

  async function loadStepManager() {
    var content = el("onboardingStepManagerContent");
    if (!content) return;

    content.innerHTML = '<div class="dashboard-empty">Loading...</div>';

    var steps, chapters;
    try {
      steps = await apiGet(API + ".get_onboarding_step_master_list", {});
      chapters = await apiGet(API + ".get_lms_chapters", {});
    } catch (error) {
      content.innerHTML = '<div class="dashboard-empty">' + escapeHtml(error.message) + "</div>";
      return;
    }

    var stageMap = {};
    var stages = [];

    steps.forEach(function (step) {
      var stageLabel = step.stage || "Unassigned";
      if (!(stageLabel in stageMap)) {
        stageMap[stageLabel] = stages.length;
        stages.push({ stage: stageLabel, steps: [] });
      }
      stages[stageMap[stageLabel]].steps.push(step);
    });

    if (!stages.length) {
      content.innerHTML = '<div class="dashboard-empty">No onboarding steps set up yet.</div>';
      return;
    }

    content.innerHTML = stages.map(function (stage) { return renderStepManagerStage(stage, chapters); }).join("");

    // Picking a different chapter needs the lesson dropdown next to it
    // rebuilt from that chapter's own lessons - it's a fresh list per
    // chapter, not shared, so nothing to do here beyond looking the
    // newly-picked chapter back up in the same data already loaded.
    content.querySelectorAll(".dashboard-onboarding-lms-chapter-select").forEach(function (chapterSelect) {
      chapterSelect.addEventListener("change", function () {
        var lessonSelect = content.querySelector(
          '.dashboard-onboarding-lms-lesson-select[data-step="' + chapterSelect.dataset.step + '"]',
        );
        if (!lessonSelect) return;

        var entry = findChapterEntry(chapters, chapterSelect.value);

        lessonSelect.innerHTML = renderLessonOptions(entry ? entry.lessons : [], 1);
      });
    });

    content.querySelectorAll(".dashboard-onboarding-save-link").forEach(function (btn) {
      btn.addEventListener("click", async function () {
        var isLms = btn.dataset.lms === "1";
        var fieldSelector = (isLms ? ".dashboard-onboarding-lms-chapter-select" : ".dashboard-onboarding-link-input") +
          '[data-step="' + btn.dataset.step + '"]';
        var field = content.querySelector(fieldSelector);
        if (!field) return;

        btn.disabled = true;
        var originalLabel = btn.textContent;
        btn.textContent = "Saving...";

        try {
          var payload = { step_name: btn.dataset.step };
          if (isLms) {
            var selectedOption = field.options[field.selectedIndex];
            var lessonSelect = content.querySelector(
              '.dashboard-onboarding-lms-lesson-select[data-step="' + btn.dataset.step + '"]',
            );
            payload.lms_chapter = field.value;
            payload.lms_course = selectedOption ? (selectedOption.dataset.course || "") : "";
            payload.lms_lesson_number = lessonSelect ? (lessonSelect.value || "1") : "1";
          } else {
            payload.link_url = field.value;
          }
          await apiPost(API + ".update_onboarding_step_master", payload);
          btn.textContent = "Saved";
          window.setTimeout(function () {
            btn.textContent = originalLabel;
            btn.disabled = false;
          }, 1200);
        } catch (error) {
          window.alert(error.message || "Could not save this link.");
          btn.textContent = originalLabel;
          btn.disabled = false;
        }
      });
    });
  }

  function showStepManager() {
    var table = el("onboardingOverviewTable");
    var detail = el("onboardingOverviewDetail");
    var manager = el("onboardingStepManagerSection");
    if (table) table.style.display = "none";
    if (detail) detail.style.display = "none";
    if (manager) manager.style.display = "block";
    loadStepManager();
  }

  function initFranchisorOnboardingPage() {
    var table = el("onboardingOverviewTable");
    if (!table) return;

    loadOverview();

    var backBtn = el("onboardingOverviewBackBtn");
    if (backBtn) {
      backBtn.addEventListener("click", function () {
        loadOverview();
      });
    }

    var manageBtn = el("onboardingManageStepsBtn");
    if (manageBtn) {
      manageBtn.addEventListener("click", showStepManager);
    }

    var hqCheckbox = el("onboardingOverviewShowCompletedCheckbox");
    if (hqCheckbox) {
      hqCheckbox.checked = getShowCompletedPreference(HQ_HIDE_COMPLETED_STORAGE_KEY);
      hqCheckbox.addEventListener("change", function () {
        setShowCompletedPreference(HQ_HIDE_COMPLETED_STORAGE_KEY, hqCheckbox.checked);
        renderCoachDetailStages();
      });
    }

    var managerBackBtn = el("onboardingStepManagerBackBtn");
    if (managerBackBtn) {
      managerBackBtn.addEventListener("click", loadOverview);
    }
  }

  function init() {
    initCoachOnboardingPage();
    initFranchisorOnboardingPage();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
