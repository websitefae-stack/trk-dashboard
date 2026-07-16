"""
Adds custom_thread_id to Notification Log - Notification Log's for_user is
a single Link, so sending one message to several recipients (on a site
without "Dashboard Conversation" installed - see _send_legacy_notification)
has always meant one separate row per recipient. Without something tying
those rows together, each recipient (and the sender, matched separately via
from_user) saw their own disconnected copy of the same conversation - a
reply on one didn't show up on anyone else's, and the sender saw one card
per recipient instead of one shared conversation.

custom_thread_id is stamped with the same value across every row created
by a single "send to N people" call, so get_notifications() can collapse
them back into one card, and replies can be mirrored across every sibling
row in the group. See notifications.py's _send_legacy_notification,
_reply_to_notification_log, and _dedupe_notification_log_rows_by_thread.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

NOTIFICATION_LOG_FIELDS = [
    {
        "fieldname": "custom_thread_id",
        "fieldtype": "Data",
        "label": "Thread ID",
        "module": "Dashboard",
    },
]


def execute():
    if not frappe.db.exists("DocType", "Notification Log"):
        return

    create_custom_fields({"Notification Log": NOTIFICATION_LOG_FIELDS}, ignore_validate=True)
    frappe.db.commit()
