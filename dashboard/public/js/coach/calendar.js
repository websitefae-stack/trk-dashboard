(function () {
  "use strict";

  const privateEvents = new Set();
  const STORAGE_KEY = "trkCoachCalendarFor";

  function getSelectedCalendarFor() {
    const params = new URLSearchParams(window.location.search);
    const fromUrl = params.get("calendar_for") || params.get("selected_calendar_for") || params.get("selected_worker");

    if (fromUrl) return fromUrl;

    return window.localStorage.getItem(STORAGE_KEY) || "__coach_me__";
  }

  function setSelectedCalendarFor(value) {
    const selected = value || "__coach_me__";

    window.localStorage.setItem(STORAGE_KEY, selected);

    const params = new URLSearchParams(window.location.search);
    params.set("calendar_for", selected);
    params.set("selected_calendar_for", selected);
    params.set("selected_worker", selected);

    window.location.href = window.location.pathname + "?" + params.toString();
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
        const selected = getSelectedCalendarFor();
        const parsed = new URL(url, window.location.origin);

        parsed.searchParams.set("calendar_for", selected);
        parsed.searchParams.set("selected_calendar_for", selected);
        parsed.searchParams.set("selected_worker", selected);

        url = parsed.toString();
      }

      input = url;
    }

    return originalFetch(input, init).then(function (response) {
      try {
        response.clone().json().then(function (data) {
          const message = data && data.message ? data.message : {};

          if (Array.isArray(message.events)) {
            privateEvents.clear();

            message.events.forEach(function (event) {
              if (Number(event.is_private || 0)) {
                privateEvents.add(event.name || event.id);
              }
            });
          }

          renderCalendarForOptions(
            Array.isArray(message.calendar_for_options) ? message.calendar_for_options : [],
            message.selected_calendar_for || getSelectedCalendarFor()
          );
        }).catch(function () {});
      } catch (error) {}

      return response;
    });
  };

  function renderCalendarForOptions(rows, selectedValue) {
    const select = document.getElementById("trkCoachCalendarWorkerSelect");
    if (!select) return;

    let html = "";

    rows.forEach(function (row) {
      const value = escapeHtml(row.value || "");
      const label = escapeHtml(row.label || row.value || "");
      const selected = selectedValue === row.value ? " selected" : "";

      html += '<option value="' + value + '"' + selected + ">" + label + "</option>";
    });

    select.innerHTML = html || '<option value="__coach_me__">My Calendar</option>';
  }

  function removePrivateActions() {
    const body = document.getElementById("trkCalendarDetailsBody");
    if (!body) return;

    const editButton = body.querySelector("[data-calendar-action='edit-session']");
    const noteButton = body.querySelector("[data-calendar-action='add-note']");
    const eventName = editButton ? editButton.getAttribute("data-event") : "";

    if (!eventName || !privateEvents.has(eventName)) return;

    if (editButton) editButton.remove();
    if (noteButton) noteButton.remove();

    const openLink = body.querySelector("a[href*='calendar_details']");
    if (openLink) openLink.remove();
  }

  function renameLabel() {
    const label = document.querySelector("label[for='trkCoachCalendarWorkerSelect']");
    if (label) label.textContent = "View Calendar For";
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
    renameLabel();

    const select = document.getElementById("trkCoachCalendarWorkerSelect");

    if (select) {
      select.addEventListener("change", function () {
        setSelectedCalendarFor(this.value || "__coach_me__");
      });
    }

    const observer = new MutationObserver(function () {
      removePrivateActions();
      renameLabel();
    });

    observer.observe(document.body, {
      childList: true,
      subtree: true
    });
  });
})();
