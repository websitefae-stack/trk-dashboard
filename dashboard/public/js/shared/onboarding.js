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
    "Done": "doc-status-completed"
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

    if (hqMode) {
      var options = HQ_STATUSES.map(function (status) {
        return '<option value="' + status + '"' + (status === step.status ? " selected" : "") + '>' + status + "</option>";
      }).join("");
      actionCell = '<select class="dashboard-select dashboard-onboarding-status-select" data-step="' + escapeHtml(step.name) + '">' + options + "</select>";
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

  function renderStage(stage, hqMode) {
    return (
      '<div class="dashboard-card dashboard-onboarding-stage">' +
        '<h3 class="dashboard-onboarding-stage-title">' + escapeHtml(stage.stage) + "</h3>" +
        '<table class="dashboard-table dashboard-doc-list-table">' +
          "<thead><tr><th>Step</th><th>Owner</th><th>Status</th><th class=\"dashboard-text-right\">Action</th></tr></thead>" +
          "<tbody>" + stage.steps.map(function (step) { return renderStepRow(step, hqMode); }).join("") + "</tbody>" +
        "</table>" +
      "</div>"
    );
  }

  function renderProgress(data) {
    var card = el("onboardingProgressCard");
    var fill = el("onboardingProgressFill");
    var label = el("onboardingProgressLabel");
    if (!card || !fill || !label) return;

    if (!data.started || !data.total_steps) {
      card.style.display = "none";
      return;
    }

    var pct = Math.round((data.done_steps / data.total_steps) * 100);
    card.style.display = "block";
    fill.style.width = pct + "%";
    label.textContent = data.done_steps + " of " + data.total_steps + " steps done (" + pct + "%)";
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

    renderProgress(data);
    content.innerHTML = data.stages.map(function (stage) { return renderStage(stage, false); }).join("");
    bindStepActions(content, loadMyOnboarding);
  }

  function initCoachOnboardingPage() {
    if (!el("onboardingPage") || window.location.pathname.indexOf("/franchisor_db") !== -1) return;
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

    content.innerHTML = data.stages.map(function (stage) { return renderStage(stage, true); }).join("");
    bindStepActions(content, function () { loadCoachDetail(coachName); });
  }

  // -------------------------------------------------------------------
  // Step list manager - lets HQ add a "Go" link (or edit one) on any
  // step directly from the dashboard, without needing Desk access.
  // Edits the master Onboarding Step, and also updates the link on any
  // Coach Onboarding Step rows already created from it, so a coach
  // already partway through sees the corrected/added link immediately
  // rather than only coaches who start onboarding from now on.
  // -------------------------------------------------------------------

  function renderStepManagerRow(step) {
    return (
      "<tr>" +
        "<td>" +
          '<div class="dashboard-doc-list-title">' + escapeHtml(step.step_name) + "</div>" +
          (step.expected_result ? '<div class="dashboard-doc-list-meta">' + escapeHtml(step.expected_result) + "</div>" : "") +
        "</td>" +
        "<td>" + escapeHtml(step.owner_type) + "</td>" +
        "<td>" +
          '<input type="text" class="dashboard-input dashboard-onboarding-link-input" data-step="' +
            escapeHtml(step.name) + '" value="' + escapeHtml(step.link_url || "") +
            '" placeholder="/coach_db/... or https://...">' +
        "</td>" +
        '<td class="dashboard-text-right">' +
          '<button type="button" class="dashboard-btn dashboard-btn-primary dashboard-onboarding-save-link" data-step="' +
            escapeHtml(step.name) + '">Save</button>' +
        "</td>" +
      "</tr>"
    );
  }

  function renderStepManagerStage(stage) {
    return (
      '<div class="dashboard-card dashboard-onboarding-stage">' +
        '<h3 class="dashboard-onboarding-stage-title">' + escapeHtml(stage.stage) + "</h3>" +
        '<table class="dashboard-table dashboard-doc-list-table">' +
          "<thead><tr><th>Step</th><th>Owner</th><th>Link URL</th><th class=\"dashboard-text-right\">Action</th></tr></thead>" +
          "<tbody>" + stage.steps.map(renderStepManagerRow).join("") + "</tbody>" +
        "</table>" +
      "</div>"
    );
  }

  async function loadStepManager() {
    var content = el("onboardingStepManagerContent");
    if (!content) return;

    content.innerHTML = '<div class="dashboard-empty">Loading...</div>';

    var steps;
    try {
      steps = await apiGet(API + ".get_onboarding_step_master_list", {});
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

    content.innerHTML = stages.map(renderStepManagerStage).join("");

    content.querySelectorAll(".dashboard-onboarding-save-link").forEach(function (btn) {
      btn.addEventListener("click", async function () {
        var input = content.querySelector('.dashboard-onboarding-link-input[data-step="' + btn.dataset.step + '"]');
        if (!input) return;

        btn.disabled = true;
        var originalLabel = btn.textContent;
        btn.textContent = "Saving...";

        try {
          await apiPost(API + ".update_onboarding_step_master", { step_name: btn.dataset.step, link_url: input.value });
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
