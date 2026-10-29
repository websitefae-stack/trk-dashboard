"""
A full, month-by-month history of franchise + marketing fees actually
paid, from when the business started to today - the figures before
1 November 2026 are typed in by hand (Franchise Fee Manual Total, one
row per month), everything from that date on is pulled automatically
from the same internal-invoice payments the franchisor dashboard's
"Outstanding Internal Invoices" section already tracks (see
dashboard._get_outstanding_internal_invoices for the sibling query this
mirrors the exclusion logic of).

"Fees paid" here means actual cash received (Payment Entry.posting_date/
paid_amount against a coach's own linked_client), not invoiced amounts -
an invoice raised in one month and paid the next shows up in the month
it was actually paid, matching what "fees paid" means in plain English.
Every linked_client invoice is, by this app's own existing convention,
an internal fee invoice (HQ billing a coach directly) - franchise fee
and marketing fee are the only things ever invoiced that way, so no
further item-level filtering is needed to isolate them.
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate, get_first_day

from dashboard.api.shared.permissions import ensure_office_user

MANUAL_DOCTYPE = "Franchise Fee Manual Total"

# Automatic pulling from real payment data starts on this date - before
# it, Ashley is backfilling the historical figures by hand (the
# dashboard itself didn't exist, or wasn't yet the source of truth, for
# those months). Deliberately a plain constant, not configurable from
# the UI - changing where this cutover sits is a business decision, not
# a settings toggle.
AUTO_CUTOFF_DATE = "2026-11-01"


def _get_linked_client_coach_map():
	if not frappe.get_meta("Coach").has_field("linked_client"):
		return {}

	coach_rows = frappe.get_all(
		"Coach",
		filters={"linked_client": ["is", "set"]},
		fields=["name", "linked_client"],
		limit_page_length=1000,
		ignore_permissions=True,
	)

	return {row.linked_client: row.name for row in coach_rows if row.linked_client}


def _get_automatic_monthly_totals():
	"""
	Every submitted Payment Entry against a coach's own linked_client,
	from AUTO_CUTOFF_DATE onward, grouped by the month it was actually
	posted - excludes a payment whose income belongs to a specific OTHER
	coach (custom_income_owner_coach set to a genuine Coach record, e.g.
	Emily invoicing SJ's linked Client on her own behalf) exactly like
	_get_outstanding_internal_invoices does, since that money was never
	office's to begin with. Unlike that function, there's no "unless the
	viewer owes it themselves" exception here - this report is purely
	office's own fee income, full stop.
	"""
	client_to_coach = _get_linked_client_coach_map()
	if not client_to_coach:
		return {}

	payment_meta = frappe.get_meta("Payment Entry")
	if not payment_meta.has_field("custom_client"):
		return {}

	fields = ["name", "posting_date", "paid_amount"]
	if payment_meta.has_field("custom_income_owner_coach"):
		fields.append("custom_income_owner_coach")

	rows = frappe.get_all(
		"Payment Entry",
		filters={
			"custom_client": ["in", list(client_to_coach.keys())],
			"docstatus": 1,
			"posting_date": [">=", AUTO_CUTOFF_DATE],
		},
		fields=fields,
		limit_page_length=0,
		ignore_permissions=True,
	)

	totals = {}

	for row in rows:
		income_owner = row.get("custom_income_owner_coach")
		if income_owner and frappe.db.exists("Coach", income_owner):
			continue

		month_key = get_first_day(row.posting_date).isoformat()
		totals[month_key] = totals.get(month_key, 0) + flt(row.paid_amount, 2)

	return totals


@frappe.whitelist()
def get_fees_report():
	ensure_office_user()

	automatic_totals = _get_automatic_monthly_totals()

	manual_rows = frappe.get_all(
		MANUAL_DOCTYPE,
		filters={"period": ["<", AUTO_CUTOFF_DATE]},
		fields=["name", "period", "amount", "note"],
		ignore_permissions=True,
	)

	rows = []

	for row in manual_rows:
		rows.append({
			"month": getdate(row.period).isoformat(),
			"amount": flt(row.amount, 2),
			"source": "Manual",
			"name": row.name,
			"note": row.note or "",
		})

	for month_key, amount in automatic_totals.items():
		rows.append({
			"month": month_key,
			"amount": amount,
			"source": "Dashboard",
			"name": "",
			"note": "",
		})

	rows.sort(key=lambda row: row["month"], reverse=True)

	grand_total = sum(row["amount"] for row in rows)

	return {
		"rows": rows,
		"grand_total": grand_total,
		"auto_cutoff_date": AUTO_CUTOFF_DATE,
	}


@frappe.whitelist()
def save_manual_fee_total(name=None, period=None, amount=None, note=None):
	ensure_office_user()

	if not period:
		frappe.throw(_("Please choose a month."))

	period = get_first_day(getdate(period))

	if period >= getdate(AUTO_CUTOFF_DATE):
		frappe.throw(
			_("{0} onward is pulled automatically from the dashboard - manual totals are only for months before that.").format(
				frappe.utils.formatdate(AUTO_CUTOFF_DATE)
			)
		)

	amount = flt(amount, 2)
	if amount < 0:
		frappe.throw(_("Amount cannot be negative."))

	name = (name or "").strip()

	if name:
		if not frappe.db.exists(MANUAL_DOCTYPE, name):
			frappe.throw(_("Entry not found."))
		doc = frappe.get_doc(MANUAL_DOCTYPE, name)
		doc.period = period
		doc.amount = amount
		doc.note = note or ""
		doc.save(ignore_permissions=True)
	else:
		existing = frappe.db.exists(MANUAL_DOCTYPE, {"period": period})
		if existing:
			doc = frappe.get_doc(MANUAL_DOCTYPE, existing)
			doc.amount = amount
			doc.note = note or ""
			doc.save(ignore_permissions=True)
		else:
			doc = frappe.get_doc({
				"doctype": MANUAL_DOCTYPE,
				"period": period,
				"amount": amount,
				"note": note or "",
			})
			doc.insert(ignore_permissions=True)

	return {"name": doc.name}


@frappe.whitelist()
def delete_manual_fee_total(name=None):
	ensure_office_user()

	name = (name or "").strip()
	if not name or not frappe.db.exists(MANUAL_DOCTYPE, name):
		frappe.throw(_("Entry not found."))

	frappe.delete_doc(MANUAL_DOCTYPE, name, ignore_permissions=True)

	return {"ok": 1}
