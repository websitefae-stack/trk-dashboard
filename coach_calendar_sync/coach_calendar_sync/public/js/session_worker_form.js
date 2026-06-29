frappe.ui.form.on("Session Worker", {
	refresh(frm) {
		setup_google_calendar_buttons(frm);
	},
});
