(function () {
  "use strict";

  var el = Dashboard.el;

  const STOCK_API = "dashboard.api.shared.coach_stock";
  const COACH_LOG_API = "dashboard.api.shared.coach_logs";

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
      throw new Error(Dashboard.extractErrorMessage(data, "There was a problem."));
    }

    return data.message || {};
  }

  function escapeHtml(value) {
    const div = document.createElement("div");
    div.textContent = value === null || value === undefined ? "" : String(value);
    return div.innerHTML;
  }

  // ===================================================================
  // Coach-facing page (/coach_db/stock) - also reached by a franchisor
  // in "view as coach" mode, same convention every other coach_db page
  // uses (see e.g. links/index.html's identical data-view-mode/
  // data-view-as attributes on #linksPage).
  // ===================================================================

  function initCoachStockPage() {
    const page = el("stockPage");
    if (!page) return;

    const viewAsCoach = page.dataset.viewAs || "";

    async function loadBalances() {
      const bodyEl = el("stockBalancesTableBody");
      try {
        const balances = await apiPost(`${STOCK_API}.get_coach_stock_balances`, viewAsCoach ? { coach: viewAsCoach } : {});
        bodyEl.innerHTML = balances.length
          ? balances.map(function (row) {
              return `<tr><td>${escapeHtml(row.item_name)}</td><td>${escapeHtml(row.balance)}</td></tr>`;
            }).join("")
          : `<tr><td colspan="2" class="dashboard-empty">No stock movements recorded yet.</td></tr>`;
      } catch (error) {
        bodyEl.innerHTML = `<tr><td colspan="2" class="dashboard-empty">${escapeHtml(error.message || "Could not load stock.")}</td></tr>`;
      }
    }

    function pendingRowHtml(client) {
      return `
        <div class="dashboard-card" data-pending-client="${escapeHtml(client.name)}" style="margin-bottom:10px;">
          <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px;">
            <div>
              <strong>${escapeHtml(client.full_name || client.name)}</strong>
              <span class="dashboard-help">(${escapeHtml(client.client_type)})</span>
            </div>
            <div style="display:flex; gap:8px; flex-wrap:wrap;">
              <button type="button" class="dashboard-btn dashboard-btn-primary" data-handover-action="Given">Given</button>
              <button type="button" class="dashboard-btn dashboard-btn-light" data-handover-action="Could Not Give - Out of Stock">Out of Stock</button>
              <button type="button" class="dashboard-btn dashboard-btn-light" data-handover-action="Not Given - Other Reason">Other Reason</button>
            </div>
          </div>
          <div class="dashboard-handover-reason" style="display:none; margin-top:10px;">
            <textarea class="dashboard-input" rows="2" placeholder="Reason"></textarea>
            <div style="margin-top:8px;">
              <button type="button" class="dashboard-btn dashboard-btn-primary" data-handover-confirm-reason>Confirm</button>
              <button type="button" class="dashboard-btn dashboard-btn-light" data-handover-cancel-reason>Cancel</button>
            </div>
          </div>
          <div class="dashboard-help dashboard-handover-message" style="color:#C01C3E; margin-top:8px;"></div>
        </div>
      `;
    }

    async function submitHandover(cardEl, clientName, status, reason) {
      const messageEl = cardEl.querySelector(".dashboard-handover-message");
      const buttons = cardEl.querySelectorAll("[data-handover-action]");

      buttons.forEach(function (button) { button.disabled = true; });
      if (messageEl) messageEl.textContent = "";

      try {
        await apiPost(`${STOCK_API}.record_pack_handover`, { client: clientName, status: status, reason: reason || "" });
        // Optimistic removal - this client no longer belongs on the
        // worklist now a handover's been recorded for them.
        cardEl.remove();
        if (!el("pendingHandoverList").children.length) {
          el("pendingHandoverList").innerHTML = `<p class="dashboard-empty">Nothing pending - every Kid/Teen client has a handover recorded.</p>`;
        }
        loadBalances();
      } catch (error) {
        if (messageEl) messageEl.textContent = error.message || "Could not record this.";
        buttons.forEach(function (button) { button.disabled = false; });
      }
    }

    function wirePendingCard(cardEl, clientName) {
      const reasonWrap = cardEl.querySelector(".dashboard-handover-reason");
      const reasonInput = reasonWrap ? reasonWrap.querySelector("textarea") : null;

      cardEl.querySelectorAll("[data-handover-action]").forEach(function (button) {
        button.addEventListener("click", function () {
          const status = button.dataset.handoverAction;

          if (status === "Not Given - Other Reason") {
            if (reasonWrap) reasonWrap.style.display = "block";
            return;
          }

          submitHandover(cardEl, clientName, status, "");
        });
      });

      cardEl.querySelector("[data-handover-confirm-reason]")?.addEventListener("click", function () {
        const reason = (reasonInput && reasonInput.value || "").trim();
        if (!reason) {
          if (reasonInput) reasonInput.focus();
          return;
        }
        submitHandover(cardEl, clientName, "Not Given - Other Reason", reason);
      });

      cardEl.querySelector("[data-handover-cancel-reason]")?.addEventListener("click", function () {
        if (reasonWrap) reasonWrap.style.display = "none";
      });
    }

    async function loadPending() {
      const listEl = el("pendingHandoverList");
      try {
        const pending = await apiPost(`${STOCK_API}.get_pending_pack_handovers`, viewAsCoach ? { coach: viewAsCoach } : {});

        listEl.innerHTML = pending.length
          ? pending.map(pendingRowHtml).join("")
          : `<p class="dashboard-empty">Nothing pending - every Kid/Teen client has a handover recorded.</p>`;

        pending.forEach(function (client) {
          const cardEl = listEl.querySelector(`[data-pending-client="${client.name}"]`);
          if (cardEl) wirePendingCard(cardEl, client.name);
        });
      } catch (error) {
        listEl.innerHTML = `<p class="dashboard-empty">${escapeHtml(error.message || "Could not load the worklist.")}</p>`;
      }
    }

    loadBalances();
    loadPending();
  }

  // ===================================================================
  // Franchisor-facing page (/franchisor_db/stock)
  // ===================================================================

  function initFranchisorStockPage() {
    if (!el("stockComplianceTableBody")) return;

    let cachedCoachOptions = [];
    let cachedItemOptions = [];

    function complianceRowHtml(row) {
      const counts = row.status_counts || {};
      const stockText = (row.stock_balances || []).length
        ? row.stock_balances.map(function (b) { return `${b.item_name}: ${b.balance}`; }).join(", ")
        : "—";

      return `
        <tr>
          <td>${escapeHtml(row.coach_name)}</td>
          <td>${escapeHtml(counts["Given"] || 0)}</td>
          <td>${escapeHtml(counts["Could Not Give - Out of Stock"] || 0)}</td>
          <td>${escapeHtml(counts["Not Given - Other Reason"] || 0)}</td>
          <td>${escapeHtml(counts["Not Recorded"] || 0)}</td>
          <td>${escapeHtml(stockText)}</td>
        </tr>
      `;
    }

    async function loadComplianceReport() {
      const bodyEl = el("stockComplianceTableBody");
      try {
        const rows = await apiPost(`${STOCK_API}.get_pack_compliance_report`, {});
        bodyEl.innerHTML = rows.length
          ? rows.map(complianceRowHtml).join("")
          : `<tr><td colspan="6" class="dashboard-empty">No coach has a Kid/Teen client yet.</td></tr>`;
      } catch (error) {
        bodyEl.innerHTML = `<tr><td colspan="6" class="dashboard-empty">${escapeHtml(error.message || "Could not load the report.")}</td></tr>`;
      }
    }

    // Per-coach drill-down behind each row's View button - current
    // balances plus the two histories behind them (who they've actually
    // given a pack to, and every stock order that topped them up).
    function coachStockDetailRow(cells) {
      return `<tr>${cells.map(function (cell) { return `<td>${cell}</td>`; }).join("")}</tr>`;
    }

    async function openCoachStockDetail(coach) {
      const modal = el("coachStockDetailModal");
      const titleEl = el("coachStockDetailTitle");
      const balancesBody = el("coachStockDetailBalancesBody");
      const givenBody = el("coachStockDetailGivenBody");
      const ordersBody = el("coachStockDetailOrdersBody");

      if (titleEl) titleEl.textContent = "Loading…";
      if (balancesBody) balancesBody.innerHTML = `<tr><td colspan="2" class="dashboard-empty">Loading…</td></tr>`;
      if (givenBody) givenBody.innerHTML = `<tr><td colspan="3" class="dashboard-empty">Loading…</td></tr>`;
      if (ordersBody) ordersBody.innerHTML = `<tr><td colspan="4" class="dashboard-empty">Loading…</td></tr>`;
      modal?.classList.add("is-open");

      try {
        const detail = await apiPost(`${STOCK_API}.get_coach_stock_detail`, { coach: coach });

        if (titleEl) titleEl.textContent = `${detail.coach_name || coach} - Stock Detail`;

        if (balancesBody) {
          balancesBody.innerHTML = (detail.balances || []).length
            ? detail.balances.map(function (b) {
                return coachStockDetailRow([escapeHtml(b.item_name), escapeHtml(b.balance)]);
              }).join("")
            : `<tr><td colspan="2" class="dashboard-empty">No stock movements recorded yet.</td></tr>`;
        }

        if (givenBody) {
          givenBody.innerHTML = (detail.given_to || []).length
            ? detail.given_to.map(function (g) {
                return coachStockDetailRow([escapeHtml(g.client_name), escapeHtml(g.item_name), escapeHtml(g.date)]);
              }).join("")
            : `<tr><td colspan="3" class="dashboard-empty">No packs given out yet.</td></tr>`;
        }

        if (ordersBody) {
          ordersBody.innerHTML = (detail.orders || []).length
            ? detail.orders.map(function (o) {
                const orderLink = o.sales_invoice
                  ? `<a href="${getDashboardBasePath()}/invoice_details?name=${encodeURIComponent(o.sales_invoice)}">${escapeHtml(o.sales_invoice)}</a>`
                  : "—";
                return coachStockDetailRow([escapeHtml(o.item_name), escapeHtml(o.quantity), orderLink, escapeHtml(o.date)]);
              }).join("")
            : `<tr><td colspan="4" class="dashboard-empty">No stock orders recorded yet.</td></tr>`;
        }
      } catch (error) {
        if (titleEl) titleEl.textContent = "Stock Detail";
        if (balancesBody) balancesBody.innerHTML = `<tr><td colspan="2" class="dashboard-empty">${escapeHtml(error.message || "Could not load this coach's stock detail.")}</td></tr>`;
        if (givenBody) givenBody.innerHTML = "";
        if (ordersBody) ordersBody.innerHTML = "";
      }
    }

    function getDashboardBasePath() {
      return (window.location.pathname || "").startsWith("/franchisor_db") ? "/franchisor_db" : "/coach_db";
    }

    el("stockTakeTableBody")?.addEventListener("click", function (event) {
      const button = event.target.closest("[data-view-coach-stock]");
      if (!button) return;
      openCoachStockDetail(button.dataset.viewCoachStock);
    });

    el("closeCoachStockDetailModal")?.addEventListener("click", function () {
      el("coachStockDetailModal")?.classList.remove("is-open");
    });

    el("coachStockDetailModal")?.addEventListener("click", function (event) {
      if (event.target === el("coachStockDetailModal")) {
        el("coachStockDetailModal").classList.remove("is-open");
      }
    });

    // Stock Take - the whole coach roster crossed with every pack Item
    // in one grid, confirmed live as the preferred way to do a real
    // stock take over the one-coach/one-item Adjust Stock modal. Reads
    // read-only by default (stockTakeEditing=false) - a franchisor
    // clicking into Edit is the deliberate step before any number can
    // actually change, rather than every cell always being a live input.
    let stockTakeItems = [];
    let stockTakeCoaches = [];
    let stockTakeEditing = false;

    function stockTakeInputId(coach, itemCode) {
      return `stockTake__${coach}__${itemCode}`;
    }

    function setStockTakeEditing(editing) {
      stockTakeEditing = editing;
      const editBtn = el("editStockTakeBtn");
      const cancelBtn = el("cancelStockTakeBtn");
      const saveBtn = el("saveStockTakeBtn");
      if (editBtn) editBtn.style.display = editing ? "none" : "";
      if (cancelBtn) cancelBtn.style.display = editing ? "" : "none";
      if (saveBtn) saveBtn.style.display = editing ? "" : "none";
      renderStockTakeBody();
    }

    function renderStockTakeBody() {
      const bodyEl = el("stockTakeTableBody");
      if (!bodyEl) return;

      if (!stockTakeCoaches.length) {
        bodyEl.innerHTML = `<tr><td colspan="${2 + stockTakeItems.length}" class="dashboard-empty">No coaches found.</td></tr>`;
        return;
      }

      if (!stockTakeItems.length) {
        bodyEl.innerHTML = `<tr><td class="dashboard-empty">No Kid Pack/Teen Pack Item set up yet - nothing to count.</td></tr>`;
        return;
      }

      bodyEl.innerHTML = stockTakeCoaches.map(function (row) {
        const cells = stockTakeItems.map(function (item) {
          const value = (row.balances || {})[item.item_code] || 0;
          if (!stockTakeEditing) {
            return `<td>${escapeHtml(value)}</td>`;
          }
          return `<td><input type="number" min="0" class="dashboard-input" id="${escapeHtml(stockTakeInputId(row.coach, item.item_code))}" data-stock-take-coach="${escapeHtml(row.coach)}" data-stock-take-item="${escapeHtml(item.item_code)}" data-original-value="${escapeHtml(value)}" value="${escapeHtml(value)}" style="width:90px;"></td>`;
        }).join("");
        return `<tr><td>${escapeHtml(row.coach_name)}</td><td><button type="button" class="dashboard-btn dashboard-btn-light" data-view-coach-stock="${escapeHtml(row.coach)}">View</button></td>${cells}</tr>`;
      }).join("");
    }

    async function loadStockTake() {
      const headEl = el("stockTakeTableHead");
      const bodyEl = el("stockTakeTableBody");

      try {
        const data = await apiPost(`${STOCK_API}.get_coach_stock_take_rows`, {});
        stockTakeItems = data.items || [];
        stockTakeCoaches = data.coaches || [];

        if (headEl) {
          headEl.innerHTML = "<th>Coach</th><th></th>" + stockTakeItems.map(function (item) {
            return `<th>${escapeHtml(item.item_name)}</th>`;
          }).join("");
        }

        renderStockTakeBody();
      } catch (error) {
        if (bodyEl) bodyEl.innerHTML = `<tr><td colspan="${2 + stockTakeItems.length}" class="dashboard-empty">${escapeHtml(error.message || "Could not load the stock take.")}</td></tr>`;
      }
    }

    async function saveStockTake() {
      const saveBtn = el("saveStockTakeBtn");
      const messageEl = el("stockTakeMessage");

      const updates = [];
      document.querySelectorAll("#stockTakeTableBody [data-stock-take-coach]").forEach(function (input) {
        const original = input.dataset.originalValue;
        if (input.value === original || input.value === "") return;

        updates.push({
          coach: input.dataset.stockTakeCoach,
          item: input.dataset.stockTakeItem,
          stock_qty: parseInt(input.value, 10) || 0,
        });
      });

      if (!updates.length) {
        if (messageEl) { messageEl.textContent = "Nothing's changed."; messageEl.style.color = ""; }
        setStockTakeEditing(false);
        return;
      }

      if (saveBtn) { saveBtn.disabled = true; saveBtn.textContent = "Saving..."; }
      if (messageEl) messageEl.textContent = "";

      try {
        const result = await apiPost(`${STOCK_API}.coach_stock_take_update`, { updates: JSON.stringify(updates) });
        if (messageEl) {
          messageEl.textContent = `Saved - ${result.updated} ${result.updated === 1 ? "count" : "counts"} updated.`;
          messageEl.style.color = "#007274";
        }
        setStockTakeEditing(false);
        await loadStockTake();
        await loadComplianceReport();
      } catch (error) {
        if (messageEl) { messageEl.textContent = error.message || "Could not save the stock take."; messageEl.style.color = "#C01C3E"; }
      } finally {
        if (saveBtn) { saveBtn.disabled = false; saveBtn.textContent = "Save Stock Take"; }
      }
    }

    el("editStockTakeBtn")?.addEventListener("click", function () {
      setStockTakeEditing(true);
    });
    el("cancelStockTakeBtn")?.addEventListener("click", function () {
      setStockTakeEditing(false);
    });
    el("saveStockTakeBtn")?.addEventListener("click", saveStockTake);

    async function ensureAdjustmentOptionsLoaded() {
      if (cachedCoachOptions.length && cachedItemOptions.length) return;

      cachedCoachOptions = await apiPost(`${COACH_LOG_API}.get_coach_log_options`, {});
      cachedItemOptions = await apiPost(`${STOCK_API}.get_pack_item_options`, {});

      const coachSelect = el("stockAdjustmentCoach");
      if (coachSelect) {
        coachSelect.innerHTML = cachedCoachOptions.map(function (option) {
          return `<option value="${escapeHtml(option.value)}">${escapeHtml(option.label)}</option>`;
        }).join("") || `<option value="">No coaches found</option>`;
      }

      const itemSelect = el("stockAdjustmentItem");
      if (itemSelect) {
        itemSelect.innerHTML = cachedItemOptions.length
          ? cachedItemOptions.map(function (option) {
              return `<option value="${escapeHtml(option.item_code)}">${escapeHtml(option.item_name)}</option>`;
            }).join("")
          : `<option value="">No Kid Pack/Teen Pack item set up yet</option>`;
      }
    }

    function clearAdjustmentForm() {
      el("stockAdjustmentQuantity").value = "";
      el("stockAdjustmentNotes").value = "";
      el("stockAdjustmentMovementType").value = "Opening Count";
      const messageEl = el("stockAdjustmentMessage");
      if (messageEl) messageEl.textContent = "";
    }

    async function openAdjustmentModal() {
      clearAdjustmentForm();
      await ensureAdjustmentOptionsLoaded();
      el("stockAdjustmentModal")?.classList.add("is-open");
    }

    function closeAdjustmentModal() {
      el("stockAdjustmentModal")?.classList.remove("is-open");
    }

    async function saveAdjustment() {
      const saveBtn = el("saveStockAdjustmentBtn");
      const messageEl = el("stockAdjustmentMessage");

      const coach = el("stockAdjustmentCoach").value;
      const item = el("stockAdjustmentItem").value;
      const movementType = el("stockAdjustmentMovementType").value;
      const quantity = parseInt(el("stockAdjustmentQuantity").value, 10);
      const notes = el("stockAdjustmentNotes").value.trim();

      if (!coach || !item) {
        if (messageEl) messageEl.textContent = "Please choose a coach and an item.";
        return;
      }

      if (!quantity) {
        if (messageEl) messageEl.textContent = "Enter a non-zero quantity.";
        return;
      }

      if (movementType === "Manual Adjustment" && !notes) {
        if (messageEl) messageEl.textContent = "Please enter a note explaining this adjustment.";
        return;
      }

      if (saveBtn) { saveBtn.disabled = true; saveBtn.textContent = "Saving..."; }
      if (messageEl) messageEl.textContent = "";

      try {
        await apiPost(`${STOCK_API}.set_coach_stock_adjustment`, {
          coach: coach,
          item: item,
          quantity_change: quantity,
          movement_type: movementType,
          notes: notes,
        });

        closeAdjustmentModal();
        await loadComplianceReport();
      } catch (error) {
        if (messageEl) messageEl.textContent = error.message || "Could not save this adjustment.";
      } finally {
        if (saveBtn) { saveBtn.disabled = false; saveBtn.textContent = "Save"; }
      }
    }

    el("addStockAdjustmentBtn")?.addEventListener("click", openAdjustmentModal);
    el("closeStockAdjustmentModal")?.addEventListener("click", closeAdjustmentModal);
    el("cancelStockAdjustmentModal")?.addEventListener("click", closeAdjustmentModal);
    el("saveStockAdjustmentBtn")?.addEventListener("click", saveAdjustment);

    const modal = el("stockAdjustmentModal");
    if (modal) {
      modal.addEventListener("click", function (event) {
        if (event.target === modal) closeAdjustmentModal();
      });
    }

    // HQ Stock - a simple, read-first list of what's held at HQ itself
    // (Item.custom_stock_qty, the same field Manage Store -> Stock Take
    // manages via its own fuller recount workflow). Same closed-by-
    // default/Edit-to-change pattern as the Stock Take grid above, but
    // this is Ashley's own quick "I gave one of these away" nudge, not
    // a formal recount - saving here only ever touches custom_stock_qty.
    let hqStockItems = [];
    let hqStockEditing = false;

    function setHqStockEditing(editing) {
      hqStockEditing = editing;
      const editBtn = el("editHqStockBtn");
      const cancelBtn = el("cancelHqStockBtn");
      const saveBtn = el("saveHqStockBtn");
      if (editBtn) editBtn.style.display = editing ? "none" : "";
      if (cancelBtn) cancelBtn.style.display = editing ? "" : "none";
      if (saveBtn) saveBtn.style.display = editing ? "" : "none";
      renderHqStockBody();
    }

    function renderHqStockBody() {
      const bodyEl = el("hqStockTableBody");
      if (!bodyEl) return;

      if (!hqStockItems.length) {
        bodyEl.innerHTML = `<tr><td colspan="2" class="dashboard-empty">No tracked stock items yet - set one up in Manage Store.</td></tr>`;
        return;
      }

      bodyEl.innerHTML = hqStockItems.map(function (item) {
        if (!hqStockEditing) {
          return `<tr><td>${escapeHtml(item.item_name)}</td><td style="text-align:left;">${escapeHtml(item.stock_qty)}</td></tr>`;
        }
        return `<tr><td>${escapeHtml(item.item_name)}</td><td style="text-align:left;"><input type="number" min="0" class="dashboard-input" data-hq-stock-item="${escapeHtml(item.item_code)}" data-original-value="${escapeHtml(item.stock_qty)}" value="${escapeHtml(item.stock_qty)}" style="width:90px;"></td></tr>`;
      }).join("");
    }

    async function loadHqStock() {
      const bodyEl = el("hqStockTableBody");
      try {
        hqStockItems = await apiPost(`${STOCK_API}.get_hq_stock_overview`, {});
        renderHqStockBody();
      } catch (error) {
        if (bodyEl) bodyEl.innerHTML = `<tr><td colspan="2" class="dashboard-empty">${escapeHtml(error.message || "Could not load HQ stock.")}</td></tr>`;
      }
    }

    async function saveHqStock() {
      const saveBtn = el("saveHqStockBtn");
      const messageEl = el("hqStockMessage");

      const updates = [];
      document.querySelectorAll("#hqStockTableBody [data-hq-stock-item]").forEach(function (input) {
        const original = input.dataset.originalValue;
        if (input.value === original || input.value === "") return;
        updates.push({ item_code: input.dataset.hqStockItem, stock_qty: parseInt(input.value, 10) || 0 });
      });

      if (!updates.length) {
        if (messageEl) { messageEl.textContent = "Nothing's changed."; messageEl.style.color = ""; }
        setHqStockEditing(false);
        return;
      }

      if (saveBtn) { saveBtn.disabled = true; saveBtn.textContent = "Saving..."; }
      if (messageEl) messageEl.textContent = "";

      try {
        const result = await apiPost(`${STOCK_API}.update_hq_stock_quantities`, { updates: JSON.stringify(updates) });
        if (messageEl) {
          messageEl.textContent = `Saved - ${result.updated} ${result.updated === 1 ? "item" : "items"} updated.`;
          messageEl.style.color = "#007274";
        }
        setHqStockEditing(false);
        await loadHqStock();
      } catch (error) {
        if (messageEl) { messageEl.textContent = error.message || "Could not save."; messageEl.style.color = "#C01C3E"; }
      } finally {
        if (saveBtn) { saveBtn.disabled = false; saveBtn.textContent = "Save"; }
      }
    }

    el("editHqStockBtn")?.addEventListener("click", function () { setHqStockEditing(true); });
    el("cancelHqStockBtn")?.addEventListener("click", function () { setHqStockEditing(false); });
    el("saveHqStockBtn")?.addEventListener("click", saveHqStock);

    loadComplianceReport();
    loadStockTake();
    loadHqStock();
  }

  function init() {
    initCoachStockPage();
    initFranchisorStockPage();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
