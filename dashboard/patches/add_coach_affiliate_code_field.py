"""
Ashley asked for an affiliate code per coach, so they can share store
products/courses and earn a commission - see dashboard/api/shared/
affiliate.py for the full mechanism (Affiliate Product Setting sets the
commission per item/course, Affiliate Commission records each paid sale
attributed to a coach's code).

affiliate_code is generated lazily (see _ensure_affiliate_code_for in
affiliate.py) the first time a coach's own link is actually requested,
not backfilled here for every existing coach - no need to mint codes
for coaches who may never use this.

Runs automatically on the next `bench migrate` - no manual step needed.
Safe to run more than once - create_custom_fields skips fields that
already exist.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

COACH_FIELDS = [
	{
		"fieldname": "affiliate_code",
		"fieldtype": "Data",
		"label": "Affiliate Code",
		"insert_after": "custom_own_client",
		"module": "Dashboard",
		"unique": 1,
		"read_only": 1,
		"description": (
			"Generated automatically the first time this coach's own affiliate link is requested - "
			"don't set by hand."
		),
	},
]


def execute():
	if not frappe.db.exists("DocType", "Coach"):
		return

	create_custom_fields({"Coach": COACH_FIELDS}, ignore_validate=True)
	frappe.db.commit()
