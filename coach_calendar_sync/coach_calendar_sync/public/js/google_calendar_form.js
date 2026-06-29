/**
 * Shared JS for the Google Calendar section on Coach and Session Worker forms.
 * Attach with doctype_js in hooks.py.
 */

function setup_google_calendar_buttons(frm) {
	frm.fields_dict.connect_google_calendar &&
		frm.fields_dict.connect_google_calendar.$input &&
		frm.fields_dict.connect_google_calendar.$input.on("click", () => {
			initiate_oauth(frm);
		});

	frm.fields_dict.disconnect_google_calendar &&
		frm.fields_dict.disconnect_google_calendar.$input &&
		frm.fields_dict.disconnect_google_calendar.$input.on("click", () => {
			frappe.confirm(
				"Disconnect Google Calendar? Stored tokens will be deleted.",
				() => disconnect_oauth(frm)
			);
		});

	frm.fields_dict.test_connection &&
		frm.fields_dict.test_connection.$input &&
		frm.fields_dict.test_connection.$input.on("click", () => {
			test_connection(frm);
		});
}

function initiate_oauth(frm) {
	frappe.call({
		method: "coach_calendar_sync.api.oauth.get_authorization_url",
		args: { doctype: frm.doctype, name: frm.doc.name },
		callback(r) {
			if (r.message) {
				window.open(r.message, "_blank", "width=600,height=700");
				frappe.show_alert({
					message: "Complete authorization in the new window, then refresh this form.",
					indicator: "blue",
				});
			}
		},
	});
}

function disconnect_oauth(frm) {
	frappe.call({
		method: "coach_calendar_sync.api.oauth.disconnect",
		args: { doctype: frm.doctype, name: frm.doc.name },
		callback() {
			frappe.show_alert({ message: "Google Calendar disconnected.", indicator: "orange" });
			frm.reload_doc();
		},
	});
}

function test_connection(frm) {
	frappe.call({
		method: "coach_calendar_sync.api.oauth.test_connection",
		args: { doctype: frm.doctype, name: frm.doc.name },
		callback(r) {
			if (r.message && r.message.status === "ok") {
				frappe.show_alert({
					message: `Connection OK — Calendar: ${r.message.calendar_summary}`,
					indicator: "green",
				});
			} else {
				frappe.show_alert({ message: "Connection test failed.", indicator: "red" });
			}
		},
	});
}
