"""
Lets a Session Worker submit their own testimonial too (Ashley's own
permission list for this role: "can upload their own testimonials -
YES") - a Coach Testimonial previously only ever belonged to a Coach
(the `coach` field). Adds a parallel `session_worker` Link, mutually
exclusive with `coach` - see testimonials.py's own save_testimonial for
how the two are resolved and kept apart.

Runs automatically on the next `bench migrate` - no manual step needed.
Safe to run more than once - create_custom_fields skips fields that
already exist.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

DOCTYPE_FIELDS = [
	{
		"fieldname": "session_worker",
		"fieldtype": "Link",
		"options": "Session Worker",
		"label": "Session Worker",
		"insert_after": "coach",
		"module": "Dashboard",
		"description": "Leave blank if this testimonial is for a Coach instead - set exactly one of the two.",
	},
]


def execute():
	if not frappe.db.exists("DocType", "Coach Testimonial"):
		return

	if not frappe.db.exists("DocType", "Session Worker"):
		return

	create_custom_fields({"Coach Testimonial": DOCTYPE_FIELDS}, ignore_validate=True)
	frappe.db.commit()
