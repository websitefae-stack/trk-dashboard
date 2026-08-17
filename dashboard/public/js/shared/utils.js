/**
 * Shared dashboard utilities.
 * Loaded first on every dashboard page (see shared_head.html).
 * All helpers live on window.Dashboard so they are available to every
 * subsequent script without polluting the global namespace further.
 *
 * Usage in any dashboard JS file:
 *   const el  = Dashboard.el;
 *   const qsa = Dashboard.qsa;
 *   const debounce = Dashboard.debounce;
 */
(function () {
  "use strict";

  window.Dashboard = window.Dashboard || {};

  /**
   * Shorthand for document.getElementById.
   * @param {string} id
   * @returns {HTMLElement|null}
   */
  Dashboard.el = function (id) {
    return document.getElementById(id);
  };

  /**
   * querySelectorAll returning a real Array.
   * @param {string} selector
   * @param {Element|Document} [root]
   * @returns {Element[]}
   */
  Dashboard.qsa = function (selector, root) {
    return Array.from((root || document).querySelectorAll(selector));
  };

  /**
   * Returns a debounced version of fn that fires after `wait` ms of quiet.
   * @param {Function} fn
   * @param {number} [wait=500]
   * @returns {Function}
   */
  Dashboard.debounce = function (fn, wait) {
    var timer = null;
    return function () {
      var args = arguments;
      clearTimeout(timer);
      timer = setTimeout(function () {
        fn.apply(null, args);
      }, wait || 500);
    };
  };

  /**
   * Inserts a one-line explainer right after a "From" sender <select> in
   * an email compose modal, the first time it's called for that element -
   * every send in this app goes out via the shared office account with
   * reply-to set to whoever's actually sending it (see
   * email_templates.get_email_sender_options() and every frappe.sendmail()
   * call across the API), which isn't obvious just from a dropdown with a
   * single "Office email" option in it. Safe to call every time a modal's
   * sender options are (re)loaded - a repeat call on the same element is a
   * no-op rather than stacking duplicate notes.
   * @param {HTMLElement|null} selectEl
   */
  Dashboard.attachSenderHint = function (selectEl) {
    if (!selectEl || !selectEl.parentNode) return;
    if (selectEl.parentNode.querySelector(".dashboard-sender-hint")) return;

    var hint = document.createElement("div");
    hint.className = "dashboard-field-hint dashboard-sender-hint";
    hint.textContent = "Sent from office@theresilienthub.co.uk, but replies go straight to your own email - let clients know to look for mail from office.";
    selectEl.insertAdjacentElement("afterend", hint);
  };
})();
