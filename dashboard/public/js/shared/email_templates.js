(function () {
  "use strict";

  var el = window.Dashboard ? window.Dashboard.el : function (id) { return document.getElementById(id); };

  const API = "dashboard.api.shared.email_templates";

  function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta && meta.content ? meta.content : "";
  }

  async function apiPost(method, args) {
    const response = await fetch(`/api/method/${method}`, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-Frappe-CSRF-Token": getCsrfToken(),
      },
      body: JSON.stringify(args || {}),
    });

    const data = await response.json();

    if (!response.ok || data.exc) {
      throw new Error(data.message || "There was a problem.");
    }

    return data.message;
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function templateRowHtml(template) {
    const deskUrl = "/app/email-template/" + encodeURIComponent(template.name);
    const statusBadge = template.has_content
      ? `<span class="dashboard-badge dashboard-status-active">Written</span>`
      : `<span class="dashboard-badge dashboard-status-failed">Empty - needs copy</span>`;

    return `
      <div class="dashboard-card" style="display:flex; align-items:center; justify-content:space-between; gap:16px; margin-bottom:10px;" data-template-row="${escapeHtml(template.name)}">
        <div>
          <strong>${escapeHtml(template.name)}</strong>
          <div>${statusBadge}</div>
        </div>
        <div style="display:flex; gap:8px; align-items:center;">
          <a class="dashboard-btn dashboard-btn-light" href="${deskUrl}" target="_blank" rel="noopener noreferrer">Open in Desk</a>
          <button type="button" class="dashboard-btn dashboard-btn-primary email-template-test-btn" data-template="${escapeHtml(template.name)}">Send Test</button>
        </div>
      </div>
    `;
  }

  async function loadTemplates() {
    const wrap = el("emailTemplateList");
    if (!wrap) return;

    wrap.innerHTML = `<p class="dashboard-field-hint">Loading...</p>`;

    try {
      const templates = await apiPost(`${API}.list_email_templates`, {});

      if (!templates || !templates.length) {
        wrap.innerHTML = `<div class="dashboard-card">No Email Templates found on this site yet.</div>`;
        return;
      }

      wrap.innerHTML = templates.map(templateRowHtml).join("");

      wrap.querySelectorAll(".email-template-test-btn").forEach((btn) => {
        btn.addEventListener("click", function () {
          sendTest(btn.dataset.template, btn);
        });
      });
    } catch (error) {
      wrap.innerHTML = `<div class="dashboard-card">Could not load templates: ${escapeHtml(error.message || "")}</div>`;
    }
  }

  async function sendTest(templateName, btn) {
    const addressInput = el("emailTemplateTestAddress");
    const testEmail = (addressInput && addressInput.value || "").trim();

    if (!testEmail) {
      alert("Enter an email address at the top of the page first.");
      return;
    }

    const originalLabel = btn.textContent;
    btn.disabled = true;
    btn.textContent = "Sending...";

    try {
      const result = await apiPost(`${API}.send_test_email`, {
        template_name: templateName,
        test_email: testEmail,
      });
      btn.textContent = `Sent to ${result.sent_to}`;
      setTimeout(() => { btn.textContent = originalLabel; btn.disabled = false; }, 2500);
    } catch (error) {
      alert(error.message || "Could not send the test email.");
      btn.textContent = originalLabel;
      btn.disabled = false;
    }
  }

  async function loadVolumeStats() {
    const wrap = el("emailVolumeStats");
    if (!wrap) return;

    try {
      const stats = await apiPost("dashboard.api.shared.mail_throttle.get_email_volume", {});
      const nearLimit = stats.sent_last_hour >= stats.hourly_budget;
      wrap.innerHTML = `
        <strong${nearLimit ? ' style="color:#C0392B;"' : ""}>${stats.sent_last_hour}</strong> sent in the last hour
        (safety budget: ${stats.hourly_budget}/hour, Titan's own cap is 50/hour) &middot;
        <strong>${stats.sent_today}</strong> sent today &middot;
        <strong>${stats.sent_last_24h}</strong> sent in the last 24 hours
      `;
    } catch (error) {
      wrap.textContent = "Could not load email volume: " + (error.message || "");
    }
  }

  function init() {
    if (!el("emailTemplateList")) return;
    loadTemplates();
    loadVolumeStats();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
