"""
One-time creation of the "Website Customers" Email Group that online
webshop orders are automatically added to (see
dashboard.api.shared.webshop_purchase._fulfil_checkout_session) - so
the group exists the first time an order comes through, without a
manual Desk step first.

Runs automatically on the next `bench migrate`. Safe to run more than
once - does nothing if the group already exists.
"""

import frappe

EMAIL_GROUP = "Website Customers"


def execute():
    if not frappe.db.exists("DocType", "Email Group"):
        return

    if frappe.db.exists("Email Group", EMAIL_GROUP):
        return

    title_field = "title" if frappe.get_meta("Email Group").has_field("title") else None

    doc = frappe.new_doc("Email Group")

    if title_field:
        doc.set(title_field, EMAIL_GROUP)
    else:
        doc.name = EMAIL_GROUP

    doc.insert(ignore_permissions=True)
    frappe.db.commit()
