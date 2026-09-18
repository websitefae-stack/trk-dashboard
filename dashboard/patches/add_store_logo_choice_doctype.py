"""
Creates the "Store Logo Choice" single doctype - one place to upload
the four brand logo images (The Resilient Kid/Teen/People/School) shown
on a product page when Item.custom_logo_choice_enabled is ticked, so
the buyer can see what each looks like before choosing which one goes
on the sleeve/leg. Uploaded once here, reused by every product that
turns the choice on - see store_products.py's get_logo_choice_options/
save_logo_choice_options.

Runs automatically on the next `bench migrate` - no manual step needed.
"""

import frappe

DOCTYPE = "Store Logo Choice"


def execute():
    if frappe.db.exists("DocType", DOCTYPE):
        return

    doc = frappe.get_doc({
        "doctype": "DocType",
        "name": DOCTYPE,
        "module": "Dashboard",
        "custom": 1,
        "issingle": 1,
        "fields": [
            {"fieldname": "kid_logo", "fieldtype": "Attach Image", "label": "The Resilient Kid - Logo"},
            {"fieldname": "teen_logo", "fieldtype": "Attach Image", "label": "The Resilient Teen - Logo"},
            {"fieldname": "people_logo", "fieldtype": "Attach Image", "label": "The Resilient People - Logo"},
            {"fieldname": "school_logo", "fieldtype": "Attach Image", "label": "The Resilient School - Logo"},
        ],
        "permissions": [
            {
                "role": "System Manager",
                "read": 1, "write": 1, "create": 1, "delete": 1,
                "report": 1, "export": 1, "print": 1, "email": 1, "share": 1,
            },
        ],
    })
    doc.insert(ignore_permissions=True)
