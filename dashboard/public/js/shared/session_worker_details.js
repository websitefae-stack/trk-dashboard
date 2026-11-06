(function () {
  var el = Dashboard.el;
  var qsa = Dashboard.qsa;
  var SHARED_API = "dashboard.api.shared.session_workers";

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
      throw new Error(Dashboard.extractErrorMessage(data, "There was a problem."));
    }

    return data.message || {};
  }

  async function initApprovedCoaches() {
    var list = el("swApprovedCoachesList");
    var saveBtn = el("swSaveApprovedCoachesBtn");
    var nameInput = el("swDetailName");
    if (!list || !saveBtn || !nameInput) return;

    var sessionWorker = nameInput.value;
    if (!sessionWorker) return;

    var statusEl = el("swApprovedCoachesStatus");

    try {
      var options = await apiPost(SHARED_API + ".get_coach_options_for_session_worker_link", {});
      var linked = await apiPost(SHARED_API + ".get_session_worker_coach_links", { session_worker: sessionWorker });
      var linkedSet = {};
      (linked || []).forEach(function (name) { linkedSet[name] = true; });

      if (!options.length) {
        list.innerHTML = '<span class="dashboard-help">No coaches found.</span>';
        return;
      }

      list.innerHTML = options.map(function (coach) {
        var checked = linkedSet[coach.name] ? " checked" : "";
        return (
          '<label style="display:flex; align-items:center; gap:8px; font-weight:400;">' +
            '<input type="checkbox" class="sw-approved-coach-checkbox" value="' + escapeHtml(coach.name) + '"' + checked + '>' +
            escapeHtml(coach.coach_name || coach.name) +
          "</label>"
        );
      }).join("");
    } catch (error) {
      list.innerHTML = '<span class="dashboard-help">' + escapeHtml(error.message || "Could not load coaches.") + "</span>";
      return;
    }

    saveBtn.addEventListener("click", async function () {
      var selected = qsa(".sw-approved-coach-checkbox")
        .filter(function (box) { return box.checked; })
        .map(function (box) { return box.value; });

      saveBtn.disabled = true;
      if (statusEl) statusEl.textContent = "Saving…";

      try {
        await apiPost(SHARED_API + ".save_session_worker_coach_links", {
          session_worker: sessionWorker,
          coaches: selected,
        });
        if (statusEl) statusEl.textContent = "Saved.";
      } catch (error) {
        if (statusEl) statusEl.textContent = error.message || "Could not save this.";
      } finally {
        saveBtn.disabled = false;
      }
    });
  }

  function initSessionWorkerDetailTabs() {
    const buttons = qsa(".dashboard-session-worker-detail-tab-btn");
    if (!buttons.length) return;

    buttons.forEach((button) => {
      if (button.dataset.sessionWorkerDetailTabBound === "1") return;

      button.dataset.sessionWorkerDetailTabBound = "1";

      button.addEventListener("click", function () {
        const target = button.dataset.tabTarget;
        if (!target) return;

        qsa(".dashboard-session-worker-detail-tab-btn").forEach((btn) => {
          btn.classList.remove("is-active");
        });

        qsa(".dashboard-session-worker-detail-panel").forEach((panel) => {
          panel.classList.remove("is-active");
        });

        button.classList.add("is-active");

        const panel = el(target);
        if (panel) panel.classList.add("is-active");
      });
    });
  }

  function initSessionWorkerDetailsPage() {
    initSessionWorkerDetailTabs();
    initApprovedCoaches();
  }

  window.TRKDashboardSessionWorkerDetails = {
    initSessionWorkerDetailTabs
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initSessionWorkerDetailsPage);
  } else {
    initSessionWorkerDetailsPage();
  }
})();
