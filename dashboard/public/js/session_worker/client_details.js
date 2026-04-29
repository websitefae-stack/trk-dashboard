(function () {
  const state = {
    addingNote: false,
    submittingChangeRequest: false
  };

  const api = window.TRKClientDetails;
  if (!api) return;

  function isCancelledAppointment(row) {
    const status = String(row.ui_status || row.status || "").trim().toLowerCase();
    return status === "cancelled" || status === "canceled";
  }

  async function loadClientContacts() {
    const clientName = api.el("clientDocname")?.value || "";
    const body = api.el("clientContactsTableBody");

    if (!clientName || !body) return;

    try {
      const result = await api.apiPost("dashboard.api.session_worker.client_details.get_client_contacts", {
        client_name: clientName
      });

      const rows = (result.message || []).map((row) => `
        <tr>
          <td>
            <a class="dashboard-inline-link" href="${api.escapeHtml(row.link)}">
              ${api.escapeHtml(row.display_name || "—")}
            </a>
            <div class="dashboard-client-type-mobile">
              ${api.escapeHtml(row.mobile || "—")}
            </div>
          </td>
          <td>${api.escapeHtml(row.mobile || "—")}</td>
          <td>${api.escapeHtml(row.email || "—")}</td>
          <td>${api.escapeHtml(row.company || "—")}</td>
          <td class="dashboard-action-cell">
            <a class="dashboard-link-btn" href="${api.escapeHtml(row.link)}">View</a>
          </td>
        </tr>
      `);

      api.renderSimpleTable("clientContactsTableBody", rows, "No linked contacts found.", 5);
    } catch (error) {
      console.error("Could not load client contacts", error);
      api.renderSimpleTable("clientContactsTableBody", [], error.message || "Could not load contacts.", 5);
    }
  }

  async function loadClientNotes() {
    const clientName = api.el("clientDocname")?.value || "";
    const body = api.el("clientNotesTableBody");

    if (!clientName || !body) return;

    try {
      const result = await api.apiPost("dashboard.api.session_worker.client_details.get_client_notes", {
        client_name: clientName
      });

      const rows = (result.message || []).map((row) => `
        <tr>
          <td>${api.formatDate(row.note_date)}</td>
          <td class="dashboard-note-user-cell">${api.escapeHtml(row.note_user_name || row.note_user || "—")}</td>
          <td>${api.escapeHtml(row.note_text || "—")}</td>
        </tr>
      `);

      api.renderSimpleTable("clientNotesTableBody", rows, "No notes found.", 3);
    } catch (error) {
      console.error("Could not load client notes", error);
      api.renderSimpleTable("clientNotesTableBody", [], error.message || "Could not load notes.", 3);
    }
  }

  async function loadClientAppointments() {
    const clientName = api.el("clientDocname")?.value || "";
    const body = api.el("clientAppointmentsTableBody");

    if (!clientName || !body) return;

    try {
      const result = await api.apiPost("dashboard.api.session_worker.client_details.get_client_appointments", {
        client_name: clientName
      });

      const visibleAppointments = (result.message || []).filter((row) => !isCancelledAppointment(row));

      const rows = visibleAppointments.map((row) => {
        const startTime = api.formatStartTime(row.time || "");
        const link = api.escapeHtml(row.record_url || "#");

        return `
          <tr>
            <td>${api.formatDate(row.date)}</td>
            <td class="client-appointment-time-mobile">${startTime}</td>
            <td>
              <a class="dashboard-inline-link" href="${link}">
                ${api.escapeHtml(row.appointment_type || "—")}
              </a>
            </td>
            <td>${api.escapeHtml(row.ui_status || row.status || "—")}</td>
            <td>${api.escapeHtml(row.location || "—")}</td>
            <td class="dashboard-action-cell">
              <a class="dashboard-link-btn" href="${link}">View</a>
            </td>
          </tr>
        `;
      });

      api.renderSimpleTable("clientAppointmentsTableBody", rows, "No appointments found.", 6);
    } catch (error) {
      console.error("Could not load client appointments", error);
      api.renderSimpleTable("clientAppointmentsTableBody", [], error.message || "Could not load appointments.", 6);
    }
  }

  async function addClientNote() {
    if (state.addingNote) return;

    const clientName = api.el("clientDocname")?.value || "";
    const noteText = api.el("newClientNoteText")?.value || "";

    if (!clientName) {
      api.showError("Client could not be identified.");
      return;
    }

    if (!noteText.trim()) {
      api.showError("Please enter a note.");
      return;
    }

    const button = api.el("addClientNote");
    state.addingNote = true;

    if (button) {
      button.disabled = true;
      button.textContent = "Adding...";
    }

    try {
      await api.apiPost("dashboard.api.session_worker.client_details.add_client_note", {
        client_name: clientName,
        note_text: noteText
      });

      if (api.el("newClientNoteText")) {
        api.el("newClientNoteText").value = "";
      }

      await loadClientNotes();
      api.showSuccess("Note added");
    } catch (error) {
      console.error("Add note failed", error);
      api.showError(error.message || "There was a problem with the request.");
    } finally {
      state.addingNote = false;

      if (button) {
        button.disabled = false;
        button.textContent = "Add Note";
      }
    }
  }

  async function submitChangeRequest() {
    if (state.submittingChangeRequest) return;

    const clientName = api.el("clientDocname")?.value || "";
    const requestType = api.el("changeRequestType")?.value || "";
    const requestedSection = api.el("changeRequestSection")?.value || "";
    const requestedChange = api.el("changeRequestText")?.value || "";
    const reason = api.el("changeRequestReason")?.value || "";

    if (!clientName) {
      api.showError("Client could not be identified.");
      return;
    }

    if (!requestedChange.trim()) {
      api.showError("Please enter the requested change.");
      return;
    }

    const button = api.el("submitChangeRequest");
    state.submittingChangeRequest = true;

    if (button) {
      button.disabled = true;
      button.textContent = "Submitting...";
    }

    try {
      await api.apiPost("dashboard.api.session_worker.change_requests.submit_change_request", {
        client_name: clientName,
        request_type: requestType,
        requested_section: requestedSection,
        requested_change: requestedChange,
        reason: reason
      });

      if (api.el("changeRequestType")) api.el("changeRequestType").value = "";
      if (api.el("changeRequestSection")) api.el("changeRequestSection").value = "";
      if (api.el("changeRequestText")) api.el("changeRequestText").value = "";
      if (api.el("changeRequestReason")) api.el("changeRequestReason").value = "";

      api.showSuccess("Change request submitted");
    } catch (error) {
      console.error("Change request failed", error);
      api.showError(error.message || "There was a problem submitting the change request.");
    } finally {
      state.submittingChangeRequest = false;

      if (button) {
        button.disabled = false;
        button.textContent = "Submit Change Request";
      }
    }
  }

  function initActions() {
    const form = api.el("clientDetailsForm");

    if (form && form.dataset.boundSubmitBlock !== "1") {
      form.dataset.boundSubmitBlock = "1";
      form.addEventListener("submit", function (event) {
        event.preventDefault();
      });
    }

    const addNoteButton = api.el("addClientNote");
    if (addNoteButton && addNoteButton.dataset.boundClick !== "1") {
      addNoteButton.dataset.boundClick = "1";
      addNoteButton.addEventListener("click", function (event) {
        event.preventDefault();
        addClientNote();
      });
    }

    const changeRequestButton = api.el("submitChangeRequest");
    if (changeRequestButton && changeRequestButton.dataset.boundClick !== "1") {
      changeRequestButton.dataset.boundClick = "1";
      changeRequestButton.addEventListener("click", function (event) {
        event.preventDefault();
        submitChangeRequest();
      });
    }
  }

  function init() {
    if (!api.el("clientDetailsForm")) return;

    api.initTabs("session_worker_client_details_active_tab");
    initActions();

    document.addEventListener("trk-dashboard-tab-active", function (event) {
      const targetId = event.detail && event.detail.targetId;

      if (targetId === "client-contacts-tab") {
        loadClientContacts();
      }

      if (targetId === "client-notes-tab") {
        loadClientNotes();
      }

      if (targetId === "client-appointments-tab") {
        loadClientAppointments();
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
