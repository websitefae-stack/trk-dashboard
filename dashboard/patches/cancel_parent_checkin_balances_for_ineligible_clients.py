"""
One-time cleanup: invoices.py's _create_client_packages_from_invoice()
has skipped creating a Parent Check-In "Client Package Balance" row for
Adult/School/Company clients for a while now (see
_client_includes_parent_checkins() - only Kid/Teen/Uni Student clients
get them), but that guard only ever applied to packages created AFTER it
was added. Any Client Package Balance for an ineligible client created
before then is still sitting there, still "Active", still showing up on
the Open Session Packs report and anywhere else that reads a client's
available balances - even though that client could never actually book
a Parent Check-In against it (the booking form has always blocked that
selection for an Adult client separately).

Cancels those stale rows rather than deleting them - the qty_purchased
on each still reflects a real, already-paid invoice line, so the row
stays as a record of what was bought; it just stops counting as
available. Safe to run more than once - only ever touches rows still
"Active".
"""

import frappe

PARENT_CHECKIN_ITEM_CODE = "PAR001"
_CLIENT_TYPES_WITH_PARENT_CHECKINS = {"Kid", "Teen", "Uni Student"}


def execute():
    if not frappe.db.exists("DocType", "Client Package Balance"):
        return

    rows = frappe.get_all(
        "Client Package Balance",
        filters={"service_item": PARENT_CHECKIN_ITEM_CODE, "status": "Active"},
        fields=["name", "client"],
    )
    if not rows:
        return

    client_types = {}
    for row in rows:
        client = row.get("client")
        if client and client not in client_types:
            client_types[client] = frappe.db.get_value("Client", client, "client_type") or ""

    stale_names = [
        row["name"] for row in rows
        if client_types.get(row.get("client")) not in _CLIENT_TYPES_WITH_PARENT_CHECKINS
    ]
    if not stale_names:
        return

    for name in stale_names:
        frappe.db.set_value(
            "Client Package Balance", name,
            {"status": "Cancelled", "qty_available": 0},
            update_modified=False,
        )

    frappe.db.commit()
