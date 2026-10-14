"""
custom_reminder_sent - lets booking_confirmations.send_online_session_
reminders() mark an Event once its 1-hour-before reminder has gone out,
so the 5-minute sweep (its matching window is wider than the cron
interval on purpose, to never miss one) never sends the same reminder
twice for the same session.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

EVENT_FIELDS = [
    {
        "fieldname": "custom_reminder_sent",
        "fieldtype": "Check",
        "label": "Online Session Reminder Sent",
        "default": "0",
        "module": "Dashboard",
    },
]


def execute():
    if not frappe.db.exists("DocType", "Event"):
        return

    create_custom_fields({"Event": EVENT_FIELDS}, ignore_validate=True)
    frappe.db.commit()
