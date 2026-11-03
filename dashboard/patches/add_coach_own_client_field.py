"""
A coach's own dedicated Client record, so a Coach Store order raised for
them (webshop_purchase.create_coach_store_order) can set Sales Invoice.
custom_client to something real instead of leaving it blank - Ashley
confirmed each coach already has a dedicated Client/Contact record set
up for exactly this (it's just never been linked anywhere a coach's own
transactions could find it automatically).

Left blank/optional on purpose: a coach with nothing set here just keeps
today's behaviour (custom_client stays blank on their own orders - see
make_sales_invoice_custom_client_optional.py) rather than this being a
hard requirement before anyone can place an order at all.

Runs automatically on the next `bench migrate` - no manual step needed.
Safe to run more than once - create_custom_fields skips fields that
already exist.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

COACH_FIELDS = [
	{
		"fieldname": "custom_own_client",
		"fieldtype": "Link",
		"options": "Client",
		"label": "Own Client Record",
		"insert_after": "training_day_completed_on",
		"module": "Dashboard",
		"description": (
			"This coach's own dedicated Client record (for billing, e.g. their own Coach Store "
			"orders) - optional, leave blank if they don't have one set up."
		),
	},
]


def execute():
	if not frappe.db.exists("DocType", "Coach"):
		return

	create_custom_fields({"Coach": COACH_FIELDS}, ignore_validate=True)
	frappe.db.commit()
