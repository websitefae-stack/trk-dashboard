"""
A read-only counter next to Bonus Limit on LMS Course, showing how many
buyers/signups have actually received the Bonus Digital File so far -
Ashley had no way to tell from Desk whether the bonus had gone out to
anyone at all, just the fixed Bonus Limit she'd set.

Kept up to date wherever a bonus is actually granted: webshop_purchase.
py's _append_bonus_digital_files (a paid course purchase) and resilient_
domains' course_signup.py _send_signup_confirmation_email (a free
signup) both set it to that buyer/signer's own 1-indexed queue
position - the two paths share one course-level count since both write
the same field.

Safe to run more than once - create_custom_fields skips fields that
already exist.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

LMS_COURSE_FIELDS = [
	{
		"fieldname": "custom_bonus_given_count",
		"fieldtype": "Int",
		"label": "Bonus Given Out",
		"insert_after": "custom_bonus_limit",
		"module": "Dashboard",
		"read_only": 1,
		"default": "0",
		"description": "How many buyers/signups have already received the Bonus Digital File, out of Bonus Limit - updates automatically.",
	},
]


def execute():
	if not frappe.db.exists("DocType", "LMS Course"):
		return

	create_custom_fields({"LMS Course": LMS_COURSE_FIELDS}, ignore_validate=True)
	frappe.db.commit()
