(function () {
  "use strict";

  const privateEvents = new Set();

  function getSelectedWorker() {
    const field = document.getElementById("trkCoachCalendarWorkerSelect");
    return field ? field.value || "" : "";
  }

  const originalFetch = window.fetch;

  window.fetch = function (input, init) {
    let url = typeof input === "string" ? input : input && input.url ? input.url : "";

    if (url.indexOf("/api/method/dashboard.api.session_worker.calendar.") !== -1) {
      url = url.replace(
        "/api/method/dashboard.api.session_worker.calendar.",
        "/api/method/dashboard.api.coach.calendar."
      );

      if (url.indexOf("get_calendar_bootstrap") !== -1) {
        const selectedWorker = getSelectedWorker();
        if (selectedWorker) {
          const parsed = new URL(url, window.location.origin);
          parsed.searchParams.set("selected_worker", selectedWorker);
          url = parsed.toString();
        }
      }

      input = url;
    }

    return originalFetch(input, init).then(function (response) {
      try {
        const cloned = response.clone();

        cloned.json().then(function (data) {
          const message = data && data.message ? data.message : {};

          if (Array.isArray(message.events)) {
            privateEvents.clear();

            message.events.forEach(function (event) {
              if (Number(event.is_private || 0)) {
                privateEvents.add(event.name || event.id);
              }
            });
          }

          if (Array.isArray(message.session_workers)) {
            renderSessionWorkerOptions(message.session_workers, message.selected_worker || "");
          }
        }).catch(function () {});
      } catch (error) {}

      return response;
    });
  };

  function renderSessionWorkerOptions(rows, selectedWorker) {
    const select = document.getElementById("trkCoachCalendarWorkerSelect");
    if (!select) return;

    const oldValue = select.value || "";
    let html = "";

    rows.forEach(function (row) {
      const value = escapeHtml(row.value || "");
      const label = escapeHtml(row.label || row.value || "");
      const selected = (selectedWorker || oldValue) === row.value ? " selected" : "";

      html += '<option value="' + value + '"' + selected + ">" + label + "</option>";
    });

    if (!html) {
      html = '<option value="">No session workers found</option>';
    }

    select.innerHTML = html;
  }

  function removePrivateActions() {
    const body = document.getElementById("trkCalendarDetailsBody");
    if (!body) return;

    const editButton = body.querySelector("[data-calendar-action='edit-session']");
    const noteButton = body.querySelector("[data-calendar-action='add-note']");

    const eventName = editButton ? editButton.getAttribute("data-event") : "";

    if (!eventName || !privateEvents.has(eventName)) {
      return;
    }

    if (editButton) editButton.remove();
    if (noteButton) noteButton.remove();

    const openLink = body.querySelector("a[href*='calendar_details']");
    if (openLink) openLink.remove();

    if (!body.querySelector(".trk-coach-private-event-notice")) {
      const notice = document.createElement("div");
      notice.className = "dashboard-notice trk-coach-private-event-notice";
      notice.style.marginTop = "14px";
      notice.textContent = "This appointment belongs to another coach. Details are hidden.";
      body.appendChild(notice);
    }
  }

  function rewriteCoachLinks() {
    document.querySelectorAll("a[href*='/session_worker_db/calendar_details']").forEach(function (link) {
      link.href = link.href.replace("/session_worker_db/calendar_details", "/coach_db/calendar_details");
    });
  }

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  document.addEventListener("DOMContentLoaded", function () {
    const select = document.getElementById("trkCoachCalendarWorkerSelect");

    if (select) {
      select.addEventListener("change", function () {
        window.location.reload();
      });
    }

    const observer = new MutationObserver(function () {
      removePrivateActions();
      rewriteCoachLinks();
    });

    observer.observe(document.body, {
      childList: true,
      subtree: true
    });
  });
})();
