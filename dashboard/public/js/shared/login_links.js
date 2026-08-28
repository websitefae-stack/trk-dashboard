/**
 * Renders a QR code into every .dashboard-login-qr placeholder on the
 * coach profile page's "Your Logins" tab (see get_coach_login_links in
 * api/shared/profile.py) - lets a coach scan straight to a login on
 * their phone instead of typing a URL. Uses the vendored qrcodejs
 * library (public/vendor/qrcodejs) rather than an external QR service,
 * so this keeps working with no outside dependency.
 */
(function () {
  "use strict";

  function renderLoginQrCodes() {
    if (typeof QRCode === "undefined") return;

    document.querySelectorAll(".dashboard-login-qr").forEach(function (el) {
      if (el.dataset.qrRendered === "1") return;

      var value = el.dataset.qrValue;
      if (!value) return;

      el.dataset.qrRendered = "1";
      /* eslint-disable no-new */
      new QRCode(el, {
        text: value,
        width: 96,
        height: 96,
        correctLevel: QRCode.CorrectLevel.M
      });
    });
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
