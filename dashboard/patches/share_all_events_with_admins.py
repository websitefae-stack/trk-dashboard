"""
One-time backfill: fix_public_events (the previous patch) only shared
appointments that were being converted from Public to Private. Any
appointment that was already Private before these changes existed - because
Private is the field's own default when nothing sets it - was never shared
with the dashboard admin accounts at all, leaving it fully inaccessible to
them in the raw Frappe backend (no view/edit/delete).

This shares every existing Event with the admin accounts, regardless of its
current event_type, closing that gap. Safe to run more than once - skips
anything already shared.

Runs automatically on the next `bench migrate` (part of a normal deploy) -
no manual step needed.
"""

import frappe

from dashboard.api.shared.calendar import DASHBOARD_ADMIN_USERS


def execute():
    event_names = frappe.get_all("Event", pluck="name")

    for name in event_names:
        for user in DASHBOARD_ADMIN_USERS:
            try:
                if not frappe.db.exists("User", user):
                    continue
                frappe.share.add_docshare(
                    "Event",
                    name,
                    user,
                    read=1,
                    write=1,
                    notify=0,
                    flags={"ignore_share_permission": True},
                )
            except Exception:
                frappe.log_error(frappe.get_traceback(), f"Share All Events with Admins - {name}")

    frappe.db.commit()
