"""
One-time cleanup for notifications already stuck referencing a user
that isn't a real Frappe User any more (e.g. a Coach record whose
linked user/coach_email held something like "JP" - an account that was
briefly a Frappe Cloud admin and has since been removed). Covers both
directions:

- Recipient side (for_user / recipient_user): these were never visible
  to anyone, since nobody's session.user ever matches a value that
  isn't an actual account, and only ever surfaced to a franchisor who
  happened to open them directly by link.
- Sender side (from_user / created_by_user, plus the stored sent_by/
  sent_by_name snapshots on messages and replies): _get_user_full_name()
  falls back to the raw stored value once the User record is gone, so
  these kept showing e.g. "JP posted this" long after that account
  stopped existing anywhere - confusing, since there's no way to tell
  who actually sent it.

create_trk_notification() (notifications.py), alongside this patch,
now refuses to create a new notification addressed to a non-existent
recipient and falls back to OFFICE_USER itself - this reroutes
whatever's already sitting stuck this way, on both ends, so nothing
reads as coming from or going to an account that no longer exists.
"""

import frappe

from dashboard.api.shared.notifications import (
    OFFICE_USER,
    NOTIFICATION_DOCTYPE,
    CONVERSATION_DOCTYPE,
    RECIPIENT_CHILD_DOCTYPE,
    MESSAGE_DOCTYPE,
)

REPLY_CHILD_DOCTYPE = "TRK Notification Reply"


def _bad_values(doctype, fieldname, office_user):
    if not frappe.db.exists("DocType", doctype) or not frappe.get_meta(doctype).has_field(fieldname):
        return set()

    values = set(frappe.get_all(
        doctype,
        filters={fieldname: ["is", "set"]},
        pluck=fieldname,
        distinct=True,
    ))

    return {
        value for value in values
        if value and value != office_user and not frappe.db.exists("User", value)
    }


def execute():
    if not frappe.db.exists("User", OFFICE_USER):
        return

    office_label = frappe.db.get_value("User", OFFICE_USER, "full_name") or OFFICE_USER

    # Recipient side.
    for bad_value in _bad_values(NOTIFICATION_DOCTYPE, "for_user", OFFICE_USER):
        frappe.db.set_value(NOTIFICATION_DOCTYPE, {"for_user": bad_value}, "for_user", OFFICE_USER, update_modified=False)

    for bad_value in _bad_values(RECIPIENT_CHILD_DOCTYPE, "recipient_user", OFFICE_USER):
        frappe.db.set_value(RECIPIENT_CHILD_DOCTYPE, {"recipient_user": bad_value}, "recipient_user", OFFICE_USER, update_modified=False)

    # Sender side - live-resolved fields just need the user id fixed.
    for bad_value in _bad_values(NOTIFICATION_DOCTYPE, "from_user", OFFICE_USER):
        frappe.db.set_value(NOTIFICATION_DOCTYPE, {"from_user": bad_value}, "from_user", OFFICE_USER, update_modified=False)

    for bad_value in _bad_values(CONVERSATION_DOCTYPE, "created_by_user", OFFICE_USER):
        frappe.db.set_value(CONVERSATION_DOCTYPE, {"created_by_user": bad_value}, "created_by_user", OFFICE_USER, update_modified=False)

    # Sender side - these also store a point-in-time "sent_by_name"/
    # "sent_by_label" snapshot that has to be rewritten too, or the stale
    # label keeps showing even after sent_by itself is fixed.
    for bad_value in _bad_values(MESSAGE_DOCTYPE, "sent_by", OFFICE_USER):
        frappe.db.set_value(
            MESSAGE_DOCTYPE,
            {"sent_by": bad_value},
            {"sent_by": OFFICE_USER, "sent_by_name": office_label},
            update_modified=False,
        )

    for bad_value in _bad_values(REPLY_CHILD_DOCTYPE, "sent_by", OFFICE_USER):
        frappe.db.set_value(
            REPLY_CHILD_DOCTYPE,
            {"sent_by": bad_value},
            {"sent_by": OFFICE_USER, "sent_by_label": office_label},
            update_modified=False,
        )

    frappe.db.commit()
