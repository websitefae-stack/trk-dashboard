"""
The same "first N buyers get a bonus download" fields Item already has
(add_item_bonus_digital_file_fields.py) - a paid course's own
purchasable Item is auto-generated and kept deliberately out of the
Store Products page (custom_store_enabled=0 - see store_products._
ensure_course_item's own docstring: "stays out of the general store
grid, only ever reachable by adding it to the cart from the course's
own page"), so there was nowhere to actually set a course's bonus from
the dashboard at all. These three fields go on LMS Course instead -
the same place Ashley already sets course_price/custom_original_price,
in Desk - and _ensure_course_item now copies them down to the course's
backing Item on every save, same as it already does for price/title/
image, so webshop_purchase.py's existing delivery logic (which only
ever reads the Item's own custom_bonus_* fields, unchanged) picks them
up with no further changes needed there.

Safe to run more than once - create_custom_fields skips fields that
already exist.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

LMS_COURSE_FIELDS = [
	{
		"fieldname": "custom_bonus_digital_file",
		"fieldtype": "Attach",
		"label": "Bonus Digital File",
		"insert_after": "custom_original_price",
		"module": "Dashboard",
		"description": "Optional - an extra download given to the first Bonus Limit buyers of this course.",
	},
	{
		"fieldname": "custom_bonus_label",
		"fieldtype": "Data",
		"label": "Bonus Label",
		"insert_after": "custom_bonus_digital_file",
		"module": "Dashboard",
		"description": 'How the bonus is described in the order confirmation email - falls back to "<course title> - Bonus" if left blank.',
	},
	{
		"fieldname": "custom_bonus_limit",
		"fieldtype": "Int",
		"label": "Bonus Limit",
		"insert_after": "custom_bonus_label",
		"module": "Dashboard",
		"description": "How many buyers (in purchase order) get the Bonus Digital File - e.g. 20 for \"first 20 buyers\". Leave blank/0 for no bonus.",
	},
]


def execute():
	if not frappe.db.exists("DocType", "LMS Course"):
		return

	create_custom_fields({"LMS Course": LMS_COURSE_FIELDS}, ignore_validate=True)
	frappe.db.commit()
