/**
 * "Testimonials" tool - capture a client testimonial (text, photo, or
 * video), who it's from (or anonymous), which coach received it, and
 * which brand(s) it's for. Shared between franchisor_db (full add/edit/
 * delete, any coach) and coach_db (add/edit their own only, coach is
 * implicit) - which mode a page is in is detected by whether
 * #testimonialCoachField exists (only the franchisor page has it).
 *
 * The brand checkboxes are filtered server-side to whatever the
 * relevant coach actually operates (dashboard.api.shared.testimonials.
 * get_coach_brand_options/get_my_coach_brand_options) - a Kid-only
 * coach never even sees the other three boxes, a 4-brand coach sees
 * all of them. Re-fetched every time the franchisor changes the coach
 * picker.
 */
(function () {
  "use strict";

  var el = Dashboard.el;
  var SHARED_API = "dashboard.api.shared.testimonials";

  var BRAND_CHECKBOX_IDS = {
    Kid: "testimonialBrandKid",
    Teen: "testimonialBrandTeen",
    People: "testimonialBrandPeople",
    School: "testimonialBrandSchool",
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
      throw new Error(Dashboard.extractErrorMessage(data, "There was a problem loading testimonials."));
    }

    return data.message || {};
  }

  async function uploadFile(file) {
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

  function isFranchisorMode() {
    return !!el("testimonialCoachField");
  }

  function formatDate(value) {
    if (!value) return "";
    var parts = String(value).split("-");
    if (parts.length !== 3) return value;
    var date = new Date(Number(parts[0]), Number(parts[1]) - 1, Number(parts[2]));
    return date.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
  }

  function brandBadges(t) {
    var labels = [];
    if (t.brand_access_kid) labels.push("TRK");
    if (t.brand_access_teen) labels.push("TRT");
    if (t.brand_access_people) labels.push("TRP");
    if (t.brand_access_school) labels.push("TRS");
    if (t.for_books) labels.push("Books");
    if (t.for_podcast) labels.push("Podcast");
    return labels.map(function (l) { return '<span class="dashboard-badge">' + l + "</span>"; }).join(" ");
  }

  function renderTestimonialCard(t, canManage, showCoach) {
    var who = t.is_anonymous || !t.client_name ? "Anonymous" : escapeHtml(t.client_name);

    var body = "";
    if (t.testimonial_type === "Photo" && t.testimonial_file) {
      body = '<img src="' + escapeHtml(t.testimonial_file) + '" alt="" style="max-width:100%; max-height:320px; border-radius:8px; margin-top:10px;">';
    } else if (t.testimonial_type === "Video" && t.testimonial_file) {
      body = '<video src="' + escapeHtml(t.testimonial_file) + '" controls style="max-width:100%; max-height:320px; border-radius:8px; margin-top:10px;"></video>';
    } else if (t.testimonial_text) {
      // testimonial_text comes from a plain <textarea> (see the form
      // below), not a rich text editor - escaped here and rendered with
      // white-space:pre-wrap so line breaks the coach/franchisor typed
      // are preserved instead of collapsing into one run-on paragraph,
      // which is both the actual bug being fixed and (since this was
      // previously injected as raw unescaped HTML) a stored-XSS fix.
      body = '<div class="dashboard-testimonial-quote">' + escapeHtml(t.testimonial_text) + "</div>";
    }

    return (
      '<div class="dashboard-card" data-testimonial-name="' + escapeHtml(t.name) + '" style="margin-bottom:12px;">' +
        '<div style="display:flex; justify-content:space-between; align-items:flex-start; gap:12px; flex-wrap:wrap;">' +
          '<div>' +
            '<div style="font-weight:600;">' + who + "</div>" +
            '<div class="dashboard-doc-list-meta" style="margin-top:4px;">' +
              [
                t.testimonial_date ? escapeHtml(formatDate(t.testimonial_date)) : "",
                showCoach && t.coach_label ? escapeHtml(t.coach_label) : "",
              ].filter(Boolean).join(" · ") +
            "</div>" +
          "</div>" +
          '<div>' + brandBadges(t) + "</div>" +
        "</div>" +

        body +

        (canManage
          ? '<div style="margin-top:10px; border-top:1px solid #eef3f3; padding-top:10px;">' +
              '<button type="button" class="dashboard-btn dashboard-btn-grey dashboard-testimonial-edit">Edit</button> ' +
              (isFranchisorMode() ? '<button type="button" class="dashboard-btn dashboard-btn-grey dashboard-testimonial-delete">Delete</button>' : "") +
            "</div>"
          : "") +
      "</div>"
    );
  }

  function renderTestimonialsList(rows, coachLabelsByName) {
    var list = el("testimonialsList");
    if (!list) return;

    if (!rows.length) {
      list.innerHTML = '<div class="dashboard-card"><div class="dashboard-empty">No testimonials yet.</div></div>';
      return;
    }

    rows.forEach(function (t) { t.coach_label = (coachLabelsByName && coachLabelsByName[t.coach]) || t.coach; });

    list.innerHTML = rows.map(function (t) { return renderTestimonialCard(t, true, isFranchisorMode()); }).join("");

    list.querySelectorAll(".dashboard-testimonial-edit").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var card = btn.closest("[data-testimonial-name]");
        var name = card && card.dataset.testimonialName;
        if (name) loadTestimonialIntoForm(name);
      });
    });

    list.querySelectorAll(".dashboard-testimonial-delete").forEach(function (btn) {
      btn.addEventListener("click", async function () {
        var card = btn.closest("[data-testimonial-name]");
        var name = card && card.dataset.testimonialName;
        if (!name) return;
        if (!window.confirm("Delete this testimonial?")) return;

        btn.disabled = true;
        try {
          await apiPost(SHARED_API + ".delete_testimonial", { name: name });
          await loadTestimonials();
        } catch (error) {
          window.alert(error.message || "Could not delete this testimonial.");
          btn.disabled = false;
        }
      });
    });
  }

  async function loadTestimonials() {
    var list = el("testimonialsList");
    if (!list) return;

    try {
      var rows;
      var coachLabelsByName = {};

      if (isFranchisorMode()) {
        var filterSelect = el("testimonialFilterCoachSelect");
        rows = await apiPost(SHARED_API + ".get_all_testimonials", {
          coach: filterSelect ? filterSelect.value : "",
        });
        var select = el("testimonialCoachSelect");
        if (select) {
          Array.prototype.forEach.call(select.options, function (opt) {
            if (opt.value) coachLabelsByName[opt.value] = opt.textContent;
          });
        }
      } else {
        var params = new URLSearchParams(window.location.search);
        rows = await apiPost(SHARED_API + ".get_my_testimonials", {
          view_as: params.get("view_as"),
          viewer: params.get("viewer"),
        });
      }

      renderTestimonialsList(Array.isArray(rows) ? rows : [], coachLabelsByName);
    } catch (error) {
      list.innerHTML = '<div class="dashboard-card"><div class="dashboard-empty">' + escapeHtml(error.message || "Could not load testimonials.") + "</div></div>";
    }
  }

  function setBrandCheckboxAvailability(allowedBrands, booksAllowed) {
    Object.keys(BRAND_CHECKBOX_IDS).forEach(function (brand) {
      var wrap = el(BRAND_CHECKBOX_IDS[brand] + "Wrap");
      var input = el(BRAND_CHECKBOX_IDS[brand]);
      var allowed = allowedBrands.indexOf(brand) !== -1;

      if (wrap) wrap.style.display = allowed ? "" : "none";
      if (input && !allowed) input.checked = false;
    });

    var booksWrap = el("testimonialForBooksWrap");
    var booksInput = el("testimonialForBooks");
    if (booksWrap) booksWrap.style.display = booksAllowed ? "" : "none";
    if (booksInput && !booksAllowed) booksInput.checked = false;
  }

  async function refreshBrandOptionsForCoach(coachName) {
    try {
      var result = coachName
        ? await apiPost(SHARED_API + ".get_coach_brand_options", { coach: coachName })
        : { brands: [], books: false };
      setBrandCheckboxAvailability(Array.isArray(result.brands) ? result.brands : [], !!result.books);
    } catch (error) {
      setBrandCheckboxAvailability([], false);
    }
  }

  async function refreshBrandOptionsForSelf() {
    try {
      var result = await apiPost(SHARED_API + ".get_my_coach_brand_options", {});
      setBrandCheckboxAvailability(Array.isArray(result.brands) ? result.brands : [], !!result.books);
    } catch (error) {
      setBrandCheckboxAvailability(Object.keys(BRAND_CHECKBOX_IDS), false);
    }
  }

  async function loadCoachOptions() {
    var addSelect = el("testimonialCoachSelect");
    var filterSelect = el("testimonialFilterCoachSelect");
    if (!addSelect && !filterSelect) return;

    var coaches = [];
    try {
      coaches = await apiPost(SHARED_API + ".get_coach_options_for_testimonials", {});
      coaches = Array.isArray(coaches) ? coaches : [];
    } catch (error) {
      coaches = [];
    }

    var coachOptionsHtml = coaches.map(function (c) {
      return '<option value="' + escapeHtml(c.name) + '">' + escapeHtml(c.coach_name || c.name) + "</option>";
    }).join("");

    if (addSelect) {
      addSelect.innerHTML = coaches.length
        ? '<option value="">Choose a coach...</option>' + coachOptionsHtml
        : '<option value="">Could not load coaches</option>';
    }

    if (filterSelect) {
      filterSelect.innerHTML = coaches.length
        ? '<option value="">All Coaches</option>' + coachOptionsHtml
        : '<option value="">All Coaches</option>';

      // Defaults to Ashley's own testimonials (she's a Coach too), same
      // as what a coach would see on their own dashboard - falls back
      // to "All Coaches" for an office login that isn't itself a Coach.
      try {
        var defaultCoach = await apiPost(SHARED_API + ".get_testimonial_filter_default", {});
        filterSelect.value = defaultCoach || "";
      } catch (error) {
        filterSelect.value = "";
      }

      filterSelect.addEventListener("change", loadTestimonials);
    }
  }

  function updateFormatFieldVisibility() {
    var type = el("testimonialType").value;
    var textWrap = el("testimonialTextWrap");
    var fileWrap = el("testimonialFileWrap");
    if (textWrap) textWrap.style.display = type === "Text" ? "" : "none";
    if (fileWrap) fileWrap.style.display = type === "Text" ? "none" : "";
  }

  function updateAnonymousFieldState() {
    var nameInput = el("testimonialClientName");
    if (!nameInput) return;
    var anonymous = el("testimonialAnonymous").checked;
    nameInput.disabled = anonymous;
    if (anonymous) nameInput.value = "";
  }

  function resetForm() {
    el("testimonialFormName").value = "";
    el("testimonialDate").value = "";
    el("testimonialType").value = "Text";
    el("testimonialClientName").value = "";
    el("testimonialAnonymous").checked = false;
    el("testimonialText").value = "";
    var fileInput = el("testimonialFile");
    if (fileInput) fileInput.value = "";
    var existingFile = el("testimonialExistingFile");
    if (existingFile) existingFile.innerHTML = "";

    Object.keys(BRAND_CHECKBOX_IDS).forEach(function (brand) {
      var input = el(BRAND_CHECKBOX_IDS[brand]);
      if (input) input.checked = false;
    });
    var booksInput = el("testimonialForBooks");
    if (booksInput) booksInput.checked = false;
    var podcastInput = el("testimonialForPodcast");
    if (podcastInput) podcastInput.checked = false;

    var coachSelect = el("testimonialCoachSelect");
    if (coachSelect) {
      coachSelect.value = "";
      setBrandCheckboxAvailability([], false);
    } else {
      refreshBrandOptionsForSelf();
    }

    updateFormatFieldVisibility();
    updateAnonymousFieldState();

    var heading = el("testimonialFormHeading");
    if (heading) heading.textContent = "Add a Testimonial";
    var saveBtn = el("saveTestimonialBtn");
    if (saveBtn) saveBtn.textContent = "Save Testimonial";
    var cancelBtn = el("cancelEditTestimonialBtn");
    if (cancelBtn) cancelBtn.style.display = "none";
  }

  async function loadTestimonialIntoForm(name) {
    try {
      var t = await apiPost(SHARED_API + ".get_testimonial_for_edit", { name: name });

      el("testimonialFormName").value = t.name || "";
      el("testimonialDate").value = t.testimonial_date || "";
      el("testimonialType").value = t.testimonial_type || "Text";
      el("testimonialClientName").value = t.client_name || "";
      el("testimonialAnonymous").checked = !!t.is_anonymous;
      el("testimonialText").value = t.testimonial_text || "";

      var existingFile = el("testimonialExistingFile");
      if (existingFile) {
        existingFile.innerHTML = t.testimonial_file
          ? '<div style="margin-top:6px; color:#839898; font-size:12px;">Current file: <a href="' + escapeHtml(t.testimonial_file) + '" target="_blank" rel="noopener noreferrer">' + escapeHtml(t.testimonial_file) + "</a> (choose a new file only if you want to replace it)</div>"
          : "";
      }

      var coachSelect = el("testimonialCoachSelect");
      if (coachSelect) {
        coachSelect.value = t.coach || "";
        await refreshBrandOptionsForCoach(t.coach);
      } else {
        await refreshBrandOptionsForSelf();
      }

      if (el(BRAND_CHECKBOX_IDS.Kid)) el(BRAND_CHECKBOX_IDS.Kid).checked = !!t.brand_access_kid;
      if (el(BRAND_CHECKBOX_IDS.Teen)) el(BRAND_CHECKBOX_IDS.Teen).checked = !!t.brand_access_teen;
      if (el(BRAND_CHECKBOX_IDS.People)) el(BRAND_CHECKBOX_IDS.People).checked = !!t.brand_access_people;
      if (el(BRAND_CHECKBOX_IDS.School)) el(BRAND_CHECKBOX_IDS.School).checked = !!t.brand_access_school;
      if (el("testimonialForBooks")) el("testimonialForBooks").checked = !!t.for_books;
      if (el("testimonialForPodcast")) el("testimonialForPodcast").checked = !!t.for_podcast;

      updateFormatFieldVisibility();
      updateAnonymousFieldState();

      var heading = el("testimonialFormHeading");
      if (heading) heading.textContent = "Edit Testimonial";
      var saveBtn = el("saveTestimonialBtn");
      if (saveBtn) saveBtn.textContent = "Update Testimonial";
      var cancelBtn = el("cancelEditTestimonialBtn");
      if (cancelBtn) cancelBtn.style.display = "";

      var form = el("testimonialForm");
      if (form) form.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (error) {
      window.alert(error.message || "Could not load this testimonial.");
    }
  }

  function initForm() {
    var saveBtn = el("saveTestimonialBtn");
    if (!saveBtn) return;

    var coachSelect = el("testimonialCoachSelect");
    if (coachSelect) {
      coachSelect.addEventListener("change", function () { refreshBrandOptionsForCoach(coachSelect.value); });
    }

    var typeSelect = el("testimonialType");
    if (typeSelect) typeSelect.addEventListener("change", updateFormatFieldVisibility);

    var anonymousCheckbox = el("testimonialAnonymous");
    if (anonymousCheckbox) anonymousCheckbox.addEventListener("change", updateAnonymousFieldState);

    saveBtn.addEventListener("click", async function () {
      var coachName = coachSelect ? coachSelect.value : "";
      if (coachSelect && !coachName) {
        window.alert("Please choose a coach.");
        return;
      }

      var type = el("testimonialType").value;
      var fileInput = el("testimonialFile");
      var file = fileInput && fileInput.files && fileInput.files[0];

      if (type === "Text" && !(el("testimonialText").value || "").trim()) {
        window.alert("Please enter the testimonial text.");
        return;
      }

      var existingName = el("testimonialFormName").value;
      if (type !== "Text" && !file && !existingName) {
        window.alert("Please choose a " + type.toLowerCase() + " file.");
        return;
      }

      saveBtn.disabled = true;

      try {
        var fileUrl = null;
        if (type !== "Text" && file) {
          fileUrl = await uploadFile(file);
        }

        var payload = {
          name: existingName || null,
          coach: coachName || null,
          testimonial_date: el("testimonialDate").value || null,
          testimonial_type: type,
          client_name: el("testimonialClientName").value,
          is_anonymous: el("testimonialAnonymous").checked ? 1 : 0,
          testimonial_text: el("testimonialText").value,
          brand_access_kid: el(BRAND_CHECKBOX_IDS.Kid) && el(BRAND_CHECKBOX_IDS.Kid).checked ? 1 : 0,
          brand_access_teen: el(BRAND_CHECKBOX_IDS.Teen) && el(BRAND_CHECKBOX_IDS.Teen).checked ? 1 : 0,
          brand_access_people: el(BRAND_CHECKBOX_IDS.People) && el(BRAND_CHECKBOX_IDS.People).checked ? 1 : 0,
          brand_access_school: el(BRAND_CHECKBOX_IDS.School) && el(BRAND_CHECKBOX_IDS.School).checked ? 1 : 0,
          for_books: el("testimonialForBooks") && el("testimonialForBooks").checked ? 1 : 0,
          for_podcast: el("testimonialForPodcast") && el("testimonialForPodcast").checked ? 1 : 0,
        };

        if (fileUrl) payload.testimonial_file = fileUrl;

        await apiPost(SHARED_API + ".save_testimonial", payload);

        resetForm();
        await loadTestimonials();
      } catch (error) {
        window.alert(error.message || "Could not save this testimonial.");
      } finally {
        saveBtn.disabled = false;
      }
    });

    var cancelBtn = el("cancelEditTestimonialBtn");
    if (cancelBtn) cancelBtn.addEventListener("click", resetForm);
  }

  async function init() {
    if (!el("testimonialsList")) return;

    if (isFranchisorMode()) {
      await loadCoachOptions();
      setBrandCheckboxAvailability([], false);
    } else {
      refreshBrandOptionsForSelf();
    }

    updateFormatFieldVisibility();
    updateAnonymousFieldState();
    initForm();
    loadTestimonials();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
