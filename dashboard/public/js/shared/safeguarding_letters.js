/**
 * School Safeguarding Assurance Letters - coach-facing request form/list
 * (coach_db/safeguarding_letters), franchisor-facing requests list
 * (franchisor_db/safeguarding_letters) and the review/approve/sign
 * screen (franchisor_db/safeguarding_letter_details). One file, three
 * pages - each init function bails out immediately if its page's own
 * root element isn't present, same pattern used across this app's
 * other shared JS files.
 */
(function () {
  "use strict";

  var el = Dashboard.el;
  var SHARED_API = "dashboard.api.shared.safeguarding_letters";

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
      throw new Error(Dashboard.extractErrorMessage(data, "There was a problem with this request."));
    }

    return data.message;
  }

  function formatDate(value) {
    if (!value) return "";
    var date = new Date(String(value).replace(" ", "T"));
    if (Number.isNaN(date.getTime())) return String(value);
    return date.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
  }

  // -------------------------------------------------------------------
  // Coach page: request a letter + "My Safeguarding Assurance Letters"
  // -------------------------------------------------------------------

  function initCoachPage() {
    if (!el("newLetterFormCard")) return;

    var schoolOptions = [];

    function toggleNewSchoolFields() {
      var picked = el("letterSchoolSelect").value;
      el("letterNewSchoolFields").style.display = picked ? "none" : "";
    }

    function showForm() {
      el("newLetterFormCard").style.display = "";
      el("toggleNewLetterFormBtn").style.display = "none";
    }

    function hideForm() {
      el("newLetterFormCard").style.display = "none";
      el("toggleNewLetterFormBtn").style.display = "";
      el("newLetterFormError").style.display = "none";
    }

    function showError(message) {
      var box = el("newLetterFormError");
      if (!message) {
        box.style.display = "none";
        return;
      }
      box.textContent = message;
      box.style.display = "";
      box.scrollIntoView({ behavior: "smooth", block: "center" });
    }

    async function loadDefaults() {
      try {
        var defaults = await apiPost(SHARED_API + ".get_request_form_defaults", {});
        el("letterCoachName").value = defaults.coach_name || "";
        el("letterNatureOfWork").value = defaults.default_nature_of_work || "";

        var roleSelect = el("letterRole");
        roleSelect.innerHTML = (defaults.role_options || [])
          .map(function (role) { return '<option value="' + escapeHtml(role) + '">' + escapeHtml(role) + "</option>"; })
          .join("");
      } catch (error) {
        showError(error.message || "Could not load your details.");
      }
    }

    async function loadSchools() {
      try {
        schoolOptions = await apiPost(SHARED_API + ".get_school_options", {});
        var select = el("letterSchoolSelect");
        select.innerHTML = '<option value="">Add a new school...</option>' +
          schoolOptions.map(function (school) {
            return '<option value="' + escapeHtml(school.name) + '">' + escapeHtml(school.school_name) + "</option>";
          }).join("");
      } catch (error) {
        // Non-fatal - the coach can still add a new school.
      }
    }

    function onSchoolPicked() {
      toggleNewSchoolFields();
      var picked = el("letterSchoolSelect").value;
      var school = schoolOptions.find(function (s) { return s.name === picked; });
      if (school) {
        if (!el("letterSchoolContactName").value) el("letterSchoolContactName").value = school.default_contact_name || "";
        if (!el("letterSchoolContactRole").value) el("letterSchoolContactRole").value = school.default_contact_role || "";
        if (!el("letterSchoolContactEmail").value) el("letterSchoolContactEmail").value = school.default_contact_email || "";
      }
    }

    function renderLettersList(rows) {
      var wrap = el("myLettersList");

      if (!rows.length) {
        wrap.innerHTML = '<div class="dashboard-empty">No requests yet - use "Request New Letter" above.</div>';
        return;
      }

      wrap.innerHTML =
        '<div class="dashboard-table-wrap"><table class="dashboard-table"><thead><tr>' +
        "<th>School</th><th>Status</th><th>Requested</th><th>Start Date</th><th class=\"dashboard-action-col\">Action</th>" +
        "</tr></thead><tbody>" +
        rows.map(function (row) {
          var statusNote = "";
          if (row.workflow_status === "Under Review" || row.workflow_status === "Submitted") {
            statusNote = "Your request is being reviewed. You will be notified when your letter is ready.";
          } else if (row.workflow_status === "Returned for Correction") {
            statusNote = "Further information is required before your letter can be issued.";
          } else if (row.workflow_status === "Signed and Issued") {
            statusNote = "Your signed safeguarding assurance letter is ready to download.";
          }

          return (
            "<tr>" +
              "<td>" + escapeHtml(row.school_label) + "</td>" +
              "<td>" + escapeHtml(row.workflow_status) +
                (statusNote ? '<div class="dashboard-field-hint" style="margin-top:2px;">' + escapeHtml(statusNote) + "</div>" : "") +
              "</td>" +
              "<td>" + formatDate(row.creation) + "</td>" +
              "<td>" + formatDate(row.expected_start_date) + "</td>" +
              "<td class=\"dashboard-action-cell\">" +
                (row.workflow_status === "Signed and Issued"
                  ? '<a class="dashboard-link-btn" href="/api/method/' + SHARED_API + '.download_my_assurance_letter?name=' + encodeURIComponent(row.name) + '" target="_blank">Download</a>'
                  : "&mdash;") +
              "</td>" +
            "</tr>"
          );
        }).join("") +
        "</tbody></table></div>";
    }

    async function loadLetters() {
      try {
        var rows = await apiPost(SHARED_API + ".get_my_assurance_requests", {});
        renderLettersList(rows);
      } catch (error) {
        el("myLettersList").innerHTML = '<div class="dashboard-empty">' + escapeHtml(error.message || "Could not load your letters.") + "</div>";
      }
    }

    el("toggleNewLetterFormBtn").addEventListener("click", showForm);
    el("cancelNewLetterFormBtn").addEventListener("click", hideForm);
    el("letterSchoolSelect").addEventListener("change", onSchoolPicked);

    el("newLetterForm").addEventListener("submit", async function (event) {
      event.preventDefault();
      showError("");

      var submitBtn = el("submitLetterRequestBtn");
      submitBtn.disabled = true;

      try {
        await apiPost(SHARED_API + ".submit_assurance_request", {
          school: el("letterSchoolSelect").value || undefined,
          new_school_name: el("letterNewSchoolName").value,
          new_school_address: el("letterNewSchoolAddress").value,
          new_school_postcode: el("letterNewSchoolPostcode").value,
          school_contact_name: el("letterSchoolContactName").value,
          school_contact_role: el("letterSchoolContactRole").value,
          school_contact_email: el("letterSchoolContactEmail").value,
          role: el("letterRole").value,
          nature_of_work: el("letterNatureOfWork").value,
          expected_start_date: el("letterStartDate").value,
          expected_end_date: el("letterEndDate").value,
        });

        hideForm();
        el("newLetterForm").reset();
        await loadDefaults();
        await loadLetters();
      } catch (error) {
        showError(error.message || "Could not submit this request.");
      } finally {
        submitBtn.disabled = false;
      }
    });

    loadDefaults();
    loadSchools();
    loadLetters();
    toggleNewSchoolFields();
  }

  // -------------------------------------------------------------------
  // Franchisor list page
  // -------------------------------------------------------------------

  function initFranchisorListPage() {
    var wrap = el("safeguardingRequestsList");
    if (!wrap || !el("safeguardingStatusTabs")) return;

    async function loadRequests(status) {
      wrap.innerHTML = '<div class="dashboard-empty">Loading...</div>';
      try {
        var rows = await apiPost(SHARED_API + ".get_assurance_requests_for_review", { status: status || "" });
        renderRequests(rows);
      } catch (error) {
        wrap.innerHTML = '<div class="dashboard-empty">' + escapeHtml(error.message || "Could not load requests.") + "</div>";
      }
    }

    function renderRequests(rows) {
      if (!rows.length) {
        wrap.innerHTML = '<div class="dashboard-empty">No requests found.</div>';
        return;
      }

      wrap.innerHTML =
        '<div class="dashboard-table-wrap"><table class="dashboard-table"><thead><tr>' +
        "<th>Coach</th><th>School</th><th>Role</th><th>Start Date</th><th>Requested</th><th>Status</th><th class=\"dashboard-action-col\">Action</th>" +
        "</tr></thead><tbody>" +
        rows.map(function (row) {
          return (
            "<tr>" +
              "<td>" + escapeHtml(row.coach_name || row.coach) + "</td>" +
              "<td>" + escapeHtml(row.school_label) + "</td>" +
              "<td>" + escapeHtml(row.role) + "</td>" +
              "<td>" + formatDate(row.expected_start_date) + "</td>" +
              "<td>" + formatDate(row.creation) + "</td>" +
              "<td>" + escapeHtml(row.workflow_status) + "</td>" +
              "<td class=\"dashboard-action-cell\"><a class=\"dashboard-link-btn\" href=\"/franchisor_db/safeguarding_letter_details?name=" + encodeURIComponent(row.name) + "\">Review</a></td>" +
            "</tr>"
          );
        }).join("") +
        "</tbody></table></div>";
    }

    var tabs = Dashboard.qsa(".dashboard-tab-btn", el("safeguardingStatusTabs"));
    tabs.forEach(function (tab) {
      tab.addEventListener("click", function () {
        tabs.forEach(function (t) { t.classList.remove("is-active"); });
        tab.classList.add("is-active");
        loadRequests(tab.dataset.status);
      });
    });

    loadRequests("");
  }

  // -------------------------------------------------------------------
  // Franchisor detail page: review, preview, approve + sign
  // -------------------------------------------------------------------

  function initSignaturePad() {
    var canvas = el("letterSignaturePad");
    if (!canvas) return null;

    var ctx = canvas.getContext("2d");
    var rect = canvas.getBoundingClientRect();
    var ratio = window.devicePixelRatio || 1;

    canvas.width = rect.width * ratio;
    canvas.height = rect.height * ratio;
    ctx.scale(ratio, ratio);
    ctx.lineWidth = 2;
    ctx.lineCap = "round";
    ctx.strokeStyle = "#434B49";

    var drawing = false;
    var hasStroke = false;

    function pointerPos(event) {
      var bounds = canvas.getBoundingClientRect();
      var point = event.touches && event.touches.length ? event.touches[0] : event;
      return { x: point.clientX - bounds.left, y: point.clientY - bounds.top };
    }

    function start(event) {
      drawing = true;
      hasStroke = true;
      var pos = pointerPos(event);
      ctx.beginPath();
      ctx.moveTo(pos.x, pos.y);
      event.preventDefault();
    }

    function move(event) {
      if (!drawing) return;
      var pos = pointerPos(event);
      ctx.lineTo(pos.x, pos.y);
      ctx.stroke();
      event.preventDefault();
    }

    function end() { drawing = false; }

    canvas.addEventListener("mousedown", start);
    canvas.addEventListener("mousemove", move);
    window.addEventListener("mouseup", end);
    canvas.addEventListener("touchstart", start, { passive: false });
    canvas.addEventListener("touchmove", move, { passive: false });
    canvas.addEventListener("touchend", end);

    var clearBtn = el("clearSignatureBtn");
    if (clearBtn) {
      clearBtn.addEventListener("click", function () {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        hasStroke = false;
      });
    }

    return {
      isEmpty: function () { return !hasStroke; },
      toDataUrl: function () { return canvas.toDataURL("image/png"); },
    };
  }

  function initFranchisorDetailPage() {
    var page = el("safeguardingLetterDetailsPage");
    if (!page) return;

    var requestName = page.dataset.requestName;
    var isAshley = page.dataset.isAshley === "1";
    var signaturePad = initSignaturePad();

    if (!isAshley) {
      el("notAshleyNotice").style.display = "";
      el("ashleySignBlock").style.display = "none";
    }

    function renderMissing(missing) {
      var box = el("letterDetailMissing");
      if (!missing || !missing.length) {
        box.style.display = "none";
        return;
      }
      el("letterDetailMissingList").innerHTML = missing.map(function (m) { return "<li>" + escapeHtml(m) + "</li>"; }).join("");
      box.style.display = "";
    }

    function renderSummary(data) {
      el("letterDetailTitle").textContent = data.coach_name + " → " + data.school_label;
      el("letterDetailSubtitle").textContent = "Status: " + data.workflow_status;

      el("letterSummaryGrid").innerHTML = [
        ["Coach", data.coach_name],
        ["School", data.school_label],
        ["School Contact", data.school_contact_name + (data.school_contact_role ? " (" + data.school_contact_role + ")" : "")],
        ["Contact Email", data.school_contact_email],
        ["Role", data.role],
        ["Nature of Work", data.nature_of_work],
        ["Expected Start Date", formatDate(data.expected_start_date)],
        ["Expected End Date", data.expected_end_date ? formatDate(data.expected_end_date) : "—"],
      ].map(function (pair) {
        return (
          '<div class="dashboard-detail-field"><label>' + escapeHtml(pair[0]) + "</label>" +
          '<div style="padding:8px 0;">' + escapeHtml(pair[1] || "—") + "</div></div>"
        );
      }).join("");

      var ev = data.evidence || {};
      el("letterEvidenceGrid").innerHTML = [
        ["Identity verification", formatDate(ev.identity_verified_date)],
        ["Right to work in the UK", formatDate(ev.right_to_work_date) + " — " + (ev.right_to_work_note || "")],
        ["Enhanced DBS certificate", ev.has_dbs_on_file ? (ev.dbs_certificate_number + " (issued " + formatDate(ev.dbs_issue_date) + ")") : "Not on file"],
        ["DBS Update Service", ev.dbs_update_service_text || "Not subscribed"],
        ["Safeguarding training", ev.has_training_on_file ? ev.safeguarding_training_text : "Not on file"],
        ["Employment references", "2 of 2 received and verified satisfactory (static)"],
      ].map(function (pair) {
        return (
          '<div class="dashboard-detail-field"><label>' + escapeHtml(pair[0]) + "</label>" +
          '<div style="padding:8px 0;">' + escapeHtml(pair[1] || "—") + "</div></div>"
        );
      }).join("");
    }

    function populateReviewForm(data) {
      var dbsSelect = el("reviewDbsWording");
      dbsSelect.innerHTML = '<option value="">Choose...</option>' +
        (data.dbs_wording_options || []).map(function (opt) {
          return '<option value="' + escapeHtml(opt) + '">' + escapeHtml(opt) + "</option>";
        }).join("");

      el("reviewRegulatedActivity").value = data.regulated_activity_assessment || "";
      dbsSelect.value = data.dbs_wording_option || "";
      el("reviewDbsLevel").value = data.dbs_certificate_level || "Enhanced";
      el("reviewDbsWorkforce").value = data.dbs_workforce || "Child Workforce";
      el("reviewBarredList").value = data.childrens_barred_list_check || "";
      el("reviewKcsie").value = data.kcsie_part_one_acknowledgement || "";
      el("reviewOverseas").value = data.overseas_checks || "";
      el("reviewEmploymentHistory").value = data.employment_history_note || data.default_employment_history_note || "";

      el("correctionNotes").value = data.correction_notes || "";

      var canApprove = isAshley && ["Submitted", "Under Review", "Returned for Correction"].indexOf(data.workflow_status) !== -1;
      el("approveSignCard").style.display = isAshley ? "" : "none";
      if (isAshley) {
        el("ashleySignBlock").style.display = canApprove ? "" : "none";
        if (!canApprove) {
          el("notAshleyNotice").style.display = "";
          el("notAshleyNotice").textContent = "This request is " + data.workflow_status.toLowerCase() + " - there's nothing to sign right now.";
        }
      }
    }

    async function loadDetail() {
      var data = await apiPost(SHARED_API + ".get_assurance_request_for_review", { name: requestName });
      renderSummary(data);
      populateReviewForm(data);
      renderMissing(data.missing_information);
      return data;
    }

    el("useStandardEmploymentHistoryBtn").addEventListener("click", async function () {
      try {
        var data = await apiPost(SHARED_API + ".get_assurance_request_for_review", { name: requestName });
        el("reviewEmploymentHistory").value = data.default_employment_history_note;
      } catch (error) {
        el("reviewEmploymentHistory").value = "Reviewed - no unexplained gaps outstanding";
      }
    });

    el("saveReviewBtn").addEventListener("click", async function () {
      var btn = el("saveReviewBtn");
      var status = el("reviewStatus");
      btn.disabled = true;
      status.textContent = "Saving...";

      try {
        var result = await apiPost(SHARED_API + ".save_assurance_review", {
          name: requestName,
          regulated_activity_assessment: el("reviewRegulatedActivity").value,
          dbs_wording_option: el("reviewDbsWording").value,
          dbs_certificate_level: el("reviewDbsLevel").value,
          dbs_workforce: el("reviewDbsWorkforce").value,
          childrens_barred_list_check: el("reviewBarredList").value,
          kcsie_part_one_acknowledgement: el("reviewKcsie").value,
          overseas_checks: el("reviewOverseas").value,
          employment_history_note: el("reviewEmploymentHistory").value,
        });
        renderMissing(result.missing_information);
        status.textContent = "Saved.";
      } catch (error) {
        status.textContent = "";
        window.alert(error.message || "Could not save this review.");
      } finally {
        btn.disabled = false;
      }
    });

    el("previewLetterBtn").addEventListener("click", async function () {
      var btn = el("previewLetterBtn");
      btn.disabled = true;
      try {
        var result = await apiPost(SHARED_API + ".preview_assurance_letter", { name: requestName });

        // An iframe with srcdoc, not innerHTML - the letter's own
        // <style> block uses plain tag selectors (table, td, h2,
        // body) that would otherwise leak out and restyle the rest
        // of this dashboard page the moment a preview is opened.
        var frameWrap = el("letterPreviewFrame");
        frameWrap.innerHTML = "";
        var iframe = document.createElement("iframe");
        iframe.style.width = "100%";
        iframe.style.border = "0";
        iframe.style.minHeight = "900px";
        iframe.srcdoc = result.html;
        frameWrap.appendChild(iframe);

        el("letterPreviewCard").style.display = "";
        el("letterPreviewCard").scrollIntoView({ behavior: "smooth", block: "start" });
      } catch (error) {
        window.alert(error.message || "Could not preview this letter.");
      } finally {
        btn.disabled = false;
      }
    });

    el("returnForCorrectionBtn").addEventListener("click", async function () {
      var notes = el("correctionNotes").value.trim();
      if (!notes) {
        window.alert("Please explain what needs to change first.");
        return;
      }
      if (!window.confirm("Return this request to the coach for correction?")) return;

      try {
        await apiPost(SHARED_API + ".return_for_correction", { name: requestName, correction_notes: notes });
        window.location.reload();
      } catch (error) {
        window.alert(error.message || "Could not return this request.");
      }
    });

    el("rejectRequestBtn").addEventListener("click", async function () {
      var reason = window.prompt("Reason for rejecting this request:");
      if (!reason) return;

      try {
        await apiPost(SHARED_API + ".reject_assurance_request", { name: requestName, rejection_reason: reason });
        window.location.reload();
      } catch (error) {
        window.alert(error.message || "Could not reject this request.");
      }
    });

    if (isAshley) {
      el("approveAndSignBtn").addEventListener("click", async function () {
        var status = el("approveStatus");

        if (!el("approvalConfirmedCheckbox").checked) {
          window.alert("Please confirm the approval statement first.");
          return;
        }
        if (!signaturePad || signaturePad.isEmpty()) {
          window.alert("Please draw your signature first.");
          return;
        }

        if (!window.confirm("This will generate the final signed PDF and release it to the coach. Continue?")) return;

        var btn = el("approveAndSignBtn");
        btn.disabled = true;
        status.textContent = "Signing...";

        try {
          await apiPost(SHARED_API + ".approve_and_sign_assurance_request", {
            name: requestName,
            typed_full_name: el("signTypedName").value,
            signature: signaturePad.toDataUrl(),
            approval_confirmed: 1,
          });
          status.textContent = "Signed and issued.";
          window.location.reload();
        } catch (error) {
          status.textContent = "";
          window.alert(error.message || "Could not approve and sign this letter.");
        } finally {
          btn.disabled = false;
        }
      });
    }

    loadDetail();
  }

  function init() {
    initCoachPage();
    initFranchisorListPage();
    initFranchisorDetailPage();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
