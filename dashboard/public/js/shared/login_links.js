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
      // Rendered well above the 140px display size (see cards.css) so the
      // downloaded PNG still looks sharp blown up for a flyer or social
      // media post, not just crisp at the small on-screen size - the CSS
      // width/height on the <img> controls how big it looks on the page,
      // this controls the actual pixel data underneath.
      new QRCode(el, {
        text: value,
        width: 500,
        height: 500,
        correctLevel: QRCode.CorrectLevel.M
      });

      wireDownloadLink(el);
    });
  }

  // qrcodejs draws the QR pattern onto a <canvas> synchronously, then
  // separately (and asynchronously the first time, behind a data-URI
  // support check - see vendor/qrcodejs/qrcode.min.js) copies it into a
  // visible <img> via canvas.toDataURL("image/png"). Reading img.src right
  // after construction can catch it before that copy has happened, leaving
  // the download link pointing at nothing (href="#") - it then "downloads"
  // the current page instead of the QR code. Reading straight off the
  // canvas instead sidesteps that timing gap entirely, since the canvas
  // itself is already fully drawn by the time this runs.
  function wireDownloadLink(qrEl) {
    var link = qrEl.parentElement && qrEl.parentElement.querySelector(".dashboard-login-qr-download");
    if (!link) return;

    var canvas = qrEl.querySelector("canvas");
    var dataUrl = canvas ? canvas.toDataURL("image/png") : null;

    if (!dataUrl) {
      var img = qrEl.querySelector("img");
      if (img && img.src && img.src.indexOf("data:") === 0) dataUrl = img.src;
    }
    if (!dataUrl) return;

    link.href = dataUrl;
    var label = qrEl.dataset.qrLabel || "login";
    link.setAttribute(
      "download",
      label.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "") + "-qr-code.png"
    );
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
