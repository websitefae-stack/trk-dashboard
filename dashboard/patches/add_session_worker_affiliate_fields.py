"""
Session workers get their own affiliate link too (Ashley's own
permission list for this role: "do they get affiliate links - YES"),
same mechanism Coach already has - see affiliate.py's _ensure_
affiliate_code_for/_current_earner, which resolve either doctype.

affiliate_code is generated lazily the first time a session worker's
own link is actually requested, not backfilled here. Unlike Coach's
own affiliate_code, this one is NOT marked unique at the DB level -
Coach and Session Worker are two separate tables, so a DB-level unique
constraint on each only guards within that one table; the actual
cross-doctype uniqueness guarantee (no Coach and Session Worker ever
sharing a code, which code resolution depends on) is enforced in
application code instead (see _ensure_affiliate_code_for, which checks
both tables before accepting a new candidate).

Runs automatically on the next `bench migrate` - no manual step
needed. Safe to run more than once - create_custom_fields skips fields
that already exist.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

SESSION_WORKER_DOCTYPE = "Session Worker"

SESSION_WORKER_FIELDS = [
	{
		"fieldname": "affiliate_code",
		"fieldtype": "Data",
		"label": "Affiliate Code",
		"module": "Dashboard",
		"read_only": 1,
		"description": (
			"Generated automatically the first time this session worker's own affiliate link is "
			"requested - don't set by hand."
		),
	},
	{
		"fieldname": "affiliate_click_count",
		"fieldtype": "Int",
		"label": "Affiliate Link Clicks",
		"insert_after": "affiliate_code",
		"module": "Dashboard",
		"default": "0",
		"read_only": 1,
		"description": "Kept in sync by affiliate.py's record_affiliate_click - don't set by hand.",
	},
]


def execute():
	if not frappe.db.exists("DocType", SESSION_WORKER_DOCTYPE):
		return

	create_custom_fields({SESSION_WORKER_DOCTYPE: SESSION_WORKER_FIELDS}, ignore_validate=True)
	frappe.db.commit()
