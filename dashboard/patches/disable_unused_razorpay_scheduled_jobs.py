"""
"we dont use razorpay" - the recurring "Scheduled jobs can't run in
maintenance mode" error Ashley kept seeing was always this specific
job (payments.payment_gateways.doctype.razorpay_settings.razorpay_
settings.capture_payment), from the Payments app's Razorpay
integration - installed, but never actually configured/used on this
site. The maintenance-mode collisions were only ever a symptom (any
scheduled job can throw that during a deploy); the actual fix is to
stop this specific job running at all, since there's nothing for it to
capture.

Stops every Scheduled Job Type whose method path starts with
"payments.payment_gateways.doctype.razorpay_settings." - not just
capture_payment - in case the Payments app registers more than one
Razorpay job on this version. Leaves every other scheduled job
(including any other payment gateway actually in use) untouched.
"""

import frappe


def execute():
	if not frappe.db.exists("DocType", "Scheduled Job Type"):
		return

	meta = frappe.get_meta("Scheduled Job Type")
	if not meta.has_field("stopped"):
		return

	rows = frappe.get_all(
		"Scheduled Job Type",
		filters={"method": ["like", "payments.payment_gateways.doctype.razorpay_settings.%"]},
		fields=["name", "stopped"],
	)

	for row in rows:
		if not row.stopped:
			frappe.db.set_value("Scheduled Job Type", row.name, "stopped", 1)

	if rows:
		frappe.db.commit()
