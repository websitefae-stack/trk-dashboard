frappe.pages["calendar-sync-dashboard"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "Calendar Sync Dashboard",
		single_column: true,
	});

	page.add_primary_action("Sync All", syncAll);
	page.add_action_item("Retry Failed", retryFailed);
	page.add_action_item("Test All Connections", testConnections);
	page.add_action_item("View Logs", () => frappe.set_route("List", "Calendar Sync Log"));

	const $body = $(page.body);

	$body.html(`
		<div class="sync-dashboard">
			<div class="stat-cards row" style="margin-bottom:24px;">
				${statCard("connected-coaches", "Connected Coaches", "blue")}
				${statCard("connected-workers", "Connected Session Workers", "blue")}
				${statCard("synced-today", "Synced Today", "green")}
				${statCard("pending-syncs", "Pending Syncs", "orange")}
				${statCard("failed-syncs", "Failed Syncs", "red")}
				${statCard("last-sync", "Last Sync", "gray")}
			</div>

			<h5>Connected Coaches</h5>
			<div class="coaches-table" style="margin-bottom:24px;"></div>

			<h5>Connected Session Workers</h5>
			<div class="workers-table"></div>
		</div>
	`);

	loadStats();
	loadPersonTable("Coach", $body.find(".coaches-table"));
	loadPersonTable("Session Worker", $body.find(".workers-table"));

	function statCard(key, label, color) {
		return `
			<div class="col-sm-2">
				<div class="card" style="padding:16px; text-align:center; margin-bottom:8px;">
					<div class="stat-value ${key}" style="font-size:2em; font-weight:bold; color:var(--${color}-500, #333);">—</div>
					<div style="font-size:12px; color:#888;">${label}</div>
				</div>
			</div>
		`;
	}

	function loadStats() {
		frappe.call({
			method: "coach_calendar_sync.api.bulk_sync.get_dashboard_stats",
			callback(r) {
				const d = r.message || {};
				$body.find(".connected-coaches").text(d.connected_coaches ?? "—");
				$body.find(".connected-workers").text(d.connected_session_workers ?? "—");
				$body.find(".synced-today").text(d.synced_today ?? "—");
				$body.find(".pending-syncs").text(d.pending_syncs ?? "—");
				$body.find(".failed-syncs").text(d.failed_syncs ?? "—");
				$body.find(".last-sync").text(
					d.last_sync ? frappe.datetime.str_to_user(d.last_sync) : "Never"
				);
			},
		});
	}

	function loadPersonTable(doctype, $container) {
		frappe.call({
			method: "frappe.client.get_list",
			args: {
				doctype,
				fields: ["name", "google_sync_enabled", "connected", "google_email", "last_sync", "last_error"],
				filters: { google_sync_enabled: 1 },
				limit: 100,
			},
			callback(r) {
				const rows = (r.message || []);
				if (!rows.length) {
					$container.html(`<p class="text-muted">No ${doctype}s with Google Sync enabled.</p>`);
					return;
				}
				const html = `
					<table class="table table-bordered table-condensed">
						<thead>
							<tr>
								<th>Name</th>
								<th>Email</th>
								<th>Connected</th>
								<th>Last Sync</th>
								<th>Last Error</th>
							</tr>
						</thead>
						<tbody>
							${rows.map(r => `
								<tr>
									<td><a href="/app/${frappe.router.slug(doctype)}/${encodeURIComponent(r.name)}">${r.name}</a></td>
									<td>${r.google_email || "—"}</td>
									<td>${r.connected
										? '<span class="indicator-pill green">Yes</span>'
										: '<span class="indicator-pill red">No</span>'
									}</td>
									<td>${r.last_sync ? frappe.datetime.str_to_user(r.last_sync) : "—"}</td>
									<td style="color:red; font-size:12px;">${r.last_error || ""}</td>
								</tr>
							`).join("")}
						</tbody>
					</table>
				`;
				$container.html(html);
			},
		});
	}

	function syncAll() {
		frappe.call({
			method: "coach_calendar_sync.sync.scheduler.run_sync_cycle",
			callback() {
				frappe.show_alert({ message: "Sync cycle started", indicator: "green" });
				setTimeout(loadStats, 3000);
			},
		});
	}

	function retryFailed() {
		frappe.call({
			method: "coach_calendar_sync.api.bulk_sync.retry_failed",
			callback(r) {
				frappe.show_alert({ message: `${r.message} events re-queued`, indicator: "green" });
				setTimeout(loadStats, 2000);
			},
		});
	}

	function testConnections() {
		frappe.show_alert({ message: "Testing connections…", indicator: "blue" });
		["Coach", "Session Worker"].forEach(doctype => {
			frappe.call({
				method: "frappe.client.get_list",
				args: {
					doctype,
					filters: { google_sync_enabled: 1, connected: 1 },
					pluck: "name",
					limit: 50,
				},
				callback(r) {
					(r.message || []).forEach(name => {
						frappe.call({
							method: "coach_calendar_sync.api.oauth.test_connection",
							args: { doctype, name },
							callback(tr) {
								const ok = tr.message && tr.message.status === "ok";
								frappe.show_alert({
									message: `${doctype} ${name}: ${ok ? "OK" : "FAILED"}`,
									indicator: ok ? "green" : "red",
								});
							},
						});
					});
				},
			});
		});
	}
};
