(function () {
  "use strict";

  const originalFetch = window.fetch;

  window.fetch = function (input, init) {
    let url = typeof input === "string" ? input : input && input.url ? input.url : "";

    if (url.indexOf("/api/method/dashboard.api.session_worker.calendar.") !== -1) {
      url = url.replace(
        "/api/method/dashboard.api.session_worker.calendar.",
        "/api/method/dashboard.api.franchisor.calendar."
      );

      input = url;
    }

    return originalFetch(input, init);
  };
})();
