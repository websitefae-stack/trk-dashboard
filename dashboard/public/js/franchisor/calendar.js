(function () {
  "use strict";

  const STORAGE_KEY = "trkFranchisorCalendarFor";

  function getSelectedCalendarFor() {
    const params = new URLSearchParams(window.location.search);
    const fromUrl = params.get("calendar_for") || params.get("selected_calendar_for") || params.get("selected_worker");

    if (fromUrl) return fromUrl;

    const field = document.getElementById("trkFranchisorCalendarForSelect");
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
    params.set("calendar_for", value || "__franchisor_me__");

    window.location.href = window.location.pathname + "?" + params.toString();
  }

  const originalFetch = window.fetch;

  window.fetch = function (input, init) {
    let url = typeof input === "string" ? input : input && input.url ? input.url : "";

    if (url.indexOf("/api/method/dashboard.api.session_worker.calendar.") !== -1) {
      url = url.replace(
        "/api/method/dashboard.api.session_worker.calendar.",
        "/api/method/dashboard.api.franchisor.calendar."
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
          const options = Array.isArray(message.calendar_for_options)
            ? message.calendar_for_options
            : [];

          renderCalendarForOptions(options, message.selected_calendar_for || "__franchisor_me__");
        }).catch(function () {});
      } catch (error) {}

      return response;
    });
  };

  function renderCalendarForOptions(rows, selectedValue) {
    const select = document.getElementById("trkFranchisorCalendarForSelect");
    if (!select) return;

    let html = "";

    rows.forEach(function (row) {
      const value = escapeHtml(row.value || "");
      const label = escapeHtml(row.label || row.value || "");
      const selected = selectedValue === row.value ? " selected" : "";

      html += '<option value="' + value + '"' + selected + ">" + label + "</option>";
    });

    select.innerHTML = html || '<option value="__franchisor_me__">Me</option>';
  }

  function rewriteLinks() {
    document.querySelectorAll("a[href*='/session_worker_db/calendar_details']").forEach(function (link) {
      link.href = link.href.replace("/session_worker_db/calendar_details", "/franchisor_db/calendar_details");
    });
  }

  function renameLabel() {
    const label = document.querySelector("label[for='trkFranchisorCalendarForSelect']");
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
    renameLabel();

    const select = document.getElementById("trkFranchisorCalendarForSelect");

    if (select) {
      select.addEventListener("change", function () {
        setSelectedCalendarFor(this.value || "__franchisor_me__");
      });
    }

    const observer = new MutationObserver(function () {
      rewriteLinks();
      renameLabel();
    });

    observer.observe(document.body, {
      childList: true,
      subtree: true
    });
  });
})();
