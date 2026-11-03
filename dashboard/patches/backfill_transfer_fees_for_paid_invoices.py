"""
One-off catch-up for the client_transfers.py fix just shipped: the
SJ-to-Emily transfer fee invoice is now raised automatically the moment
the receiving coach's own first invoice to the transferred client is
paid in full (Payment Entry.on_submit hook), rather than on the lead
converting to a Client as before.

Any Completed transfer where that invoice already happened to get paid
before this fix existed (or before this app even had the earlier,
conversion-based trigger at all) would otherwise sit forever without a
fee invoice, since nothing re-checks a transfer once it's Completed.
Runs the exact same backfill the franchisor can also re-trigger any time
via backfill_transfer_fees_for_paid_invoices - safe to run again, since
it only ever acts on transfers with no fee invoice yet.
"""

import frappe

from dashboard.api.shared.client_transfers import _backfill_transfer_fees_for_paid_invoices


def execute():
    if not frappe.db.exists("DocType", "Client Transfer Agreement"):
        return

    _backfill_transfer_fees_for_paid_invoices()
