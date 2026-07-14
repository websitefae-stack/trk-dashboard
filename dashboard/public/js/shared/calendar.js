(function () {
  "use strict";

  // Wide enough to cover early school-run visits and late evening company
  // meetings/personal appointments without clipping them off the grid -
  // an event starting before START_HOUR used to be silently skipped
  // entirely (see the top < 0 guard in renderEvents()), which is why some
  // appointment types looked like they were "missing" when really they
  // were just scheduled outside the old 7am-7pm window.
  const START_HOUR = 5;
  const END_HOUR = 23;
  const SLOT_MINUTES = 30;
  const SLOT_HEIGHT = 44;
  const MOBILE_BREAKPOINT = 860;

  const DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  const MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

  const SHARED_API = "dashboard.api.shared.calendar";

  // Matches RECURRING_ALLOWED_TYPES in dashboard/api/shared/calendar.py -
  // the backend silently forces repeat_count back to 1 for anything else,
  // so showing the recurring controls for other types would be misleading.
  // Every type except Holiday (its own from_date/to_date range, not a
  // single start time) and Initial Consultation (a one-off by nature).
  const RECURRING_ALLOWED_TYPES = [
    "Therapy Session", "Parent Check-In",
    "Internal Training", "School Visit", "Company Meeting",
    "School Session", "Company Session", "Event / Stall", "Personal",
  ];

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
    "Internal Training": 360,
    "School Visit": 120,
    "Company Meeting": 120,
    "School Session": 45,
    "Company Session": 45,
    "Event / Stall": 180,
    "Holiday": 0,
    "Personal": 60
  };

  const CLIENT_REQUIRED_TYPES = ["Therapy Session", "Parent Check-In"];
  const NON_CLIENT_TITLE_TYPES = ["Internal Training", "Event / Stall", "Personal"];
  const SCHOOL_LINKED_TYPES = ["School Visit", "Company Meeting", "School Session", "Company Session"];
  const GOOGLE_MEET_TYPES = ["Therapy Session", "Parent Check-In", "Initial Consultation"];

  const DEFAULT_BILLING_BY_TYPE = {
    "Therapy Session": "One to One",
    "Parent Check-In": "One to One",
    "Initial Consultation": "Non-Billable",
    "Internal Training": "Non-Billable",
    "School Visit": "Non-Billable",
    "Company Meeting": "Non-Billable",
    "School Session": "One to One",
    "Company Session": "One to One",
    "Event / Stall": "Non-Billable",
    "Holiday": "Non-Billable",
    "Personal": "Non-Billable"
  };

  const TYPE_STYLES = {
    "Therapy Session":    { background: "#AC455C", border: "#7A1E35", textColor: "#FFFFFF" },
    "Parent Check-In":    { background: "#E94763", border: "#C01C3E", textColor: "#FFFFFF" },
    "Initial Consultation": { background: "#582581", border: "#3D1760", textColor: "#FFFFFF" },
    "Internal Training":  { background: "#9A4795", border: "#722870", textColor: "#FFFFFF" },
    "School Visit":       { background: "#5FE07C", border: "#2AAD4A", textColor: "#002B0A" },
    "Event / Stall":      { background: "#98962A", border: "#6E6C1A", textColor: "#FFFFFF" },
    "Company Meeting":    { background: "#FF8438", border: "#CC5200", textColor: "#FFFFFF" },
    "School Session":     { background: "#1FA37A", border: "#127A5A", textColor: "#FFFFFF" },
    "Company Session":    { background: "#B85C1F", border: "#8A4415", textColor: "#FFFFFF" },
    "Holiday":            { background: "#2C9A48", border: "#1A6830", textColor: "#FFFFFF" },
    "Personal":           { background: "#D5DA39", border: "#A0A500", textColor: "#2B2D00" },
    "General":            { background: "#00A19E", border: "#007A78", textColor: "#FFFFFF" }
  };

  const state = {
    dashboardType: getDashboardType(),
    currentView: getDefaultCalendarView(),
    currentDate: stripTime(new Date()),
    selectedCalendarFor: "",
    calendarForOptions: [],
    events: [],
    clients: [],
    schools: [],
    companies: [],
    additionalWorkerOptions: [],
    currentWorkerLabel: "",
    resolutionNote: "",
    selectedEvent: null,
    loading: false,
    autoOpenBookingClient: "",
    autoOpenBookingLead: "",
    autoOpenBookingLeadName: "",
    pendingClientLead: "",
    allowDoubleBooking: false
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

    const params = new URLSearchParams(window.location.search);
    state.autoOpenBookingClient = params.get("book_client") || "";
    state.autoOpenBookingLead = params.get("book_lead") || "";
    state.autoOpenBookingLeadName = params.get("book_lead_name") || "";

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

    bindClick("trkSyncGoogleCalendarBtn", syncGoogleCalendarNow);

    bindClick("trkCalendarConflictBookAnywayBtn", function () {
      state.allowDoubleBooking = true;
      saveBooking();
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

    document.addEventListener("click", function (event) {
      if (event.target && event.target.id === "trkCalendarRecurring") {
        setTimeout(syncBookingFields, 0);
      }

      if (event.target && event.target.id === "trkCalendarGoogleMeet") {
        setTimeout(syncBookingFields, 0);
      }
    });

    document.addEventListener("change", function (event) {
      if (event.target && (event.target.matches("[data-occurrence-date]") || event.target.matches("[data-occurrence-time]"))) {
        const row = event.target.closest("[data-occurrence-index]");
        if (row) row.dataset.userEdited = "1";
        return;
      }

      if (event.target && event.target.id === "trkCalendarType") {
        const newType = event.target.value;
        const startTime = getValue("trkCalendarTime") || "09:00";
        setValue("trkCalendarEndTime", addMinutesToTimeString(startTime, DURATION_BY_TYPE[newType] || 45));
        renderSchoolOptions();
        syncBookingFields();
      }

      if (event.target && event.target.id === "trkCalendarRecurring") {
        syncBookingFields();
      }

      if (
        event.target &&
        (event.target.id === "trkCalendarDate" ||
          event.target.id === "trkCalendarTime" ||
          event.target.id === "trkCalendarRecurringFrequency" ||
          event.target.id === "trkCalendarRecurringCount")
      ) {
        renderRecurringPreview();
      }

      if (event.target && event.target.id === "trkCalendarGoogleMeet") {
        syncBookingFields();
      }

      if (event.target && event.target.id === "trkCalendarLocationType") {
        syncBookingFields();
      }

      if (event.target && event.target.id === "trkCalendarClientSelect") {
        renderParentContactOptions();
        syncBookingFields();
      }

      if (event.target && event.target.id === "trkCalendarSchoolSelect") {
        syncBookingFields();
      }
    });

    const editTypeSelect = document.getElementById("trkEditType");
    if (editTypeSelect) {
      editTypeSelect.addEventListener("change", syncEditFields);
    }

    const editLocationTypeSelect = document.getElementById("trkEditLocationType");
    if (editLocationTypeSelect) {
      editLocationTypeSelect.addEventListener("change", syncEditLocationFields);
    }

    const editDateField = document.getElementById("trkEditDate");
    if (editDateField) {
      editDateField.addEventListener("change", function () {
        updateDatePickerDisplay("trkEditDate", "trkEditDateDisplay");
      });
    }

    const noteDateField = document.getElementById("trkNoteSessionDate");
    if (noteDateField) {
      noteDateField.addEventListener("change", function () {
        updateDatePickerDisplay("trkNoteSessionDate", "trkNoteSessionDateDisplay");
      });
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

          var panel = document.querySelector(".trk-calendar-sidepanel");
          if (panel) {
            panel.scrollIntoView({ behavior: "smooth", block: "nearest" });
          }
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

  function syncGoogleCalendarNow() {
    const button = document.getElementById("trkSyncGoogleCalendarBtn");
    if (button) {
      button.disabled = true;
      button.textContent = "Syncing...";
    }

    apiPost("coach_calendar_sync.api.manual_sync.trigger_pull_for_current_user", {})
      .then(function (result) {
        const imported = Number((result && result.imported) || 0);
        const updated = Number((result && result.updated) || 0);

        if (!imported && !updated) {
          showToast("No new appointments found on Google Calendar.");
        } else {
          showToast(
            "Synced from Google Calendar: " +
            [imported ? imported + " new" : "", updated ? updated + " updated" : ""]
              .filter(Boolean).join(", ")
          );
        }

        loadCalendarData();
      })
      .catch(function (error) {
        showToast(error.message || "Could not sync Google Calendar");
      })
      .finally(function () {
        if (button) {
          button.disabled = false;
          button.textContent = "Sync Google Calendar";
        }
      });
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
      state.schools = Array.isArray(message.schools) ? message.schools : [];
      state.companies = Array.isArray(message.companies) ? message.companies : [];
      state.additionalWorkerOptions = Array.isArray(message.additional_worker_options) ? message.additional_worker_options : [];
      state.calendarForOptions = Array.isArray(message.calendar_for_options) ? message.calendar_for_options : [];
      state.selectedCalendarFor = message.selected_calendar_for || state.selectedCalendarFor || getDefaultCalendarFor();
      state.currentWorkerLabel = message.current_worker_label || "";
      state.resolutionNote = message.resolution_note || "";

      renderCalendarForOptions();
      renderClientOptions();
      renderSchoolOptions();
      updateClientNotice();
      renderCalendar();
      refreshSelectedEvent();
      setLoading(false);
      autoOpenBookingFromClient();
      autoOpenBookingFromLead();
    }).catch(function (error) {
      console.error("Calendar bootstrap failed:", error);

      state.events = [];
      state.clients = [];
      state.schools = [];
      state.companies = [];
      state.additionalWorkerOptions = [];
      state.calendarForOptions = [];
      state.currentWorkerLabel = "";
      state.resolutionNote = "";

      renderCalendarForOptions();
      renderClientOptions();
      renderSchoolOptions();
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

    grid.querySelectorAll(".trk-calendar-day-column").forEach(function (column) {
      column.addEventListener("dragover", function (dragEvent) {
        dragEvent.preventDefault();
        dragEvent.dataTransfer.dropEffect = "move";
        column.classList.add("is-drag-over");
      });

      column.addEventListener("dragleave", function () {
        column.classList.remove("is-drag-over");
      });

      column.addEventListener("drop", function (dragEvent) {
        dragEvent.preventDefault();
        column.classList.remove("is-drag-over");

        const eventName = dragEvent.dataTransfer.getData("text/plain");
        const targetSlot = column.querySelector(".trk-calendar-grid-slot");
        const targetDate = targetSlot ? targetSlot.dataset.date : "";

        if (eventName && targetDate) {
          moveEventToDate(eventName, targetDate);
        }
      });
    });
  }

  function moveEventToDate(eventName, targetDate) {
    const event = getEventByName(eventName);
    if (event && event.date === targetDate) return;

    apiPost(SHARED_API + ".reschedule_event", {
      dashboard_type: state.dashboardType,
      event: eventName,
      date: targetDate
    }).then(function () {
      showToast("Session moved to " + formatLongDisplayDate(targetDate));
      loadCalendarData();
    }).catch(function (error) {
      console.error("Reschedule event failed:", error);
      showToast(error.message || "Could not move this session");
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
      // Pin anything before START_HOUR to the very top of the grid instead
      // of silently dropping it - a real appointment should always be
      // visible somewhere, even if the grid's normal time bounds don't
      // quite reach it.
      const top = Math.max(((startMinutes - START_HOUR * 60) / SLOT_MINUTES) * SLOT_HEIGHT + 2, 2);
      const height = Math.max((duration / SLOT_MINUTES) * SLOT_HEIGHT - 6, 36);

      applyEventTypeStyle(eventNode, event.type, event.ui_status);


      eventNode.style.top = top + "px";
      eventNode.style.height = height + "px";

      eventNode.innerHTML =
        '<span class="trk-calendar-event-title">' + escapeHtml(event.client_display_name || event.title || "Session") + '</span>';

      eventNode.addEventListener("click", function (clickEvent) {
        clickEvent.stopPropagation();

        state.selectedEvent = event;
        renderDetails(event);

        var panel = document.querySelector(".trk-calendar-sidepanel");
        if (panel) {
          panel.scrollIntoView({ behavior: "smooth", block: "nearest" });
        }
      });

      // Private placeholders (a coach can't see another coach's client
      // details) and still-queued "pending booking" preview rows aren't
      // real, movable Event records - dragging either would either fail
      // server-side or move the wrong thing.
      if (!event.is_private && !event.is_pending && state.currentView !== "month") {
        eventNode.draggable = true;

        eventNode.addEventListener("dragstart", function (dragEvent) {
          dragEvent.dataTransfer.setData("text/plain", event.name);
          dragEvent.dataTransfer.effectAllowed = "move";
          eventNode.classList.add("is-dragging");
        });

        eventNode.addEventListener("dragend", function () {
          eventNode.classList.remove("is-dragging");
        });
      }

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
        const style = TYPE_STYLES[row.type] || TYPE_STYLES["General"];
        const monthLabel = getMonthEventLabel(row);

        var monthEventStyle = "width:100%;display:block;text-align:left;border:0;border-radius:8px;padding:5px 7px;font-size:11px;font-weight:700;line-height:1.2;background:" + escapeHtml(style.background) + ";color:" + escapeHtml(style.textColor || "#FFFFFF") + ";cursor:pointer;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;min-width:0;box-sizing:border-box;";
        html += '<button type="button"'
          + ' data-calendar-month-event="' + escapeHtml(row.name || "") + '"'
          + ' style="' + monthEventStyle + '">'
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

    if (Number(event.is_pending || 0) === 1) {
      const isFailed = Number(event.is_failed || 0) === 1;

      body.innerHTML = isFailed
        ? '<div class="trk-calendar-detail-group">'
          + '<div class="trk-calendar-detail-label">Could not be saved</div>'
          + '<div class="trk-calendar-detail-value">'
          + escapeHtml(event.title || "This booking")
          + ' could not be saved after several attempts. Please delete this and try booking it again.'
          + '</div>'
          + (event.last_error
              ? '<div class="trk-calendar-detail-value" style="margin-top:8px;font-size:12px;color:#888;">'
                + escapeHtml(event.last_error)
                + '</div>'
              : '')
          + '</div>'
        : '<div class="trk-calendar-detail-group">'
          + '<div class="trk-calendar-detail-label">Still saving</div>'
          + '<div class="trk-calendar-detail-value">'
          + escapeHtml(event.title || "This booking")
          + ' is still being saved and will finish shortly. No action needed.'
          + '</div>'
          + '</div>';
      return;
    }

    const detailsUrl = getDefaultDetailsUrl(event.name || "");
    const isPrivate = Number(event.is_private || 0) === 1;
    const viewMode = getViewModeParams();

    const workerValue = event.worker || state.currentWorkerLabel || "";
    const showWorker = workerValue && workerValue !== "Me" && workerValue !== "Current Session Worker";

    let actions = "";

    if (!isPrivate && !viewMode.isViewMode) {
      actions =
        '<div class="dashboard-detail-actions" style="margin-top:16px;display:flex;gap:10px;flex-wrap:wrap;">'
        + '<button type="button" class="dashboard-btn dashboard-btn-primary" data-calendar-action="edit-session" data-event="' + escapeHtml(event.name || "") + '">Edit</button>';

      if (event.client_name) {
        actions += '<button type="button" class="dashboard-btn dashboard-btn-light" data-calendar-action="add-note" data-event="' + escapeHtml(event.name || "") + '">Add Note</button>';
      }

      actions += '<a class="dashboard-link-btn" href="' + escapeHtml(detailsUrl) + '">Open Full Page</a>'
        + '</div>';
    } else if (!isPrivate) {
      actions =
        '<div class="dashboard-detail-actions" style="margin-top:16px;">'
        + '<a class="dashboard-link-btn" href="' + escapeHtml(detailsUrl) + '">Open Full Page</a>'
        + '</div>';
    }

    body.innerHTML =
      '<div class="trk-calendar-form-row">'
        + '<div class="trk-calendar-detail-group"><div class="trk-calendar-detail-label">Client / Session</div><div class="trk-calendar-detail-value">' + escapeHtml(event.title || "Session") + '</div></div>'
        + '<div class="trk-calendar-detail-group"><div class="trk-calendar-detail-label">Status</div><div class="trk-calendar-detail-value"><span class="dashboard-badge ' + getBadgeClass(event.ui_status) + '">' + escapeHtml(event.ui_status || "Booked") + '</span></div></div>'
      + '</div>'

      + '<div class="trk-calendar-form-row">'
        + '<div class="trk-calendar-detail-group"><div class="trk-calendar-detail-label">Date</div><div class="trk-calendar-detail-value">' + escapeHtml(formatLongDisplayDate(event.date)) + '</div></div>'
        + '<div class="trk-calendar-detail-group"><div class="trk-calendar-detail-label">Time</div><div class="trk-calendar-detail-value">' + escapeHtml((event.start_time || "") + " - " + (event.end_time || "")) + '</div></div>'
      + '</div>'

      + (
        showWorker
          ? '<div class="trk-calendar-detail-group"><div class="trk-calendar-detail-label">Worker</div><div class="trk-calendar-detail-value">' + escapeHtml(workerValue) + '</div></div>'
          : ''
      )

      + (
        isPrivate
          ? ''
          : (
              '<div class="trk-calendar-form-row">'
                + '<div class="trk-calendar-detail-group"><div class="trk-calendar-detail-label">Type</div><div class="trk-calendar-detail-value">' + escapeHtml(event.type || "Session") + '</div></div>'
                + getSessionProgressDetailHtml(event)
              + '</div>'
              + getBookingWarningDetailHtml(event)
              + '<div class="trk-calendar-detail-group"><div class="trk-calendar-detail-label">Location</div><div class="trk-calendar-detail-value">' + escapeHtml(event.location || "Not set") + '</div></div>'
              + getGoogleMeetLinkDetailHtml(event)
            )
      )
      + actions;
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
      html += '<option'
        + ' value="' + escapeHtml(client.value) + '"'
        + ' data-therapy-location="' + escapeHtml(client.therapy_location || "") + '"'
        + ' data-therapy-location-label="' + escapeHtml(client.therapy_location_label || client.therapy_location || "") + '"'
        + ' data-client-type="' + escapeHtml(client.client_type || "") + '"'
        + '>'
        + escapeHtml(client.label)
        + '</option>';
    });

    select.innerHTML = html;
    renderParentContactOptions();
    syncParentCheckInAvailability();
  }

  function renderParentContactOptions() {
    const select = document.getElementById("trkCalendarParentContactSelect");
    if (!select) return;

    const clientId = getValue("trkCalendarClientSelect");
    const client = state.clients.find(function (row) {
      return row.value === clientId;
    });

    const contacts = client && Array.isArray(client.contacts) ? client.contacts : [];

    let html = '<option value="">Select parent/contact</option>';

    contacts.forEach(function (contact) {
      html += '<option value="' + escapeHtml(contact.value || "") + '">'
        + escapeHtml(contact.label || contact.value || "")
        + '</option>';
    });

    select.innerHTML = html;
  }

  function renderSchoolOptions() {
    const select = document.getElementById("trkCalendarSchoolSelect");
    if (!select) return;

    const type = getValue("trkCalendarType") || "Therapy Session";
    const isCompany = type === "Company Meeting" || type === "Company Session";
    const options = isCompany ? state.companies : state.schools;
    const noun = isCompany ? "company" : "school";

    const selectLabel = document.querySelector('label[for="trkCalendarSchoolSelect"]');
    if (selectLabel) selectLabel.textContent = isCompany ? "Company" : "School";

    const manualLabel = document.querySelector('label[for="trkCalendarSchoolManualName"]');
    if (manualLabel) manualLabel.textContent = "Or type " + noun + " name";

    const manualInput = document.getElementById("trkCalendarSchoolManualName");
    if (manualInput) manualInput.placeholder = "Enter " + noun + " name if not listed";

    let html = '<option value="">Select existing ' + noun + '</option>';

    options.forEach(function (option) {
      html += '<option'
        + ' value="' + escapeHtml(option.value || "") + '"'
        + ' data-location="' + escapeHtml(option.location || "") + '"'
        + '>'
        + escapeHtml(option.label || option.value || "")
        + '</option>';
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
    const type = getValue("trkCalendarType") || "Therapy Session";

    const clientId = getValue("trkCalendarClientSelect");
    const clientName = getSelectedText("trkCalendarClientSelect");
    const parentContact = getValue("trkCalendarParentContactSelect");
    const leadName = getValue("trkCalendarLeadName");
    const itemName = getValue("trkCalendarItemName");
    const schoolId = getValue("trkCalendarSchoolSelect");
    const schoolManualName = getValue("trkCalendarSchoolManualName");
    const schoolName = schoolId ? getSelectedText("trkCalendarSchoolSelect") : schoolManualName;

    const date = getValue("trkCalendarDate");
    const time = getValue("trkCalendarTime");
    const fromDate = getValue("trkCalendarFromDate");
    const toDate = getValue("trkCalendarToDate");

    const duration = String(getBookingDurationMinutes(type));
    const locationType = getValue("trkCalendarLocationType") || "client_default";
    const googleMeet = isChecked("trkCalendarGoogleMeet") ? "1" : "0";
    const travelCharged = isChecked("trkCalendarTravelChargedSingle") ? "1" : "0";
    const phone = getValue("trkCalendarPhone");
    const notes = getValue("trkCalendarNotes");

    let location = "";

    if (locationType === "online") {
      location = "Online";
    } else if (locationType === "telephone") {
      location = phone ? "Telephone: " + phone : "Telephone";
    } else if (locationType === "home") {
      location = "Home";
    } else if (locationType === "school") {
      location = getSelectedSchoolLocation() || "School";
    } else if (locationType === "manual") {
      location = getValue("trkCalendarLocation");
    }

    if (CLIENT_REQUIRED_TYPES.indexOf(type) !== -1 && !clientId) {
      showToast("Please select a client");
      return;
    }

    if (type === "Initial Consultation" && !leadName) {
      showToast("Please enter the person's name");
      return;
    }

    if (NON_CLIENT_TITLE_TYPES.indexOf(type) !== -1 && !itemName) {
      showToast("Please enter a title");
      return;
    }

    const isSchoolVisit = SCHOOL_LINKED_TYPES.indexOf(type) !== -1;
    if (isSchoolVisit && !schoolId && !schoolManualName) {
      showToast("Please select a school or type the school / company name");
      return;
    }

    if (type === "Holiday") {
      if (!fromDate || !toDate) {
        showToast("Please select from and to dates");
        return;
      }
    } else if (!date || !time) {
      showToast("Please select date and time");
      return;
    } else {
      const endTime = getValue("trkCalendarEndTime");
      if (!endTime) {
        showToast("Please select an end time");
        return;
      }
      if (timeToMinutes(endTime) <= timeToMinutes(time)) {
        showToast("End time must be after the start time");
        return;
      }
    }

    setButtonLoading("trkCalendarSaveBtn", true, "Saving...");
    hideNoBalanceNotice();
    hideConflictNotice();

    apiPost(SHARED_API + ".create_booking", {
      dashboard_type: state.dashboardType,
      client: clientId,
      client_name: clientName,
      parent_contact: parentContact,
      lead_name: leadName,
      client_lead: state.pendingClientLead || "",
      item_name: itemName,
      school: schoolId,
      school_name: schoolName,
      school_manual_name: schoolManualName,
      booking_date: date,
      booking_time: time,
      from_date: fromDate,
      to_date: toDate,
      duration_minutes: duration,
      appointment_type: type,
      billing_type: DEFAULT_BILLING_BY_TYPE[type] || "Non-Billable",
      travel_charged: travelCharged,
      location_type: locationType,
      location: location,
      phone: phone,
      google_meet: googleMeet,
      recurring: isChecked("trkCalendarRecurring") ? "1" : "0",
      recurring_frequency: getValue("trkCalendarRecurringFrequency"),
      recurring_count: getValue("trkCalendarRecurringCount"),
      occurrence_overrides: JSON.stringify(getRecurringOccurrenceOverrides() || []),
      notes: notes,
      additional_workers: (function () {
        var checked = document.querySelectorAll("#trkCalendarAdditionalWorkersList input[type='checkbox']:checked");
        return JSON.stringify(Array.prototype.map.call(checked, function (cb) { return cb.dataset.workerValue; }));
      })(),
      allow_double_booking: state.allowDoubleBooking ? "1" : "0"
    }).then(function () {
      setButtonLoading("trkCalendarSaveBtn", false, "Save Calendar Item");
      state.allowDoubleBooking = false;
      closeBookingModal();
      showToast(type === "Therapy Session" ? "Session booked" : "Calendar item added");
      loadCalendarData();
    }).catch(function (error) {
      console.error("Save calendar item failed:", error);

      setButtonLoading("trkCalendarSaveBtn", false, "Save Calendar Item");
      showToast(error.message || "Could not save calendar item");
      showNoBalanceNoticeIfApplicable(error.message || "", clientId || schoolId);
      showConflictNoticeIfApplicable(error.message || "");
    });
  }

  // The exact wording here is this app's own (see the two
  // "already has something booked" frappe.throw() calls in
  // _create_booking_impl), so it's safe to match precisely.
  function showConflictNoticeIfApplicable(errorMessage) {
    const notice = document.getElementById("trkCalendarConflictNotice");
    const messageEl = document.getElementById("trkCalendarConflictMessage");
    if (!notice || !messageEl) return;

    if (errorMessage.indexOf("already has something booked") === -1) {
      notice.style.display = "none";
      return;
    }

    messageEl.textContent = errorMessage;
    notice.style.display = "";
  }

  function hideConflictNotice() {
    const notice = document.getElementById("trkCalendarConflictNotice");
    if (notice) notice.style.display = "none";
  }

  // Package Booking Validation (a Frappe Server Script, not something in
  // this app's own code) blocks the booking outright when a client has no
  // sessions left on their pack, rather than an ordinary validation error -
  // "balance" is the one word that's a safe bet to appear in its message
  // regardless of the exact wording, since every other booking failure
  // (missing fields, a time conflict) is about something else entirely.
  function showNoBalanceNoticeIfApplicable(errorMessage, clientId) {
    const notice = document.getElementById("trkCalendarNoBalanceNotice");
    const messageEl = document.getElementById("trkCalendarNoBalanceMessage");
    const link = document.getElementById("trkCalendarNoBalanceInvoiceLink");
    if (!notice || !messageEl || !link) return;

    const invoiceUrl = getInvoiceUrlForClient(clientId);

    if (!invoiceUrl || !/balance/i.test(errorMessage)) {
      notice.style.display = "none";
      return;
    }

    messageEl.textContent = errorMessage;
    link.href = invoiceUrl;
    notice.style.display = "";
  }

  function hideNoBalanceNotice() {
    const notice = document.getElementById("trkCalendarNoBalanceNotice");
    if (notice) notice.style.display = "none";
  }

  function getInvoiceUrlForClient(clientId) {
    if (!clientId) return "";
    if (state.dashboardType === "coach") return "/coach_db/invoice_details?new=1&client=" + encodeURIComponent(clientId);
    if (state.dashboardType === "franchisor") return "/franchisor_db/invoice_details?new=1&client=" + encodeURIComponent(clientId);
    return "";
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

    const location = resolveEditLocation();

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

    var linkClient = getValue("trkEditClient") || "";

    apiPost(SHARED_API + ".update_session", {
      dashboard_type: state.dashboardType,
      event: eventName,
      booking_date: bookingDate,
      booking_time: bookingTime,
      status: status,
      appointment_type: appointmentType,
      billing_type: billingType,
      travel_charged: travelCharged,
      location: location,
      link_client: linkClient
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

  function autoOpenBookingFromClient() {
    if (!state.autoOpenBookingClient) return;

    const clientToBook = state.autoOpenBookingClient;
    state.autoOpenBookingClient = "";

    openBookingModal(formatDateKey(state.currentDate), "09:00", clientToBook);
  }

  function autoOpenBookingFromLead() {
    if (!state.autoOpenBookingLead) return;

    const leadToBook = state.autoOpenBookingLead;
    const leadName = state.autoOpenBookingLeadName;
    state.autoOpenBookingLead = "";
    state.autoOpenBookingLeadName = "";

    openBookingModal(formatDateKey(state.currentDate), "09:00", "", {
      appointmentType: "Initial Consultation",
      clientLead: leadToBook,
      leadName: leadName
    });
  }

  function openBookingModal(dateStr, timeStr, clientName, options) {
    options = options || {};
    state.allowDoubleBooking = false;

    setValue("trkCalendarClientSelect", clientName || "");
    setValue("trkCalendarParentContactSelect", "");
    setValue("trkCalendarLeadName", options.leadName || "");
    setValue("trkCalendarItemName", "");
    setValue("trkCalendarSchoolSelect", "");
    setValue("trkCalendarSchoolManualName", "");

    setValue("trkCalendarDate", dateStr || "");
    setValue("trkCalendarTime", timeStr || "");
    setValue("trkCalendarFromDate", dateStr || "");
    setValue("trkCalendarToDate", dateStr || "");

    setValue("trkCalendarType", options.appointmentType || "Therapy Session");
    setValue(
      "trkCalendarEndTime",
      addMinutesToTimeString(timeStr || "09:00", DURATION_BY_TYPE[options.appointmentType] || 45)
    );
    setValue("trkCalendarLocationType", "client_default");
    setValue("trkCalendarLocation", "");
    setValue("trkCalendarPhone", "");
    setChecked("trkCalendarTravelChargedSingle", false);
    setChecked("trkCalendarGoogleMeet", false);
    setChecked("trkCalendarRecurring", false);
    setValue("trkCalendarRecurringFrequency", "Weekly");
    setValue("trkCalendarRecurringCount", "4");
    setValue("trkCalendarNotes", "");

    state.pendingClientLead = options.clientLead || "";

    if (clientName) {
      const clientSelect = document.getElementById("trkCalendarClientSelect");

      if (clientSelect && clientSelect.value !== clientName) {
        const option = document.createElement("option");
        option.value = clientName;
        option.textContent = clientName;
        option.selected = true;
        clientSelect.appendChild(option);
        clientSelect.value = clientName;
      }
    }

    renderParentContactOptions();
    syncBookingFields();
    hideNoBalanceNotice();
    hideConflictNotice();
    toggleModal("trkCalendarModal", true);
  }

  function closeBookingModal() {
    toggleModal("trkCalendarModal", false);
    hideNoBalanceNotice();
    hideConflictNotice();
    state.allowDoubleBooking = false;
    var listEl = document.getElementById("trkCalendarAdditionalWorkersList");
    if (listEl) listEl.innerHTML = "";
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
    updateDatePickerDisplay("trkEditDate", "trkEditDateDisplay");
    setValue("trkEditTime", event.start_time || "");
    setValue("trkEditStatus", event.ui_status || "Booked");
    setValue("trkEditType", event.type || "Therapy Session");
    setValue("trkEditBillingType", event.billing_type || "");
    setValue("trkEditTravelCharged", String(Number(event.travel_charged || 0)));
    setValue("trkEditTravelChargedSingle", String(Number(event.travel_charged || 0)));
    applyLocationToEditForm(event.location || "");

    var linkingRow = document.getElementById("trkEditLinkingRow");
    var linkClientSelect = document.getElementById("trkEditClient");

    if (event.needs_linking && linkingRow && linkClientSelect) {
      var options = '<option value="">— Select client —</option>';
      state.clients.forEach(function (c) {
        options += '<option value="' + escapeHtml(c.value || "") + '">' + escapeHtml(c.label || c.value || "") + '</option>';
      });
      linkClientSelect.innerHTML = options;
      linkClientSelect.value = "";
      linkingRow.style.display = "";
    } else if (linkingRow) {
      linkingRow.style.display = "none";
    }

    try { syncEditFields(); } catch (e) { console.error("syncEditFields error:", e); }
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
    updateDatePickerDisplay("trkNoteSessionDate", "trkNoteSessionDateDisplay");
    setValue("trkNoteSessionType", mapAppointmentTypeToClientNoteType(event.type || ""));
    setValue("trkNoteText", "");

    toggleModal("trkCalendarNoteModal", true);
  }

  function closeNoteModal() {
    toggleModal("trkCalendarNoteModal", false);
  }

  function renderRecurringPreview() {
    const wrap = document.getElementById("trkCalendarRecurringPreviewWrap");
    const list = document.getElementById("trkCalendarRecurringPreviewList");
    if (!wrap || !list) return;

    const type = getValue("trkCalendarType") || "Therapy Session";
    const count = parseInt(getValue("trkCalendarRecurringCount") || "1", 10) || 1;
    const isRecurring = RECURRING_ALLOWED_TYPES.includes(type) && isChecked("trkCalendarRecurring") && count > 1;

    const baseDateKey = getValue("trkCalendarDate");
    const baseTime = getValue("trkCalendarTime");
    const baseDateObj = baseDateKey ? parseDateKey(baseDateKey) : null;

    if (!isRecurring || !baseDateObj || !baseTime) {
      wrap.style.display = "none";
      list.innerHTML = "";
      return;
    }

    // Preserve dates/times the coach has genuinely adjusted by hand, but
    // only those - previously ANY existing value (even ones nobody touched,
    // just auto-computed from a stale frequency) was kept as-is, which meant
    // switching Weekly -> Fortnightly/Monthly silently had no visible effect
    // since every row's old date always "won" over the freshly computed one.
    const existingRows = list.querySelectorAll("[data-occurrence-index]");
    const existingValues = {};
    existingRows.forEach(function (row) {
      const index = row.dataset.occurrenceIndex;
      const dateField = row.querySelector("[data-occurrence-date]");
      const timeField = row.querySelector("[data-occurrence-time]");
      existingValues[index] = {
        date: dateField ? dateField.value : "",
        time: timeField ? timeField.value : "",
        userEdited: row.dataset.userEdited === "1"
      };
    });

    const frequency = getValue("trkCalendarRecurringFrequency") || "Weekly";
    let html = "";

    for (let index = 0; index < count; index++) {
      let occurrenceDate = baseDateObj;

      if (index) {
        if (frequency === "Fortnightly") {
          occurrenceDate = addDays(baseDateObj, 14 * index);
        } else if (frequency === "Monthly") {
          occurrenceDate = addMonths(baseDateObj, index);
        } else {
          occurrenceDate = addDays(baseDateObj, 7 * index);
        }
      }

      const previous = existingValues[String(index)];
      const isUserEdited = !!(previous && previous.userEdited);
      const dateValue = isUserEdited && previous.date ? previous.date : formatDateKey(occurrenceDate);
      const timeValue = isUserEdited && previous.time ? previous.time : baseTime;

      html += '<div class="trk-recurring-preview-row" data-occurrence-index="' + index + '"'
        + (isUserEdited ? ' data-user-edited="1"' : '') + '>'
        + '<span class="trk-recurring-preview-index">' + (index + 1) + '</span>'
        + '<input type="date" class="dashboard-input" data-occurrence-date value="' + escapeHtml(dateValue) + '">'
        + '<input type="time" class="dashboard-input" data-occurrence-time value="' + escapeHtml(timeValue) + '">'
        + '</div>';
    }

    list.innerHTML = html;
    wrap.style.display = "";
  }

  function getRecurringOccurrenceOverrides() {
    const wrap = document.getElementById("trkCalendarRecurringPreviewWrap");
    const list = document.getElementById("trkCalendarRecurringPreviewList");
    if (!wrap || !list || wrap.style.display === "none") return null;

    const rows = Array.from(list.querySelectorAll("[data-occurrence-index]"));
    if (!rows.length) return null;

    return rows.map(function (row) {
      // Only send a date/time override for occurrences the coach actually
      // hand-edited - the backend already computes correct weekly/
      // fortnightly/monthly dates itself, and previously this sent the
      // preview's displayed value for every occurrence unconditionally,
      // which silently overrode that server-side math with whatever the
      // (buggy, stale) preview happened to be showing at submit time.
      if (row.dataset.userEdited !== "1") {
        return { date: "", time: "" };
      }

      return {
        date: row.querySelector("[data-occurrence-date]")?.value || "",
        time: row.querySelector("[data-occurrence-time]")?.value || ""
      };
    });
  }

  // Parent Check-In means "check in with the parent/carer" - meaningless
  // for an Adult client, who has no parent in that sense. Disables/hides
  // the option once an Adult client is selected, and bumps the type
  // selection off it if it was already chosen, rather than letting one get
  // booked that never made sense in the first place.
  function syncParentCheckInAvailability() {
    const typeSelect = document.getElementById("trkCalendarType");
    if (!typeSelect) return;

    const option = Array.prototype.find.call(typeSelect.options, function (opt) {
      return opt.value === "Parent Check-In";
    });
    if (!option) return;

    const clientSelect = document.getElementById("trkCalendarClientSelect");
    const selectedOption = clientSelect && clientSelect.selectedIndex >= 0
      ? clientSelect.options[clientSelect.selectedIndex]
      : null;
    const clientType = selectedOption ? (selectedOption.getAttribute("data-client-type") || "") : "";
    const isAdult = clientType === "Adult";

    option.disabled = isAdult;
    option.hidden = isAdult;

    if (isAdult && typeSelect.value === "Parent Check-In") {
      typeSelect.value = "Therapy Session";
      showToast("Parent Check-In isn't available for an adult client - switched to Therapy Session.");
    }
  }

  function syncBookingFields() {
    syncParentCheckInAvailability();

    const type = getValue("trkCalendarType") || "Therapy Session";
    const isHoliday = type === "Holiday";
    const isClientType = CLIENT_REQUIRED_TYPES.indexOf(type) !== -1;
    const isParentCheckIn = type === "Parent Check-In";
    const isInitialConsultation = type === "Initial Consultation";
    const isSchoolVisit = SCHOOL_LINKED_TYPES.indexOf(type) !== -1;
    const isNamedItem = NON_CLIENT_TITLE_TYPES.indexOf(type) !== -1;

    toggleDisplay("trkCalendarClientRow", isClientType);
    toggleDisplay("trkCalendarParentContactRow", false);
    toggleDisplay("trkCalendarLeadNameRow", isInitialConsultation);
    if (isInitialConsultation) {
      toggleDisplay("trkCalendarClientRow", false);
      toggleDisplay("trkCalendarLeadNameRow", true);
      toggleDisplay("trkCalendarLocationTypeInlineRow", true);

      if (!getValue("trkCalendarLocationType") || getValue("trkCalendarLocationType") === "client_default") {
        setValue("trkCalendarLocationType", "online");
      }
    }
    toggleDisplay("trkCalendarItemNameRow", isNamedItem);
    toggleDisplay("trkCalendarSchoolRow", isSchoolVisit);
    toggleDisplay("trkCalendarSchoolManualRow", isSchoolVisit);

    toggleDisplay("trkCalendarSingleDateTimeRow", !isHoliday);
    toggleDisplay("trkCalendarHolidayDateRow", isHoliday);
    toggleDisplay("trkCalendarDurationRow", !isHoliday);

    toggleDisplay("trkCalendarTravelRow", ["Therapy Session", "Parent Check-In"].concat(SCHOOL_LINKED_TYPES).indexOf(type) !== -1);
    toggleDisplay("trkCalendarGoogleMeetRow", GOOGLE_MEET_TYPES.indexOf(type) !== -1);
    toggleDisplay("trkCalendarRecurringRow", RECURRING_ALLOWED_TYPES.includes(type));

    var additionalWorkerTypes = ["Internal Training", "Company Meeting", "School Visit", "Event / Stall"];
    var showWorkers = additionalWorkerTypes.indexOf(type) !== -1;
    toggleDisplay("trkCalendarAdditionalWorkersRow", showWorkers);
    if (showWorkers) {
      var listEl = document.getElementById("trkCalendarAdditionalWorkersList");
      if (listEl && listEl.childElementCount === 0) {
        var opts = state.additionalWorkerOptions.filter(function (o) {
          return o.value;
        });
        if (opts.length === 0) {
          listEl.innerHTML = '<span style="font-size:12px;color:#888;">No other coaches available</span>';
        } else {
          listEl.innerHTML = opts.map(function (o) {
            var id = "trkWorkerChk_" + o.value.replace(/[^a-zA-Z0-9]/g, "_");
            return '<label style="display:flex;align-items:center;gap:8px;font-size:13px;cursor:pointer;">'
              + '<input type="checkbox" data-worker-value="' + escapeHtml(o.value) + '" id="' + escapeHtml(id) + '">'
              + escapeHtml(o.label || o.value)
              + '</label>';
          }).join("");
        }
      }
    }
    
    const showRecurringOptions = RECURRING_ALLOWED_TYPES.includes(type) && isChecked("trkCalendarRecurring");
    toggleDisplay("trkCalendarRecurringOptions", showRecurringOptions);
    renderRecurringPreview();

    const locationTypeSelect = document.getElementById("trkCalendarLocationType");
    const clientSelect = document.getElementById("trkCalendarClientSelect");
    const selectedClientOption = clientSelect && clientSelect.selectedIndex >= 0
      ? clientSelect.options[clientSelect.selectedIndex]
      : null;

    if (locationTypeSelect) {
      const clientDefaultOption = locationTypeSelect.querySelector('option[value="client_default"]');
      const schoolOption = locationTypeSelect.querySelector('option[value="school"]');
      const locationLabel = selectedClientOption
        ? selectedClientOption.dataset.therapyLocationLabel || ""
        : "";

      if (clientDefaultOption) {
        clientDefaultOption.textContent = locationLabel
          ? locationLabel
          : "Main Therapy Location";

        clientDefaultOption.style.display = isClientType ? "" : "none";
      }

      if (schoolOption) {
        schoolOption.style.display = isSchoolVisit ? "" : "none";
      }

      if (!isClientType && getValue("trkCalendarLocationType") === "client_default") {
        setValue("trkCalendarLocationType", isSchoolVisit ? "school" : "manual");
      }

      if (!isSchoolVisit && getValue("trkCalendarLocationType") === "school") {
        setValue("trkCalendarLocationType", "manual");
      }

      if ((isInitialConsultation || isParentCheckIn) && getValue("trkCalendarLocationType") === "client_default") {
        setValue("trkCalendarLocationType", "online");
      }
    }

    const locationType = getValue("trkCalendarLocationType") || "manual";
    const googleMeet = isChecked("trkCalendarGoogleMeet");
    if (type === "Therapy Session") {
      toggleDisplay("trkCalendarRecurringOptions", isChecked("trkCalendarRecurring"));
    }

    if (googleMeet && GOOGLE_MEET_TYPES.indexOf(type) !== -1) {
      setValue("trkCalendarLocationType", "online");
    }

    toggleDisplay("trkCalendarPhoneRow", getValue("trkCalendarLocationType") === "telephone");
    toggleDisplay("trkCalendarLocationTypeInlineRow", !isHoliday);
    toggleDisplay("trkCalendarLocationManualRow", ["manual"].indexOf(getValue("trkCalendarLocationType")) !== -1);

    const startTimeForDuration = getValue("trkCalendarTime");
    if (startTimeForDuration && getBookingDurationMinutes(type) === 45) {
      if (type === "Parent Check-In") {
        setValue("trkCalendarEndTime", addMinutesToTimeString(startTimeForDuration, 30));
      } else if (type === "Initial Consultation") {
        setValue("trkCalendarEndTime", addMinutesToTimeString(startTimeForDuration, 60));
      }
    }

    if (isHoliday) {
      setChecked("trkCalendarGoogleMeet", false);
      setChecked("trkCalendarTravelChargedSingle", false);
    }

    if (isSchoolVisit && getValue("trkCalendarLocationType") === "school") {
      const schoolLocation = getSelectedSchoolLocation();
      if (schoolLocation) {
        setValue("trkCalendarLocation", schoolLocation);
      }
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

  // Reuses the exact same location-type -> text convention the booking
  // modal already saves with ("Online", "Telephone: X"/"Telephone", "Home",
  // otherwise a manual location) so editing round-trips correctly, and lets
  // a coach pick a different type for an appointment already booked rather
  // than only being able to retype the free-text location.
  function deriveLocationType(locationText) {
    const text = (locationText || "").trim();

    if (text === "Online") return { type: "online", manual: "", phone: "" };
    if (/^Telephone/.test(text)) {
      const match = /^Telephone:\s*(.*)$/.exec(text);
      return { type: "telephone", manual: "", phone: match ? match[1] : "" };
    }
    if (text === "Home") return { type: "home", manual: "", phone: "" };

    return { type: "manual", manual: text, phone: "" };
  }

  function applyLocationToEditForm(locationText) {
    const derived = deriveLocationType(locationText);
    setValue("trkEditLocationType", derived.type);
    setValue("trkEditLocation", derived.manual);
    setValue("trkEditPhone", derived.phone);
    syncEditLocationFields();
  }

  function syncEditLocationFields() {
    const locationType = getValue("trkEditLocationType") || "manual";
    toggleDisplay("trkEditPhoneRow", locationType === "telephone");
    toggleDisplay("trkEditLocationManualRow", locationType === "manual");
  }

  function resolveEditLocation() {
    const locationType = getValue("trkEditLocationType") || "manual";
    const phone = getValue("trkEditPhone");

    if (locationType === "online") return "Online";
    if (locationType === "telephone") return phone ? "Telephone: " + phone : "Telephone";
    if (locationType === "home") return "Home";
    return getValue("trkEditLocation");
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

    function isChecked(id) {
    const node = document.getElementById(id);
    return !!(node && node.checked);
  }

  function setChecked(id, checked) {
    const node = document.getElementById(id);
    if (node) node.checked = !!checked;
  }

  function getSelectedSchoolLocation() {
    const select = document.getElementById("trkCalendarSchoolSelect");
    if (!select || select.selectedIndex < 0) return "";

    const option = select.options[select.selectedIndex];
    return option ? (option.dataset.location || "") : "";
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

  function applyEventTypeStyle(node, type, status) {
    const style = TYPE_STYLES[type] || TYPE_STYLES["General"];
    const cleanStatus = status || "";

    node.style.background = style.background;
    node.style.borderLeft = "4px solid " + style.border;
    node.style.color = style.textColor || "#FFFFFF";
    node.style.opacity = "1";
    node.style.textDecoration = "none";

    if (cleanStatus === "Attended") {
      node.style.opacity = "0.65";
    }

    if (cleanStatus === "Cancelled") {
      node.style.background = "#F2F8F8";
      node.style.borderLeft = "4px solid #839898";
      node.style.color = "#434B49";
      node.style.textDecoration = "line-through";
    }

    if (cleanStatus === "No Show") {
      node.style.borderLeft = "6px solid #FF8438";
    }

    if (cleanStatus === "Failed") {
      node.style.background = "#FDECEC";
      node.style.borderLeft = "4px solid #C0392B";
      node.style.color = "#7A1E1E";
    }
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
    if (!event) return '<div class="trk-calendar-detail-group"><div class="trk-calendar-detail-label">Session Progress</div><div class="trk-calendar-detail-value">—</div></div>';

    const progressText = event.progress_text || "";
    const sessionNumber = Number(event.session_number || 0);
    const totalSessions = Number(event.total_sessions || 0);

    let label = "";

    if (progressText) {
      label = progressText;
    } else if (sessionNumber && totalSessions) {
      label = sessionNumber + " of " + totalSessions;
    }

    return '<div class="trk-calendar-detail-group">'
      + '<div class="trk-calendar-detail-label">Session Progress</div>'
      + '<div class="trk-calendar-detail-value">' + (label ? '<strong>Session ' + escapeHtml(label) + '</strong>' : '—') + '</div>'
      + '</div>';
  }

  function getBookingWarningDetailHtml(event) {
    if (!event || !event.booking_warning) return "";

    return '<div class="dashboard-notice" style="margin:10px 0 14px 0;background:#fff7ed;border-left:4px solid #ff8438;color:#7c2d12;">'
      + escapeHtml(event.booking_warning)
      + '</div>';
  }

  function getGoogleMeetLinkDetailHtml(event) {
    if (!event || !event.google_meet_link) return "";
    return '<div class="trk-calendar-detail-group">'
      + '<div class="trk-calendar-detail-label">Meeting Link</div>'
      + '<div class="trk-calendar-detail-value">'
      + '<a href="' + escapeHtml(event.google_meet_link) + '" target="_blank" rel="noopener">'
      + escapeHtml(event.google_meet_link)
      + '</a></div></div>';
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

  function addMonths(date, months) {
    const target = new Date(date.getFullYear(), date.getMonth() + months, 1);
    const daysInTargetMonth = new Date(target.getFullYear(), target.getMonth() + 1, 0).getDate();
    target.setDate(Math.min(date.getDate(), daysInTargetMonth));

    return stripTime(target);
  }

  function stripTime(date) {
    return new Date(date.getFullYear(), date.getMonth(), date.getDate());
  }

  function formatDisplayDate(date) {
    return date.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
  }

  function updateDatePickerDisplay(inputId, displayId) {
    // <input type="date"> renders its own text using the visitor's browser/
    // OS locale, not anything this code controls - this label guarantees
    // day/month/year regardless of what the native picker shows.
    const field = document.getElementById(inputId);
    const display = document.getElementById(displayId);
    if (!field || !display) return;

    const date = parseDateKey(field.value);
    display.textContent = date ? formatDisplayDate(date) : "";
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

  function addMinutesToTimeString(timeStr, minutes) {
    return minutesToTime(timeToMinutes(timeStr) + Number(minutes || 0));
  }

  // Falls back to the type's default length whenever start/end aren't both
  // set yet, or end isn't after start (e.g. mid-edit) - never lets a save
  // go through with a zero/negative duration.
  function getBookingDurationMinutes(type) {
    const start = getValue("trkCalendarTime");
    const end = getValue("trkCalendarEndTime");

    if (start && end) {
      const minutes = timeToMinutes(end) - timeToMinutes(start);
      if (minutes > 0) return minutes;
    }

    return DURATION_BY_TYPE[type] || 45;
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
