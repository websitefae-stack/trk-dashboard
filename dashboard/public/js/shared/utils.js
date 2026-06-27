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
})();
