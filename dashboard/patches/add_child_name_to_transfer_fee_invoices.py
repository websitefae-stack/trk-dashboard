"""
One-off catch-up for the client_transfers.py fix just shipped: a
transfer fee invoice's "Bill To" only ever shows the receiving coach's
own name (it's a coach-to-coach fee, not a real Client invoice), so the
actual transferred child's name - needed to trace an invoice back to
which transfer it belongs to - lived only in a line item description
nobody opens. New invoices now put it in the item's own display name
and in the invoice's remarks too; this updates every transfer fee
invoice that already exists (created before this fix, or by the
backfill patch that ran just before this one) to match.

Direct field updates only (item_name/description/remarks), not a
re-submission - safe on an already-submitted invoice.
"""

import frappe

from dashboard.api.shared.client_transfers import TRANSFER_DOCTYPE, TRANSFER_FEE_ITEM_CODE, _coach_label


def execute():
    if not frappe.db.exists("DocType", TRANSFER_DOCTYPE):
        return

    transfers = frappe.get_all(
        TRANSFER_DOCTYPE,
        filters={"invoice": ["is", "set"]},
        fields=["name", "invoice", "client_name", "transferring_coach", "receiving_coach"],
    )

    for row in transfers:
        if not row.invoice or not frappe.db.exists("Sales Invoice", row.invoice):
            continue

        item_row_name = frappe.db.get_value(
            "Sales Invoice Item",
            {"parent": row.invoice, "item_code": TRANSFER_FEE_ITEM_CODE},
            "name",
        )
        if not item_row_name:
            continue

        transfer_summary = "{0} transferred from {1} to {2}".format(
            row.client_name, _coach_label(row.transferring_coach), _coach_label(row.receiving_coach),
        )

        frappe.db.set_value(
            "Sales Invoice Item", item_row_name,
            {
                "item_name": "{0} - {1}".format(TRANSFER_FEE_ITEM_CODE, row.client_name),
                "description": "Client transfer fee - {0}".format(transfer_summary),
            },
            update_modified=False,
        )
        frappe.db.set_value(
            "Sales Invoice", row.invoice,
            "remarks", "Client transfer fee - {0}".format(transfer_summary),
            update_modified=False,
        )

    frappe.db.commit()
