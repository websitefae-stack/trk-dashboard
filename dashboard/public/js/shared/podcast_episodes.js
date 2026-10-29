/**
 * "Podcasts" tool - a single shared list of every podcast episode
 * (title, status, show notes, topics, downloadable resources, and
 * Spotify/YouTube links) so Ashley and coaches can see what's been
 * covered and what's planned next, instead of that living only in a
 * Trello board. Shared between franchisor_db (full add/edit/delete) and
 * coach_db (read-only - no #podcastEpisodeForm on that page, so the
 * add/edit wiring below simply never runs there).
 */
(function () {
  "use strict";

  var el = Dashboard.el;
  var SHARED_API = "dashboard.api.shared.podcast_episodes";

  // Show Notes is real rich text (bullets, links) now, not a plain
  // textarea - Dashboard.richTextEditorHtml()/wireRichTextEditor() are
  // the same small editor already used for School Pipeline emails (see
  // utils.js). Only one instance on this page, so a single module-level
  // controller is enough - set up once in initShowNotesEditor().
  var showNotesEditor = null;

  function initShowNotesEditor() {
    var container = el("episodeShowNotesRichtext");
    if (!container || showNotesEditor) return;
    container.innerHTML = Dashboard.richTextEditorHtml("What this episode covers…");
    showNotesEditor = Dashboard.wireRichTextEditor(container.querySelector(".dashboard-richtext"));
  }

  // Resources (transcript, worksheets, etc.) - an in-memory list of
  // {label, file} the form is currently holding, uploaded one at a time
  // via the same generic upload_file endpoint testimonials.js already
  // uses for its own file field. Rebuilt from the episode's own
  // resources on edit, cleared on resetForm.
  var currentResources = [];

  function renderResourcesList() {
    var container = el("episodeResourcesList");
    if (!container) return;

    if (!currentResources.length) {
      container.innerHTML = '<div style="color:#839898; font-size:13px;">No files added yet.</div>';
      return;
    }

    container.innerHTML = currentResources.map(function (resource, index) {
      return (
        '<div style="display:flex; align-items:center; gap:8px; margin-top:6px;" data-resource-index="' + index + '">' +
          '<input type="text" class="dashboard-input" data-resource-label placeholder="Label (e.g. Transcript)" value="' + escapeHtml(resource.label || "") + '" style="flex:1;">' +
          '<a href="' + escapeHtml(resource.file) + '" target="_blank" rel="noopener noreferrer" style="font-size:12px; white-space:nowrap;">View file</a>' +
          '<button type="button" class="dashboard-btn dashboard-btn-grey dashboard-resource-remove">Remove</button>' +
        "</div>"
      );
    }).join("");

    container.querySelectorAll("[data-resource-label]").forEach(function (input, index) {
      input.addEventListener("input", function () {
        currentResources[index].label = input.value;
      });
    });

    container.querySelectorAll(".dashboard-resource-remove").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var row = btn.closest("[data-resource-index]");
        var index = row ? Number(row.dataset.resourceIndex) : -1;
        if (index < 0) return;
        currentResources.splice(index, 1);
        renderResourcesList();
      });
    });
  }

  async function uploadResourceFile(file) {
    var formData = new FormData();
    formData.append("file", file);
    formData.append("is_private", 0);

    var response = await fetch("/api/method/upload_file", {
      method: "POST",
      credentials: "same-origin",
      headers: { "X-Frappe-CSRF-Token": getCsrfToken() },
      body: formData,
    });

    var data = await response.json();

    if (!response.ok || data.exc) {
      throw new Error(Dashboard.extractErrorMessage(data, "Could not upload the file."));
    }

    return data.message && data.message.file_url;
  }

  function initResourcesField() {
    var addBtn = el("addEpisodeResourceBtn");
    var fileInput = el("episodeResourcesFileInput");
    if (!addBtn || !fileInput) return;

    addBtn.addEventListener("click", function () {
      fileInput.click();
    });

    fileInput.addEventListener("change", async function () {
      var files = Array.prototype.slice.call(fileInput.files || []);
      fileInput.value = "";
      if (!files.length) return;

      addBtn.disabled = true;
      try {
        for (var i = 0; i < files.length; i++) {
          var fileUrl = await uploadResourceFile(files[i]);
          if (fileUrl) {
            currentResources.push({ label: files[i].name, file: fileUrl });
          }
        }
        renderResourcesList();
      } catch (error) {
        window.alert(error.message || "Could not upload one of the files.");
      } finally {
        addBtn.disabled = false;
      }
    });

    renderResourcesList();
  }

  var STATUS_BADGE_CLASS = {
    Planned: "dashboard-badge",
    Recorded: "dashboard-badge dashboard-status-onhold",
    Published: "dashboard-badge dashboard-status-active",
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
      throw new Error(Dashboard.extractErrorMessage(data, "There was a problem loading podcast episodes."));
    }

    return data.message || {};
  }

  function formatDate(value) {
    if (!value) return "";
    var parts = String(value).split("-");
    if (parts.length !== 3) return value;
    var date = new Date(Number(parts[0]), Number(parts[1]) - 1, Number(parts[2]));
    return date.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
  }

  function linkRow(label, url) {
    if (!url) return "";
    return '<a href="' + escapeHtml(url) + '" target="_blank" rel="noopener noreferrer" class="dashboard-btn dashboard-btn-light" style="margin-right:8px; margin-top:6px;">' + escapeHtml(label) + "</a>";
  }

  function renderEpisodeCard(episode, canManage) {
    var statusClass = STATUS_BADGE_CLASS[episode.status] || "dashboard-badge";
    var titleBits = [];
    if (episode.season_number && episode.episode_number) {
      titleBits.push("S" + escapeHtml(episode.season_number) + "E" + escapeHtml(episode.episode_number));
    } else if (episode.episode_number) {
      titleBits.push("#" + escapeHtml(episode.episode_number));
    }
    titleBits.push(escapeHtml(episode.episode_title));

    return (
      '<div class="dashboard-card" data-episode-name="' + escapeHtml(episode.name) + '" style="margin-bottom:12px;">' +
        '<div style="display:flex; justify-content:space-between; align-items:flex-start; gap:12px; flex-wrap:wrap;">' +
          '<div>' +
            '<div style="font-weight:600; font-size:16px;">' + titleBits.join(" - ") + "</div>" +
            '<div class="dashboard-doc-list-meta" style="margin-top:4px;">' +
              [
                episode.air_date ? escapeHtml(formatDate(episode.air_date)) : "",
                episode.guest_name ? "Guest: " + escapeHtml(episode.guest_name) : "",
                episode.topics ? escapeHtml(episode.topics) : "",
              ].filter(Boolean).join(" · ") +
            "</div>" +
          "</div>" +
          '<span class="' + statusClass + '">' + escapeHtml(episode.status) + "</span>" +
        "</div>" +

        (episode.show_notes ? '<div style="margin-top:10px;">' + episode.show_notes + "</div>" : "") +

        (episode.resources && episode.resources.length
          ? '<div style="margin-top:10px;">' +
              episode.resources.map(function (resource) {
                return linkRow(resource.label || "Download", resource.file);
              }).join("") +
            "</div>"
          : "") +

        '<div style="margin-top:10px;">' +
          linkRow("Spotify", episode.spotify_url) +
          linkRow("YouTube", episode.youtube_url) +
        "</div>" +

        (canManage
          ? '<div style="margin-top:10px; border-top:1px solid #eef3f3; padding-top:10px;">' +
              '<button type="button" class="dashboard-btn dashboard-btn-grey dashboard-episode-edit">Edit</button> ' +
              '<button type="button" class="dashboard-btn dashboard-btn-grey dashboard-episode-delete">Delete</button>' +
            "</div>"
          : "") +
      "</div>"
    );
  }

  function renderEpisodeList(episodes, canManage) {
    var list = el("podcastEpisodesList");
    if (!list) return;

    if (!episodes.length) {
      list.innerHTML = '<div class="dashboard-card"><div class="dashboard-empty">No podcast episodes yet.</div></div>';
      return;
    }

    list.innerHTML = episodes.map(function (ep) { return renderEpisodeCard(ep, canManage); }).join("");

    if (!canManage) return;

    list.querySelectorAll(".dashboard-episode-edit").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var card = btn.closest("[data-episode-name]");
        var name = card && card.dataset.episodeName;
        if (name) loadEpisodeIntoForm(name);
      });
    });

    list.querySelectorAll(".dashboard-episode-delete").forEach(function (btn) {
      btn.addEventListener("click", async function () {
        var card = btn.closest("[data-episode-name]");
        var name = card && card.dataset.episodeName;
        if (!name) return;
        if (!window.confirm("Delete this episode?")) return;

        btn.disabled = true;
        try {
          await apiPost(SHARED_API + ".delete_podcast_episode", { name: name });
          await loadEpisodes();
        } catch (error) {
          window.alert(error.message || "Could not delete this episode.");
          btn.disabled = false;
        }
      });
    });
  }

  async function loadEpisodes() {
    var list = el("podcastEpisodesList");
    if (!list) return;

    var canManage = !!el("podcastEpisodeForm");

    try {
      var rows = await apiPost(SHARED_API + ".get_podcast_episodes", {});
      renderEpisodeList(Array.isArray(rows) ? rows : [], canManage);
    } catch (error) {
      list.innerHTML = '<div class="dashboard-card"><div class="dashboard-empty">' + escapeHtml(error.message || "Could not load podcast episodes.") + "</div></div>";
    }
  }

  function resetForm() {
    el("episodeFormName").value = "";
    el("episodeTitle").value = "";
    el("episodeSeason").value = "";
    el("episodeNumber").value = "";
    el("episodeGuest").value = "";
    el("episodeStatus").value = "Published";
    el("episodeAirDate").value = "";
    el("episodeTopics").value = "";
    if (showNotesEditor) showNotesEditor.setHtml("");
    currentResources = [];
    renderResourcesList();
    el("episodePlanningNotes").value = "";
    el("episodeSpotify").value = "";
    el("episodeYoutube").value = "";

    var heading = el("podcastFormHeading");
    if (heading) heading.textContent = "Add an Episode";
    var saveBtn = el("saveEpisodeBtn");
    if (saveBtn) saveBtn.textContent = "Save Episode";
    var cancelBtn = el("cancelEditEpisodeBtn");
    if (cancelBtn) cancelBtn.style.display = "none";
  }

  async function loadEpisodeIntoForm(name) {
    try {
      var episode = await apiPost(SHARED_API + ".get_podcast_episode_for_edit", { name: name });

      el("episodeFormName").value = episode.name || "";
      el("episodeTitle").value = episode.episode_title || "";
      el("episodeSeason").value = episode.season_number || "";
      el("episodeNumber").value = episode.episode_number || "";
      el("episodeGuest").value = episode.guest_name || "";
      el("episodeStatus").value = episode.status || "Published";
      el("episodeAirDate").value = episode.air_date || "";
      el("episodeTopics").value = episode.topics || "";
      if (showNotesEditor) showNotesEditor.setHtml(episode.show_notes || "");
      currentResources = (episode.resources || []).map(function (resource) {
        return { label: resource.label || "", file: resource.file };
      });
      renderResourcesList();
      el("episodePlanningNotes").value = episode.planning_notes || "";
      el("episodeSpotify").value = episode.spotify_url || "";
      el("episodeYoutube").value = episode.youtube_url || "";

      var heading = el("podcastFormHeading");
      if (heading) heading.textContent = "Edit Episode";
      var saveBtn = el("saveEpisodeBtn");
      if (saveBtn) saveBtn.textContent = "Update Episode";
      var cancelBtn = el("cancelEditEpisodeBtn");
      if (cancelBtn) cancelBtn.style.display = "";

      var form = el("podcastEpisodeForm");
      if (form) form.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (error) {
      window.alert(error.message || "Could not load this episode.");
    }
  }

  function initForm() {
    var saveBtn = el("saveEpisodeBtn");
    if (!saveBtn) return;

    saveBtn.addEventListener("click", async function () {
      var title = (el("episodeTitle").value || "").trim();
      if (!title) {
        window.alert("Please enter an episode title.");
        return;
      }

      saveBtn.disabled = true;

      try {
        await apiPost(SHARED_API + ".save_podcast_episode", {
          name: el("episodeFormName").value || null,
          episode_title: title,
          season_number: el("episodeSeason").value || null,
          episode_number: el("episodeNumber").value || null,
          guest_name: el("episodeGuest").value,
          status: el("episodeStatus").value,
          air_date: el("episodeAirDate").value || null,
          topics: el("episodeTopics").value,
          show_notes: showNotesEditor ? showNotesEditor.getHtml() : "",
          resources: currentResources,
          planning_notes: el("episodePlanningNotes").value,
          spotify_url: el("episodeSpotify").value,
          youtube_url: el("episodeYoutube").value,
        });

        resetForm();
        await loadEpisodes();
      } catch (error) {
        window.alert(error.message || "Could not save this episode.");
      } finally {
        saveBtn.disabled = false;
      }
    });

    var cancelBtn = el("cancelEditEpisodeBtn");
    if (cancelBtn) {
      cancelBtn.addEventListener("click", resetForm);
    }
  }

  function init() {
    if (!el("podcastEpisodesList")) return;

    initShowNotesEditor();
    initResourcesField();
    loadEpisodes();
    initForm();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
