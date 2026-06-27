(function () {
  var el = Dashboard.el;
  var qsa = Dashboard.qsa;

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
