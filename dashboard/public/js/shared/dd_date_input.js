/**
 * Every native <input type="date"> on this site types in whatever segment
 * order the visitor's own browser/OS locale dictates - that can't be
 * overridden with CSS or JS, it's a browser platform behaviour. This
 * converts every date input, site-wide, into a plain dd/mm/yyyy text field
 * (auto-inserting slashes as you type, always day first) paired with the
 * original native input kept alive off-screen as both the value source of
 * truth (so every existing getElementById(id).value / setValue() call
 * elsewhere keeps working unchanged) and a calendar-icon picker trigger.
 *
 * Loaded once, globally, in shared_head.html - no other file needs to know
 * this exists.
 */
(function () {
  "use strict";

  function pad2(n) {
    return String(n).padStart(2, "0");
  }

  function isoToDisplay(iso) {
    const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso || "");
    if (!match) return "";
    return `${match[3]}/${match[2]}/${match[1]}`;
  }

  function displayToIso(display) {
    const match = /^(\d{1,2})\/(\d{1,2})\/(\d{4})$/.exec((display || "").trim());
    if (!match) return "";

    const day = parseInt(match[1], 10);
    const month = parseInt(match[2], 10);
    const year = parseInt(match[3], 10);

    if (month < 1 || month > 12 || day < 1 || day > 31 || year < 1000) return "";

    // Round-trips through a real Date to reject calendar-invalid combos
    // (e.g. 30 Feb) instead of silently accepting them.
    const check = new Date(year, month - 1, day);
    if (check.getFullYear() !== year || check.getMonth() !== month - 1 || check.getDate() !== day) {
      return "";
    }

    return `${year}-${pad2(month)}-${pad2(day)}`;
  }

  function formatWhileTyping(raw) {
    const digits = raw.replace(/\D/g, "").slice(0, 8);
    let out = digits.slice(0, 2);
    if (digits.length > 2) out += "/" + digits.slice(2, 4);
    if (digits.length > 4) out += "/" + digits.slice(4, 8);
    return out;
  }

  function syncDisabledState(nativeInput, textInput, trigger) {
    const isDisabled = nativeInput.disabled || nativeInput.readOnly;
    textInput.disabled = nativeInput.disabled;
    textInput.readOnly = nativeInput.readOnly;
    trigger.style.pointerEvents = isDisabled ? "none" : "";
    trigger.style.display = isDisabled ? "none" : "";
  }

  function openNativePicker(nativeInput) {
    if (typeof nativeInput.showPicker === "function") {
      try {
        nativeInput.showPicker();
        return;
      } catch (error) {
        // falls through to focus() below (showPicker throws if the input
        // isn't visible/focusable in some browsers)
      }
    }
    nativeInput.focus();
  }

  function removeSuperseded(nativeInput) {
    // Earlier, narrower fixes added one-off "formatted date" labels next to
    // specific native date inputs before this global converter existed -
    // now redundant since the visible text field always shows dd/mm/yyyy
    // itself. Removed by naming convention so every prior instance of that
    // pattern is cleaned up without having to revisit each file it's in.
    if (!nativeInput.id) return;

    [`${nativeInput.id}_display`, `${nativeInput.id}Display`].forEach(function (candidateId) {
      const node = document.getElementById(candidateId);
      if (node) node.remove();
    });
  }

  function convertDateInput(nativeInput) {
    if (nativeInput.dataset.ddConverted === "1") return;

    // Some pages (e.g. the calendar's own date-picker trigger) deliberately
    // keep a native <input type="date"> invisible and 1x1px, only ever
    // opened programmatically via a separate visible button/pill - wrapping
    // it in the normal dd/mm/yyyy text-input UI would give it real layout
    // width again and break that page's own layout around it.
    if (nativeInput.dataset.ddSkip === "1") return;

    nativeInput.dataset.ddConverted = "1";

    removeSuperseded(nativeInput);

    const wrap = document.createElement("span");
    wrap.className = "dd-date-wrap";

    const textInput = document.createElement("input");
    textInput.type = "text";
    textInput.inputMode = "numeric";
    textInput.autocomplete = "off";
    textInput.placeholder = "dd/mm/yyyy";
    textInput.maxLength = 10;
    textInput.className = nativeInput.className;
    if (nativeInput.id) textInput.dataset.ddTextFor = nativeInput.id;

    const trigger = document.createElement("button");
    trigger.type = "button";
    trigger.className = "dd-date-trigger";
    trigger.setAttribute("aria-label", "Open calendar");
    trigger.tabIndex = -1;
    trigger.textContent = "\u{1F4C5}";

    nativeInput.parentNode.insertBefore(wrap, nativeInput);
    wrap.appendChild(textInput);
    wrap.appendChild(trigger);
    wrap.appendChild(nativeInput);

    nativeInput.classList.add("dd-date-native");
    nativeInput.tabIndex = -1;

    // Preserve whatever value/state was already on the field (server-
    // rendered value=, or already-disabled/readonly) before wiring anything.
    textInput.value = isoToDisplay(nativeInput.value);
    syncDisabledState(nativeInput, textInput, trigger);

    // Every existing page sets dates via nativeInput.value = "yyyy-mm-dd"
    // (setValue/updateReadOnlyText/etc, scattered across many files) -
    // rather than touching every call site, the value setter itself is
    // overridden so any programmatic assignment keeps the visible text in
    // sync automatically.
    const descriptor = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value");
    Object.defineProperty(nativeInput, "value", {
      configurable: true,
      get() {
        return descriptor.get.call(this);
      },
      set(v) {
        descriptor.set.call(this, v);
        textInput.value = isoToDisplay(v);
      },
    });

    // Editing partway into an already-filled date (e.g. clicking between
    // the "1" and "0" of "10" to fix just the month) inserts a digit into
    // the middle of the existing string rather than replacing it -
    // formatWhileTyping() then re-slices ALL the digits including the ones
    // that were never meant to move, which can scramble the day/month/year
    // into something that isn't the date anyone typed. Selecting the whole
    // value on focus means any typing starts fresh instead.
    textInput.addEventListener("focus", function () {
      textInput.select();
    });

    textInput.addEventListener("input", function () {
      const caretWasAtEnd = textInput.selectionStart === textInput.value.length;
      textInput.value = formatWhileTyping(textInput.value);
      if (caretWasAtEnd) {
        textInput.setSelectionRange(textInput.value.length, textInput.value.length);
      }

      const iso = displayToIso(textInput.value);
      if (iso) {
        descriptor.set.call(nativeInput, iso);
        nativeInput.dispatchEvent(new Event("change", { bubbles: true }));
        nativeInput.dispatchEvent(new Event("input", { bubbles: true }));
      } else if (textInput.value === "") {
        descriptor.set.call(nativeInput, "");
        nativeInput.dispatchEvent(new Event("change", { bubbles: true }));
      }
    });

    textInput.addEventListener("blur", function () {
      // An incomplete/invalid typed date doesn't clobber whatever the
      // field's last valid value was - revert the visible text to match it.
      const iso = displayToIso(textInput.value);
      if (!iso && textInput.value !== "") {
        textInput.value = isoToDisplay(nativeInput.value);
      }
    });

    // The native picker's own calendar UI still fires real 'change'/'input'
    // events (unlike a programmatic .value assignment), which is what
    // updates the visible text when someone picks a date that way.
    nativeInput.addEventListener("change", function () {
      textInput.value = isoToDisplay(descriptor.get.call(nativeInput));
    });

    trigger.addEventListener("click", function () {
      if (nativeInput.disabled || nativeInput.readOnly) return;
      openNativePicker(nativeInput);
    });

    // readOnly/disabled are standard reflected boolean attributes, so a
    // plain attribute observer reliably catches every existing page's
    // `field.readOnly = ...` / `field.disabled = ...` toggle, wherever in
    // the app it happens.
    new MutationObserver(function () {
      syncDisabledState(nativeInput, textInput, trigger);
    }).observe(nativeInput, { attributes: true, attributeFilter: ["readonly", "disabled"] });
  }

  function convertAll(root) {
    (root || document).querySelectorAll('input[type="date"]:not([data-dd-converted])').forEach(convertDateInput);
  }

  function watchForNewDateInputs() {
    const observer = new MutationObserver(function (mutations) {
      mutations.forEach(function (mutation) {
        mutation.addedNodes.forEach(function (node) {
          if (node.nodeType !== 1) return;

          if (node.matches && node.matches('input[type="date"]')) {
            convertDateInput(node);
          }

          if (node.querySelectorAll) {
            convertAll(node);
          }
        });
      });
    });

    observer.observe(document.body, { childList: true, subtree: true });
  }

  function init() {
    convertAll(document);
    watchForNewDateInputs();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
