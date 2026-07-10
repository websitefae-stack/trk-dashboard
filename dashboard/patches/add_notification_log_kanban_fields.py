"""
Adds custom_due_date and custom_archived to Notification Log - core
Frappe's Notification Log doctype has neither, but they're needed to
drive the Notifications Kanban board (New / In Progress / Past Due /
Archived) on sites without "Dashboard Conversation" installed, where
sending/reading notifications falls back to plain Notification Log
records (see notifications.py's _send_legacy_notification /
_format_notification_log).
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

NOTIFICATION_LOG_FIELDS = [
    {
        "fieldname": "custom_due_date",
        "fieldtype": "Date",
        "label": "Due Date",
        "module": "Dashboard",
    },
    {
        "fieldname": "custom_archived",
        "fieldtype": "Check",
        "label": "Archived",
        "default": "0",
        "module": "Dashboard",
    },
]


def execute():
    if not frappe.db.exists("DocType", "Notification Log"):
        return

    create_custom_fields({"Notification Log": NOTIFICATION_LOG_FIELDS}, ignore_validate=True)
    frappe.db.commit()
