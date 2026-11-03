"""
A standalone HQ Stock Item doctype - Ashley's own physical inventory
count, separate from anything in the Store (custom=1, no link to Item
at all). Most of what's on her own stock-tracker spreadsheet was never
set up as a real Store Product (pens, bracelets, bags, hoodies, sensory
pods, etc. - she's explicit this is never meant to be: "it is not
linked to the store it is just for ashley to keep track of what she
has so she knows"), so get_hq_stock_overview() in coach_stock.py now
merges this list in alongside the existing Store-Item-backed one,
sorted together alphabetically, rather than requiring every one of
these to become a real purchasable product just to be counted.

Seeded from her own spreadsheet's current counts - skips any item_name
that already exists, so a re-run (or a manually added row in between)
is never overwritten.

Same custom=1, frappe.get_doc({...}).insert(ignore_permissions=True)
pattern as create_coach_stock_movement_doctype.py. Runs automatically
on the next `bench migrate` - no manual step needed.
"""

import frappe

DOCTYPE = "HQ Stock Item"

# (item_name, stock_qty) - straight from Ashley's own Resilient_Stock_
# Tracker.xlsx. "Parents book" had no quantity recorded at all there -
# seeded at 0 rather than guessed.
SEED_ITEMS = [
	("Weighted polar bear", 1),
	("Weighted sloth", 2),
	("Weighted panda", 1),
	("Toasty socks", 43),
	("Resilient Teen pens", 40),
	("Resilient Kid pens", 40),
	("Resilient People pens", 3),
	("Steady Me bracelets", 17),
	("Resilient fidget rings", 26),
	("Teen mirrors", 44),
	("Freebie fans", 62),
	("Freebie pens", 21),
	("Freebie fidgets", 38),
	("Necklaces", 17),
	("iPad covers", 44),
	("Teen bag - Teal", 14),
	("Teen bag - Black", 6),
	("Teen bag - Green", 15),
	("Cups", 36),
	("Sensory pod - Small", 4),
	("Sensory pod - Medium", 3),
	("Sensory pod - Large", 1),
	("Sleep masks", 44),
	("Notebooks", 39),
	("Worry worms", 37),
	("Resilient Teen pin badges", 167),
	("Resilient Kid pin badges", 115),
	("Brave jars", 13),
	("Hoodie - Pink - Small", 2),
	("Hoodie - Pink - Medium", 2),
	("Hoodie - Pink - Large", 2),
	("Hoodie - Pink - XL", 2),
	("Hoodie - Teal - Small", 2),
	("Hoodie - Teal - Medium", 2),
	("Hoodie - Teal - Large", 2),
	("Hoodie - Teal - XL", 2),
	("Hoodie - Black - Small", 2),
	("Hoodie - Black - Medium", 2),
	("Hoodie - Black - Large", 2),
	("Hoodie - Black - XL", 2),
	("Hoodie - Brown - Small", 2),
	("Hoodie - Brown - Medium", 2),
	("Hoodie - Brown - Large", 2),
	("Hoodie - Brown - XL", 2),
	("Weighted blanket - Small", 1),
	("Weighted blanket - Medium", 1),
	("Weighted blanket - Large", 1),
	("Moonstone bracelets", 46),
	("Hoodie - Pink - XS", 2),
	("Hoodie - Black - XS", 2),
	("Hoodie - Teal - XS", 2),
	("Hoodie - Brown - XS", 2),
	("teen journal", 13),
	("Parents book", 0),
]


def _ensure_doctype():
	if frappe.db.exists("DocType", DOCTYPE):
		return

	doc = frappe.get_doc({
		"doctype": "DocType",
		"name": DOCTYPE,
		"module": "Dashboard",
		"custom": 1,
		"naming_rule": "Autoincrement",
		"autoname": "autoincrement",
		"fields": [
			{
				"fieldname": "item_name",
				"fieldtype": "Data",
				"label": "Item",
				"reqd": 1,
				"unique": 1,
				"in_list_view": 1,
			},
			{
				"fieldname": "stock_qty",
				"fieldtype": "Int",
				"label": "Quantity",
				"default": "0",
				"in_list_view": 1,
			},
		],
		"permissions": [
			{
				"role": "System Manager",
				"read": 1, "write": 1, "create": 1, "delete": 1,
				"report": 1, "export": 1, "print": 1, "email": 1, "share": 1,
			},
		],
		"sort_field": "item_name",
		"sort_order": "ASC",
		"track_changes": 1,
	})
	doc.insert(ignore_permissions=True)


def _seed_items():
	for item_name, qty in SEED_ITEMS:
		if frappe.db.exists(DOCTYPE, {"item_name": item_name}):
			continue

		frappe.get_doc({
			"doctype": DOCTYPE,
			"item_name": item_name,
			"stock_qty": qty or 0,
		}).insert(ignore_permissions=True)


def execute():
	_ensure_doctype()
	_seed_items()
	frappe.db.commit()
