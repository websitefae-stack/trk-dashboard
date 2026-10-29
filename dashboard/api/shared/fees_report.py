"""
A full, month-by-month history of franchise + marketing fees actually
paid by each coach, from when the business started to today - the
figures before 1 November 2026 are typed in by hand, one row per
(coach, month) - see save_manual_fee_total() - and everything from
that date on is pulled automatically from the same internal-invoice
payments the franchisor dashboard's "Outstanding Internal Invoices"
section already tracks (see dashboard._get_outstanding_internal_invoices
for the sibling query this mirrors the exclusion logic of).

"Fees paid" here means actual cash received (Payment Entry.posting_date/
paid_amount against a coach's own linked_client), not invoiced amounts -
an invoice raised in one month and paid the next shows up in the month
it was actually paid.

Every figure here - manual or automatic - is attributed to a specific
fee-paying coach (which includes Ashley's own Coach record - she pays
fees like any other franchisee), never to office/HQ. get_fees_report()
lists month-by-month, filterable to one coach; get_fee_totals_by_coach()
is the other shape of the same data - one row per coach, summed over an
optional date range, for "how much has each coach paid"/"how much did
everyone pay in August" style questions.

Automatic rows are split into Franchise Fee vs Marketing Fee - done by
looking at the Sales Invoice backing each payment and working out what
fraction of its grand_total those two configured Items (Fees Report
Settings) made up, then allocating that same fraction of the payment
itself. A payment is usually for a single-item invoice (100% one or the
other), but this still holds up if an invoice ever mixes several fee
items on one Sales Invoice. Falls back to one undifferentiated "Fees
Paid" bucket per payment until both Items are configured.
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate, get_first_day, add_months

from dashboard.api.shared.permissions import ensure_office_user, FRANCHISOR_USERS

SETTINGS_DOCTYPE = "Fees Report Settings"
MANUAL_DOCTYPE = "Franchise Fee Manual Total"
COACH_DOCTYPE = "Coach"

# Logins that must never be selectable as a "fee-paying coach" even if
# they happen to have their own Coach record (office/HQ's calendar-sync
# identity, e.g. "The Resilient Office") - Ashley's own login is
# deliberately NOT in this set, since she pays fees like any other
# franchisee and the coach picker needs to include her.
NON_COACH_FRANCHISOR_LOGINS = {
	email.lower() for email in FRANCHISOR_USERS
	if email.lower() != "ashley@theresilientkid.co.uk"
}

# Automatic pulling from real payment data starts on this date - before
# it, Ashley is backfilling the historical figures by hand (the
# dashboard itself didn't exist, or wasn't yet the source of truth, for
# those months). Deliberately a plain constant, not configurable from
# the UI - changing where this cutover sits is a business decision, not
# a settings toggle.
AUTO_CUTOFF_DATE = "2026-11-01"


@frappe.whitelist()
def get_fees_report_settings():
	ensure_office_user()

	doc = frappe.get_single(SETTINGS_DOCTYPE)

	return {
		"franchise_fee_item": doc.franchise_fee_item or "",
		"marketing_fee_item": doc.marketing_fee_item or "",
	}


@frappe.whitelist()
def save_fees_report_settings(franchise_fee_item=None, marketing_fee_item=None):
	ensure_office_user()

	doc = frappe.get_single(SETTINGS_DOCTYPE)
	doc.franchise_fee_item = (franchise_fee_item or "").strip()
	doc.marketing_fee_item = (marketing_fee_item or "").strip()
	doc.save(ignore_permissions=True)

	return {"ok": 1}


def _get_linked_client_coach_map():
	if not frappe.get_meta(COACH_DOCTYPE).has_field("linked_client"):
		return {}

	coach_rows = frappe.get_all(
		COACH_DOCTYPE,
		filters={"linked_client": ["is", "set"]},
		fields=["name", "linked_client"],
		limit_page_length=1000,
		ignore_permissions=True,
	)

	return {row.linked_client: row.name for row in coach_rows if row.linked_client}


def _coach_login_emails(coach_name):
	meta = frappe.get_meta(COACH_DOCTYPE)
	emails = set()
	for fieldname in ("user", "coach_email"):
		if meta.has_field(fieldname):
			value = frappe.db.get_value(COACH_DOCTYPE, coach_name, fieldname)
			if value:
				emails.add(value.strip().lower())
	return emails


@frappe.whitelist()
def get_coach_options_for_fees():
	"""
	Every fee-paying coach - everyone except office/HQ's own Coach
	record(s) (NON_COACH_FRANCHISOR_LOGINS), but including Ashley's own.
	Used both for the manual-entry form's coach picker and the report
	filters - deliberately the full list, not get_fee_paying_coaches()'s
	linked_client-only subset, since a coach backfilling a historical
	month may not have (or need) a linked_client/invoice at all.
	"""
	ensure_office_user()

	rows = frappe.get_all(
		COACH_DOCTYPE,
		fields=["name", "coach_name"],
		order_by="coach_name asc",
		limit_page_length=5000,
		ignore_permissions=True,
	)

	return [row for row in rows if not (_coach_login_emails(row.name) & NON_COACH_FRANCHISOR_LOGINS)]


def _get_fee_item_breakdown_per_invoice(invoice_names, franchise_item, marketing_item):
	"""{invoice_name: {"grand_total": x, "Franchise Fee": y, "Marketing Fee": z}}"""
	if not invoice_names:
		return {}

	invoices = frappe.get_all(
		"Sales Invoice",
		filters={"name": ["in", invoice_names]},
		fields=["name", "grand_total"],
	)
	result = {
		inv.name: {"grand_total": flt(inv.grand_total, 2), "Franchise Fee": 0.0, "Marketing Fee": 0.0}
		for inv in invoices
	}

	item_codes = [code for code in (franchise_item, marketing_item) if code]
	if not item_codes:
		return result

	item_rows = frappe.get_all(
		"Sales Invoice Item",
		filters={"parent": ["in", invoice_names], "item_code": ["in", item_codes]},
		fields=["parent", "item_code", "amount"],
	)

	for row in item_rows:
		bucket = result.get(row.parent)
		if not bucket:
			continue
		if row.item_code == franchise_item:
			bucket["Franchise Fee"] += flt(row.amount, 2)
		elif row.item_code == marketing_item:
			bucket["Marketing Fee"] += flt(row.amount, 2)

	return result


def _get_automatic_rows(coach_filter=None):
	"""
	One row per (payment, fee type) - [{month, coach, fee_type, amount}].
	Excludes a payment whose income belongs to a specific OTHER coach
	(custom_income_owner_coach set to a genuine Coach record, e.g. Emily
	invoicing SJ's linked Client on her own behalf) exactly like
	_get_outstanding_internal_invoices does, since that money was never
	office's to begin with. Unlike that function, there's no "unless the
	viewer owes it themselves" exception here - this report is purely
	office's own fee income, full stop.
	"""
	client_to_coach = _get_linked_client_coach_map()
	if not client_to_coach:
		return []

	if coach_filter:
		client_to_coach = {client: coach for client, coach in client_to_coach.items() if coach == coach_filter}
		if not client_to_coach:
			return []

	payment_meta = frappe.get_meta("Payment Entry")
	if not payment_meta.has_field("custom_client"):
		return []

	fields = ["name", "posting_date", "paid_amount", "custom_client"]
	if payment_meta.has_field("custom_income_owner_coach"):
		fields.append("custom_income_owner_coach")

	payments = frappe.get_all(
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

	payments = [
		row for row in payments
		if not (row.get("custom_income_owner_coach") and frappe.db.exists("Coach", row.get("custom_income_owner_coach")))
	]
	if not payments:
		return []

	payment_names = [row.name for row in payments]

	refs = frappe.get_all(
		"Payment Entry Reference",
		filters={"parent": ["in", payment_names], "reference_doctype": "Sales Invoice"},
		fields=["parent", "reference_name"],
	)
	# This app's own allocate_invoice_payment() always creates a payment
	# for exactly one invoice (get_payment_entry("Sales Invoice",
	# invoice_name, ...)), so first-reference-wins is safe - there's
	# never genuinely more than one for these payments.
	payment_to_invoice = {}
	for ref in refs:
		payment_to_invoice.setdefault(ref.parent, ref.reference_name)

	invoice_names = list({name for name in payment_to_invoice.values() if name})

	settings = frappe.get_single(SETTINGS_DOCTYPE)
	franchise_item = settings.franchise_fee_item or ""
	marketing_item = settings.marketing_fee_item or ""

	invoice_breakdown = _get_fee_item_breakdown_per_invoice(invoice_names, franchise_item, marketing_item)

	rows = []

	for payment in payments:
		coach = client_to_coach.get(payment.custom_client)
		if not coach:
			continue

		month_key = get_first_day(payment.posting_date).isoformat()
		paid_amount = flt(payment.paid_amount, 2)
		invoice_name = payment_to_invoice.get(payment.name)
		breakdown = invoice_breakdown.get(invoice_name) if invoice_name else None

		if not breakdown or not (franchise_item or marketing_item):
			rows.append({"month": month_key, "coach": coach, "fee_type": "Fees Paid", "amount": paid_amount})
			continue

		grand_total = breakdown["grand_total"]
		franchise_item_amount = breakdown["Franchise Fee"]
		marketing_item_amount = breakdown["Marketing Fee"]
		fee_item_total = franchise_item_amount + marketing_item_amount

		if grand_total <= 0 or fee_item_total <= 0:
			rows.append({"month": month_key, "coach": coach, "fee_type": "Fees Paid", "amount": paid_amount})
			continue

		franchise_portion = flt(paid_amount * (franchise_item_amount / grand_total), 2)
		marketing_portion = flt(paid_amount * (marketing_item_amount / grand_total), 2)
		unmatched_portion = flt(paid_amount - franchise_portion - marketing_portion, 2)

		if franchise_portion:
			rows.append({"month": month_key, "coach": coach, "fee_type": "Franchise Fee", "amount": franchise_portion})
		if marketing_portion:
			rows.append({"month": month_key, "coach": coach, "fee_type": "Marketing Fee", "amount": marketing_portion})
		if unmatched_portion > 0.01:
			# The invoice had other, non-fee items mixed in alongside the
			# fee items - shouldn't normally happen for a linked_client
			# invoice, but if it does, this makes sure that money is still
			# accounted for rather than silently dropped.
			rows.append({"month": month_key, "coach": coach, "fee_type": "Other", "amount": unmatched_portion})

	return rows


def _get_manual_rows(coach_filter=None):
	"""One row per (manual entry, fee type) - same shape as
	_get_automatic_rows(), so both can be combined/aggregated the same
	way. Skips the handful of legacy rows with no coach attached (see
	the split_manual_fee_total patches) - those predate per-coach
	tracking and were never attributable to one person."""
	filters = {"period": ["<", AUTO_CUTOFF_DATE], "coach": ["is", "set"]}
	if coach_filter:
		filters["coach"] = coach_filter

	manual_rows = frappe.get_all(
		MANUAL_DOCTYPE,
		filters=filters,
		fields=["name", "coach", "period", "franchise_fee_amount", "marketing_fee_amount", "note"],
		ignore_permissions=True,
	)

	rows = []
	for row in manual_rows:
		month_key = getdate(row.period).isoformat()
		if flt(row.franchise_fee_amount, 2):
			rows.append({
				"month": month_key, "coach": row.coach, "fee_type": "Franchise Fee",
				"amount": flt(row.franchise_fee_amount, 2), "name": row.name, "note": row.note or "",
			})
		if flt(row.marketing_fee_amount, 2):
			rows.append({
				"month": month_key, "coach": row.coach, "fee_type": "Marketing Fee",
				"amount": flt(row.marketing_fee_amount, 2), "name": row.name, "note": row.note or "",
			})

	return rows


@frappe.whitelist()
def get_fees_report(coach=None):
	ensure_office_user()

	coach = (coach or "").strip()

	rows = []

	for row in _get_manual_rows(coach_filter=coach or None):
		rows.append({
			"month": row["month"],
			"amount": row["amount"],
			"source": "Manual",
			"fee_type": row["fee_type"],
			"coach": row["coach"],
			"name": row["name"],
			"note": row["note"],
		})

	monthly_totals = {}
	for row in _get_automatic_rows(coach_filter=coach or None):
		key = (row["month"], row["fee_type"])
		monthly_totals[key] = monthly_totals.get(key, 0) + row["amount"]

	for (month_key, fee_type), amount in monthly_totals.items():
		rows.append({
			"month": month_key,
			"amount": flt(amount, 2),
			"source": "Dashboard",
			"fee_type": fee_type,
			"coach": coach or "",
			"name": "",
			"note": "",
		})

	coach_labels = {}
	if not coach:
		coach_names = {row["coach"] for row in rows if row.get("coach")}
		if coach_names:
			coach_labels = {
				row.name: row.coach_name
				for row in frappe.get_all(COACH_DOCTYPE, filters={"name": ["in", list(coach_names)]}, fields=["name", "coach_name"])
			}
	for row in rows:
		row["coach_label"] = coach_labels.get(row.get("coach"), "")

	rows.sort(key=lambda row: (row["month"], row["fee_type"]), reverse=True)

	grand_total = sum(row["amount"] for row in rows)

	settings = frappe.get_single(SETTINGS_DOCTYPE)

	return {
		"rows": rows,
		"grand_total": grand_total,
		"auto_cutoff_date": AUTO_CUTOFF_DATE,
		"fee_items_configured": bool(settings.franchise_fee_item and settings.marketing_fee_item),
	}


def _month_bounds(from_month, to_month):
	from_date = get_first_day(getdate(from_month)) if from_month else None
	to_date_exclusive = add_months(get_first_day(getdate(to_month)), 1) if to_month else None
	return from_date, to_date_exclusive


@frappe.whitelist()
def get_fee_totals_by_coach(from_month=None, to_month=None):
	"""
	One row per coach - Franchise Fee / Marketing Fee / combined total,
	summed across both manual and automatic data, over an optional date
	range ("how much has each coach paid", "how much did everyone pay
	in August" - from_month=to_month="2026-08-01"). No range at all
	means all-time.
	"""
	ensure_office_user()

	from_date, to_date_exclusive = _month_bounds(from_month, to_month)

	def _in_range(month_key):
		month_date = getdate(month_key)
		if from_date and month_date < from_date:
			return False
		if to_date_exclusive and month_date >= to_date_exclusive:
			return False
		return True

	all_rows = _get_manual_rows() + _get_automatic_rows()

	totals = {}
	for row in all_rows:
		if not row.get("coach") or not _in_range(row["month"]):
			continue
		bucket = totals.setdefault(row["coach"], {"franchise_fee_total": 0.0, "marketing_fee_total": 0.0, "other_total": 0.0})
		if row["fee_type"] == "Franchise Fee":
			bucket["franchise_fee_total"] += row["amount"]
		elif row["fee_type"] == "Marketing Fee":
			bucket["marketing_fee_total"] += row["amount"]
		else:
			bucket["other_total"] += row["amount"]

	if not totals:
		return []

	coach_labels = {
		row.name: row.coach_name
		for row in frappe.get_all(COACH_DOCTYPE, filters={"name": ["in", list(totals.keys())]}, fields=["name", "coach_name"])
	}

	results = []
	for coach_name, bucket in totals.items():
		franchise_total = flt(bucket["franchise_fee_total"], 2)
		marketing_total = flt(bucket["marketing_fee_total"], 2)
		other_total = flt(bucket["other_total"], 2)
		results.append({
			"coach": coach_name,
			"coach_label": coach_labels.get(coach_name, coach_name),
			"franchise_fee_total": franchise_total,
			"marketing_fee_total": marketing_total,
			"other_total": other_total,
			"total": flt(franchise_total + marketing_total + other_total, 2),
		})

	results.sort(key=lambda row: row["coach_label"].lower())

	return results


@frappe.whitelist()
def save_manual_fee_total(name=None, coach=None, period=None, franchise_fee_amount=None, marketing_fee_amount=None, note=None):
	ensure_office_user()

	coach = (coach or "").strip()
	if not coach or not frappe.db.exists(COACH_DOCTYPE, coach):
		frappe.throw(_("Please choose a coach."))

	if _coach_login_emails(coach) & NON_COACH_FRANCHISOR_LOGINS:
		frappe.throw(_("Office/HQ don't pay fees - please choose an actual coach."))

	if not period:
		frappe.throw(_("Please choose a month."))

	period = get_first_day(getdate(period))

	if period >= getdate(AUTO_CUTOFF_DATE):
		frappe.throw(
			_("{0} onward is pulled automatically from the dashboard - manual totals are only for months before that.").format(
				frappe.utils.formatdate(AUTO_CUTOFF_DATE)
			)
		)

	franchise_fee_amount = flt(franchise_fee_amount, 2)
	marketing_fee_amount = flt(marketing_fee_amount, 2)
	if franchise_fee_amount < 0 or marketing_fee_amount < 0:
		frappe.throw(_("Amount cannot be negative."))

	values = {
		"coach": coach,
		"period": period,
		"franchise_fee_amount": franchise_fee_amount,
		"marketing_fee_amount": marketing_fee_amount,
		"note": note or "",
	}

	name = (name or "").strip()

	if name:
		if not frappe.db.exists(MANUAL_DOCTYPE, name):
			frappe.throw(_("Entry not found."))
		doc = frappe.get_doc(MANUAL_DOCTYPE, name)
		doc.update(values)
		doc.save(ignore_permissions=True)
	else:
		existing = frappe.db.exists(MANUAL_DOCTYPE, {"coach": coach, "period": period})
		if existing:
			doc = frappe.get_doc(MANUAL_DOCTYPE, existing)
			doc.update(values)
			doc.save(ignore_permissions=True)
		else:
			doc = frappe.get_doc({"doctype": MANUAL_DOCTYPE, **values})
			doc.insert(ignore_permissions=True)

	return {"name": doc.name}


@frappe.whitelist()
def get_manual_fee_total(name=None):
	ensure_office_user()

	name = (name or "").strip()
	if not name or not frappe.db.exists(MANUAL_DOCTYPE, name):
		frappe.throw(_("Entry not found."))

	doc = frappe.get_doc(MANUAL_DOCTYPE, name)

	return {
		"name": doc.name,
		"coach": doc.coach or "",
		"period": doc.period,
		"franchise_fee_amount": flt(doc.franchise_fee_amount, 2),
		"marketing_fee_amount": flt(doc.marketing_fee_amount, 2),
		"note": doc.note or "",
	}


@frappe.whitelist()
def delete_manual_fee_total(name=None):
	ensure_office_user()

	name = (name or "").strip()
	if not name or not frappe.db.exists(MANUAL_DOCTYPE, name):
		frappe.throw(_("Entry not found."))

	frappe.delete_doc(MANUAL_DOCTYPE, name, ignore_permissions=True)

	return {"ok": 1}
