/**
 * "Reminders" tool (franchisor_db/reminders) - personal, date-based
 * reminders ("speak to Ashley about price increases every 1st of
 * November") that fire into the same in-app notification bell
 * everything else in this app already uses
 * (dashboard.api.shared.reminders.send_due_reminders, a daily scheduled
 * job). This file is just the list/add/pause/delete UI around that API.
 */
(function () {
  "use strict";

  var el = Dashboard.el;

  var SHARED_API = "dashboard.api.shared.reminders";

  var RECURRENCE_LABELS = {
    None: "Just once",
    Weekly: "Every week",
    Monthly: "Every month",
    Yearly: "Every year",
  };

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function getCsrfToken() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    return meta && meta.content ? meta.content : "";
  }

  async function apiPost(method, args) {
    var response = await fetch("/api/method/" + method, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-Frappe-CSRF-Token": getCsrfToken(),
      },
      body: JSON.stringify(args || {}),
    });

    var data = await response.json();

    if (!response.ok || data.exc) {
      throw new Error(Dashboard.extractErrorMessage(data, "There was a problem saving this reminder."));
    }

    return data.message || {};
  }

  function formatDate(value) {
    if (!value) return "";
    var parts = String(value).split("-");
    if (parts.length !== 3) return value;
    var date = new Date(Number(parts[0]), Number(parts[1]) - 1, Number(parts[2]));
    return date.toLocaleDateString(undefined, { day: "numeric", month: "long", year: "numeric" });
  }

  function renderReminders(rows) {
    var list = el("remindersList");
    if (!list) return;

    if (!rows.length) {
      list.innerHTML = '<div class="dashboard-card"><div class="dashboard-empty">No reminders yet - add one above.</div></div>';
      return;
    }

    list.innerHTML = rows.map(function (row) {
      var statusBadge = row.active
        ? '<span class="dashboard-badge dashboard-status-active">Active</span>'
        : '<span class="dashboard-badge">Paused</span>';

      return (
        '<div class="dashboard-card" data-reminder-name="' + escapeHtml(row.name) + '" style="margin-bottom:12px; display:flex; justify-content:space-between; align-items:flex-start; gap:16px; flex-wrap:wrap;">' +
          '<div>' +
            '<div style="font-weight:600;">' + escapeHtml(row.title) + "</div>" +
            (row.note ? '<div style="color:#839898; margin-top:4px;">' + escapeHtml(row.note) + "</div>" : "") +
            '<div class="dashboard-doc-list-meta" style="margin-top:8px;">' +
              escapeHtml(formatDate(row.remind_date)) + " · " + escapeHtml(RECURRENCE_LABELS[row.recurrence] || "Just once") +
            "</div>" +
          "</div>" +
          '<div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap;">' +
            statusBadge +
            '<button type="button" class="dashboard-btn dashboard-btn-light dashboard-reminder-toggle" data-active="' + (row.active ? "1" : "0") + '">' + (row.active ? "Pause" : "Resume") + "</button>" +
            '<button type="button" class="dashboard-btn dashboard-btn-grey dashboard-reminder-delete">Delete</button>' +
          "</div>" +
        "</div>"
      );
    }).join("");

    list.querySelectorAll(".dashboard-reminder-toggle").forEach(function (btn) {
      btn.addEventListener("click", async function () {
        var card = btn.closest("[data-reminder-name]");
        var name = card && card.dataset.reminderName;
        if (!name) return;

        var nextActive = btn.dataset.active === "1" ? 0 : 1;
        btn.disabled = true;

        try {
          await apiPost(SHARED_API + ".update_reminder", { name: name, active: nextActive });
          await loadReminders();
        } catch (error) {
          window.alert(error.message || "Could not update this reminder.");
          btn.disabled = false;
        }
      });
    });

    list.querySelectorAll(".dashboard-reminder-delete").forEach(function (btn) {
      btn.addEventListener("click", async function () {
        var card = btn.closest("[data-reminder-name]");
        var name = card && card.dataset.reminderName;
        if (!name) return;

        if (!window.confirm("Delete this reminder?")) return;

        btn.disabled = true;

        try {
          await apiPost(SHARED_API + ".delete_reminder", { name: name });
          await loadReminders();
        } catch (error) {
          window.alert(error.message || "Could not delete this reminder.");
          btn.disabled = false;
        }
      });
    });
  }

  async function loadReminders() {
    var list = el("remindersList");
    if (!list) return;

    try {
      var rows = await apiPost(SHARED_API + ".get_my_reminders", {});
      renderReminders(Array.isArray(rows) ? rows : []);
    } catch (error) {
      list.innerHTML = '<div class="dashboard-card"><div class="dashboard-empty">' + escapeHtml(error.message || "Could not load reminders.") + "</div></div>";
    }
  }

  function initAddForm() {
    var btn = el("addReminderBtn");
    if (!btn) return;

    btn.addEventListener("click", async function () {
      var title = (el("reminderTitle").value || "").trim();
      var note = (el("reminderNote").value || "").trim();
      var remindDate = el("reminderDate").value;
      var recurrence = el("reminderRecurrence").value;

      if (!title) {
        window.alert("Please enter a title for this reminder.");
        return;
      }
      if (!remindDate) {
        window.alert("Please choose a date.");
        return;
      }

      btn.disabled = true;

      try {
        await apiPost(SHARED_API + ".create_reminder", {
          title: title,
          note: note,
          remind_date: remindDate,
          recurrence: recurrence,
        });

        el("reminderTitle").value = "";
        el("reminderNote").value = "";
        el("reminderDate").value = "";
        el("reminderRecurrence").value = "None";

        await loadReminders();
      } catch (error) {
        window.alert(error.message || "Could not add this reminder.");
      } finally {
        btn.disabled = false;
      }
    });
  }

  function init() {
    if (!el("remindersList")) return;

    loadReminders();
    initAddForm();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
