(function () {
  const SHARED_API = "dashboard.api.shared.invoices";

  var el = Dashboard.el;

  var rows = [];

  function getCsrfToken() {
    const hidden = el("csrfToken");
    if (hidden && hidden.value) return hidden.value;
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta && meta.content ? meta.content : "";
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
      throw new Error(data.message || data._server_messages || "Request failed.");
    }

    return data.message;
  }

  function showAlert(message, indicator) {
    if (window.frappe && typeof window.frappe.show_alert === "function") {
      window.frappe.show_alert({ message: message, indicator: indicator || "green" });
      return;
    }
    window.alert(message);
  }

  function formatMoney(amount, currency) {
    try {
      return new Intl.NumberFormat("en-GB", { style: "currency", currency: currency || "GBP" }).format(amount || 0);
    } catch (e) {
      return (currency || "GBP") + " " + (amount || 0).toFixed(2);
    }
  }

  function escapeHtml(value) {
    return String(value == null ? "" : value).replace(/[&<>"']/g, function (ch) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch];
    });
  }

  function selectedClientNames() {
    return Array.from(document.querySelectorAll(".statements-row-check:checked")).map(function (cb) {
      return cb.value;
    });
  }

  function updateSendSelectedState() {
    const btn = el("statementsSendSelected");
    if (btn) btn.disabled = selectedClientNames().length === 0;
  }

  function renderRows() {
    const tbody = el("statementsTableBody");
    const count = el("statementsCount");
    if (!tbody) return;

    if (count) count.textContent = rows.length + (rows.length === 1 ? " client" : " clients");

    if (!rows.length) {
      tbody.innerHTML = '<tr><td colspan="5" class="dashboard-empty">No outstanding balances.</td></tr>';
      updateSendSelectedState();
      return;
    }

    tbody.innerHTML = rows.map(function (row) {
      return (
        "<tr>" +
          '<td><input type="checkbox" class="statements-row-check" value="' + escapeHtml(row.client) + '"></td>' +
          "<td>" + escapeHtml(row.client_label) + "</td>" +
          "<td>" + escapeHtml(row.invoice_count) + "</td>" +
          '<td class="dashboard-text-right">' + escapeHtml(formatMoney(row.total_outstanding, row.currency)) + "</td>" +
          '<td class="dashboard-text-right"><button type="button" class="dashboard-btn dashboard-btn-light statements-send-one" data-client="' + escapeHtml(row.client) + '">Send Statement</button></td>' +
        "</tr>"
      );
    }).join("");

    updateSendSelectedState();
  }

  function setStatus(message) {
    const status = el("statementsStatus");
    if (!status) return;
    if (!message) {
      status.style.display = "none";
      status.textContent = "";
    } else {
      status.style.display = "block";
      status.textContent = message;
    }
  }

  async function loadBalances() {
    const tbody = el("statementsTableBody");
    if (tbody) tbody.innerHTML = '<tr><td colspan="5" class="dashboard-empty">Loading...</td></tr>';
    setStatus("");

    const coachSelector = el("statementsCoachSelector");
    const selectedCoach = coachSelector ? coachSelector.value : "";

    try {
      const data = await apiPost(SHARED_API + ".get_outstanding_client_balances", { selected_coach: selectedCoach });
      rows = (data && data.rows) || [];
      renderRows();
    } catch (error) {
      if (tbody) tbody.innerHTML = '<tr><td colspan="5" class="dashboard-empty">' + escapeHtml(error.message || "Could not load balances.") + "</td></tr>";
    }
  }

  async function sendStatements(clientNames, confirmMessage) {
    if (!clientNames.length) return;

    if (confirmMessage && !window.confirm(confirmMessage)) return;

    setStatus("Sending " + clientNames.length + (clientNames.length === 1 ? " statement..." : " statements..."));

    try {
      const result = await apiPost(SHARED_API + ".send_client_statements", { client_names: clientNames });
      const sent = (result && result.sent) || 0;
      const failed = (result && result.failed) || [];

      if (!failed.length) {
        showAlert("Sent " + sent + (sent === 1 ? " statement." : " statements."), "green");
        setStatus("");
      } else {
        const failedLabels = failed.map(function (row) { return row.label; }).join(", ");
        setStatus("Sent " + sent + ", but " + failed.length + " failed: " + failedLabels);
        showAlert(sent + " sent, " + failed.length + " failed - see details below.", "orange");
      }

      loadBalances();
    } catch (error) {
      setStatus("");
      showAlert(error.message || "Could not send statements.", "red");
    }
  }

  function initStatementsPage() {
    if (!el("statementsTableBody")) return;

    loadBalances();

    const refreshBtn = el("statementsRefresh");
    if (refreshBtn) refreshBtn.addEventListener("click", loadBalances);

    const coachSelector = el("statementsCoachSelector");
    if (coachSelector) coachSelector.addEventListener("change", loadBalances);

    const selectAll = el("statementsSelectAll");
    if (selectAll) {
      selectAll.addEventListener("change", function () {
        document.querySelectorAll(".statements-row-check").forEach(function (cb) {
          cb.checked = selectAll.checked;
        });
        updateSendSelectedState();
      });
    }

    document.addEventListener("change", function (event) {
      if (event.target && event.target.classList && event.target.classList.contains("statements-row-check")) {
        updateSendSelectedState();
      }
    });

    document.addEventListener("click", function (event) {
      const sendOneBtn = event.target.closest && event.target.closest(".statements-send-one");
      if (sendOneBtn) {
        const client = sendOneBtn.dataset.client;
        const row = rows.find(function (r) { return r.client === client; });
        sendStatements([client], "Send a statement to " + (row ? row.client_label : "this client") + "?");
      }
    });

    const sendSelectedBtn = el("statementsSendSelected");
    if (sendSelectedBtn) {
      sendSelectedBtn.addEventListener("click", function () {
        const names = selectedClientNames();
        sendStatements(names, "Send a statement to " + names.length + " selected client" + (names.length === 1 ? "" : "s") + "?");
      });
    }

    const sendAllBtn = el("statementsSendAll");
    if (sendAllBtn) {
      sendAllBtn.addEventListener("click", function () {
        const names = rows.map(function (r) { return r.client; });
        if (!names.length) {
          showAlert("There are no outstanding balances to send.", "orange");
          return;
        }
        sendStatements(names, "Send a statement to all " + names.length + " clients shown?");
      });
    }
  }

  document.addEventListener("DOMContentLoaded", initStatementsPage);
})();
