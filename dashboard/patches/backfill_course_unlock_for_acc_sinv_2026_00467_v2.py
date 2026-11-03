"""
v2 retry for ACC-SINV-2026-00467 - the v1 backfill (backfill_course_
unlock_for_acc_sinv_2026_00467) ran, but got further than the original
ordering bug only to hit a second, separate bug: _ensure_portal_access
tried to use the buyer's raw email as a Client Contact Link row's
contact_name, which is validated as a Frappe "Name" field (letters/
spaces only) - an email's "@" always fails that. Fixed in webshop_
purchase.py (falls back to "Customer" instead of the email); this
re-runs the same unlock now that it can actually complete.

Safe to run more than once - process_invoice_course_unlock already skips
anyone already enrolled, and never raises (every failure is caught and
logged, not re-thrown).
"""

import frappe

INVOICE = "ACC-SINV-2026-00467"


def execute():
    if not frappe.db.exists("Sales Invoice", INVOICE):
        return

    from dashboard.api.shared.course_unlock_on_payment import process_invoice_course_unlock

    process_invoice_course_unlock(INVOICE)
