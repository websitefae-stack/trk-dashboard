(function () {
  "use strict";

  const START_HOUR = 7;
  const END_HOUR = 19;
  const SLOT_MINUTES = 30;
  const SLOT_HEIGHT = 44;
  const MOBILE_BREAKPOINT = 860;

  const DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  const MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

  const SHARED_API = "dashboard.api.shared.calendar";

  const COACH_ME_VALUE = "__coach_me__";
  const FRANCHISOR_ME_VALUE = "__franchisor_me__";

  const STORAGE_KEYS = {
    coach: "trkCoachCalendarFor",
    franchisor: "trkFranchisorCalendarFor"
  };

  const DURATION_BY_TYPE = {
    "Therapy Session": 45,
    "Parent Check-In": 30,
    "Initial Consultation": 60,
    "General": 45
  };

  const DEFAULT_BILLING_BY_TYPE = {
    "Therapy Session": "One to One",
    "Parent Check-In": "One to One",
    "Initial Consultation": "One to One"
  };

  const TYPE_STYLES = {
    "Therapy Session": { background: "#E94763", border: "#C73B54", textColor: "#FFFFFF" },
    "Parent Check-In": { background: "#FF8438", border: "#D96D29", textColor: "#FFFFFF" },
    "Initial Consultation": { background: "#00A19E", border: "#007F7D", textColor: "#FFFFFF" },
    "General": { background: "#D5DA39", border: "#AEB32E", textColor: "#2F3312" }
  };

  const state = {
    dashboardType: getDashboardType(),
    currentView: getDefaultCalendarView(),
    currentDate: stripTime(new Date()),
    selectedCalendarFor: "",
    calendarForOptions: [],
    events: [],
    clients: [],
    currentWorkerLabel: "",
    resolutionNote: "",
    selectedEvent: null,
    loading: false
  };

  function getDefaultCalendarView() {
    return window.innerWidth <= MOBILE_BREAKPOINT ? "day" : "week";
  }

  function getDashboardType() {
    const path = window.location.pathname || "";

    if (path.indexOf("/coach_db/") !== -1) return "coach";
    if (path.indexOf("/franchisor_db/") !== -1) return "franchisor";

    return "session_worker";
  }

  function getDefaultCalendarFor() {
    if (state.dashboardType === "coach") return COACH_ME_VALUE;
    if (state.dashboardType === "franchisor") return FRANCHISOR_ME_VALUE;
    return "";
  }

  function getCalendarForSelectId() {
    if (state.dashboardType === "coach") return "trkCoachCalendarWorkerSelect";
    if (state.dashboardType === "franchisor") return "trkFranchisorCalendarForSelect";
    return "";
  }

  function getViewModeParams() {
    const root =
      document.getElementById("sessionWorkerCalendarShell") ||
      document.getElementById("sessionWorkerCalendarDetailsShell");
  
    const params = new URLSearchParams(window.location.search);
  
    return {
      isViewMode: root && String(root.dataset.viewMode || "0") === "1",
      viewAs: (root && root.dataset.viewAs) || params.get("view_as") || "",
      viewer: params.get("viewer") || ""
    };
  }
    
  function getSelectedCalendarForFromPage() {
    const viewMode = getViewModeParams();

    if (state.dashboardType === "coach" && viewMode.isViewMode) {
      return COACH_ME_VALUE;
    }
    
    if (state.dashboardType === "session_worker") return "";

    const params = new URLSearchParams(window.location.search);
    const fromUrl = params.get("calendar_for") || params.get("selected_calendar_for") || params.get("selected_worker");

    if (fromUrl) return fromUrl;

    const select = document.getElementById(getCalendarForSelectId());
    if (select && select.value) return select.value;

    return window.localStorage.getItem(STORAGE_KEYS[state.dashboardType]) || getDefaultCalendarFor();
  }

  function setSelectedCalendarFor(value) {
    if (state.dashboardType === "session_worker") return;

    const selected = value || getDefaultCalendarFor();
    state.selectedCalendarFor = selected;

    window.localStorage.setItem(STORAGE_KEYS[state.dashboardType], selected);

    const params = new URLSearchParams(window.location.search);
    params.set("calendar_for", selected);
    params.set("selected_calendar_for", selected);
    params.set("selected_worker", selected);
    params.set("view", state.currentView);
    params.set("date", formatDateKey(state.currentDate));

    window.location.href = window.location.pathname + "?" + params.toString();
  }

  function init() {
    const root = document.getElementById("sessionWorkerCalendarRoot");
    if (!root) return;

    restoreCalendarStateFromUrl();
    state.selectedCalendarFor = getSelectedCalendarForFromPage();

    bindEvents();
    renderDetailsEmptyState();
    renameCalendarForLabel();
    updateViewButtons();
    renderCalendar();
    loadCalendarData();
  }

  function bindEvents() {
    bindClick("trkCalendarPrevBtn", goPrev);
    bindClick("trkCalendarNextBtn", goNext);
    bindClick("trkCalendarTodayBtn", goToday);

    bindClick("trkCalendarNewBtn", function () {
      openBookingModal(formatDateKey(state.currentDate), "09:00");
    });

    bindClick("trkCalendarDatePickerBtn", openCalendarDatePicker);

    const datePicker = document.getElementById("trkCalendarDatePicker");
    if (datePicker) {
      datePicker.addEventListener("change", function () {
        const selectedDate = parseDateKey(this.value || "");
        if (!selectedDate) return;

        state.currentDate = selectedDate;
        saveCalendarStateToUrl();
        loadCalendarData();
      });
    }

    bindClick("trkCalendarWeekViewBtn", function () {
      state.currentView = "week";
      saveCalendarStateToUrl();
      loadCalendarData();
    });

    bindClick("trkCalendarDayViewBtn", function () {
      state.currentView = "day";
      saveCalendarStateToUrl();
      loadCalendarData();
    });

    bindClick("trkCalendarMonthViewBtn", function () {
      state.currentView = "month";
      saveCalendarStateToUrl();
      loadCalendarData();
    });

    const calendarForSelectId = getCalendarForSelectId();
    const calendarForSelect = calendarForSelectId ? document.getElementById(calendarForSelectId) : null;

    if (calendarForSelect) {
      calendarForSelect.addEventListener("change", function () {
        setSelectedCalendarFor(this.value || getDefaultCalendarFor());
      });
    }

    bindClick("trkCalendarModalClose", closeBookingModal);
    bindClick("trkCalendarModalCancel", closeBookingModal);
    bindClick("trkCalendarSaveBtn", saveBooking);

    bindClick("trkCalendarEditModalClose", closeEditModal);
    bindClick("trkCalendarEditModalCancel", closeEditModal);
    bindClick("trkCalendarEditSaveBtn", saveSessionChanges);

    bindClick("trkCalendarNoteModalClose", closeNoteModal);
    bindClick("trkCalendarNoteModalCancel", closeNoteModal);
    bindClick("trkCalendarNoteSaveBtn", saveClientNote);

    const typeSelect = document.getElementById("trkCalendarType");
    if (typeSelect) {
      typeSelect.addEventListener("change", function () {
        setValue("trkCalendarDuration", String(DURATION_BY_TYPE[this.value] || 45));
        syncBookingFields();
      });
    }

    const editTypeSelect = document.getElementById("trkEditType");
    if (editTypeSelect) {
      editTypeSelect.addEventListener("change", syncEditFields);
    }

    document.addEventListener("click", function (event) {
      const editBtn = event.target.closest("[data-calendar-action='edit-session']");
      if (editBtn) {
        openEditModal(editBtn.dataset.event);
        return;
      }

      const noteBtn = event.target.closest("[data-calendar-action='add-note']");
      if (noteBtn) {
        openNoteModal(noteBtn.dataset.event);
        return;
      }

      const monthCell = event.target.closest("[data-calendar-month-date]");
      if (monthCell && !event.target.closest("[data-calendar-month-event]")) {
        const dateValue = monthCell.dataset.calendarMonthDate || "";
        if (dateValue) {
          state.currentDate = parseDateKey(dateValue) || state.currentDate;
          state.currentView = "day";
          saveCalendarStateToUrl();
          loadCalendarData();
        }
      }

      const monthEvent = event.target.closest("[data-calendar-month-event]");
      if (monthEvent) {
        event.stopPropagation();

        const eventName = monthEvent.dataset.calendarMonthEvent || "";
        const row = getEventByName(eventName);

        if (row) {
          state.selectedEvent = row;
          renderDetails(row);
        }
      }
    });

    bindBackdropClose("trkCalendarModal", closeBookingModal);
    bindBackdropClose("trkCalendarEditModal", closeEditModal);
    bindBackdropClose("trkCalendarNoteModal", closeNoteModal);
  }

  function goPrev() {
    if (state.currentView === "day") {
      state.currentDate = addDays(state.currentDate, -1);
    } else if (state.currentView === "month") {
      state.currentDate = new Date(state.currentDate.getFullYear(), state.currentDate.getMonth() - 1, 1);
    } else {
      state.currentDate = addDays(state.currentDate, -7);
    }

    saveCalendarStateToUrl();
    loadCalendarData();
  }

  function goNext() {
    if (state.currentView === "day") {
      state.currentDate = addDays(state.currentDate, 1);
    } else if (state.currentView === "month") {
      state.currentDate = new Date(state.currentDate.getFullYear(), state.currentDate.getMonth() + 1, 1);
    } else {
      state.currentDate = addDays(state.currentDate, 7);
    }

    saveCalendarStateToUrl();
    loadCalendarData();
  }

  function goToday() {
    state.currentDate = stripTime(new Date());
    saveCalendarStateToUrl();
    loadCalendarData();
  }

  function openCalendarDatePicker() {
    const picker = document.getElementById("trkCalendarDatePicker");
    if (!picker) return;

    picker.value = formatDateKey(state.currentDate);

    if (typeof picker.showPicker === "function") {
      picker.showPicker();
    } else {
      picker.focus();
      picker.click();
    }
  }

  function bindClick(id, handler) {
    const node = document.getElementById(id);
    if (node) node.addEventListener("click", handler);
  }

  function bindBackdropClose(id, closer) {
    const modal = document.getElementById(id);
    if (!modal) return;

    modal.addEventListener("click", function (event) {
      if (event.target === modal) closer();
    });
  }

  function loadCalendarData() {
    setLoading(true);

    state.selectedCalendarFor = getSelectedCalendarForFromPage();

    const viewMode = getViewModeParams();

    apiGet(SHARED_API + ".get_calendar_bootstrap", {
      dashboard_type: state.dashboardType,
      week_start: formatDateKey(getWeekStart(state.currentDate)),
      view: state.currentView,
      date: formatDateKey(state.currentDate),
      calendar_for: state.selectedCalendarFor,
      selected_calendar_for: state.selectedCalendarFor,
      selected_worker: state.selectedCalendarFor,
      view_as: viewMode.viewAs,
      viewer: viewMode.viewer
    }).then(function (message) {
      state.events = Array.isArray(message.events)
        ? message.events.filter(function (event) {
            return !isCancelledEvent(event);
          })
        : [];

      state.clients = Array.isArray(message.clients) ? message.clients : [];
      state.calendarForOptions = Array.isArray(message.calendar_for_options) ? message.calendar_for_options : [];
      state.selectedCalendarFor = message.selected_calendar_for || state.selectedCalendarFor || getDefaultCalendarFor();
      state.currentWorkerLabel = message.current_worker_label || "";
      state.resolutionNote = message.resolution_note || "";

      renderCalendarForOptions();
      renderClientOptions();
      updateClientNotice();
      renderCalendar();
      refreshSelectedEvent();
      setLoading(false);
    }).catch(function (error) {
      console.error("Calendar bootstrap failed:", error);

      state.events = [];
      state.clients = [];
      state.calendarForOptions = [];
      state.currentWorkerLabel = "";
      state.resolutionNote = "";

      renderCalendarForOptions();
      renderClientOptions();
      updateClientNotice(error.message || "");
      renderCalendar();
      renderDetailsEmptyState();
      setLoading(false);
      showToast(error.message || "Could not load calendar data");
    });
  }

  function renderCalendarForOptions() {
    const selectId = getCalendarForSelectId();
    if (!selectId) return;

    const select = document.getElementById(selectId);
    if (!select) return;

    let html = "";

    state.calendarForOptions.forEach(function (row) {
      const value = row.value || "";
      const label = row.label || row.value || "";
      const selected = state.selectedCalendarFor === value ? " selected" : "";

      html += '<option value="' + escapeHtml(value) + '"' + selected + ">" + escapeHtml(label) + "</option>";
    });

    if (!html) {
      if (state.dashboardType === "coach") {
        html = '<option value="' + COACH_ME_VALUE + '">My Calendar</option>';
      } else if (state.dashboardType === "franchisor") {
        html = '<option value="' + FRANCHISOR_ME_VALUE + '">Me</option>';
      }
    }

    select.innerHTML = html;
  }

  function renameCalendarForLabel() {
    const coachLabel = document.querySelector("label[for='trkCoachCalendarWorkerSelect']");
    if (coachLabel) coachLabel.textContent = "View Calendar For";

    const franchisorLabel = document.querySelector("label[for='trkFranchisorCalendarForSelect']");
    if (franchisorLabel) franchisorLabel.textContent = "View Calendar For";
  }

  function renderCalendar() {
    updateViewButtons();

    if (state.currentView === "month") {
      renderMonthView();
      return;
    }

    renderRangeLabel();
    renderTimeColumn();
    renderDayHeader();
    renderDayGrid();
    renderEvents();
  }

  function updateViewButtons() {
    setTabActive("trkCalendarWeekViewBtn", state.currentView === "week");
    setTabActive("trkCalendarDayViewBtn", state.currentView === "day");
    setTabActive("trkCalendarMonthViewBtn", state.currentView === "month");
  }

  function setTabActive(id, active) {
    const node = document.getElementById(id);
    if (!node) return;

    node.classList.toggle("is-active", !!active);
  }

  function renderRangeLabel() {
    const label = document.getElementById("trkCalendarRangeLabel");
    if (!label) return;

    if (state.currentView === "day") {
      label.textContent = formatLongDisplayDate(formatDateKey(state.currentDate));
      return;
    }

    const start = getWeekStart(state.currentDate);
    const end = addDays(start, 6);

    label.textContent = formatDisplayDate(start) + " to " + formatDisplayDate(end);
  }

  function renderTimeColumn() {
    const board = document.getElementById("trkCalendarBoard");
    const column = document.getElementById("trkCalendarTimeColumn");
    const wrap = document.querySelector(".trk-calendar-grid-wrap");
    const grid = document.getElementById("trkCalendarDayGrid");
    const header = document.getElementById("trkCalendarDayHeader");

    if (!column || !board || !wrap || !grid || !header) return;

    board.classList.remove("trk-calendar-board-month");
    board.style.display = "grid";
    board.style.gridTemplateColumns = "60px minmax(0, 1fr)";
    board.style.minHeight = "620px";

    wrap.style.display = "";
    wrap.style.overflowX = "auto";
    wrap.style.minWidth = "0";

    header.style.display = "grid";
    grid.style.display = "grid";
    column.style.display = "";

    let html = "";

    for (let hour = START_HOUR; hour < END_HOUR; hour++) {
      html += '<div class="trk-calendar-time-slot trk-calendar-time-slot-label">' + pad(hour) + ':00</div>';
      html += '<div class="trk-calendar-time-slot"></div>';
    }

    column.innerHTML = html;
  }

  function renderDayHeader() {
    const header = document.getElementById("trkCalendarDayHeader");
    if (!header) return;

    const todayStr = formatDateKey(new Date());
    let html = "";

    const daysToRender = state.currentView === "day" ? 1 : 7;
    const startDate = state.currentView === "day" ? stripTime(state.currentDate) : getWeekStart(state.currentDate);

    for (let i = 0; i < daysToRender; i++) {
      const day = addDays(startDate, i);
      const dateKey = formatDateKey(day);
      const isToday = dateKey === todayStr ? " is-today" : "";

      html += '<div class="trk-calendar-day-header-cell' + isToday + '">'
        + '<div class="trk-calendar-day-name">' + DAYS[day.getDay()] + '</div>'
        + '<div class="trk-calendar-day-number">' + day.getDate() + '</div>'
        + '</div>';
    }

    header.style.gridTemplateColumns = "repeat(" + daysToRender + ", minmax(110px, 1fr))";
    header.innerHTML = html;
  }

  function renderDayGrid() {
    const grid = document.getElementById("trkCalendarDayGrid");
    if (!grid) return;

    let html = "";
    const daysToRender = state.currentView === "day" ? 1 : 7;
    const startDate = state.currentView === "day" ? stripTime(state.currentDate) : getWeekStart(state.currentDate);

    for (let i = 0; i < daysToRender; i++) {
      const day = addDays(startDate, i);
      const dateKey = formatDateKey(day);
      const weekendClass = day.getDay() === 0 || day.getDay() === 6 ? " is-weekend" : "";

      html += '<div class="trk-calendar-day-column' + weekendClass + '" id="trkCalendarDayCol-' + i + '">';

      for (let minutes = START_HOUR * 60; minutes < END_HOUR * 60; minutes += SLOT_MINUTES) {
        const slotTime = minutesToTime(minutes);

        html += '<button type="button" class="trk-calendar-grid-slot"'
          + ' data-date="' + escapeHtml(dateKey) + '"'
          + ' data-time="' + escapeHtml(slotTime) + '"'
          + ' aria-label="Book at ' + escapeHtml(slotTime) + ' on ' + escapeHtml(dateKey) + '"></button>';
      }

      html += '</div>';
    }

    grid.style.display = "grid";
    grid.style.gridTemplateColumns = "repeat(" + daysToRender + ", minmax(110px, 1fr))";
    grid.innerHTML = html;

    grid.querySelectorAll(".trk-calendar-grid-slot").forEach(function (slot) {
      slot.addEventListener("click", function () {
        openBookingModal(this.dataset.date, this.dataset.time);
      });
    });
  }

  function renderEvents() {
    document.querySelectorAll(".trk-calendar-event").forEach(function (node) {
      node.remove();
    });

    const rows = getVisibleEvents();
    if (!rows.length) return;

    const startDate = state.currentView === "day" ? stripTime(state.currentDate) : getWeekStart(state.currentDate);

    rows.forEach(function (event) {
      const date = parseDateKey(event.date);
      if (!date) return;

      const dayIndex = state.currentView === "day" ? 0 : dayOffsetWithinWeek(date, startDate);
      const maxIndex = state.currentView === "day" ? 0 : 6;

      if (dayIndex < 0 || dayIndex > maxIndex) return;

      const dayColumn = document.getElementById("trkCalendarDayCol-" + dayIndex);
      if (!dayColumn) return;

      const eventNode = document.createElement("button");
      eventNode.type = "button";
      eventNode.className = "trk-calendar-event";

      const startMinutes = timeToMinutes(event.start_time);
      const endMinutes = timeToMinutes(event.end_time);
      const duration = Math.max(endMinutes - startMinutes, SLOT_MINUTES);
      const top = ((startMinutes - START_HOUR * 60) / SLOT_MINUTES) * SLOT_HEIGHT + 2;
      const height = Math.max((duration / SLOT_MINUTES) * SLOT_HEIGHT - 6, 36);

      if (top < 0) return;

      applyEventTypeStyle(eventNode, event.type);

      eventNode.style.top = top + "px";
      eventNode.style.height = height + "px";

      eventNode.innerHTML =
        '<span class="trk-calendar-event-title">' + escapeHtml(event.title || "Session") + '</span>' +
        '<span class="trk-calendar-event-time">' + escapeHtml((event.start_time || "") + " - " + (event.end_time || "")) + '</span>' +
        getCalendarEventProgressHtml(event);

      eventNode.addEventListener("click", function (clickEvent) {
        clickEvent.stopPropagation();

        state.selectedEvent = event;
        renderDetails(event);
      });

      dayColumn.appendChild(eventNode);
    });
  }

  function renderMonthView() {
    const board = document.getElementById("trkCalendarBoard");
    const timeColumn = document.getElementById("trkCalendarTimeColumn");
    const header = document.getElementById("trkCalendarDayHeader");
    const grid = document.getElementById("trkCalendarDayGrid");
    const label = document.getElementById("trkCalendarRangeLabel");
    const wrap = document.querySelector(".trk-calendar-grid-wrap");

    if (!board || !timeColumn || !header || !grid || !label || !wrap) return;

    const monthStart = new Date(state.currentDate.getFullYear(), state.currentDate.getMonth(), 1);
    const monthEnd = new Date(state.currentDate.getFullYear(), state.currentDate.getMonth() + 1, 0);
    const firstGridDate = addDays(monthStart, -monthStart.getDay());
    const lastGridDate = addDays(monthEnd, 6 - monthEnd.getDay());

    label.textContent = MONTH_NAMES[state.currentDate.getMonth()] + " " + state.currentDate.getFullYear();

    board.classList.add("trk-calendar-board-month");
    board.style.display = "block";
    board.style.gridTemplateColumns = "";
    board.style.minHeight = "0";

    timeColumn.style.display = "none";

    wrap.style.display = "block";
    wrap.style.overflowX = "hidden";
    wrap.style.width = "100%";

    let headerHtml = "";

    for (let i = 0; i < 7; i++) {
      headerHtml += '<div class="trk-calendar-day-header-cell">'
        + '<div class="trk-calendar-day-name">' + DAYS[i] + '</div>'
        + '</div>';
    }

    header.style.display = "grid";
    header.style.gridTemplateColumns = "repeat(7, minmax(0, 1fr))";
    header.innerHTML = headerHtml;

    const eventsByDate = {};

    state.events.forEach(function (row) {
      const key = row.date || "";
      if (!eventsByDate[key]) eventsByDate[key] = [];
      eventsByDate[key].push(row);
    });

    let html = '<div class="trk-calendar-month-grid" style="display:grid;grid-template-columns:repeat(7,minmax(0,1fr));width:100%;border-top:1px solid #D9E6E6;border-left:1px solid #D9E6E6;">';

    for (let cursor = new Date(firstGridDate); cursor <= lastGridDate; cursor = addDays(cursor, 1)) {
      const dateKey = formatDateKey(cursor);
      const isCurrentMonth = cursor.getMonth() === state.currentDate.getMonth();
      const isToday = dateKey === formatDateKey(new Date());

      const cellEvents = (eventsByDate[dateKey] || []).slice().sort(function (a, b) {
        return timeToMinutes(a.start_time) - timeToMinutes(b.start_time);
      });

      html += '<div'
        + ' data-calendar-month-date="' + escapeHtml(dateKey) + '"'
        + ' style="min-height:112px;padding:6px;border-right:1px solid #D9E6E6;border-bottom:1px solid #D9E6E6;background:' + (isCurrentMonth ? "#FFFFFF" : "#F7FAFA") + ';cursor:pointer;min-width:0;box-sizing:border-box;">';

      html += '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">'
        + '<div style="font-size:12px;font-weight:700;color:' + (isCurrentMonth ? "#434B49" : "#A2B2B2") + ';'
        + (isToday ? 'background:#00A19E;color:#FFFFFF;border-radius:999px;min-width:24px;height:24px;display:flex;align-items:center;justify-content:center;' : '') + '">'
        + cursor.getDate()
        + '</div>'
        + '</div>';

      html += '<div style="display:flex;flex-direction:column;gap:4px;min-width:0;">';

      cellEvents.forEach(function (row) {
        const style = TYPE_STYLES[row.type] || TYPE_STYLES["Therapy Session"];
        const monthLabel = getMonthEventLabel(row);

        html += '<button type="button"'
          + ' data-calendar-month-event="' + escapeHtml(row.name || "") + '"'
          + ' style="width:100%;display:block;text-align:left;border:0;border-radius:8px;padding:5px 7px;font-size:11px;font-weight:700;line-height:1.2;background:' + escapeHtml(style.background) + ';color:' + escapeHtml(style.textColor || "#FFFFFF") + ';cursor:pointer;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;min-width:0;box-sizing:border-box;">'
          + escapeHtml(monthLabel)
          + '</button>';
      });

      html += '</div></div>';
    }

    html += '</div>';

    grid.style.display = "block";
    grid.style.gridTemplateColumns = "";
    grid.style.width = "100%";
    grid.innerHTML = html;
  }

  function renderDetails(event) {
    const body = document.getElementById("trkCalendarDetailsBody");
    if (!body) return;

    const detailsUrl = getDefaultDetailsUrl(event.name || "");
    const isPrivate = Number(event.is_private || 0) === 1;

    let actions = "";
    const viewMode = getViewModeParams();

    if (!isPrivate) {
      actions =
        '<div class="dashboard-detail-actions" style="margin-top:16px;">';

      if (!viewMode.isViewMode) {
        actions +=
          '<button type="button" class="dashboard-btn dashboard-btn-primary" data-calendar-action="edit-session" data-event="' + escapeHtml(event.name || "") + '">Edit Session</button>'
          + '<button type="button" class="dashboard-btn dashboard-btn-light" data-calendar-action="add-note" data-event="' + escapeHtml(event.name || "") + '">Add Note</button>';
      }

      actions +=
        '<a class="dashboard-link-btn" href="' + escapeHtml(detailsUrl) + '">Open details page ↗</a>'
        + '</div>';
    }

    body.innerHTML =
      '<div class="trk-calendar-detail-group"><div class="trk-calendar-detail-label">Client / Session</div><div class="trk-calendar-detail-value">' + escapeHtml(event.title || "Session") + '</div></div>' +
      '<div class="trk-calendar-detail-group"><div class="trk-calendar-detail-label">Date</div><div class="trk-calendar-detail-value">' + escapeHtml(formatLongDisplayDate(event.date)) + '</div></div>' +
      '<div class="trk-calendar-detail-group"><div class="trk-calendar-detail-label">Time</div><div class="trk-calendar-detail-value">' + escapeHtml((event.start_time || "") + " - " + (event.end_time || "")) + '</div></div>' +
      '<div class="trk-calendar-detail-group"><div class="trk-calendar-detail-label">Status</div><div class="trk-calendar-detail-value"><span class="dashboard-badge ' + getBadgeClass(event.ui_status) + '">' + escapeHtml(event.ui_status || "Booked") + '</span></div></div>' +
      '<div class="trk-calendar-detail-group"><div class="trk-calendar-detail-label">Worker</div><div class="trk-calendar-detail-value">' + escapeHtml(event.worker || state.currentWorkerLabel || "Current Session Worker") + '</div></div>' +
      (
        isPrivate
          ? ''
          : (
              '<div class="trk-calendar-detail-group"><div class="trk-calendar-detail-label">Type</div><div class="trk-calendar-detail-value">' + escapeHtml(event.type || "Session") + '</div></div>' +
              getSessionProgressDetailHtml(event) +
              getBookingWarningDetailHtml(event) +
              '<div class="trk-calendar-detail-group"><div class="trk-calendar-detail-label">Billing Type</div><div class="trk-calendar-detail-value">' + escapeHtml(event.billing_type || "Non-Billable") + '</div></div>' +
              '<div class="trk-calendar-detail-group"><div class="trk-calendar-detail-label">Travel Charged</div><div class="trk-calendar-detail-value">' + (Number(event.travel_charged || 0) ? "Yes" : "No") + '</div></div>' +
              '<div class="trk-calendar-detail-group"><div class="trk-calendar-detail-label">Location</div><div class="trk-calendar-detail-value">' + escapeHtml(event.location || "Not set") + '</div></div>'
            )
      ) +
      actions;
  }

  function getDefaultDetailsUrl(eventName) {
    if (state.dashboardType === "coach") {
      const params = new URLSearchParams(window.location.search);
      params.set("event", eventName || "");
      params.delete("calendar_for");
      params.delete("selected_calendar_for");
      params.delete("selected_worker");
      params.delete("view");
      params.delete("date");

      return "/coach_db/calendar_details?" + params.toString();
    }

    if (state.dashboardType === "franchisor") {
      return "/franchisor_db/calendar_details?event=" + encodeURIComponent(eventName || "");
    }

    const params = new URLSearchParams(window.location.search);
    params.set("event", eventName || "");
    return "/session_worker_db/calendar_details?" + params.toString();
  }

  function renderDetailsEmptyState() {
    const body = document.getElementById("trkCalendarDetailsBody");
    if (!body) return;

    body.innerHTML = '<div class="dashboard-empty">Select a calendar item to view its details.</div>';
  }

  function refreshSelectedEvent() {
    if (!state.selectedEvent || !state.selectedEvent.name) return;

    const fresh = getEventByName(state.selectedEvent.name);

    if (!fresh) {
      state.selectedEvent = null;
      renderDetailsEmptyState();
      return;
    }

    state.selectedEvent = fresh;
    renderDetails(fresh);
  }

  function renderClientOptions() {
    const select = document.getElementById("trkCalendarClientSelect");
    if (!select) return;

    let html = '<option value="">Select a client</option>';

    state.clients.forEach(function (client) {
      html += '<option value="' + escapeHtml(client.value) + '">' + escapeHtml(client.label) + '</option>';
    });

    select.innerHTML = html;
  }

  function updateClientNotice(errorMessage) {
    const notice = document.getElementById("trkCalendarClientNotice");
    if (!notice) return;

    if (errorMessage) {
      notice.textContent = errorMessage;
    } else if (state.resolutionNote && !state.clients.length) {
      notice.textContent = state.resolutionNote;
    } else if (!state.clients.length) {
      notice.textContent = "No clients linked to this calendar were found.";
    } else {
      notice.textContent = "";
    }

    notice.style.display = notice.textContent ? "" : "none";
  }

  function saveBooking() {
    const clientId = getValue("trkCalendarClientSelect");
    const clientName = getSelectedText("trkCalendarClientSelect");
    const date = getValue("trkCalendarDate");
    const time = getValue("trkCalendarTime");
    const type = getValue("trkCalendarType") || "Therapy Session";
    const duration = getValue("trkCalendarDuration") || "45";

    const billingType = type === "General"
      ? (getValue("trkCalendarBillingType") || "")
      : (DEFAULT_BILLING_BY_TYPE[type] || "One to One");

    const travelCharged = type === "General"
      ? (getValue("trkCalendarTravelCharged") || "0")
      : (getValue("trkCalendarTravelChargedSingle") || "0");

    const location = getValue("trkCalendarLocation");
    const notes = getValue("trkCalendarNotes");

    if (!clientId) {
      showToast("Please select a client");
      return;
    }

    if (!date || !time) {
      showToast("Please select date and time");
      return;
    }

    if (type === "General" && !billingType) {
      showToast("Please select a billing type");
      return;
    }

    setButtonLoading("trkCalendarSaveBtn", true, "Saving...");

    apiPost(SHARED_API + ".create_booking", {
      dashboard_type: state.dashboardType,
      client: clientId,
      client_name: clientName,
      booking_date: date,
      booking_time: time,
      duration_minutes: duration,
      appointment_type: type,
      billing_type: billingType,
      travel_charged: travelCharged,
      location: location,
      notes: notes
    }).then(function () {
      setButtonLoading("trkCalendarSaveBtn", false, "Save Session");
      closeBookingModal();
      showToast("Session booked");
      loadCalendarData();
    }).catch(function (error) {
      console.error("Save booking failed:", error);

      setButtonLoading("trkCalendarSaveBtn", false, "Save Session");
      showToast(error.message || "Could not save session");
    });
  }

  function saveSessionChanges() {
    const eventName = getValue("trkEditEventName");
    const bookingDate = getValue("trkEditDate");
    const bookingTime = getValue("trkEditTime");
    const status = getValue("trkEditStatus");
    const appointmentType = getValue("trkEditType");

    const billingType = appointmentType === "General"
      ? (getValue("trkEditBillingType") || "")
      : (DEFAULT_BILLING_BY_TYPE[appointmentType] || "One to One");

    const travelCharged = appointmentType === "General"
      ? (getValue("trkEditTravelCharged") || "0")
      : (getValue("trkEditTravelChargedSingle") || "0");

    const location = getValue("trkEditLocation");

    if (!eventName) {
      showToast("No session selected");
      return;
    }

    if (!bookingDate || !bookingTime) {
      showToast("Please select date and time");
      return;
    }

    if (appointmentType === "General" && !billingType) {
      showToast("Please select a billing type");
      return;
    }

    setButtonLoading("trkCalendarEditSaveBtn", true, "Saving...");

    apiPost(SHARED_API + ".update_session", {
      dashboard_type: state.dashboardType,
      event: eventName,
      booking_date: bookingDate,
      booking_time: bookingTime,
      status: status,
      appointment_type: appointmentType,
      billing_type: billingType,
      travel_charged: travelCharged,
      location: location
    }).then(function () {
      setButtonLoading("trkCalendarEditSaveBtn", false, "Save Changes");
      closeEditModal();
      showToast("Session updated");
      loadCalendarData();
    }).catch(function (error) {
      console.error("Update session failed:", error);

      setButtonLoading("trkCalendarEditSaveBtn", false, "Save Changes");
      showToast(error.message || "Could not save session");
    });
  }

  function saveClientNote() {
    const client = getValue("trkNoteClientName");
    const sessionDate = getValue("trkNoteSessionDate");
    const sessionType = getValue("trkNoteSessionType");
    const notes = getValue("trkNoteText").trim();

    if (!client) {
      showToast("This session is not linked to a client");
      return;
    }

    if (!notes) {
      showToast("Please enter a note");
      return;
    }

    setButtonLoading("trkCalendarNoteSaveBtn", true, "Saving...");

    apiPost(SHARED_API + ".add_client_note", {
      dashboard_type: state.dashboardType,
      client: client,
      session_date: sessionDate,
      session_type: sessionType,
      notes: notes
    }).then(function () {
      setButtonLoading("trkCalendarNoteSaveBtn", false, "Save Note");
      closeNoteModal();
      showToast("Client note saved");
    }).catch(function (error) {
      console.error("Save note failed:", error);

      setButtonLoading("trkCalendarNoteSaveBtn", false, "Save Note");
      showToast(error.message || "Could not save client note");
    });
  }

  function openBookingModal(dateStr, timeStr) {
    setValue("trkCalendarClientSelect", "");
    setValue("trkCalendarDate", dateStr || "");
    setValue("trkCalendarTime", timeStr || "");
    setValue("trkCalendarType", "Therapy Session");
    setValue("trkCalendarDuration", "45");
    setValue("trkCalendarBillingType", "");
    setValue("trkCalendarTravelCharged", "0");
    setValue("trkCalendarTravelChargedSingle", "0");
    setValue("trkCalendarLocation", "");
    setValue("trkCalendarNotes", "");

    syncBookingFields();
    toggleModal("trkCalendarModal", true);
  }

  function closeBookingModal() {
    toggleModal("trkCalendarModal", false);
  }

  function openEditModal(eventName) {
    const event = getEventByName(eventName);

    if (!event) {
      showToast("Session not found");
      return;
    }

    if (Number(event.is_private || 0) === 1) {
      showToast("This session cannot be edited from this dashboard");
      return;
    }

    setValue("trkEditEventName", event.name || "");
    setValue("trkEditDate", event.date || "");
    setValue("trkEditTime", event.start_time || "");
    setValue("trkEditStatus", event.ui_status || "Booked");
    setValue("trkEditType", event.type || "Therapy Session");
    setValue("trkEditBillingType", event.billing_type || "");
    setValue("trkEditTravelCharged", String(Number(event.travel_charged || 0)));
    setValue("trkEditTravelChargedSingle", String(Number(event.travel_charged || 0)));
    setValue("trkEditLocation", event.location || "");

    syncEditFields();
    toggleModal("trkCalendarEditModal", true);
  }

  function closeEditModal() {
    toggleModal("trkCalendarEditModal", false);
  }

  function openNoteModal(eventName) {
    const event = getEventByName(eventName);

    if (!event) {
      showToast("Session not found");
      return;
    }

    if (Number(event.is_private || 0) === 1) {
      showToast("This session cannot be edited from this dashboard");
      return;
    }

    if (!event.client_name) {
      showToast("This session is not linked to a client");
      return;
    }

    setValue("trkNoteEventName", event.name || "");
    setValue("trkNoteClientName", event.client_name || "");
    setValue("trkNoteSessionDate", event.date || "");
    setValue("trkNoteSessionType", mapAppointmentTypeToClientNoteType(event.type || ""));
    setValue("trkNoteText", "");

    toggleModal("trkCalendarNoteModal", true);
  }

  function closeNoteModal() {
    toggleModal("trkCalendarNoteModal", false);
  }

  function syncBookingFields() {
    const type = getValue("trkCalendarType");
    const isGeneral = type === "General";

    toggleDisplay("trkCalendarBillingTypeRow", isGeneral);
    toggleDisplay("trkCalendarTravelRow", !isGeneral);

    if (!isGeneral) {
      setValue("trkCalendarBillingType", "");
    }
  }

  function syncEditFields() {
    const type = getValue("trkEditType");
    const isGeneral = type === "General";

    toggleDisplay("trkEditBillingTypeRow", isGeneral);
    toggleDisplay("trkEditTravelRow", !isGeneral);

    if (!isGeneral) {
      setValue("trkEditBillingType", "");
    }
  }

  function toggleDisplay(id, show) {
    const node = document.getElementById(id);
    if (!node) return;

    node.style.display = show ? "" : "none";
  }

  function toggleModal(id, show) {
    const modal = document.getElementById(id);
    if (modal) modal.classList.toggle("show", !!show);
  }

  function setLoading(show) {
    state.loading = !!show;

    const node = document.getElementById("trkCalendarLoading");
    if (node) node.classList.toggle("show", state.loading);
  }

  function setButtonLoading(id, loading, text) {
    const btn = document.getElementById(id);
    if (!btn) return;

    btn.disabled = !!loading;
    btn.textContent = text;
  }

  function apiGet(method, params) {
    const url = new URL("/api/method/" + method, window.location.origin);

    Object.keys(params || {}).forEach(function (key) {
      const value = params[key];
      if (value !== undefined && value !== null && value !== "") {
        url.searchParams.set(key, value);
      }
    });

    return fetch(url.toString(), {
      method: "GET",
      credentials: "same-origin",
      headers: { "Accept": "application/json" }
    }).then(handleApiResponse);
  }

  function apiPost(method, payload) {
    return fetch("/api/method/" + method, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-Frappe-CSRF-Token": getCsrfToken()
      },
      body: JSON.stringify(payload || {})
    }).then(handleApiResponse);
  }

  function handleApiResponse(response) {
    return response.text().then(function (text) {
      let data = {};

      try {
        data = text ? JSON.parse(text) : {};
      } catch (error) {
        throw new Error("Invalid server response");
      }

      if (!response.ok) {
        throw new Error(extractErrorMessage(data) || "Request failed");
      }

      if (data && data.exc) {
        throw new Error(extractErrorMessage(data) || "Server error");
      }

      return data && data.message ? data.message : {};
    });
  }

  function extractErrorMessage(data) {
    if (!data) return "";

    if (typeof data._server_messages === "string" && data._server_messages) {
      try {
        const parsed = JSON.parse(data._server_messages);

        if (Array.isArray(parsed) && parsed.length) {
          const first = JSON.parse(parsed[0]);
          if (first && first.message) return first.message;
        }
      } catch (error) {
        console.error("Could not parse server messages:", error);
      }
    }

    if (typeof data.message === "string") return data.message;
    if (data.exception) return String(data.exception);

    return "";
  }

  function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    if (meta && meta.content) return meta.content;

    const match = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  function getEventByName(name) {
    return state.events.find(function (row) {
      return row.name === name;
    }) || null;
  }

  function getBadgeClass(uiStatus) {
    if (uiStatus === "Attended") return "dashboard-status-active";
    if (uiStatus === "Cancelled") return "dashboard-status-archived";
    if (uiStatus === "No Show") return "dashboard-status-onhold";

    return "dashboard-status-onhold";
  }

  function mapAppointmentTypeToClientNoteType(appointmentType) {
    if (appointmentType === "Initial Consultation") return "Initial Consultation";
    if (appointmentType === "Parent Check-In") return "Parent Feedback";
    if (appointmentType === "Therapy Session") return "Coaching Session";

    return "Other";
  }

  function getSelectedText(id) {
    const node = document.getElementById(id);
    if (!node || node.selectedIndex < 0) return "";

    return node.options[node.selectedIndex].text || "";
  }

  function setValue(id, value) {
    const node = document.getElementById(id);
    if (node) node.value = value;
  }

  function getValue(id) {
    const node = document.getElementById(id);
    return node ? node.value : "";
  }

  function showToast(message) {
    const toast = document.getElementById("trkCalendarToast");
    if (!toast) return;

    toast.textContent = message;
    toast.classList.add("show");

    clearTimeout(toast._hideTimer);
    toast._hideTimer = setTimeout(function () {
      toast.classList.remove("show");
    }, 2400);
  }

  function restoreCalendarStateFromUrl() {
    const params = new URLSearchParams(window.location.search);
    const view = params.get("view");
    const date = params.get("date");

    if (view === "day" || view === "week" || view === "month") {
      state.currentView = view;
    } else {
      state.currentView = getDefaultCalendarView();
    }

    const parsedDate = parseDateKey(date || "");
    state.currentDate = parsedDate || stripTime(new Date());
  }

  function saveCalendarStateToUrl() {
    const params = new URLSearchParams(window.location.search);

    params.set("view", state.currentView);
    params.set("date", formatDateKey(state.currentDate));

    if (state.dashboardType !== "session_worker" && state.selectedCalendarFor) {
      params.set("calendar_for", state.selectedCalendarFor);
      params.set("selected_calendar_for", state.selectedCalendarFor);
      params.set("selected_worker", state.selectedCalendarFor);
    }

    const newUrl = window.location.pathname + "?" + params.toString();
    window.history.replaceState({}, "", newUrl);
  }

  function isCancelledEvent(event) {
    const status = String(event.ui_status || event.status || "").toLowerCase().trim();
    return status === "cancelled" || status === "canceled";
  }

  function getVisibleEvents() {
    if (state.currentView === "month") {
      return state.events;
    }

    if (state.currentView === "day") {
      const key = formatDateKey(state.currentDate);

      return state.events.filter(function (row) {
        return row.date === key;
      });
    }

    const start = getWeekStart(state.currentDate);
    const end = addDays(start, 6);

    return state.events.filter(function (row) {
      const date = parseDateKey(row.date);
      if (!date) return false;

      const cleanDate = stripTime(date);

      return cleanDate >= stripTime(start) && cleanDate <= stripTime(end);
    });
  }

  function applyEventTypeStyle(node, type) {
    const style = TYPE_STYLES[type] || TYPE_STYLES["Therapy Session"];

    node.style.background = style.background;
    node.style.borderLeft = "4px solid " + style.border;
    node.style.color = style.textColor || "#FFFFFF";
  }

  function getCalendarEventProgressHtml(event) {
    if (!event) return "";

    const progressText = event.progress_text || "";
    const sessionNumber = Number(event.session_number || 0);
    const totalSessions = Number(event.total_sessions || 0);

    let label = "";

    if (progressText) {
      label = progressText;
    } else if (sessionNumber && totalSessions) {
      label = sessionNumber + " of " + totalSessions;
    }

    if (!label) return "";

    return '<span class="trk-calendar-event-time" style="font-weight:800;">Session ' + escapeHtml(label) + '</span>';
  }

  function getSessionProgressDetailHtml(event) {
    if (!event) return "";

    const progressText = event.progress_text || "";
    const sessionNumber = Number(event.session_number || 0);
    const totalSessions = Number(event.total_sessions || 0);

    let label = "";

    if (progressText) {
      label = progressText;
    } else if (sessionNumber && totalSessions) {
      label = sessionNumber + " of " + totalSessions;
    }

    if (!label) return "";

    return '<div class="trk-calendar-detail-group">'
      + '<div class="trk-calendar-detail-label">Session Progress</div>'
      + '<div class="trk-calendar-detail-value"><strong>Session ' + escapeHtml(label) + '</strong></div>'
      + '</div>';
  }

  function getBookingWarningDetailHtml(event) {
    if (!event || !event.booking_warning) return "";

    return '<div class="dashboard-notice" style="margin:10px 0 14px 0;background:#fff7ed;border-left:4px solid #ff8438;color:#7c2d12;">'
      + escapeHtml(event.booking_warning)
      + '</div>';
  }

  function getWeekStart(date) {
    const d = stripTime(date);
    d.setDate(d.getDate() - d.getDay());

    return d;
  }

  function addDays(date, days) {
    const d = new Date(date.getTime());
    d.setDate(d.getDate() + days);

    return stripTime(d);
  }

  function stripTime(date) {
    return new Date(date.getFullYear(), date.getMonth(), date.getDate());
  }

  function formatDisplayDate(date) {
    return date.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
  }

  function formatLongDisplayDate(dateKey) {
    const date = parseDateKey(dateKey);

    if (!date) return dateKey;

    return date.toLocaleDateString("en-GB", {
      weekday: "long",
      day: "numeric",
      month: "long",
      year: "numeric"
    });
  }

  function formatDateKey(date) {
    return [date.getFullYear(), pad(date.getMonth() + 1), pad(date.getDate())].join("-");
  }

  function parseDateKey(value) {
    if (!value || typeof value !== "string") return null;

    const parts = value.split("-").map(Number);
    if (parts.length !== 3) return null;

    return new Date(parts[0], parts[1] - 1, parts[2]);
  }

  function dayOffsetWithinWeek(date, weekStart) {
    const oneDay = 24 * 60 * 60 * 1000;

    return Math.round((stripTime(date).getTime() - stripTime(weekStart).getTime()) / oneDay);
  }

  function timeToMinutes(timeValue) {
    const parts = String(timeValue || "00:00").split(":");
    const hours = parseInt(parts[0], 10) || 0;
    const minutes = parseInt(parts[1], 10) || 0;

    return (hours * 60) + minutes;
  }

  function minutesToTime(totalMinutes) {
    const hours = Math.floor(totalMinutes / 60);
    const minutes = totalMinutes % 60;

    return pad(hours) + ":" + pad(minutes);
  }

  function pad(value) {
    return value < 10 ? "0" + value : String(value);
  }

  function getMonthEventLabel(row) {
    if (row && row.client_name) return row.client_name;

    const title = String((row && row.title) || "").trim();
    if (!title) return "Session";

    if (title.includes(" - ")) {
      return title.split(" - ")[0].trim() || title;
    }

    if (title.includes(" | ")) {
      return title.split(" | ")[0].trim() || title;
    }

    return title;
  }

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
