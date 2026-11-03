"""
One-off catch-up for the client_transfers.py fix just shipped: a
transfer's own invoice field went stale on at least 2 of the 3 "Leo"
Client Transfer Agreements (Liz <-> Sarah-Jane) - each pointed at a
Sales Invoice that had since been deleted, but the backfill and the
payment hook both only ever check whether that field is set, not
whether the invoice it names still exists, so those two transfers were
silently treated as "already invoiced" forever.

Runs the same backfill the franchisor can also re-trigger any time via
backfill_transfer_fees_for_paid_invoices - it now clears any stale
invoice reference before scanning for pending transfers, so this
immediately re-opens and reconsiders the two affected transfers rather
than waiting for someone to notice and re-run it by hand.
"""

import frappe

from dashboard.api.shared.client_transfers import _backfill_transfer_fees_for_paid_invoices


def execute():
    if not frappe.db.exists("DocType", "Client Transfer Agreement"):
        return

    _backfill_transfer_fees_for_paid_invoices()
