"""
One-time cleanup for notifications already stuck addressed to a
recipient_user/for_user that isn't a real Frappe User (e.g. a Coach
record whose linked user/coach_email held something like "JP" instead
of a real email) - these were never visible to anyone, since nobody's
session.user ever matches a value that isn't an actual account, and
only ever surfaced to a franchisor who happened to open them directly
by link. create_trk_notification() (notifications.py), alongside this
patch, now refuses to create a new one this way and falls back to
OFFICE_USER itself - this reroutes whatever's already sitting
orphaned in the same way, so it actually reaches an inbox someone
reads.
"""

import frappe

from dashboard.api.shared.notifications import (
    OFFICE_USER,
    NOTIFICATION_DOCTYPE,
    CONVERSATION_DOCTYPE,
    RECIPIENT_CHILD_DOCTYPE,
)


def execute():
    if not frappe.db.exists("User", OFFICE_USER):
        return

    if frappe.db.exists("DocType", NOTIFICATION_DOCTYPE) and frappe.get_meta(NOTIFICATION_DOCTYPE).has_field("for_user"):
        orphaned_for_users = set(frappe.get_all(
            NOTIFICATION_DOCTYPE,
            filters={"for_user": ["is", "set"]},
            pluck="for_user",
            distinct=True,
        ))
        bad_for_users = {
            value for value in orphaned_for_users
            if value and value != OFFICE_USER and not frappe.db.exists("User", value)
        }

        for bad_value in bad_for_users:
            frappe.db.set_value(
                NOTIFICATION_DOCTYPE,
                {"for_user": bad_value},
                "for_user",
                OFFICE_USER,
                update_modified=False,
            )

    if frappe.db.exists("DocType", CONVERSATION_DOCTYPE) and frappe.db.exists("DocType", RECIPIENT_CHILD_DOCTYPE):
        orphaned_recipients = set(frappe.get_all(
            RECIPIENT_CHILD_DOCTYPE,
            filters={"recipient_user": ["is", "set"]},
            pluck="recipient_user",
            distinct=True,
        ))
        bad_recipients = {
            value for value in orphaned_recipients
            if value and value != OFFICE_USER and not frappe.db.exists("User", value)
        }

        for bad_value in bad_recipients:
            frappe.db.set_value(
                RECIPIENT_CHILD_DOCTYPE,
                {"recipient_user": bad_value},
                "recipient_user",
                OFFICE_USER,
                update_modified=False,
            )

    frappe.db.commit()
