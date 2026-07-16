"""
Adds the fields booking_confirmations.py uses to hold a "send confirmation
email" request until any online session in the batch has its Google Meet
link (or has waited long enough that it's not coming) - see
send_pending_booking_confirmations() for how these are read.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

EVENT_FIELDS = [
    {
        "fieldname": "custom_confirmation_pending",
        "fieldtype": "Check",
        "label": "Booking Confirmation Email Pending",
        "default": "0",
        "module": "Dashboard",
    },
    {
        "fieldname": "custom_confirmation_recipient",
        "fieldtype": "Data",
        "label": "Booking Confirmation Recipient",
        "module": "Dashboard",
    },
    {
        "fieldname": "custom_confirmation_batch_events",
        "fieldtype": "Long Text",
        "label": "Booking Confirmation Batch Events",
        "module": "Dashboard",
    },
]


def execute():
    if not frappe.db.exists("DocType", "Event"):
        return

    create_custom_fields({"Event": EVENT_FIELDS}, ignore_validate=True)
    frappe.db.commit()
