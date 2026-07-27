/**
 * "Documents" - one section per Practice Document Type, listing the
 * current user's own Coach Document Requirement rows of that type
 * (documents_page), and the in-dashboard "Open Document" view for
 * reading/acknowledging/signing one, or allocating it to a client
 * (document_view page). Sections are read dynamically from the Document
 * Type Select options, so adding/renaming a type there is the only thing
 * needed to change what shows up here.
 */
(function () {
  "use strict";

  var el = Dashboard.el;
  var qsa = Dashboard.qsa;

  var API = "dashboard.api.shared.practice_documents";

  var STATUS_CLASS = {
    "Not Viewed": "doc-status-new",
    "Overdue": "doc-status-overdue",
    "Completed": "doc-status-completed",
    "Superseded": "doc-status-superseded"
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
      throw new Error(data.message || "There was a problem saving this.");
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

  function formatDate(value) {
    if (!value) return "";
    var date = new Date(String(value).replace(" ", "T"));
    if (Number.isNaN(date.getTime())) return String(value);
    return date.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
  }

  function formatDateTime(value) {
    if (!value) return "";
    var date = new Date(String(value).replace(" ", "T"));
    if (Number.isNaN(date.getTime())) return String(value);
    return date.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" }) +
      " at " + date.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
  }

  function dashboardBase() {
    var path = window.location.pathname || "";
    if (path.startsWith("/franchisor_db")) return "/franchisor_db";
    if (path.startsWith("/session_worker_db")) return "/session_worker_db";
    return "/coach_db";
  }

  // -------------------------------------------------------------------
  // Documents list page - one table per Document Type tab
  // -------------------------------------------------------------------

  function renderDocumentRow(row) {
    var statusClass = STATUS_CLASS[row.status] || "";
    var viewUrl = dashboardBase() + "/document_view?name=" + encodeURIComponent(row.name);

    return (
      "<tr>" +
        "<td>" +
          '<div class="dashboard-doc-list-title">' + escapeHtml(row.document_title) +
            (row.mandatory ? ' <span class="dashboard-badge">Mandatory</span>' : "") +
          "</div>" +
          '<div class="dashboard-doc-list-meta">' +
            escapeHtml(row.document_code || "") +
            (row.document_version ? " &middot; v" + escapeHtml(row.document_version) : "") +
          "</div>" +
        "</td>" +
        "<td>" + (row.due_date ? escapeHtml(formatDate(row.due_date)) : "&mdash;") + "</td>" +
        '<td><span class="dashboard-badge ' + statusClass + '">' + escapeHtml(row.status) + "</span></td>" +
        '<td class="dashboard-text-right"><a class="dashboard-btn dashboard-btn-primary" href="' + viewUrl + '">Open</a></td>' +
      "</tr>"
    );
  }

  function renderTypeSection(documentType, rows) {
    var body = rows.length
      ? (
          '<table class="dashboard-table dashboard-doc-list-table">' +
            "<thead><tr><th>Document</th><th>Due Date</th><th>Status</th><th class=\"dashboard-text-right\">Action</th></tr></thead>" +
            "<tbody>" + rows.map(renderDocumentRow).join("") + "</tbody>" +
          "</table>"
        )
      : '<div class="dashboard-empty">No ' + escapeHtml(documentType).toLowerCase() + ' documents assigned.</div>';

    return (
      '<div class="dashboard-tab-panel" id="docType_' + escapeHtml(documentType).replace(/[^a-zA-Z0-9]/g, "") + '">' +
        '<div class="dashboard-card">' + body + "</div>" +
      "</div>"
    );
  }

  function activateTab(targetId) {
    qsa(".dashboard-tab-btn[data-tab-target]").forEach(function (button) {
      button.classList.toggle("is-active", button.dataset.tabTarget === targetId);
    });

    qsa(".dashboard-tab-panel").forEach(function (panel) {
      panel.classList.toggle("is-active", panel.id === targetId);
      panel.style.display = panel.id === targetId ? "block" : "none";
    });
  }

  function initTabs(firstTargetId) {
    var tabsWrap = el("documentTypeTabs");
    if (!tabsWrap) return;

    qsa(".dashboard-tab-btn[data-tab-target]", tabsWrap).forEach(function (button) {
      button.addEventListener("click", function () {
        activateTab(button.dataset.tabTarget);
      });
    });

    if (firstTargetId) activateTab(firstTargetId);
  }

  async function loadDocuments() {
    var tabsWrap = el("documentTypeTabs");
    var panelsWrap = el("documentTypePanels");
    if (!tabsWrap || !panelsWrap) return;

    panelsWrap.innerHTML = '<div class="dashboard-empty">Loading documents...</div>';

    var data;
    try {
      data = await apiGet(API + ".get_my_documents_by_type", {});
    } catch (error) {
      panelsWrap.innerHTML = '<div class="dashboard-empty">' + escapeHtml(error.message) + "</div>";
      return;
    }

    var types = data.types || [];
    var documents = data.documents || {};

    if (!types.length) {
      tabsWrap.innerHTML = "";
      panelsWrap.innerHTML = '<div class="dashboard-empty">No document types are configured yet.</div>';
      return;
    }

    tabsWrap.innerHTML = types.map(function (documentType, index) {
      var targetId = "docType_" + documentType.replace(/[^a-zA-Z0-9]/g, "");
      var count = (documents[documentType] || []).length;
      return (
        '<button type="button" class="dashboard-tab-btn' + (index === 0 ? " is-active" : "") + '" data-tab-target="' + targetId + '">' +
          escapeHtml(documentType) + (count ? " (" + count + ")" : "") +
        "</button>"
      );
    }).join("");

    panelsWrap.innerHTML = types.map(function (documentType) {
      return renderTypeSection(documentType, documents[documentType] || []);
    }).join("");

    var firstTargetId = "docType_" + types[0].replace(/[^a-zA-Z0-9]/g, "");
    initTabs(firstTargetId);
  }

  function initDocumentsListPage() {
    if (!el("documentsPage")) return;
    loadDocuments();
  }

  // -------------------------------------------------------------------
  // Document view / completion page
  // -------------------------------------------------------------------

  var signaturePad = null;

  function getRequirementName() {
    var page = el("documentViewPage");
    return page ? page.dataset.requirementName : "";
  }

  function showDocError(message) {
    var box = el("documentViewError");
    if (box) {
      box.textContent = message;
      box.style.display = "block";
    }
  }

  function clearDocError() {
    var box = el("documentViewError");
    if (box) box.style.display = "none";
  }

  function hideCompletionSections() {
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

  function renderSuccessPanel(data) {
    el("docSuccessPanel").style.display = "block";
    setText("docSuccessCompletedOn", "Completed on: " + formatDateTime(data.completed_on));
    setText("docSuccessReference", "Completion reference: " + (data.completion_reference || ""));
  }

  function renderAllocateSection(data) {
    var wrap = el("docAllocateSection");
    if (!wrap) return;

    if (!data.can_allocate_to_client) {
      wrap.style.display = "none";
      return;
    }

    wrap.style.display = "block";
    loadAllocationClients();
  }

  async function loadAllocationClients() {
    var select = el("docAllocateClient");
    if (!select) return;

    select.innerHTML = '<option value="">Loading clients...</option>';

    try {
      var clients = await apiGet(API + ".get_allocation_target_clients", {});
      select.innerHTML = '<option value="">Select a client...</option>' + (clients || []).map(function (client) {
        return '<option value="' + escapeHtml(client.name) + '">' + escapeHtml(client.display_name) + "</option>";
      }).join("");
    } catch (error) {
      select.innerHTML = '<option value="">Could not load clients</option>';
    }
  }

  function bindAllocateForm() {
    var button = el("docAllocateSubmit");
    if (!button) return;

    button.addEventListener("click", async function () {
      var client = el("docAllocateClient").value;
      var recipientType = el("docAllocateRecipientType").value;
      var message = el("docAllocateMessage").value;
      var successBox = el("docAllocateSuccess");

      if (successBox) successBox.style.display = "none";

      if (!client) {
        window.alert("Choose a client.");
        return;
      }

      if (!recipientType) {
        window.alert("Choose a recipient type.");
        return;
      }

      button.disabled = true;
      button.textContent = "Allocating...";

      try {
        await apiPost(API + ".allocate_document_to_client", {
          requirement_name: getRequirementName(),
          client: client,
          recipient_type: recipientType,
          message: message
        });

        if (successBox) {
          successBox.textContent = "Allocated to client.";
          successBox.style.display = "block";
        }
      } catch (error) {
        window.alert(error.message || "Could not allocate this document.");
      } finally {
        button.disabled = false;
        button.textContent = "Allocate to Client";
      }
    });
  }

  function renderDocumentView(data) {
    setText("docTitle", data.document_title);
    setText("docCode", data.document_code);
    setText("docVersion", data.document_version);
    setText("docType", data.document_type);
    setText("docStatus", data.status);

    var dueWrap = el("docDueWrap");
    if (data.due_date && dueWrap) {
      setText("docDue", formatDate(data.due_date));
      dueWrap.style.display = "inline";
    } else if (dueWrap) {
      dueWrap.style.display = "none";
    }

    var mandatoryBadge = el("docMandatoryBadge");
    if (mandatoryBadge) mandatoryBadge.style.display = data.mandatory ? "inline-flex" : "none";

    var openBtn = el("docOpenFileBtn");
    var embed = el("docFileEmbed");
    var fileUrl = "/api/method/" + API + ".get_my_document_file?requirement_name=" + encodeURIComponent(data.name);

    if (data.document_file) {
      if (openBtn) openBtn.href = fileUrl;

      if (/\.pdf(\?|$)/i.test(data.document_file) && embed) {
        embed.src = fileUrl;
        embed.style.display = "block";
      }
    } else if (openBtn) {
      openBtn.style.display = "none";
    }

    if (data.summary) {
      el("docSummaryWrap").style.display = "block";
      setText("docSummary", data.summary);
    }

    if (data.document_text) {
      el("docTextWrap").style.display = "block";
      el("docText").innerHTML = data.document_text;
    }

    hideCompletionSections();

    if (data.docstatus === 1 || data.status === "Completed") {
      renderSuccessPanel(data);
    } else if (data.status === "Superseded") {
      showDocError("This document has been superseded and can no longer be completed.");
    } else if (data.required_action === "Read Only") {
      el("docActionReadOnly").style.display = "block";
      el("docReadConfirmed").checked = !!data.read_confirmed;
    } else if (data.required_action === "Acknowledge") {
      el("docActionAcknowledge").style.display = "block";
      setText("docAcknowledgementDeclaration", data.acknowledgement_declaration || "");
    } else if (data.required_action === "Sign") {
      el("docActionSign").style.display = "block";
      setText("docSignatureDeclaration", data.signature_declaration || "");
      if (!signaturePad) signaturePad = initSignaturePad();
    }

    renderAllocateSection(data);
  }

  async function loadDocumentView() {
    var name = getRequirementName();
    if (!name) return;

    el("documentViewLoading").style.display = "block";
    clearDocError();
    el("documentViewContent").style.display = "none";

    var data;
    try {
      data = await apiGet(API + ".get_my_document_requirement", { requirement_name: name });
    } catch (error) {
      el("documentViewLoading").style.display = "none";
      showDocError(error.message || "You do not have permission to access this document.");
      return;
    }

    el("documentViewLoading").style.display = "none";
    el("documentViewContent").style.display = "block";

    renderDocumentView(data);
  }

  async function submitCompletion(payload) {
    payload.requirement_name = getRequirementName();

    try {
      await apiPost(API + ".complete_my_document_requirement", payload);
      await loadDocumentView();
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

        if (!el("docReadConfirmed").checked) {
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

        if (!el("docAcknowledgementConfirmed").checked) {
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

  function initDocumentViewPage() {
    if (!el("documentViewPage")) return;
    bindCompletionButtons();
    bindAllocateForm();
    loadDocumentView();
  }

  function init() {
    initDocumentsListPage();
    initDocumentViewPage();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
