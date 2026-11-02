"""
A limited-quantity bonus for a store product (e.g. a course) - give
the first N buyers an extra digital download (e.g. a free PDF copy of
a book) alongside whatever they actually bought. Three new Item
fields, same "Rachel/Ashley attaches it once on the product" pattern
as the existing custom_digital_file (add_item_digital_file_and_
course_unlock_fields.py), not a one-off for any single product:

- custom_bonus_digital_file (Attach) - the bonus file itself.
- custom_bonus_label (Data) - optional display name for it in the
  order confirmation email (e.g. "Ashley's Book (PDF)") - falls back
  to "<item name> - Bonus" when left blank.
- custom_bonus_limit (Int) - how many total paid orders for this item
  still get the bonus. Counted live against actual submitted Sales
  Invoice Item rows at fulfilment time (webshop_purchase.py), not a
  separately-maintained counter - see that file's own comment for why.

Safe to run more than once - create_custom_fields skips fields that
already exist.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

ITEM_FIELDS = [
	{
		"fieldname": "custom_bonus_digital_file",
		"fieldtype": "Attach",
		"label": "Bonus Digital File",
		"insert_after": "custom_unlocks_lms_course",
		"module": "Dashboard",
		"description": "Optional - an extra download given to the first Bonus Limit buyers of this product.",
	},
	{
		"fieldname": "custom_bonus_label",
		"fieldtype": "Data",
		"label": "Bonus Label",
		"insert_after": "custom_bonus_digital_file",
		"module": "Dashboard",
		"description": 'How the bonus is described in the order confirmation email - falls back to "<product name> - Bonus" if left blank.',
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
	if not frappe.db.exists("DocType", "Item"):
		return

	create_custom_fields({"Item": ITEM_FIELDS}, ignore_validate=True)
	frappe.db.commit()
