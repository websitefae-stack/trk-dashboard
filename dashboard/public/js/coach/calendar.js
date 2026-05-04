(function () {
  "use strict";

  const privateEvents = new Set();
  const STORAGE_KEY = "trkCoachCalendarFor";

  function getSelectedCalendarFor() {
    const params = new URLSearchParams(window.location.search);
    const fromUrl = params.get("calendar_for") || params.get("selected_calendar_for") || params.get("selected_worker");

    if (fromUrl) return fromUrl;

    const field = document.getElementById("trkCoachCalendarWorkerSelect");
    if (field && field.value) return field.value;

    return window.localStorage.getItem(STORAGE_KEY) || "";
  }

  function setSelectedCalendarFor(value) {
    if (value) {
      window.localStorage.setItem(STORAGE_KEY, value);
    } else {
      window.localStorage.removeItem(STORAGE_KEY);
    }

    const params = new URLSearchParams(window.location.search);
    params.set("calendar_for", value || "__coach_me__");

    const newUrl = window.location.pathname + "?" + params.toString();
    window.location.href = newUrl;
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
        const selectedCalendarFor = getSelectedCalendarFor();

        if (selectedCalendarFor) {
          const parsed = new URL(url, window.location.origin);
          parsed.searchParams.set("selected_calendar_for", selectedCalendarFor);
          parsed.searchParams.set("selected_worker", selectedCalendarFor);
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

          const options = Array.isArray(message.calendar_for_options)
            ? message.calendar_for_options
            : (Array.isArray(message.session_workers) ? message.session_workers : []);

          renderCalendarForOptions(options, message.selected_calendar_for || message.selected_worker || "__coach_me__");
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

    select.innerHTML = html || '<option value="__coach_me__">Me</option>';
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

  function renameCalendarForLabel() {
    const label = document.querySelector("label[for='trkCoachCalendarWorkerSelect']");
    if (label) {
      label.textContent = "View Calendar For";
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
    renameCalendarForLabel();

    const select = document.getElementById("trkCoachCalendarWorkerSelect");

    if (select) {
      select.addEventListener("change", function () {
        setSelectedCalendarFor(this.value || "__coach_me__");
      });
    }

    const observer = new MutationObserver(function () {
      removePrivateActions();
      rewriteCoachLinks();
      renameCalendarForLabel();
    });

    observer.observe(document.body, {
      childList: true,
      subtree: true
    });
  });
})();
