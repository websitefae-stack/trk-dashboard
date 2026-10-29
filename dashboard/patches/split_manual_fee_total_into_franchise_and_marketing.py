"""
Franchise Fee Manual Total used to be a single "Total Fees Paid" figure
per month - now split into franchise_fee_amount/marketing_fee_amount so
Ashley can enter the two separately for her backfilled historical
months (see fees_report.py). The old `amount` field is kept on the
doctype (hidden, read-only, deprecated) rather than removed, so this
patch never risks losing a figure already entered.

For any existing row where amount has a value but franchise_fee_amount
is still blank/zero, copies the old total into franchise_fee_amount
(the simplest way to make sure the money is still accounted for in the
report's grand total) - marketing_fee_amount is left at 0 for Ashley to
split properly by hand later if she wants the two figures separated
for that particular month. Safe to run more than once: a row already
showing a non-zero franchise_fee_amount is left alone.
"""

import frappe


def execute():
	if not frappe.db.exists("DocType", "Franchise Fee Manual Total"):
		return

	meta = frappe.get_meta("Franchise Fee Manual Total")
	if not (meta.has_field("amount") and meta.has_field("franchise_fee_amount")):
		return

	rows = frappe.get_all(
		"Franchise Fee Manual Total",
		filters={"amount": [">", 0]},
		fields=["name", "amount", "franchise_fee_amount"],
	)

	for row in rows:
		if row.franchise_fee_amount:
			continue

		frappe.db.set_value(
			"Franchise Fee Manual Total", row.name, "franchise_fee_amount", row.amount, update_modified=False,
		)
