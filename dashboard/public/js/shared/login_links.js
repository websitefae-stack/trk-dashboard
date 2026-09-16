/**
 * Renders a QR code into every .dashboard-login-qr placeholder on the
 * coach profile page's "Your Logins" tab (see get_coach_login_links in
 * api/shared/profile.py) - lets a coach scan straight to a login on
 * their phone instead of typing a URL. Actual rendering/download wiring
 * lives in Dashboard.renderQrCodes (utils.js), shared with the Links
 * page's own QR codes.
 */
(function () {
  "use strict";

  function renderLoginQrCodes() {
    Dashboard.renderQrCodes({ format: "png" });
  }

  document.addEventListener("DOMContentLoaded", renderLoginQrCodes);

  // The Your Logins tab panel starts display:none like every other tab
  // panel - re-running (harmless, guarded by data-qr-rendered above)
  // when it's actually opened avoids relying on canvas sizing inside a
  // hidden container working correctly in every browser.
  document.addEventListener("click", function (event) {
    var btn = event.target.closest && event.target.closest('.dashboard-tab-btn[data-tab="logins"]');
    if (btn) window.setTimeout(renderLoginQrCodes, 0);
  });
})();
