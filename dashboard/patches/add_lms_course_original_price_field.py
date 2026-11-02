"""
LMS Course.custom_original_price - an optional "was" price shown
struck through next to the real course_price on the public course
detail page (resilient_domains' trh-course-detail) whenever it's set
and higher than course_price, to advertise a course as discounted.
course_price itself stays the actual price charged (what Buy Course
adds to the cart) - this is purely the comparison figure shown
alongside it. Blank (the default) means "not currently discounted" -
the page falls back to showing just the plain price, same as today.

Safe to run more than once - create_custom_fields skips fields that
already exist.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

LMS_COURSE_FIELDS = [
	{
		"fieldname": "custom_original_price",
		"fieldtype": "Currency",
		"label": "Original Price (before discount)",
		"insert_after": "course_price",
		"module": "Dashboard",
		"description": (
			"Optional - set this to the course's normal price to show it struck through next to the "
			"current (discounted) course_price on the public course page. Leave blank when the course "
			"isn't currently discounted."
		),
	},
]


def execute():
	if not frappe.db.exists("DocType", "LMS Course"):
		return

	create_custom_fields({"LMS Course": LMS_COURSE_FIELDS}, ignore_validate=True)
	frappe.db.commit()
