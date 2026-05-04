(function () {
  "use strict";

  const privateEvents = new Set();

  function getUrlSelectedCalendarFor() {
    const params = new URLSearchParams(window.location.search);
    return params.get("calendar_for") || "";
  }

  function setUrlSelectedCalendarFor(value) {
    const params = new URLSearchParams(window.location.search);
    params.set("calendar_for", value || "__coach_me__");

    const newUrl = window.location.pathname + "?" + params.toString();
    window.history.replaceState({}, "", newUrl);
  }

  function getSelectedWorker() {
    const field = document.getElementById("trkCoachCalendarWorkerSelect");
    return field && field.value ? field.value : getUrlSelectedCalendarFor();
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

    const urlSelected = getUrlSelectedCalendarFor();
    const finalSelected = selectedWorker || urlSelected || "__coach_me__";

    let html = "";

    rows.forEach(function (row) {
      const value = escapeHtml(row.value || "");
      const label = escapeHtml(row.label || row.value || "");
      const selected = finalSelected === row.value ? " selected" : "";

      html += '<option value="' + value + '"' + selected + ">" + label + "</option>";
    });

    select.innerHTML = html || '<option value="">No calendars found</option>';

    if (finalSelected) {
      select.value = finalSelected;
      setUrlSelectedCalendarFor(finalSelected);
    }
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
      const urlSelected = getUrlSelectedCalendarFor();
      if (urlSelected) {
        select.innerHTML = '<option value="' + escapeHtml(urlSelected) + '" selected>Loading...</option>';
      }

      select.addEventListener("change", function () {
        setUrlSelectedCalendarFor(this.value || "__coach_me__");
        window.location.reload();
      });
    }
  });
})();
