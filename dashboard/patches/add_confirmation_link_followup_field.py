"""
Adds custom_confirmation_link_pending to Event - tracks a booking
confirmation that had to go out before its Google Meet link was ready (see
send_pending_booking_confirmations() in booking_confirmations.py), so a
short follow-up email with the actual link can be sent once it turns up
instead of the client being told "it'll follow separately" and then never
hearing anything else.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

EVENT_FIELDS = [
    {
        "fieldname": "custom_confirmation_link_pending",
        "fieldtype": "Check",
        "label": "Meeting Link Follow-Up Email Pending",
        "default": "0",
        "module": "Dashboard",
    },
]


def execute():
    if not frappe.db.exists("DocType", "Event"):
        return

    create_custom_fields({"Event": EVENT_FIELDS}, ignore_validate=True)
    frappe.db.commit()
