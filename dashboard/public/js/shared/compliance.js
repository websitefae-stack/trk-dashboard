/**
 * "My Documents" - dashboard card, /coach-documents list page and
 * /coach-document/<name> completion page. All three surfaces read/write
 * through dashboard.api.shared.compliance, which always scopes to
 * frappe.session.user server-side - nothing here passes "which user" to
 * the server, only which requirement.
 */
(function () {
  "use strict";

  var el = Dashboard.el;
  var qsa = Dashboard.qsa;

  var STATUS_LABELS = {
    "Not Viewed": "New",
    "Viewed": "Viewed",
    "In Progress": "In Progress",
    "Overdue": "Overdue",
    "Completed": "Completed",
    "Superseded": "Superseded"
  };

  var STATUS_CLASS = {
    "Not Viewed": "dashboard-doc-card-status-new",
    "Overdue": "dashboard-doc-card-status-overdue",
    "Completed": "dashboard-doc-card-status-completed",
    "Superseded": "dashboard-doc-card-status-superseded"
  };

  function getCsrfToken() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    return meta && meta.content ? meta.content : "";
  }

  async function apiGet(method, args) {
    var params = new URLSearchParams(args || {});
    var response = await fetch("/api/method/" + method + "?" + params.toString(), {
      method: "GET",
      credentials: "same-origin"
    });

    var data = await response.json();

    if (!response.ok || data.exc) {
      throw new Error(data.message || "There was a problem loading your documents.");
    }

    return data.message;
  }

  async function apiPost(method, args) {
    var response = await fetch("/api/method/" + method, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-Frappe-CSRF-Token": getCsrfToken()
      },
      body: JSON.stringify(args || {})
    });

    var data = await response.json();

    if (!response.ok || data.exc) {
      throw new Error(data.message || "There was a problem submitting this document.");
    }

    return data.message;
  }

  function setText(id, value) {
    var node = el(id);
    if (node) node.textContent = value == null ? "" : value;
  }

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function formatDateDisplay(value) {
    if (!value) return "";
    var date = new Date(value);
    if (isNaN(date.getTime())) return value;
    return date.toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" });
  }

  function formatDateTimeDisplay(value) {
    if (!value) return "";
    var date = new Date(String(value).replace(" ", "T"));
    if (isNaN(date.getTime())) return value;
    var datePart = date.toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" });
    var timePart = date.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", hour12: false });
    return datePart + " at " + timePart;
  }

  // -----------------------------------------------------------------
  // Dashboard card (coach_db / franchisor_db / session_worker_db home)
  // -----------------------------------------------------------------

  async function initMyDocumentsCard() {
    var card = el("myDocumentsCard");
    if (!card) return;

    var summary;
    try {
      summary = await apiGet("dashboard.api.shared.compliance.get_my_document_summary", {});
    } catch (error) {
      return;
    }

    setText("myDocumentsOutstanding", summary.outstanding);
    setText("myDocumentsOverdue", summary.overdue);
    setText("myDocumentsCompleted", summary.completed);

    var badge = el("myDocumentsBadge");
    if (badge) {
      if (summary.outstanding > 0) {
        badge.style.display = "inline-flex";
        badge.textContent = summary.outstanding;
      } else {
        badge.style.display = "none";
      }
    }

    var overdueStat = el("myDocumentsOverdueStat");
    if (overdueStat) {
      overdueStat.classList.toggle("dashboard-mydocs-stat-overdue", summary.overdue > 0);
    }

    var nextDueWrap = el("myDocumentsNextDueWrap");
    var upToDate = el("myDocumentsUpToDate");

    if (summary.outstanding === 0) {
      if (upToDate) upToDate.style.display = "block";
      if (nextDueWrap) nextDueWrap.style.display = "none";
    } else {
      if (upToDate) upToDate.style.display = "none";
      if (summary.next_due_date && nextDueWrap) {
        nextDueWrap.style.display = "block";
        setText("myDocumentsNextDue", formatDateDisplay(summary.next_due_date));
      } else if (nextDueWrap) {
        nextDueWrap.style.display = "none";
      }
    }
  }

  // -----------------------------------------------------------------
  // /coach-documents list page
  // -----------------------------------------------------------------

  var currentTab = "outstanding";
  var lastSummary = null;

  function renderDocCard(row) {
    var statusClass = STATUS_CLASS[row.status] || "";
    var dueLine = row.due_date ? "Due: " + formatDateDisplay(row.due_date) : "No due date";
    var categories = (row.categories || []).join(", ");

    return (
      '<div class="dashboard-doc-card">' +
        '<div class="dashboard-doc-card-header">' +
          '<div class="dashboard-doc-card-title">' + escapeHtml(row.document_title) + "</div>" +
          '<span class="dashboard-doc-card-status ' + statusClass + '">' + escapeHtml(row.status_label) + "</span>" +
        "</div>" +
        '<div class="dashboard-doc-card-meta">' +
          "<span>Code: " + escapeHtml(row.document_code || "") + "</span>" +
          "<span>Version: " + escapeHtml(row.document_version || "") + "</span>" +
          "<span>Type: " + escapeHtml(row.document_type || "") + "</span>" +
          "<span>Action required: " + escapeHtml(row.required_action || "") + "</span>" +
          "<span>" + escapeHtml(dueLine) + "</span>" +
          (row.mandatory ? '<span class="dashboard-doc-card-mandatory">Mandatory</span>' : "") +
        "</div>" +
        (categories ? '<div class="dashboard-doc-card-categories">Categories: ' + escapeHtml(categories) + "</div>" : "") +
        '<div class="dashboard-doc-card-actions">' +
          '<a class="dashboard-btn dashboard-btn-primary" href="/coach-document/' + encodeURIComponent(row.name) + '">Open Document</a>' +
        "</div>" +
      "</div>"
    );
  }

  async function refreshSummaryCards() {
    lastSummary = await apiGet("dashboard.api.shared.compliance.get_my_document_summary", {});
    setText("coachDocumentsSummaryOutstanding", lastSummary.outstanding);
    setText("coachDocumentsSummaryOverdue", lastSummary.overdue);
    setText("coachDocumentsSummaryCompleted", lastSummary.completed);
    setText("coachDocumentsSummaryTotal", lastSummary.total);
    return lastSummary;
  }

  async function loadDocList(tab) {
    var listEl = el("coachDocumentsList");
    if (!listEl) return;

    listEl.innerHTML = '<div class="dashboard-empty">Loading documents...</div>';

    var rows;
    try {
      rows = await apiGet("dashboard.api.shared.compliance.get_my_documents", { status_group: tab });
    } catch (error) {
      listEl.innerHTML = '<div class="dashboard-doc-error">' + escapeHtml(error.message) + "</div>";
      return;
    }

    if (!rows.length) {
      var message = "No documents to show.";

      if (tab === "outstanding") {
        message = (lastSummary && lastSummary.total > 0)
          ? "You are up to date. All assigned documents have been completed."
          : "You do not currently have any documents to complete.";
      }

      listEl.innerHTML = '<div class="dashboard-empty">' + escapeHtml(message) + "</div>";
      return;
    }

    listEl.innerHTML = rows.map(renderDocCard).join("");
  }

  function initDocumentsTabs() {
    var tabsWrap = el("coachDocumentsTabs");
    if (!tabsWrap) return;

    var buttons = qsa(".dashboard-tab-btn[data-tab-target]", tabsWrap);

    buttons.forEach(function (button) {
      button.addEventListener("click", function () {
        buttons.forEach(function (b) { b.classList.remove("is-active"); });
        button.classList.add("is-active");
        currentTab = button.dataset.tabTarget;
        loadDocList(currentTab);
      });
    });
  }

  async function initDocumentsListPage() {
    if (!el("coachDocumentsPage")) return;

    initDocumentsTabs();
    await refreshSummaryCards();
    loadDocList(currentTab);
  }

  // -----------------------------------------------------------------
  // /coach-document/<name> completion page
  // -----------------------------------------------------------------

  var signaturePad = null;

  function getRequirementName() {
    var page = el("coachDocumentPage");
    return page ? page.dataset.requirementName : "";
  }

  function showDocError(message) {
    var box = el("coachDocumentError");
    if (box) {
      box.textContent = message;
      box.style.display = "block";
    }
  }

  function clearDocError() {
    var box = el("coachDocumentError");
    if (box) box.style.display = "none";
  }

  function hideAllCompletionSections() {
    ["docActionReadOnly", "docActionAcknowledge", "docActionSign", "docSuccessPanel"].forEach(function (id) {
      var node = el(id);
      if (node) node.style.display = "none";
    });
  }

  function initSignaturePad() {
    var canvas = el("docSignaturePad");
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

    function end() {
      drawing = false;
    }

    canvas.addEventListener("mousedown", start);
    canvas.addEventListener("mousemove", move);
    window.addEventListener("mouseup", end);
    canvas.addEventListener("touchstart", start, { passive: false });
    canvas.addEventListener("touchmove", move, { passive: false });
    canvas.addEventListener("touchend", end);

    var clearBtn = el("docSignatureClear");
    if (clearBtn) {
      clearBtn.addEventListener("click", function () {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        hasStroke = false;
      });
    }

    return {
      isEmpty: function () { return !hasStroke; },
      toDataUrl: function () { return canvas.toDataURL("image/png"); }
    };
  }

  function setDueDisplay(row) {
    var wrap = el("docDueWrap");
    if (row.due_date) {
      setText("docDue", formatDateDisplay(row.due_date));
      if (wrap) wrap.style.display = "inline";
    } else if (wrap) {
      wrap.style.display = "none";
    }
  }

  function renderSuccessPanel(data) {
    el("docSuccessPanel").style.display = "block";
    setText("docSuccessCompletedOn", "Completed on: " + formatDateTimeDisplay(data.completed_on));
    setText("docSuccessCompletedBy", "Completed by: " + (data.completed_by || ""));
    setText("docSuccessReference", "Completion reference: " + (data.completion_reference || ""));

    if (data.required_action === "Read Only" && data.read_confirmed_on) {
      el("docSuccessReadOn").style.display = "block";
      setText("docSuccessReadOn", "Read confirmed on: " + formatDateTimeDisplay(data.read_confirmed_on));
    }

    if (data.required_action === "Acknowledge" && data.acknowledged_on) {
      el("docSuccessAcknowledgedOn").style.display = "block";
      setText("docSuccessAcknowledgedOn", "Acknowledged on: " + formatDateTimeDisplay(data.acknowledged_on));
    }

    if (data.required_action === "Sign" && data.signed_on) {
      el("docSuccessSignedOn").style.display = "block";
      setText("docSuccessSignedOn", (data.typed_full_name || "") + " - signed on: " + formatDateTimeDisplay(data.signed_on));

      if (data.signature) {
        el("docSuccessSignatureWrap").style.display = "block";
        el("docSuccessSignatureImg").src = data.signature;
      }
    }
  }

  function renderDocumentDetail(data) {
    setText("docTitle", data.document_title);
    setText("docCode", data.document_code);
    setText("docVersion", data.document_version);
    setText("docType", data.document_type);
    setText("docStatus", STATUS_LABELS[data.status] || data.status);
    setDueDisplay(data);

    var mandatoryBadge = el("docMandatoryBadge");
    if (mandatoryBadge) mandatoryBadge.style.display = data.mandatory ? "inline-flex" : "none";

    var fileActions = el("docFileActions");
    var openBtn = el("docOpenFileBtn");
    var embed = el("docFileEmbed");

    if (data.document_file) {
      if (fileActions) fileActions.style.display = "flex";
      if (openBtn) openBtn.href = data.document_file;

      if (/\.pdf(\?|$)/i.test(data.document_file) && embed) {
        embed.src = data.document_file;
        embed.style.display = "block";
      }
    }

    if (data.practice_document_summary) {
      el("docSummaryWrap").style.display = "block";
      setText("docSummary", data.practice_document_summary);
    }

    if (data.practice_document_text) {
      el("docTextWrap").style.display = "block";
      el("docText").innerHTML = data.practice_document_text;
    }

    hideAllCompletionSections();

    if (data.status === "Completed") {
      renderSuccessPanel(data);
      return;
    }

    if (data.status === "Superseded") {
      showDocError("This document has been superseded and can no longer be completed.");
      return;
    }

    if (data.required_action === "Read Only") {
      el("docActionReadOnly").style.display = "block";
    } else if (data.required_action === "Acknowledge") {
      el("docActionAcknowledge").style.display = "block";
      setText("docAcknowledgementDeclaration", data.acknowledgement_declaration || "");
    } else if (data.required_action === "Sign") {
      el("docActionSign").style.display = "block";
      setText("docSignatureDeclaration", data.signature_declaration || "");
      if (!signaturePad) signaturePad = initSignaturePad();
    }
  }

  async function loadDocumentDetail() {
    var name = getRequirementName();
    if (!name) return;

    el("coachDocumentLoading").style.display = "block";
    clearDocError();
    el("coachDocumentContent").style.display = "none";

    var data;
    try {
      data = await apiGet("dashboard.api.shared.compliance.get_my_document_requirement", { requirement_name: name });
    } catch (error) {
      el("coachDocumentLoading").style.display = "none";
      showDocError(error.message || "You do not have permission to access this document.");
      return;
    }

    el("coachDocumentLoading").style.display = "none";
    el("coachDocumentContent").style.display = "block";

    renderDocumentDetail(data);

    if (data.status !== "Completed" && data.status !== "Superseded") {
      try {
        await apiPost("dashboard.api.shared.compliance.mark_document_viewed", { requirement_name: name });
      } catch (error) {
        // View tracking is best-effort - never blocks reading/completing the document.
      }
    }
  }

  async function submitCompletion(payload) {
    var name = getRequirementName();
    payload.requirement_name = name;

    try {
      var result = await apiPost("dashboard.api.shared.compliance.complete_document_requirement", payload);
      await loadDocumentDetail();
      return result;
    } catch (error) {
      showDocError(error.message || "There was a problem submitting this document.");
      throw error;
    }
  }

  function bindCompletionButtons() {
    var readBtn = el("docSubmitReadOnly");
    if (readBtn) {
      readBtn.addEventListener("click", function () {
        clearDocError();
        var checked = el("docReadConfirmed").checked;

        if (!checked) {
          showDocError("Please confirm you have read this document before submitting.");
          return;
        }

        readBtn.disabled = true;
        submitCompletion({ read_confirmed: 1 }).catch(function () {}).finally(function () {
          readBtn.disabled = false;
        });
      });
    }

    var ackBtn = el("docSubmitAcknowledge");
    if (ackBtn) {
      ackBtn.addEventListener("click", function () {
        clearDocError();
        var checked = el("docAcknowledgementConfirmed").checked;

        if (!checked) {
          showDocError("Please confirm the acknowledgement before submitting.");
          return;
        }

        ackBtn.disabled = true;
        submitCompletion({ acknowledgement_confirmed: 1 }).catch(function () {}).finally(function () {
          ackBtn.disabled = false;
        });
      });
    }

    var signBtn = el("docSubmitSign");
    if (signBtn) {
      signBtn.addEventListener("click", function () {
        clearDocError();
        var typedName = (el("docTypedFullName").value || "").trim();
        var confirmed = el("docSignatureConfirmed").checked;

        if (!typedName) {
          showDocError("Please enter your full name before submitting.");
          return;
        }

        if (!signaturePad || signaturePad.isEmpty()) {
          showDocError("Please sign the document before submitting.");
          return;
        }

        if (!confirmed) {
          showDocError("Please confirm the declaration before submitting.");
          return;
        }

        signBtn.disabled = true;
        submitCompletion({
          typed_full_name: typedName,
          signature: signaturePad.toDataUrl(),
          signature_confirmed: 1
        }).catch(function () {}).finally(function () {
          signBtn.disabled = false;
        });
      });
    }
  }

  async function initDocumentDetailPage() {
    if (!el("coachDocumentPage")) return;

    bindCompletionButtons();
    await loadDocumentDetail();
  }

  // -----------------------------------------------------------------

  function init() {
    initMyDocumentsCard();
    initDocumentsListPage();
    initDocumentDetailPage();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  window.addEventListener("pageshow", function () {
    if (el("myDocumentsCard")) initMyDocumentsCard();
  });
})();
