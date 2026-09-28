/**
 * Every native <input type="date"> on this site types in whatever segment
 * order the visitor's own browser/OS locale dictates - that can't be
 * overridden with CSS or JS, it's a browser platform behaviour. This
 * converts every date input, site-wide, into a plain dd/mm/yyyy text field
 * (auto-inserting slashes as you type, always day first) paired with the
 * original native input kept alive off-screen as the value source of truth
 * (so every existing getElementById(id).value / setValue() call elsewhere
 * keeps working unchanged), plus a fully custom-drawn calendar popup this
 * script owns outright.
 *
 * Deliberately NOT the browser's own native picker (window.showPicker()) any
 * more - that's OS/browser chrome this script has no API to close, which is
 * exactly what caused it to sometimes stay open after a date was clicked.
 * Owning the popup ourselves means the click handler that sets the date is
 * the same handler that removes the popup from the DOM - there's no "stuck
 * open" state possible. It also lets month/year jump straight to any value
 * via two <select> dropdowns instead of only stepping one month at a time,
 * which is what made picking an old date of birth so slow before.
 *
 * Loaded once, globally, in shared_head.html - no other file needs to know
 * this exists.
 */
(function () {
  "use strict";

  const MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
  ];
  const WEEKDAY_LABELS = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"];

  // Wide enough either direction to cover a date of birth decades back or a
  // document expiry years ahead, without the year <select> becoming
  // unreasonably long.
  const YEAR_RANGE_PAST = 120;
  const YEAR_RANGE_FUTURE = 15;

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

  // ---------------------------------------------------------------
  // Custom calendar popup - a single shared instance reused for whichever
  // field is currently open, rather than one per field.
  // ---------------------------------------------------------------

  let popupEl = null;
  let popupState = null; // { nativeInput, textInput, descriptor, viewYear, viewMonth }

  function closePopup() {
    if (popupEl && popupEl.parentNode) popupEl.parentNode.removeChild(popupEl);
    popupEl = null;
    popupState = null;
    document.removeEventListener("mousedown", handleOutsideClick, true);
    document.removeEventListener("keydown", handlePopupKeydown, true);
    window.removeEventListener("scroll", closePopup, true);
    window.removeEventListener("resize", closePopup, true);
  }

  function handleOutsideClick(event) {
    if (!popupEl) return;
    if (popupEl.contains(event.target)) return;
    if (popupState && (event.target === popupState.textInput || event.target === popupState.trigger)) return;
    closePopup();
  }

  function handlePopupKeydown(event) {
    if (event.key === "Escape") {
      closePopup();
      if (popupState) popupState.textInput.focus();
    }
  }

  function daysInMonth(year, month) {
    return new Date(year, month + 1, 0).getDate();
  }

  function selectDate(year, month, day) {
    const iso = `${year}-${pad2(month + 1)}-${pad2(day)}`;
    const { nativeInput, descriptor } = popupState;
    descriptor.set.call(nativeInput, iso);
    nativeInput.dispatchEvent(new Event("change", { bubbles: true }));
    nativeInput.dispatchEvent(new Event("input", { bubbles: true }));
    // Closing here - not just after some later event - is the fix for the
    // popup previously staying open after a date was picked: this IS the
    // click handler for the day cell, so there's no separate "did the
    // browser decide to dismiss its own chrome" step to fail.
    closePopup();
  }

  function renderPopup() {
    const { viewYear, viewMonth, nativeInput } = popupState;
    const selectedIso = nativeInput.value || "";
    const selectedMatch = /^(\d{4})-(\d{2})-(\d{2})/.exec(selectedIso);
    const today = new Date();

    popupEl.innerHTML = "";

    const header = document.createElement("div");
    header.className = "dd-date-popup-header";

    const prevBtn = document.createElement("button");
    prevBtn.type = "button";
    prevBtn.className = "dd-date-popup-nav";
    prevBtn.textContent = "‹";
    prevBtn.setAttribute("aria-label", "Previous month");
    prevBtn.addEventListener("click", function () {
      popupState.viewMonth -= 1;
      if (popupState.viewMonth < 0) {
        popupState.viewMonth = 11;
        popupState.viewYear -= 1;
      }
      renderPopup();
    });

    const monthSelect = document.createElement("select");
    monthSelect.className = "dd-date-popup-select dd-date-popup-month-select";
    MONTH_NAMES.forEach(function (name, index) {
      const opt = document.createElement("option");
      opt.value = String(index);
      opt.textContent = name;
      if (index === viewMonth) opt.selected = true;
      monthSelect.appendChild(opt);
    });
    monthSelect.addEventListener("change", function () {
      popupState.viewMonth = parseInt(monthSelect.value, 10);
      renderPopup();
    });

    const yearSelect = document.createElement("select");
    yearSelect.className = "dd-date-popup-select dd-date-popup-year-select";
    const thisYear = today.getFullYear();
    for (let y = thisYear + YEAR_RANGE_FUTURE; y >= thisYear - YEAR_RANGE_PAST; y--) {
      const opt = document.createElement("option");
      opt.value = String(y);
      opt.textContent = String(y);
      if (y === viewYear) opt.selected = true;
      yearSelect.appendChild(opt);
    }
    yearSelect.addEventListener("change", function () {
      popupState.viewYear = parseInt(yearSelect.value, 10);
      renderPopup();
    });

    const nextBtn = document.createElement("button");
    nextBtn.type = "button";
    nextBtn.className = "dd-date-popup-nav";
    nextBtn.textContent = "›";
    nextBtn.setAttribute("aria-label", "Next month");
    nextBtn.addEventListener("click", function () {
      popupState.viewMonth += 1;
      if (popupState.viewMonth > 11) {
        popupState.viewMonth = 0;
        popupState.viewYear += 1;
      }
      renderPopup();
    });

    header.appendChild(prevBtn);
    header.appendChild(monthSelect);
    header.appendChild(yearSelect);
    header.appendChild(nextBtn);
    popupEl.appendChild(header);

    const weekdayRow = document.createElement("div");
    weekdayRow.className = "dd-date-popup-weekdays";
    WEEKDAY_LABELS.forEach(function (label) {
      const cell = document.createElement("span");
      cell.textContent = label;
      weekdayRow.appendChild(cell);
    });
    popupEl.appendChild(weekdayRow);

    const grid = document.createElement("div");
    grid.className = "dd-date-popup-grid";

    // Monday-first grid: JS getDay() is Sunday=0, shift so Monday=0.
    const firstOfMonth = new Date(viewYear, viewMonth, 1).getDay();
    const leadingBlanks = (firstOfMonth + 6) % 7;
    const total = daysInMonth(viewYear, viewMonth);

    for (let i = 0; i < leadingBlanks; i++) {
      grid.appendChild(document.createElement("span"));
    }

    for (let day = 1; day <= total; day++) {
      const cell = document.createElement("button");
      cell.type = "button";
      cell.className = "dd-date-popup-day";
      cell.textContent = String(day);

      const isSelected = !!selectedMatch
        && parseInt(selectedMatch[1], 10) === viewYear
        && parseInt(selectedMatch[2], 10) === viewMonth + 1
        && parseInt(selectedMatch[3], 10) === day;
      if (isSelected) cell.classList.add("dd-date-popup-day-selected");

      const isToday = today.getFullYear() === viewYear && today.getMonth() === viewMonth && today.getDate() === day;
      if (isToday) cell.classList.add("dd-date-popup-day-today");

      cell.addEventListener("click", function () {
        selectDate(viewYear, viewMonth, day);
      });

      grid.appendChild(cell);
    }

    popupEl.appendChild(grid);

    const footer = document.createElement("div");
    footer.className = "dd-date-popup-footer";

    const todayBtn = document.createElement("button");
    todayBtn.type = "button";
    todayBtn.className = "dd-date-popup-footer-btn";
    todayBtn.textContent = "Today";
    todayBtn.addEventListener("click", function () {
      selectDate(today.getFullYear(), today.getMonth(), today.getDate());
    });
    footer.appendChild(todayBtn);

    const clearBtn = document.createElement("button");
    clearBtn.type = "button";
    clearBtn.className = "dd-date-popup-footer-btn";
    clearBtn.textContent = "Clear";
    clearBtn.addEventListener("click", function () {
      const { nativeInput, descriptor } = popupState;
      descriptor.set.call(nativeInput, "");
      nativeInput.dispatchEvent(new Event("change", { bubbles: true }));
      nativeInput.dispatchEvent(new Event("input", { bubbles: true }));
      closePopup();
    });
    footer.appendChild(clearBtn);

    popupEl.appendChild(footer);
  }

  function positionPopup(anchorEl) {
    const rect = anchorEl.getBoundingClientRect();
    const popupHeight = popupEl.offsetHeight;
    const spaceBelow = window.innerHeight - rect.bottom;

    const top = spaceBelow >= popupHeight + 8 || spaceBelow >= rect.top
      ? rect.bottom + window.scrollY + 4
      : rect.top + window.scrollY - popupHeight - 4;

    let left = rect.left + window.scrollX;
    const overflowRight = left + popupEl.offsetWidth - (window.scrollX + window.innerWidth);
    if (overflowRight > 0) left -= overflowRight + 8;
    if (left < 8) left = 8;

    popupEl.style.top = `${top}px`;
    popupEl.style.left = `${left}px`;
  }

  function openPopup(nativeInput, textInput, trigger, descriptor) {
    if (popupState && popupState.nativeInput === nativeInput) {
      closePopup();
      return;
    }

    closePopup();

    const iso = nativeInput.value || "";
    const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
    const today = new Date();

    popupEl = document.createElement("div");
    popupEl.className = "dd-date-popup";
    document.body.appendChild(popupEl);

    popupState = {
      nativeInput,
      textInput,
      trigger,
      descriptor,
      viewYear: match ? parseInt(match[1], 10) : today.getFullYear(),
      viewMonth: match ? parseInt(match[2], 10) - 1 : today.getMonth(),
    };

    renderPopup();
    positionPopup(textInput);

    // Captured on the way down (not bubble) so a click landing on another
    // dd-date trigger while this popup is open reliably counts as
    // "outside" before that trigger's own click handler runs.
    document.addEventListener("mousedown", handleOutsideClick, true);
    document.addEventListener("keydown", handlePopupKeydown, true);
    window.addEventListener("scroll", closePopup, true);
    window.addEventListener("resize", closePopup, true);
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
        if (popupState && popupState.nativeInput === nativeInput) renderPopup();
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

    // Clicking into the field opens the calendar popup straight away (same
    // as clicking the 📅 button), so picking a date is the natural first
    // thing that happens rather than something only found by noticing the
    // small trigger button. Typing is still fully possible - the popup
    // doesn't block the field, and picking a day just fills it in as if it
    // had been typed.
    textInput.addEventListener("click", function () {
      if (nativeInput.disabled || nativeInput.readOnly) return;
      openPopup(nativeInput, textInput, trigger, descriptor);
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
        if (popupState && popupState.nativeInput === nativeInput) {
          const [, y, m] = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
          popupState.viewYear = parseInt(y, 10);
          popupState.viewMonth = parseInt(m, 10) - 1;
          renderPopup();
        }
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

    trigger.addEventListener("click", function () {
      if (nativeInput.disabled || nativeInput.readOnly) return;
      openPopup(nativeInput, textInput, trigger, descriptor);
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

  function injectStyles() {
    if (document.getElementById("dd-date-popup-styles")) return;

    const style = document.createElement("style");
    style.id = "dd-date-popup-styles";
    style.textContent = `
      .dd-date-popup {
        position: absolute;
        /* Higher than .trk-calendar-modal-backdrop's 99990/.trk-calendar-
           toast's 99999 (calendar.css) - many date fields this wraps live
           inside those modals, so this must render above them or it'd be
           invisible behind the backdrop when opened from one. */
        z-index: 100000;
        background: #FFFFFF;
        border-radius: 12px;
        box-shadow: 0 12px 30px rgba(0, 0, 0, 0.18);
        border: 1px solid #E6EFEF;
        padding: 12px;
        width: 260px;
        font-family: inherit;
      }
      .dd-date-popup-header {
        display: flex;
        align-items: center;
        gap: 4px;
        margin-bottom: 8px;
      }
      .dd-date-popup-nav {
        background: none;
        border: none;
        cursor: pointer;
        font-size: 18px;
        line-height: 1;
        padding: 4px 6px;
        border-radius: 6px;
        color: #434B49;
      }
      .dd-date-popup-nav:hover {
        background: #F2F8F8;
      }
      .dd-date-popup-select {
        border: 1px solid #E6EFEF;
        border-radius: 6px;
        padding: 4px 4px;
        font-size: 13px;
        background: #FFFFFF;
        color: #434B49;
      }
      .dd-date-popup-month-select {
        flex: 1;
        min-width: 0;
      }
      .dd-date-popup-year-select {
        width: 78px;
      }
      .dd-date-popup-weekdays {
        display: grid;
        grid-template-columns: repeat(7, 1fr);
        text-align: center;
        font-size: 11px;
        font-weight: 700;
        color: #839898;
        margin-bottom: 4px;
      }
      .dd-date-popup-grid {
        display: grid;
        grid-template-columns: repeat(7, 1fr);
        gap: 2px;
      }
      .dd-date-popup-day {
        border: none;
        background: none;
        cursor: pointer;
        padding: 6px 0;
        border-radius: 6px;
        font-size: 13px;
        color: #434B49;
      }
      .dd-date-popup-day:hover {
        background: #F2F8F8;
      }
      .dd-date-popup-day-today {
        font-weight: 700;
        color: #00A19A;
      }
      .dd-date-popup-day-selected {
        background: #00A19A;
        color: #FFFFFF;
      }
      .dd-date-popup-day-selected:hover {
        background: #00897F;
      }
      .dd-date-popup-footer {
        display: flex;
        justify-content: space-between;
        margin-top: 8px;
        padding-top: 8px;
        border-top: 1px solid #E6EFEF;
      }
      .dd-date-popup-footer-btn {
        background: none;
        border: none;
        cursor: pointer;
        color: #00A19A;
        font-size: 12px;
        font-weight: 600;
        padding: 4px 6px;
      }
      .dd-date-popup-footer-btn:hover {
        text-decoration: underline;
      }
      .dd-date-wrap {
        position: relative;
        display: block;
        width: 100%;
      }
      .dd-date-wrap input[type="text"] {
        padding-right: 40px;
      }
      .dd-date-trigger {
        position: absolute;
        top: 50%;
        right: 6px;
        transform: translateY(-50%);
        width: 28px;
        height: 28px;
        border: none;
        background: transparent;
        font-size: 15px;
        line-height: 1;
        cursor: pointer;
        border-radius: 6px;
      }
      .dd-date-trigger:hover {
        background: #F2F8F8;
      }
      .dd-date-native {
        position: absolute;
        top: 0;
        right: 0;
        width: 1px;
        height: 1px;
        opacity: 0;
        pointer-events: none;
        padding: 0;
        border: none;
      }
    `;
    document.head.appendChild(style);
  }

  function init() {
    injectStyles();
    convertAll(document);
    watchForNewDateInputs();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
