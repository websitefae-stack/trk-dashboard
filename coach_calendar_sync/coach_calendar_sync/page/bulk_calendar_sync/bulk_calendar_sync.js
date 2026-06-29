frappe.pages["bulk-calendar-sync"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "Bulk Calendar Sync",
		single_column: true,
	});

	// ── Filters ──────────────────────────────────────────────────────────────
	const $filters = $(`
		<div class="bulk-sync-filters" style="margin-bottom:16px; display:flex; flex-wrap:wrap; gap:12px; align-items:flex-end;">
			<div>
				<label>Coach</label>
				<div class="coach-filter"></div>
			</div>
			<div>
				<label>Session Worker</label>
				<div class="sw-filter"></div>
			</div>
			<div>
				<label>From Date</label>
				<input type="date" class="form-control from-date" style="width:160px">
			</div>
			<div>
				<label>To Date</label>
				<input type="date" class="form-control to-date" style="width:160px">
			</div>
			<div style="display:flex; gap:8px; align-items:center; padding-top:20px;">
				<input type="checkbox" id="resync-existing"> <label for="resync-existing" style="margin:0">Resync Existing</label>
			</div>
			<div style="display:flex; gap:8px; align-items:center; padding-top:20px;">
				<input type="checkbox" id="dry-run"> <label for="dry-run" style="margin:0">Dry Run</label>
			</div>
		</div>
	`).appendTo(page.body);

	// Link fields for Coach and Session Worker
	const coachField = frappe.ui.form.make_control({
		df: { fieldtype: "Link", options: "Coach", fieldname: "coach", label: "Coach" },
		parent: $filters.find(".coach-filter"),
		render_input: true,
	});
	const swField = frappe.ui.form.make_control({
		df: { fieldtype: "Link", options: "Session Worker", fieldname: "session_worker", label: "Session Worker" },
		parent: $filters.find(".sw-filter"),
		render_input: true,
	});

	// ── Action buttons ────────────────────────────────────────────────────────
	page.add_primary_action("Load Events", loadEvents);
	page.add_action_item("Sync Selected", () => runSync(false));
	page.add_action_item("Sync All Loaded", () => runSyncAll(false));
	page.add_action_item("Delete Google Events", deleteSelected);
	page.add_action_item("Retry Failed", retryFailed);

	// ── Progress bar ─────────────────────────────────────────────────────────
	const $progress = $(`
		<div class="bulk-sync-progress" style="display:none; margin-bottom:12px;">
			<div class="progress"><div class="progress-bar" style="width:0%"></div></div>
			<div class="progress-label text-muted" style="font-size:12px; margin-top:4px;"></div>
		</div>
	`).appendTo(page.body);

	// ── Stats ─────────────────────────────────────────────────────────────────
	const $stats = $(`
		<div class="bulk-sync-stats" style="display:none; margin-bottom:12px; display:flex; gap:16px;">
			<span class="badge badge-success success-count">0 succeeded</span>
			<span class="badge badge-danger failed-count">0 failed</span>
			<span class="badge badge-warning skipped-count">0 skipped</span>
		</div>
	`).appendTo(page.body);

	// ── Table ─────────────────────────────────────────────────────────────────
	const $tableWrap = $(`<div class="bulk-sync-table"></div>`).appendTo(page.body);
	let loadedEvents = [];

	function loadEvents() {
		const filters = getFilters();
		frappe.call({
			method: "coach_calendar_sync.api.bulk_sync.get_events",
			args: filters,
			callback(r) {
				loadedEvents = r.message || [];
				renderTable(loadedEvents);
			},
		});
	}

	function getFilters() {
		return {
			coach: coachField.get_value(),
			session_worker: swField.get_value(),
			from_date: $filters.find(".from-date").val(),
			to_date: $filters.find(".to-date").val(),
			resync_existing: $("#resync-existing").is(":checked") ? 1 : 0,
		};
	}

	function renderTable(events) {
		if (!events.length) {
			$tableWrap.html("<p class='text-muted'>No events found.</p>");
			return;
		}
		const rows = events.map(e => `
			<tr>
				<td><input type="checkbox" class="event-check" data-name="${e.name}"></td>
				<td><a href="/app/event/${e.name}" target="_blank">${e.subject}</a></td>
				<td>${frappe.datetime.str_to_user(e.starts_on)}</td>
				<td>${e.custom_coach || e.custom_session_worker || "—"}</td>
				<td><span class="indicator-pill ${statusClass(e.custom_sync_status)}">${e.custom_sync_status || "—"}</span></td>
				<td>${e.custom_google_event_id ? "✓" : "—"}</td>
			</tr>
		`).join("");

		$tableWrap.html(`
			<table class="table table-bordered table-condensed">
				<thead>
					<tr>
						<th><input type="checkbox" id="check-all"></th>
						<th>Event</th>
						<th>Starts On</th>
						<th>Coach / Worker</th>
						<th>Sync Status</th>
						<th>Has Google ID</th>
					</tr>
				</thead>
				<tbody>${rows}</tbody>
			</table>
		`);

		$("#check-all").on("change", function () {
			$(".event-check").prop("checked", this.checked);
		});
	}

	function statusClass(status) {
		return { Synced: "green", Failed: "red", Pending: "orange" }[status] || "gray";
	}

	function getSelected() {
		return $(".event-check:checked").map(function () {
			return $(this).data("name");
		}).get();
	}

	function runSync(dryRun) {
		const selected = getSelected();
		if (!selected.length) {
			frappe.msgprint("Select at least one event.");
			return;
		}
		executeSync(selected, dryRun);
	}

	function runSyncAll(dryRun) {
		const allNames = loadedEvents.map(e => e.name);
		executeSync(allNames, dryRun);
	}

	function executeSync(names, dryRun) {
		const isDry = dryRun || $("#dry-run").is(":checked");
		showProgress(0, names.length);
		frappe.call({
			method: "coach_calendar_sync.api.bulk_sync.sync_events",
			args: { event_names: names, dry_run: isDry ? 1 : 0 },
			callback(r) {
				const result = r.message || {};
				showStats(result);
				hideProgress();
				if (!isDry) loadEvents();
			},
		});
	}

	function deleteSelected() {
		const selected = getSelected();
		if (!selected.length) { frappe.msgprint("Select at least one event."); return; }
		frappe.confirm("Delete Google Calendar events for selected items?", () => {
			frappe.call({
				method: "coach_calendar_sync.api.bulk_sync.delete_google_events",
				args: { event_names: selected, dry_run: 0 },
				callback(r) { showStats(r.message || {}); loadEvents(); },
			});
		});
	}

	function retryFailed() {
		frappe.call({
			method: "coach_calendar_sync.api.bulk_sync.retry_failed",
			callback(r) {
				frappe.show_alert({ message: `${r.message} failed events re-queued`, indicator: "green" });
			},
		});
	}

	function showProgress(done, total) {
		$progress.show();
		const pct = total ? Math.round((done / total) * 100) : 0;
		$progress.find(".progress-bar").css("width", pct + "%");
		$progress.find(".progress-label").text(`${done} / ${total}`);
	}

	function hideProgress() {
		$progress.hide();
	}

	function showStats(result) {
		$stats.show();
		$stats.find(".success-count").text(`${(result.success || []).length} succeeded`);
		$stats.find(".failed-count").text(`${(result.failed || []).length} failed`);
		$stats.find(".skipped-count").text(`${(result.skipped || []).length} skipped`);
	}
};
