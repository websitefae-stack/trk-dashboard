"""
Adds custom_invoice_sent_on to Sales Invoice - stamped automatically by
send_invoice_email() (invoices.py) every time an invoice is emailed to a
client, and overwritten on each resend so it always reflects the most
recent send. Drives the "Sent" column on the invoice list, the client
file's Invoices table, and the franchisor invoice list.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

SALES_INVOICE_FIELDS = [
    {
        "fieldname": "custom_invoice_sent_on",
        "fieldtype": "Datetime",
        "label": "Invoice Sent On",
        "read_only": 1,
        "module": "Dashboard",
    },
]


def execute():
    if not frappe.db.exists("DocType", "Sales Invoice"):
        return

    create_custom_fields({"Sales Invoice": SALES_INVOICE_FIELDS}, ignore_validate=True)
    frappe.db.commit()
