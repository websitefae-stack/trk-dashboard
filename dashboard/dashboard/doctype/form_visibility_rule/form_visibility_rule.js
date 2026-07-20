frappe.ui.form.on("Form Visibility Rule", {
	refresh(frm) {
		frm.set_query("form_doctype", () => ({
			filters: {
				module: "Forms",
				istable: 0,
				issingle: 0,
			},
		}));
	},
});
