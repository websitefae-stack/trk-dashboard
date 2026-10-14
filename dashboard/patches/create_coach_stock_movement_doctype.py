"""
Coach Stock Movement - add-only ledger of per-coach Kid/Teen Pack stock
changes (see dashboard.api.shared.coach_stock's own module docstring for
the full feature). A coach's current balance for an item is always
SUM(quantity_change) grouped by coach+item, computed fresh every time
it's needed - never a separately cached balance field, so there's
nothing that can ever drift out of sync with the ledger it's meant to
summarise.

item is a plain Link to Item, not a Kid/Teen enum - deliberately, so a
future "additional workbook" SKU (out of scope for this build - those
are bought on an ongoing basis as a client progresses, not part of the
pack included in a client's first invoice) needs zero schema change.

Same custom=1, frappe.get_doc({...}).insert(ignore_permissions=True)
pattern as create_knowledge_vault_doctypes.py. Runs automatically on the
next `bench migrate` - no manual step needed.
"""

import frappe

DOCTYPE = "Coach Stock Movement"

MOVEMENT_TYPE_OPTIONS = "Opening Count\nReceived (Order)\nGiven to Client\nManual Adjustment"


def execute():
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
                "fieldname": "coach",
                "fieldtype": "Link",
                "options": "Coach",
                "label": "Coach",
                "reqd": 1,
                "in_list_view": 1,
            },
            {
                "fieldname": "item",
                "fieldtype": "Link",
                "options": "Item",
                "label": "Item",
                "reqd": 1,
                "in_list_view": 1,
            },
            {
                "fieldname": "quantity_change",
                "fieldtype": "Int",
                "label": "Quantity Change",
                "reqd": 1,
                "in_list_view": 1,
                "description": "Positive for received/opening/upward adjustment, negative for given-to-client/downward adjustment.",
            },
            {
                "fieldname": "movement_type",
                "fieldtype": "Select",
                "options": MOVEMENT_TYPE_OPTIONS,
                "label": "Movement Type",
                "reqd": 1,
                "in_list_view": 1,
            },
            {
                "fieldname": "reference_client",
                "fieldtype": "Link",
                "options": "Client",
                "label": "Reference Client",
                "description": "Set when movement_type is Given to Client.",
            },
            {
                "fieldname": "reference_sales_invoice",
                "fieldtype": "Link",
                "options": "Sales Invoice",
                "label": "Reference Sales Invoice",
                "description": "Set when movement_type is Received (Order).",
            },
            {
                "fieldname": "notes",
                "fieldtype": "Small Text",
                "label": "Notes",
                "description": "Required by the calling code (not this schema) when movement_type is Manual Adjustment.",
            },
            {
                "fieldname": "created_by_user",
                "fieldtype": "Link",
                "options": "User",
                "label": "Created By User",
            },
        ],
        "permissions": [
            {
                "role": "System Manager",
                "read": 1, "write": 1, "create": 1, "delete": 1,
                "report": 1, "export": 1, "print": 1, "email": 1, "share": 1,
            },
        ],
        "sort_field": "creation",
        "sort_order": "DESC",
        "track_changes": 1,
    })
    doc.insert(ignore_permissions=True)
