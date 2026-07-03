"""
One-time cleanup: appointments were previously created with event_type
"Public", which - per Frappe's own Event permission model - made every
appointment visible (and reminder-eligible) to every user, not just its
owner. Flips any still-Public Event to Private, and shares each one with
the dashboard admin accounts so they keep full visibility in the raw
Frappe backend without needing Public.

Runs automatically on the next `bench migrate` (part of a normal deploy) -
no manual step needed.
"""

import frappe

from dashboard.api.shared.calendar import DASHBOARD_ADMIN_USERS


def execute():
    event_names = frappe.get_all("Event", filters={"event_type": "Public"}, pluck="name")

    for name in event_names:
        try:
            frappe.db.set_value("Event", name, "event_type", "Private", update_modified=False)
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Fix Public Events - set Private - {name}")
            continue

        _share_with_admins(name)

    frappe.db.commit()


def _share_with_admins(event_name):
    for user in DASHBOARD_ADMIN_USERS:
        try:
            if not frappe.db.exists("User", user):
                continue
            if frappe.db.exists(
                "DocShare", {"share_doctype": "Event", "share_name": event_name, "user": user}
            ):
                continue
            frappe.share.add_docshare(
                "Event",
                event_name,
                user,
                read=1,
                notify=0,
                flags={"ignore_share_permission": True},
            )
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Fix Public Events - share - {event_name}")
