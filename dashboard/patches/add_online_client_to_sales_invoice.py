"""
Adds custom_online_client to Sales Invoice - the counterpart to
custom_client, but for invoices raised from a guest online purchase
(see api/shared/webshop_purchase.py) rather than an existing coaching
Client. Kept as a separate field (not reused/mixed into custom_client)
so online purchases never pollute the real Client list - Ashley links
the two manually later, by matching email address, via Online
Client.linked_client.

Also adds custom_stripe_session_id, which webshop_purchase.py's Stripe
webhook uses to recognise a checkout.session.completed event it's
already fulfilled (Stripe retries webhook deliveries until it gets a
200 back, so the same event can arrive more than once).
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

SALES_INVOICE_FIELDS = [
    {
        "fieldname": "custom_online_client",
        "fieldtype": "Link",
        "label": "Online Client",
        "options": "Online Client",
        "insert_after": "customer",
        "module": "Dashboard",
    },
    {
        "fieldname": "custom_stripe_session_id",
        "fieldtype": "Data",
        "label": "Stripe Checkout Session ID",
        "insert_after": "custom_online_client",
        "read_only": 1,
        "module": "Dashboard",
    },
]


def execute():
    if not frappe.db.exists("DocType", "Sales Invoice") or not frappe.db.exists("DocType", "Online Client"):
        return

    create_custom_fields({"Sales Invoice": SALES_INVOICE_FIELDS}, ignore_validate=True)
    frappe.db.commit()
