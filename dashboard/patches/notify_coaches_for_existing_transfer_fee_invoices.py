"""
One-off catch-up for the client_transfers.py notification just added:
_maybe_invoice_transfer_fee now tells both coaches when a transfer fee
invoice is raised, but the two real invoices already created before
that existed (transfer eg3o6r2852 -> ACC-SINV-2026-00485, transfer
84esistlld -> ACC-SINV-2026-00416) never notified anyone. Sends that
notification now, for exactly those two already-known transfers - not
a blanket re-notify of every transfer ever invoiced, which would dig up
old, already-handled ones from well before this automation existed.
"""

import frappe

from dashboard.api.shared.client_transfers import TRANSFER_DOCTYPE, _notify_transfer_fee_invoiced

TRANSFERS_TO_NOTIFY = ["eg3o6r2852", "84esistlld"]


def execute():
    if not frappe.db.exists("DocType", TRANSFER_DOCTYPE):
        return

    for transfer_name in TRANSFERS_TO_NOTIFY:
        if not frappe.db.exists(TRANSFER_DOCTYPE, transfer_name):
            continue

        transfer = frappe.get_doc(TRANSFER_DOCTYPE, transfer_name)
        if not transfer.invoice:
            continue

        _notify_transfer_fee_invoiced(transfer)
