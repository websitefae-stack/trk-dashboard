(function () {
  function el(id) {
    return document.getElementById(id);
  }

  function qsa(selector, root) {
    return Array.from((root || document).querySelectorAll(selector));
  }

  function getCsrfToken() {
    const hidden = el("csrfToken");
    if (hidden && hidden.value) return hidden.value;

    const meta = document.querySelector('meta[name="csrf-token"]');
    if (meta && meta.content) return meta.content;

    return "";
  }

  function parseServerMessages(serverMessages) {
    if (!serverMessages) return "";

    try {
      const decoded = JSON.parse(serverMessages);
      if (!Array.isArray(decoded) || !decoded.length) return "";

      return decoded
        .map((msg) => {
          try {
            const parsed = JSON.parse(msg);
            return parsed.message || msg;
          } catch (e) {
            return msg;
          }
        })
        .join("<br>");
    } catch (e) {
      return "";
    }
  }

  function showSuccess(message) {
    if (window.frappe && typeof window.frappe.show_alert === "function") {
      window.frappe.show_alert({ message, indicator: "green" });
      return;
    }

    console.log(message);
  }

  function showError(messageHtml) {
    if (window.frappe && typeof window.frappe.msgprint === "function") {
      window.frappe.msgprint(messageHtml);
      return;
    }

    const temp = document.createElement("div");
    temp.innerHTML = messageHtml;
    window.alert(temp.textContent || "There was a problem.");
  }

  async function apiPost(method, args) {
    const body = new URLSearchParams();

    Object.entries(args || {}).forEach(([key, value]) => {
      if (typeof value === "string") {
        body.append(key, value);
      } else {
        body.append(key, JSON.stringify(value));
      }
    });

    const response = await fetch(`/api/method/${method}`, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Frappe-CSRF-Token": getCsrfToken()
      },
      body: body.toString()
    });

    let data = {};
    try {
      data = await response.json();
    } catch (e) {
      throw new Error("Could not read server response.");
    }

    if (!response.ok || data.exc) {
      const serverMessage = parseServerMessages(data._server_messages);
      throw new Error(serverMessage || data.message || "There was a problem with the request.");
    }

    return data;
  }

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function formatDate(value) {
    return value ? escapeHtml(value) : "—";
  }

  function formatStartTime(value) {
    if (!value) return "—";

    const text = String(value).trim();

    if (text.includes(" - ")) return escapeHtml(text.split(" - ")[0].trim());
    if (text.includes("–")) return escapeHtml(text.split("–")[0].trim());
    if (text.includes("-")) return escapeHtml(text.split("-")[0].trim());

    return escapeHtml(text);
  }

  function renderSimpleTable(bodyId, rows, emptyMessage, columns) {
    const body = el(bodyId);
    if (!body) return;

    if (!rows || !rows.length) {
      body.innerHTML = `<tr><td colspan="${columns}" class="dashboard-empty">${emptyMessage}</td></tr>`;
      return;
    }

    body.innerHTML = rows.join("");
  }

  function initTabs(storageKey) {
    const buttons = qsa(".dashboard-tab-btn");
    if (!buttons.length) return;

    function saveActiveTab(targetId) {
      if (!targetId || !storageKey) return;

      try {
        sessionStorage.setItem(storageKey, targetId);
      } catch (e) {
        console.warn("Could not save active tab", e);
      }
    }

    function getSavedActiveTab() {
      if (!storageKey) return "";

      try {
        return sessionStorage.getItem(storageKey) || "";
      } catch (e) {
        return "";
      }
    }

    function activateTab(targetId) {
      if (!targetId) return;

      qsa(".dashboard-tab-btn").forEach((button) => {
        button.classList.toggle("is-active", button.dataset.tabTarget === targetId);
      });

      qsa(".dashboard-tab-panel").forEach((panel) => {
        panel.classList.toggle("is-active", panel.id === targetId);
      });

      saveActiveTab(targetId);

      document.dispatchEvent(
        new CustomEvent("trk-dashboard-tab-active", {
          detail: { targetId }
        })
      );
    }

    buttons.forEach((button) => {
      if (button.dataset.boundTab === "1") return;

      button.dataset.boundTab = "1";
      button.addEventListener("click", function (event) {
        event.preventDefault();
        activateTab(button.dataset.tabTarget);
      });
    });

    const savedTab = getSavedActiveTab();
    const savedButton = savedTab ? buttons.find((button) => button.dataset.tabTarget === savedTab) : null;
    const firstButton = buttons[0];

    if (savedButton && savedButton.dataset.tabTarget) {
      activateTab(savedButton.dataset.tabTarget);
    } else if (firstButton && firstButton.dataset.tabTarget) {
      activateTab(firstButton.dataset.tabTarget);
    }
  }

  window.TRKClientDetails = {
    apiPost,
    el,
    escapeHtml,
    formatDate,
    formatStartTime,
    initTabs,
    qsa,
    renderSimpleTable,
    showError,
    showSuccess
  };
})();
