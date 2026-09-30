"""
Adds custom_online_contact to Sales Invoice - a Client-less fallback for
_get_or_create_portal_client()/_fulfil_checkout_session() in
webshop_purchase.py, for the one case a straight Client.email match can't
resolve on its own: several Clients sharing the same email (e.g. two kids
with no email of their own, both using a parent's), where there's no way
to tell from the email alone which specific Client a purchase was
actually for. Rather than guessing, that invoice attaches to the shared
Contact instead of any one Client - custom_client stays blank, this
field is set instead - and the client_portal app's "Combined" view (see
its get_combined_invoices) shows it across every client linked to that
Contact rather than under just one.

A purchase whose email matches exactly one Client (the normal case)
still sets custom_client as before; this field is only ever used for
the ambiguous multi-match case.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

SALES_INVOICE_FIELDS = [
    {
        "fieldname": "custom_online_contact",
        "fieldtype": "Link",
        "label": "Online Contact (ambiguous Client match)",
        "options": "Contact",
        "insert_after": "custom_client",
        "read_only": 1,
        "module": "Dashboard",
    },
]


def execute():
    if not frappe.db.exists("DocType", "Sales Invoice"):
        return

    create_custom_fields({"Sales Invoice": SALES_INVOICE_FIELDS}, ignore_validate=True)
    frappe.db.commit()
