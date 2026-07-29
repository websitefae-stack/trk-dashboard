(function () {
  "use strict";

  const SHARED_API = "dashboard.api.shared.calendar";

  const state = {
    dashboardType: getDashboardType(),
    eventName: "",
    eventData: null,
    savingNote: false,
    savingEdit: false
  };

  function getDashboardType() {
    const path = window.location.pathname || "";
    if (path.indexOf("/coach_db/") !== -1) return "coach";
    if (path.indexOf("/franchisor_db/") !== -1) return "franchisor";
    return "session_worker";
  }

  var el = Dashboard.el;

  function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    if (meta && meta.content) return meta.content;

    const match = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  function getQueryParam(name) {
    const params = new URLSearchParams(window.location.search);
    return params.get(name) || "";
  }

  function getViewModeParams() {
    const root = document.getElementById("sessionWorkerCalendarDetailsShell");
    const params = new URLSearchParams(window.location.search);
  
    return {
      isViewMode: root && String(root.dataset.viewMode || "0") === "1",
      viewAs: (root && root.dataset.viewAs) || params.get("view_as") || "",
      viewer: params.get("viewer") || ""
    };
  }
    
  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function formatDisplayDate(value) {
    if (!value) return "—";

    const datePart = String(value).slice(0, 10);
    const date = new Date(`${datePart}T00:00:00`);

    if (isNaN(date.getTime())) return escapeHtml(String(value));

    return escapeHtml(date.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" }));
  }

  async function apiGet(method, params) {
    const url = new URL("/api/method/" + method, window.location.origin);

    Object.keys(params || {}).forEach(function (key) {
      if (params[key] !== undefined && params[key] !== null && params[key] !== "") {
        url.searchParams.set(key, params[key]);
      }
    });

    const response = await fetch(url.toString(), {
      method: "GET",
      credentials: "same-origin",
      headers: { "Accept": "application/json" }
    });

    return handleApiResponse(response);
  }

  async function apiPost(method, payload) {
    const response = await fetch("/api/method/" + method, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-Frappe-CSRF-Token": getCsrfToken()
      },
      body: JSON.stringify(payload || {})
    });

    return handleApiResponse(response);
  }

  async function uploadFile(file) {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("is_private", 1);

    const response = await fetch("/api/method/upload_file", {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "X-Frappe-CSRF-Token": getCsrfToken()
      },
      body: formData
    });

    return handleApiResponse(response);
  }

  async function handleApiResponse(response) {
    let data = {};
    let text = "";

    try {
      text = await response.text();
      data = text ? JSON.parse(text) : {};
    } catch (error) {
      throw new Error("Could not read server response.");
    }

    if (!response.ok || data.exc) {
      throw new Error(getServerMessage(data) || data.message || data.exception || "Request failed.");
    }

    return data.message || {};
  }

  function getServerMessage(data) {
    if (!data) return "";

    if (typeof data._server_messages === "string" && data._server_messages) {
      try {
        const messages = JSON.parse(data._server_messages);
        if (!Array.isArray(messages) || !messages.length) return "";

        const first = JSON.parse(messages[0]);
        return first.message || "";
      } catch (error) {
        return "";
      }
    }

    if (typeof data.message === "string") return data.message;
    if (data.exception) return String(data.exception);

    return "";
  }

  function showNotice(message) {
    if (el("trkCalendarDetailsNotice")) {
      el("trkCalendarDetailsNotice").style.display = "";
      el("trkCalendarDetailsNotice").textContent = message || "";
    }

    if (el("trkCalendarDetailsContent")) {
      el("trkCalendarDetailsContent").style.display = "none";
    }
  }

  function showContent() {
    if (el("trkCalendarDetailsNotice")) {
      el("trkCalendarDetailsNotice").style.display = "none";
    }

    if (el("trkCalendarDetailsContent")) {
      el("trkCalendarDetailsContent").style.display = "";
    }
  }

  function setHtml(id, value) {
    const node = el(id);
    if (!node) return;
    node.innerHTML = value || "—";
  }

  function setValue(id, value) {
    const node = el(id);
    if (!node) return;
    node.value = value || "";
  }

  function getValue(id) {
    const node = el(id);
    return node ? node.value : "";
  }

  function badge(status) {
    const clean = status || "Booked";
    let cls = "dashboard-status-onhold";

    if (clean === "Attended") cls = "dashboard-status-active";
    if (clean === "Cancelled") cls = "dashboard-status-archived";
    if (clean === "No Show") cls = "dashboard-status-onhold";

    return '<span class="dashboard-badge ' + cls + '">' + escapeHtml(clean) + "</span>";
  }

  function yesNo(value) {
    return Number(value || 0) ? "Yes" : "No";
  }

  function getSessionProgressHtml(data) {
    if (!data) return "—";

    const progressText = data.progress_text || "";
    const sessionNumber = Number(data.session_number || 0);
    const totalSessions = Number(data.total_sessions || 0);

    let label = "";

    if (progressText) {
      label = progressText;
    } else if (sessionNumber && totalSessions) {
      label = sessionNumber + " of " + totalSessions;
    }

    if (!label) return "—";

    return "<strong>Session " + escapeHtml(label) + "</strong>";
  }

  function getBookingWarningHtml(data) {
    if (!data || !data.booking_warning) return "—";

    return '<div class="dashboard-notice" style="margin:0;background:#fff7ed;border-left:4px solid #ff8438;color:#7c2d12;">'
      + escapeHtml(data.booking_warning)
      + "</div>";
  }

  function renderGoogleMeetLink(link) {
    const locationNode = el("trkDetailLocation");
    if (!locationNode) return;

    let wrap = el("trkDetailGoogleMeetLinkWrap");

    if (!wrap) {
      wrap = document.createElement("div");
      wrap.id = "trkDetailGoogleMeetLinkWrap";
      wrap.className = "trk-calendar-detail-group";
      wrap.innerHTML =
        '<div class="trk-calendar-detail-label">Meeting Link</div>' +
        '<div class="trk-calendar-detail-value" id="trkDetailGoogleMeetLink">—</div>';

      const group = locationNode.closest(".trk-calendar-detail-group") || locationNode.parentElement;
      if (group && group.parentElement) {
        group.parentElement.insertBefore(wrap, group.nextSibling);
      }
    }

    const valueNode = el("trkDetailGoogleMeetLink");
    if (!valueNode) return;

    if (!link) {
      valueNode.innerHTML = "—";
      return;
    }

    valueNode.innerHTML = '<a href="' + escapeHtml(link) + '" target="_blank" rel="noopener">Open Google Meet</a>';
  }

  async function loadDetails() {
    state.eventName = getQueryParam("event") || getQueryParam("name");

    if (!state.eventName) {
      showNotice("No session was selected.");
      return;
    }

    showNotice("Loading session details...");

    try {
      const viewMode = getViewModeParams();

      const data = await apiGet(SHARED_API + ".get_event_details", {
        dashboard_type: state.dashboardType,
        event: state.eventName,
        view_as: viewMode.viewAs,
        viewer: viewMode.viewer
      });

      state.eventData = data;
      renderDetails(data);
      showContent();
    } catch (error) {
      console.error("Could not load session details", error);
      showNotice(error.message || "Could not load session details.");
    }
  }

  function getClientDetailsUrl(clientName) {
    const viewMode = getViewModeParams();

    if (state.dashboardType === "franchisor") {
      return "/franchisor_db/client_details?name=" + encodeURIComponent(clientName || "");
    }

    const params = new URLSearchParams();
    params.set("name", clientName || "");
    if (viewMode.viewAs) params.set("view_as", viewMode.viewAs);
    if (viewMode.viewer) params.set("viewer", viewMode.viewer);

    const base = state.dashboardType === "coach" ? "/coach_db" : "/session_worker_db";
    return base + "/client_details?" + params.toString();
  }

  function renderDetails(data) {
    if (data.client_name) {
      setHtml(
        "trkDetailClient",
        '<a href="' + escapeHtml(getClientDetailsUrl(data.client_name)) + '">'
          + escapeHtml(data.client_label || data.client_name)
          + '</a>'
      );
    } else {
      setHtml("trkDetailClient", escapeHtml(data.client_label || "—"));
    }
    setHtml("trkDetailType", escapeHtml(data.appointment_type || "—"));
    setHtml("trkDetailStatus", badge(data.ui_status || data.status || "Booked"));
    setHtml("trkDetailWorker", escapeHtml(data.worker_label || "—"));
    setHtml("trkDetailDate", escapeHtml(data.display_date || "—"));
    setHtml("trkDetailTime", escapeHtml(data.display_time || "—"));
    setHtml("trkDetailLocation", escapeHtml(data.location || "—"));
    renderGoogleMeetLink(data.google_meet_link || "");
    setHtml("trkDetailRecordId", escapeHtml(data.name || state.eventName || "—"));
    setHtml("trkDetailBillingType", escapeHtml(data.billing_type || "—"));
    setHtml("trkDetailTravelCharged", escapeHtml(yesNo(data.travel_charged)));
    setHtml("trkDetailSessionProgress", getSessionProgressHtml(data));
    setHtml("trkDetailBookingWarning", getBookingWarningHtml(data));

    const emailBtn = el("trkDetailEmailBtn");
    if (emailBtn) emailBtn.style.display = data.client_name ? "" : "none";

    setValue("trkClientNoteSessionDate", data.session_date || "");
    updateNoteDateDisplay();
    setValue("trkClientNoteSessionType", mapAppointmentTypeToClientNoteType(data.appointment_type || ""));

    renderClientNotes(data.client_notes || []);
  }

  function renderClientNotes(notes) {
    const wrap = el("trkClientNotesHistory");
    if (!wrap) return;

    if (!notes.length) {
      wrap.innerHTML = '<div class="dashboard-empty">No client notes found.</div>';
      return;
    }

    wrap.innerHTML =
      '<div class="dashboard-table-wrap">'
      + '<table class="dashboard-table calendar-client-notes-table">'
      + '<thead><tr><th>Date</th><th>User</th><th>Note</th><th>Attachment</th></tr></thead>'
      + '<tbody>'
      + notes.map(function (note) {
        const noteUser = note.note_user_name || note.note_user || "—";
        const attachment = note.attachement
          ? '<a href="' + escapeHtml(note.attachement) + '" target="_blank" rel="noopener noreferrer">View</a>'
          : "—";

        return '<tr>'
          + '<td>' + formatDisplayDate(note.session_date) + '</td>'
          + '<td>' + escapeHtml(noteUser) + '</td>'
          + '<td>' + escapeHtml(note.notes || "—") + '</td>'
          + '<td>' + attachment + '</td>'
          + '</tr>';
      }).join("")
      + '</tbody></table></div>';
  }

  function mapAppointmentTypeToClientNoteType(type) {
    if (type === "Initial Consultation") return "Initial Consultation";
    if (type === "Parent Check-In") return "Parent Feedback";
    if (type === "Therapy Session") return "Coaching Session";
    return "Other";
  }

  function openEditModal() {
    const data = state.eventData;
    if (!data) return;

    setValue("trkDetailEditEventName", data.name || state.eventName);
    setValue("trkDetailEditDate", data.session_date || "");
    updateEditDateDisplay();
    setValue("trkDetailEditTime", data.start_time || "");
    setValue("trkDetailEditStatus", data.ui_status || "Booked");
    setValue("trkDetailEditType", data.appointment_type || "Therapy Session");
    setValue("trkDetailEditBillingType", data.billing_type || "");
    setValue("trkDetailEditTravelCharged", String(Number(data.travel_charged || 0)));
    setValue("trkDetailEditTravelChargedSolo", String(Number(data.travel_charged || 0)));
    applyLocationToEditForm(data.location || "");

    syncEditFields();
    toggleModal(true);
  }

  function closeEditModal() {
    toggleModal(false);
  }

  function getCalendarListUrl() {
    const base = state.dashboardType === "coach"
      ? "/coach_db/calendar"
      : state.dashboardType === "franchisor"
        ? "/franchisor_db/calendar"
        : "/session_worker_db/calendar";

    const viewMode = getViewModeParams();
    const params = new URLSearchParams();
    if (viewMode.viewAs) params.set("view_as", viewMode.viewAs);
    if (viewMode.viewer) params.set("viewer", viewMode.viewer);

    const qs = params.toString();
    return qs ? base + "?" + qs : base;
  }

  async function deleteSession() {
    const data = state.eventData;
    const eventName = (data && data.name) || state.eventName;
    if (!eventName) return;

    const label = (data && (data.client_label || data.client_name)) || "this appointment";
    if (!window.confirm("Delete " + label + "? This cannot be undone, and will also remove it from Google Calendar if it was synced.")) {
      return;
    }

    const button = el("trkDetailDeleteBtn");
    if (button) {
      button.disabled = true;
      button.textContent = "Deleting...";
    }

    try {
      await apiPost(SHARED_API + ".delete_session", {
        dashboard_type: state.dashboardType,
        event: eventName
      });

      window.location.href = getCalendarListUrl();
    } catch (error) {
      console.error("Could not delete appointment", error);
      alert(error.message || "Could not delete appointment.");

      if (button) {
        button.disabled = false;
        button.textContent = "Delete Appointment";
      }
    }
  }

  function toggleModal(show) {
    const modal = el("trkDetailEditModal");
    if (!modal) return;
    modal.classList.toggle("show", !!show);
  }

  function syncEditFields() {
    const type = getValue("trkDetailEditType");
    const isGeneral = type === "General";

    if (el("trkDetailEditBillingTypeRow")) {
      el("trkDetailEditBillingTypeRow").style.display = isGeneral ? "" : "none";
    }

    if (el("trkDetailEditTravelOnlyRow")) {
      el("trkDetailEditTravelOnlyRow").style.display = isGeneral ? "none" : "";
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
    setValue("trkDetailEditLocationType", derived.type);
    setValue("trkDetailEditLocation", derived.manual);
    setValue("trkDetailEditPhone", derived.phone);
    syncEditLocationFields();
  }

  function syncEditLocationFields() {
    const locationType = getValue("trkDetailEditLocationType") || "manual";

    if (el("trkDetailEditPhoneRow")) {
      el("trkDetailEditPhoneRow").style.display = locationType === "telephone" ? "" : "none";
    }

    if (el("trkDetailEditLocationManualRow")) {
      el("trkDetailEditLocationManualRow").style.display = locationType === "manual" ? "" : "none";
    }
  }

  function resolveEditLocation() {
    const locationType = getValue("trkDetailEditLocationType") || "manual";
    const phone = getValue("trkDetailEditPhone");

    if (locationType === "online") return "Online";
    if (locationType === "telephone") return phone ? "Telephone: " + phone : "Telephone";
    if (locationType === "home") return "Home";
    return getValue("trkDetailEditLocation");
  }

  async function saveEdit() {
    if (state.savingEdit) return;

    const eventName = getValue("trkDetailEditEventName");
    const bookingDate = getValue("trkDetailEditDate");
    const bookingTime = getValue("trkDetailEditTime");
    const status = getValue("trkDetailEditStatus");
    const appointmentType = getValue("trkDetailEditType");

    const billingType = appointmentType === "General"
      ? getValue("trkDetailEditBillingType")
      : "";

    const travelCharged = appointmentType === "General"
      ? getValue("trkDetailEditTravelCharged")
      : getValue("trkDetailEditTravelChargedSolo");

    const location = resolveEditLocation();

    if (!eventName || !bookingDate || !bookingTime) {
      alert("Please complete the required fields.");
      return;
    }

    state.savingEdit = true;

    const button = el("trkDetailEditSaveBtn");
    if (button) {
      button.disabled = true;
      button.textContent = "Saving...";
    }

    try {
      await apiPost(SHARED_API + ".update_session", {
        dashboard_type: state.dashboardType,
        event: eventName,
        booking_date: bookingDate,
        booking_time: bookingTime,
        status: status,
        appointment_type: appointmentType,
        billing_type: billingType,
        travel_charged: travelCharged,
        location: location
      });

      closeEditModal();
      await loadDetails();
    } catch (error) {
      console.error("Could not save session", error);
      alert(error.message || "Could not save session.");
    } finally {
      state.savingEdit = false;

      if (button) {
        button.disabled = false;
        button.textContent = "Save Changes";
      }
    }
  }

  async function saveClientNote() {
    if (state.savingNote) return;

    const data = state.eventData;
    if (!data) return;

    const sessionDate = getValue("trkClientNoteSessionDate") || data.session_date || "";
    const sessionType = getValue("trkClientNoteSessionType") || mapAppointmentTypeToClientNoteType(data.appointment_type || "");
    const notes = getValue("trkClientNoteText").trim();
    const fileInput = el("trkClientNoteFile");
    const file = fileInput && fileInput.files && fileInput.files[0];

    if (!notes) {
      alert("Please enter a note.");
      return;
    }

    state.savingNote = true;

    const button = el("trkSaveClientNoteBtn");
    if (button) {
      button.disabled = true;
      button.textContent = "Saving...";
    }

    try {
      let attachement = "";

      if (file) {
        const uploaded = await uploadFile(file);
        attachement = (uploaded && uploaded.file_url) || "";
      }

      await apiPost(SHARED_API + ".add_client_note", {
        dashboard_type: state.dashboardType,
        client: data.client_name || "",
        lead: data.client_name ? "" : data.lead_name,
        event: (!data.client_name && !data.lead_name) ? state.eventName : "",
        session_date: sessionDate,
        session_type: sessionType,
        notes: notes,
        attachement: attachement
      });

      if (fileInput) fileInput.value = "";

      setValue("trkClientNoteText", "");
      await loadDetails();
    } catch (error) {
      console.error("Could not save client note", error);
      alert(error.message || "Could not save client note.");
    } finally {
      state.savingNote = false;

      if (button) {
        button.disabled = false;
        button.textContent = "Save Client Note";
      }
    }
  }

  function updateNoteDateDisplay() {
    const field = el("trkClientNoteSessionDate");
    const display = el("trkClientNoteSessionDateDisplay");
    if (!field || !display) return;

    // <input type="date"> renders its own text using the visitor's browser/
    // OS locale, not anything this code controls - this label guarantees
    // day/month/year regardless of what the native picker shows.
    display.textContent = field.value ? formatDisplayDate(field.value) : "";
  }

  function updateEditDateDisplay() {
    const field = el("trkDetailEditDate");
    const display = el("trkDetailEditDateDisplay");
    if (!field || !display) return;

    display.textContent = field.value ? formatDisplayDate(field.value) : "";
  }

  function fillSelect(select, options) {
    if (!select) return;
    select.innerHTML = "";
    (options || []).forEach(function (opt) {
      const option = document.createElement("option");
      option.value = opt.value;
      option.textContent = opt.label;
      select.appendChild(option);
    });
  }

  function openBookingEmailModal() {
    const modal = el("trkBookingEmailModal");
    if (modal) modal.classList.add("show");
  }

  function closeBookingEmailModal() {
    const modal = el("trkBookingEmailModal");
    if (modal) modal.classList.remove("show");
  }

  async function prepareBookingEmail() {
    const eventName = state.eventName;
    if (!eventName) return;

    const btn = el("trkDetailEmailBtn");
    if (btn) {
      btn.disabled = true;
      btn.textContent = "Loading...";
    }

    try {
      const [defaults, senderOptions] = await Promise.all([
        apiGet(SHARED_API + ".get_booking_confirmation_email_defaults", { event: eventName }),
        apiGet("dashboard.api.shared.email_templates.get_email_sender_options", {})
      ]);

      fillSelect(el("trkBookingEmailRecipient"), defaults.email_options || []);
      if (defaults.recipient) setValue("trkBookingEmailRecipient", defaults.recipient);
      fillSelect(el("trkBookingEmailSender"), senderOptions || []);

      setValue("trkBookingEmailCc", "");
      setValue("trkBookingEmailSubject", defaults.subject || "");
      setValue("trkBookingEmailMessage", defaults.message || "");

      const statusEl = el("trkBookingEmailStatus");
      if (statusEl) statusEl.textContent = "";

      openBookingEmailModal();
    } catch (error) {
      console.error("Could not load booking confirmation email", error);
      alert(error.message || "Could not load the booking confirmation email.");
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.textContent = "Email Booking Confirmation";
      }
    }
  }

  async function confirmSendBookingEmail() {
    const eventName = state.eventName;
    const statusEl = el("trkBookingEmailStatus");
    const submitBtn = el("trkBookingEmailSubmit");

    const recipient = getValue("trkBookingEmailRecipient");
    if (!recipient) {
      if (statusEl) statusEl.textContent = "Select an email address to send to.";
      return;
    }

    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.textContent = "Sending...";
    }

    if (statusEl) statusEl.textContent = "";

    try {
      await apiPost(SHARED_API + ".send_booking_confirmation_email", {
        event: eventName,
        recipient: recipient,
        subject: getValue("trkBookingEmailSubject"),
        message: getValue("trkBookingEmailMessage"),
        sender: getValue("trkBookingEmailSender"),
        cc: getValue("trkBookingEmailCc")
      });

      closeBookingEmailModal();
    } catch (error) {
      if (statusEl) statusEl.textContent = error.message || "Could not send the booking confirmation.";
    } finally {
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.textContent = "Send";
      }
    }
  }

  function bindEvents() {
    const viewMode = getViewModeParams();

    if (viewMode.isViewMode) {
      if (el("trkDetailEditBtn")) el("trkDetailEditBtn").style.display = "none";
      if (el("trkDetailDeleteBtn")) el("trkDetailDeleteBtn").style.display = "none";
      if (el("trkDetailEmailBtn")) el("trkDetailEmailBtn").style.display = "none";
      if (el("trkSaveClientNoteBtn")) el("trkSaveClientNoteBtn").style.display = "none";
      if (el("trkClientNoteText")) el("trkClientNoteText").setAttribute("readonly", "readonly");
      if (el("trkClientNoteFile")) el("trkClientNoteFile").setAttribute("disabled", "disabled");
      return;
    }
    if (el("trkDetailEditBtn")) el("trkDetailEditBtn").addEventListener("click", openEditModal);
    if (el("trkDetailDeleteBtn")) el("trkDetailDeleteBtn").addEventListener("click", deleteSession);
    if (el("trkDetailEditModalClose")) el("trkDetailEditModalClose").addEventListener("click", closeEditModal);
    if (el("trkDetailEditModalCancel")) el("trkDetailEditModalCancel").addEventListener("click", closeEditModal);
    if (el("trkDetailEditSaveBtn")) el("trkDetailEditSaveBtn").addEventListener("click", saveEdit);
    if (el("trkSaveClientNoteBtn")) el("trkSaveClientNoteBtn").addEventListener("click", saveClientNote);
    if (el("trkDetailEditType")) el("trkDetailEditType").addEventListener("change", syncEditFields);
    if (el("trkDetailEditLocationType")) el("trkDetailEditLocationType").addEventListener("change", syncEditLocationFields);
    if (el("trkClientNoteSessionDate")) el("trkClientNoteSessionDate").addEventListener("change", updateNoteDateDisplay);
    if (el("trkDetailEditDate")) el("trkDetailEditDate").addEventListener("change", updateEditDateDisplay);

    if (el("trkDetailEmailBtn")) el("trkDetailEmailBtn").addEventListener("click", prepareBookingEmail);
    if (el("trkBookingEmailModalClose")) el("trkBookingEmailModalClose").addEventListener("click", closeBookingEmailModal);
    if (el("trkBookingEmailCancel")) el("trkBookingEmailCancel").addEventListener("click", closeBookingEmailModal);
    if (el("trkBookingEmailSubmit")) el("trkBookingEmailSubmit").addEventListener("click", confirmSendBookingEmail);

    const modal = el("trkDetailEditModal");
    if (modal) {
      modal.addEventListener("click", function (event) {
        if (event.target === modal) closeEditModal();
      });
    }
  }

  function init() {
    if (!el("sessionWorkerCalendarDetailsShell")) return;
    bindEvents();
    loadDetails();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
