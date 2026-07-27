(function () {
  "use strict";

  var el = Dashboard.el;
  var qsa = Dashboard.qsa;

  var API = "dashboard.api.shared";

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
      throw new Error(data.message || "There was a problem loading this.");
    }

    return data.message || {};
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

    return data.message || {};
  }

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function formatDateTime(value) {
    if (!value) return "—";
    var date = new Date(String(value).replace(" ", "T"));
    if (Number.isNaN(date.getTime())) return String(value);
    return date.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" }) +
      " " + date.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
  }

  // -------------------------------------------------------------------
  // Client Resources card (coach_db home)
  // -------------------------------------------------------------------

  function renderResourcesCard(summary) {
    var countEl = el("dashboardResourcesCount");
    if (countEl) countEl.textContent = summary.total_resources || 0;

    var categoriesEl = el("dashboardResourcesCategories");
    if (categoriesEl) {
      categoriesEl.innerHTML = (summary.categories || []).map(function (label) {
        return '<span class="dashboard-badge">' + escapeHtml(label) + "</span>";
      }).join("");
    }

    var recentEl = el("dashboardResourcesRecent");
    if (recentEl) {
      var recent = summary.recent_resources || [];
      recentEl.innerHTML = recent.length
        ? recent.map(function (row) {
            return '<div class="dashboard-resources-recent-row">' + escapeHtml(row.document_title) + "</div>";
          }).join("")
        : '<div class="dashboard-resources-recent-row">No resources published yet.</div>';
    }
  }

  async function initResourcesCard() {
    if (!el("dashboardClientResourcesCard")) return;

    try {
      var summary = await apiGet(API + ".practice_documents.get_client_resources_summary");
      renderResourcesCard(summary);
    } catch (err) {
      // Card is decorative on the home dashboard - fail quietly rather
      // than blocking the rest of the dashboard from loading.
    }
  }

  // -------------------------------------------------------------------
  // Client Resources page: tabs
  // -------------------------------------------------------------------

  function initTabs() {
    var buttons = qsa(".dashboard-tab-btn[data-tab-target]");
    if (!buttons.length) return;

    buttons.forEach(function (button) {
      button.addEventListener("click", function () {
        var targetId = button.dataset.tabTarget;

        qsa(".dashboard-tab-btn[data-tab-target]").forEach(function (btn) {
          btn.classList.toggle("is-active", btn === button);
        });

        qsa(".dashboard-tab-panel").forEach(function (panel) {
          panel.classList.toggle("is-active", panel.id === targetId);
        });
      });
    });
  }

  // -------------------------------------------------------------------
  // Client Resources page: library grid + Share modal
  // -------------------------------------------------------------------

  var shareState = {
    document: null,
    recipients: []
  };

  function renderLibrary(resources) {
    var grid = el("clientResourceGrid");
    if (!grid) return;

    if (!resources.length) {
      grid.innerHTML = '<div class="dashboard-empty">No client resources have been published yet.</div>';
      return;
    }

    grid.innerHTML = resources.map(function (doc) {
      var categories = (doc.categories || []).map(function (label) {
        return '<span class="dashboard-badge">' + escapeHtml(label) + "</span>";
      }).join("");

      var fileUrl = doc.attached_file
        ? "/api/method/" + API + ".practice_documents.get_practice_document_file?practice_document_name=" + encodeURIComponent(doc.name)
        : "";

      return (
        '<div class="client-resource-card" data-document="' + escapeHtml(doc.name) + '">' +
          '<div class="client-resource-card-title">' + escapeHtml(doc.document_title) + "</div>" +
          '<div class="client-resource-card-meta">' +
            escapeHtml(doc.document_code || "") + (doc.version ? " · v" + escapeHtml(doc.version) : "") +
            (doc.document_type ? " · " + escapeHtml(doc.document_type) : "") +
          "</div>" +
          (doc.summary ? '<div class="client-resource-card-summary">' + escapeHtml(doc.summary) + "</div>" : "") +
          (categories ? '<div class="client-resource-card-categories">' + categories + "</div>" : "") +
          '<div class="client-resource-card-row"><strong>Shareable With:</strong> ' + escapeHtml(doc.shareable_with || "—") + "</div>" +
          '<div class="client-resource-card-row"><strong>Client Action:</strong> ' + escapeHtml(doc.client_action_required || "None") + "</div>" +
          (doc.sharing_instructions ? '<div class="client-resource-card-row"><strong>Instructions:</strong> ' + escapeHtml(doc.sharing_instructions) + "</div>" : "") +
          '<div class="client-resource-card-actions">' +
            (fileUrl ? '<a class="dashboard-btn dashboard-btn-light" href="' + escapeHtml(fileUrl) + '" target="_blank" rel="noopener">View</a>' : '<span class="dashboard-btn dashboard-btn-light" style="opacity:.5;pointer-events:none;">View</span>') +
            '<button type="button" class="dashboard-btn dashboard-btn-primary share-document-btn" data-document="' + escapeHtml(doc.name) + '">Share with Client</button>' +
          "</div>" +
        "</div>"
      );
    }).join("");

    qsa(".share-document-btn", grid).forEach(function (button) {
      button.addEventListener("click", function () {
        var doc = resources.find(function (row) { return row.name === button.dataset.document; });
        if (doc) openShareModal(doc);
      });
    });
  }

  async function loadLibrary() {
    var grid = el("clientResourceGrid");
    if (!grid) return;

    try {
      var resources = await apiGet(API + ".practice_documents.get_client_resource_library");
      renderLibrary(resources || []);
    } catch (err) {
      grid.innerHTML = '<div class="dashboard-empty">' + escapeHtml(err.message || "Could not load resources.") + "</div>";
    }
  }

  function setShareError(message) {
    var errorEl = el("shareDocumentError");
    if (!errorEl) return;

    if (!message) {
      errorEl.style.display = "none";
      errorEl.textContent = "";
    } else {
      errorEl.style.display = "";
      errorEl.textContent = message;
    }
  }

  async function populateShareClients() {
    var select = el("shareClientSelect");
    if (!select) return;

    select.innerHTML = '<option value="">Loading clients...</option>';

    try {
      var clients = await apiGet(API + ".client_document_share.get_share_target_clients");

      select.innerHTML = '<option value="">Select a client...</option>' + clients.map(function (client) {
        var label = client.full_name || client.name1 || client.name;
        return '<option value="' + escapeHtml(client.name) + '">' + escapeHtml(label) + "</option>";
      }).join("");
    } catch (err) {
      select.innerHTML = '<option value="">Could not load clients</option>';
    }
  }

  async function onShareClientChange() {
    var clientSelect = el("shareClientSelect");
    var recipientSelect = el("shareRecipientSelect");
    if (!clientSelect || !recipientSelect) return;

    var clientName = clientSelect.value;
    setShareError("");

    if (!clientName) {
      recipientSelect.innerHTML = '<option value="">Select a client first...</option>';
      recipientSelect.disabled = true;
      shareState.recipients = [];
      return;
    }

    recipientSelect.disabled = true;
    recipientSelect.innerHTML = '<option value="">Loading recipients...</option>';

    try {
      var recipients = await apiGet(API + ".client_document_share.get_share_recipients", { client_name: clientName });
      shareState.recipients = recipients || [];

      if (!recipients.length) {
        recipientSelect.innerHTML = '<option value="">No authorised contacts with an email found</option>';
        return;
      }

      recipientSelect.innerHTML = '<option value="">Select a recipient...</option>' + recipients.map(function (recipient, index) {
        var label = recipient.name + " (" + recipient.recipient_type + ") — " + recipient.email;
        return '<option value="' + index + '">' + escapeHtml(label) + "</option>";
      }).join("");
      recipientSelect.disabled = false;
    } catch (err) {
      recipientSelect.innerHTML = '<option value="">Could not load recipients</option>';
    }
  }

  function openShareModal(doc) {
    shareState.document = doc;

    el("shareDocumentName").value = doc.name;
    setShareError("");

    var deliveryMethod = el("shareDeliveryMethod");
    if (deliveryMethod) deliveryMethod.value = doc.sharing_method || "Secure Portal Link";

    var message = el("shareCoachMessage");
    if (message) message.value = "";

    var recipientSelect = el("shareRecipientSelect");
    if (recipientSelect) {
      recipientSelect.innerHTML = '<option value="">Select a client first...</option>';
      recipientSelect.disabled = true;
    }

    populateShareClients().then(function () {
      var clientSelect = el("shareClientSelect");
      if (clientSelect) clientSelect.value = "";
    });

    var modal = el("shareDocumentModal");
    if (modal) modal.classList.add("is-open");
    document.body.classList.add("dashboard-modal-open");
  }

  function closeShareModal() {
    var modal = el("shareDocumentModal");
    if (modal) modal.classList.remove("is-open");
    document.body.classList.remove("dashboard-modal-open");
    shareState.document = null;
    shareState.recipients = [];
  }

  async function confirmShare() {
    var clientSelect = el("shareClientSelect");
    var recipientSelect = el("shareRecipientSelect");
    var deliveryMethod = el("shareDeliveryMethod");
    var message = el("shareCoachMessage");
    var confirmButton = el("confirmShareDocumentModal");

    if (!shareState.document) return;

    var clientName = clientSelect ? clientSelect.value : "";
    var recipientIndex = recipientSelect ? recipientSelect.value : "";

    if (!clientName) {
      setShareError("Choose a client.");
      return;
    }

    if (recipientIndex === "") {
      setShareError("Choose a recipient.");
      return;
    }

    var recipient = shareState.recipients[Number(recipientIndex)];
    if (!recipient) {
      setShareError("Choose a recipient.");
      return;
    }

    setShareError("");
    if (confirmButton) {
      confirmButton.disabled = true;
      confirmButton.textContent = "Sending...";
    }

    try {
      await apiPost(API + ".client_document_share.create_share", {
        practice_document: shareState.document.name,
        client: clientName,
        recipient_type: recipient.recipient_type,
        recipient_contact: recipient.contact || "",
        delivery_method: deliveryMethod ? deliveryMethod.value : "Secure Portal Link",
        coach_message: message ? message.value : ""
      });

      closeShareModal();
      loadSharedDocuments();
    } catch (err) {
      setShareError(err.message || "Could not share this document.");
    } finally {
      if (confirmButton) {
        confirmButton.disabled = false;
        confirmButton.textContent = "Send";
      }
    }
  }

  function initShareModal() {
    var modal = el("shareDocumentModal");
    if (!modal) return;

    var closeButton = el("closeShareDocumentModal");
    var cancelButton = el("cancelShareDocumentModal");
    var confirmButton = el("confirmShareDocumentModal");
    var clientSelect = el("shareClientSelect");

    if (closeButton) closeButton.addEventListener("click", closeShareModal);
    if (cancelButton) cancelButton.addEventListener("click", closeShareModal);
    if (confirmButton) confirmButton.addEventListener("click", confirmShare);
    if (clientSelect) clientSelect.addEventListener("change", onShareClientChange);
  }

  // -------------------------------------------------------------------
  // Client Resources page: Shared Documents tab
  // -------------------------------------------------------------------

  function renderSharedDocuments(rows) {
    var body = el("sharedDocumentsTableBody");
    if (!body) return;

    if (!rows.length) {
      body.innerHTML = '<tr><td colspan="9" class="dashboard-empty">Nothing has been shared yet.</td></tr>';
      return;
    }

    body.innerHTML = rows.map(function (row) {
      var actions = [];

      if (row.status !== "Revoked" && (row.delivery_method === "Secure Portal Link" || row.delivery_method === "Email Attachment")) {
        actions.push('<a class="dashboard-link-btn resend-share-btn" data-share="' + escapeHtml(row.name) + '">Resend</a>');
      }

      if (row.secure_link) {
        actions.push('<a class="dashboard-link-btn copy-link-btn" data-link="' + escapeHtml(row.secure_link) + '">Copy Link</a>');
      }

      if (row.status !== "Revoked") {
        actions.push('<a class="dashboard-link-btn revoke-share-btn" data-share="' + escapeHtml(row.name) + '">Revoke</a>');
      }

      if (row.status === "Completed" || row.client_acknowledged) {
        actions.push('<a class="dashboard-link-btn view-completion-btn" data-share="' + escapeHtml(row.name) + '">View Response</a>');
      }

      return (
        "<tr>" +
          "<td>" + escapeHtml(row.document_title) + "</td>" +
          "<td>" + escapeHtml(row.client_label) + "</td>" +
          "<td>" + escapeHtml(row.recipient_name) + " (" + escapeHtml(row.recipient_type) + ")</td>" +
          "<td>" + formatDateTime(row.shared_on) + "</td>" +
          "<td>" + escapeHtml(row.delivery_method) + "</td>" +
          '<td><span class="dashboard-badge share-status-' + escapeHtml(row.status) + '">' + escapeHtml(row.status) + "</span></td>" +
          "<td>" + formatDateTime(row.viewed_on) + "</td>" +
          "<td>" + formatDateTime(row.completed_on) + "</td>" +
          '<td class="dashboard-text-right"><div class="shared-doc-actions">' + actions.join("") + "</div></td>" +
        "</tr>"
      );
    }).join("");

    qsa(".resend-share-btn", body).forEach(function (link) {
      link.addEventListener("click", function () { resendShare(link.dataset.share); });
    });

    qsa(".copy-link-btn", body).forEach(function (link) {
      link.addEventListener("click", function () { copyShareLink(link.dataset.link); });
    });

    qsa(".revoke-share-btn", body).forEach(function (link) {
      link.addEventListener("click", function () { revokeShare(link.dataset.share); });
    });

    qsa(".view-completion-btn", body).forEach(function (link) {
      link.addEventListener("click", function () { viewCompletion(link.dataset.share); });
    });
  }

  async function loadSharedDocuments() {
    var body = el("sharedDocumentsTableBody");
    if (!body) return;

    try {
      var rows = await apiGet(API + ".client_document_share.get_share_history");
      renderSharedDocuments(rows || []);
    } catch (err) {
      body.innerHTML = '<tr><td colspan="9" class="dashboard-empty">' + escapeHtml(err.message || "Could not load shared documents.") + "</td></tr>";
    }
  }

  async function resendShare(shareName) {
    if (!shareName) return;

    try {
      await apiPost(API + ".client_document_share.resend_share", { share_name: shareName });
      loadSharedDocuments();
    } catch (err) {
      window.alert(err.message || "Could not resend this share.");
    }
  }

  async function copyShareLink(link) {
    if (!link) return;

    try {
      await navigator.clipboard.writeText(link);
    } catch (err) {
      window.prompt("Copy this link:", link);
    }
  }

  async function revokeShare(shareName) {
    if (!shareName) return;
    if (!window.confirm("Revoke this link? The recipient will no longer be able to open it.")) return;

    try {
      await apiPost(API + ".client_document_share.revoke_share", { share_name: shareName });
      loadSharedDocuments();
    } catch (err) {
      window.alert(err.message || "Could not revoke this share.");
    }
  }

  async function viewCompletion(shareName) {
    if (!shareName) return;

    var body = el("viewCompletionBody");
    var modal = el("viewCompletionModal");
    if (!body || !modal) return;

    body.innerHTML = "Loading...";
    modal.classList.add("is-open");
    document.body.classList.add("dashboard-modal-open");

    try {
      var completion = await apiGet(API + ".client_document_share.get_share_completion", { share_name: shareName });

      var rows = [
        ["Status", completion.status],
        ["Viewed On", formatDateTime(completion.viewed_on)],
        ["Acknowledged", completion.client_acknowledged ? "Yes" : "No"],
        ["Typed Name", completion.client_typed_name || "—"],
        ["Completed On", formatDateTime(completion.completed_on || completion.client_response_on)]
      ];

      var html = rows.map(function (pair) {
        return '<div class="client-response-field"><label>' + escapeHtml(pair[0]) + "</label>" + escapeHtml(pair[1]) + "</div>";
      }).join("");

      if (completion.client_signature) {
        html += '<div class="client-response-field client-response-signature"><label>Signature</label><img src="' + escapeHtml(completion.client_signature) + '" /></div>';
      }

      if (completion.has_completion_record_pdf) {
        var pdfUrl = "/api/method/" + API + ".client_document_share.get_share_completion_pdf?share_name=" + encodeURIComponent(shareName);
        html += '<div class="client-response-field"><a class="dashboard-btn dashboard-btn-light" href="' + pdfUrl + '" target="_blank" rel="noopener">Download Completion Record PDF</a></div>';
      }

      body.innerHTML = html;
    } catch (err) {
      body.innerHTML = escapeHtml(err.message || "Could not load this response.");
    }
  }

  function closeViewCompletionModal() {
    var modal = el("viewCompletionModal");
    if (modal) modal.classList.remove("is-open");
    document.body.classList.remove("dashboard-modal-open");
  }

  function initViewCompletionModal() {
    var modal = el("viewCompletionModal");
    if (!modal) return;

    var closeButton = el("closeViewCompletionModal");
    var closeFooterButton = el("closeViewCompletionModalFooter");

    if (closeButton) closeButton.addEventListener("click", closeViewCompletionModal);
    if (closeFooterButton) closeFooterButton.addEventListener("click", closeViewCompletionModal);
  }

  function initClientResourcesPage() {
    if (!el("coachClientResourcesPage")) return;

    initTabs();
    initShareModal();
    initViewCompletionModal();

    loadLibrary();
    loadSharedDocuments();
  }

  function init() {
    initResourcesCard();
    initClientResourcesPage();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
