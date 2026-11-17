"""
Client Portal Access report feedback: "there are no dates when access
was granted" - even rows that already had portal_access_enabled=1 from
before the granted-on tracking existed show "-" forever, since that
field is only ever set going forward, on a fresh off -> on transition.

Backfills it for any already-enabled Client Contact Link row that's
still missing it, using the row's own creation date as the closest
available estimate of when access was actually turned on.
"""

import frappe


def execute():
    if not frappe.db.exists("DocType", "Client Contact Link"):
        return

    meta = frappe.get_meta("Client Contact Link")
    if not meta.has_field("portal_access_granted_on"):
        return

    rows = frappe.get_all(
        "Client Contact Link",
        filters={
            "portal_access_enabled": 1,
            "portal_access_granted_on": ["in", ["", None]],
        },
        fields=["name", "creation"],
    )

    for row in rows:
        frappe.db.set_value(
            "Client Contact Link",
            row.name,
            "portal_access_granted_on",
            frappe.utils.getdate(row.creation),
            update_modified=False,
        )

    frappe.db.commit()
