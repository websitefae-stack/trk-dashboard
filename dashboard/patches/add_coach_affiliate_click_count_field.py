"""
Ashley asked to see how many clicks each coach's affiliate link got -
see affiliate.py's record_affiliate_click (called from
resilient_domains' cart.js the moment a genuine ?aff=<code> is found in
the URL) and get_affiliate_coach_performance (the Affiliates page's own
per-coach summary).

A plain running count, not a full click log - good enough for "how much
traffic is this link actually getting", not click-by-click analytics.

Runs automatically on the next `bench migrate` - no manual step needed.
Safe to run more than once - create_custom_fields skips fields that
already exist.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

COACH_FIELDS = [
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
	if not frappe.db.exists("DocType", "Coach"):
		return

	create_custom_fields({"Coach": COACH_FIELDS}, ignore_validate=True)
	frappe.db.commit()
