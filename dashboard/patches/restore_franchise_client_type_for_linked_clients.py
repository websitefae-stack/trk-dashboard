"""
One-time correction for apply_age_and_client_type()'s bug: it used to
unconditionally overwrite client_type from a Client's date_of_birth,
including on a Coach's own linked_client record (the Client used to
represent that coach for internal/cross-coach invoicing) - those must
always be client_type "Franchise", never an age bracket, since several
things throughout the app key off it (bank-account confirmation prompts,
interbusiness revenue splitting, and other franchisees being able to see
and invoice each other at all - a Client that isn't actually "Franchise"
type loses that visibility).

Runs automatically on the next `bench migrate` (part of a normal deploy) -
no manual step needed.
"""

import frappe


def execute():
    if not frappe.db.exists("DocType", "Coach") or not frappe.db.exists("DocType", "Client"):
        return

    coach_meta = frappe.get_meta("Coach")
    client_meta = frappe.get_meta("Client")

    if not coach_meta.has_field("linked_client") or not client_meta.has_field("client_type"):
        return

    linked_client_names = frappe.get_all(
        "Coach",
        filters={"linked_client": ["is", "set"]},
        pluck="linked_client",
    )

    if not linked_client_names:
        return

    rows = frappe.get_all(
        "Client",
        filters={
            "name": ["in", linked_client_names],
            "client_type": ["!=", "Franchise"],
        },
        pluck="name",
    )

    for name in rows:
        try:
            frappe.db.set_value("Client", name, "client_type", "Franchise", update_modified=False)
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Restore Franchise Client Type - {name}")

    frappe.db.commit()
