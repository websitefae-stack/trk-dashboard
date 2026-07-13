"""
Adds custom_replies to Notification Log - a Table field (options "TRK
Notification Reply") so notifications that fall back to plain Notification
Log records (see notifications.py's reply_to_notification /
_format_notification_log) can carry an actual reply thread, the same way
"Dashboard Conversation" already supports replies where that doctype exists.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

NOTIFICATION_LOG_FIELDS = [
    {
        "fieldname": "custom_replies",
        "fieldtype": "Table",
        "label": "Replies",
        "options": "TRK Notification Reply",
        "module": "Dashboard",
    },
]


def execute():
    if not frappe.db.exists("DocType", "Notification Log"):
        return

    create_custom_fields({"Notification Log": NOTIFICATION_LOG_FIELDS}, ignore_validate=True)
    frappe.db.commit()
