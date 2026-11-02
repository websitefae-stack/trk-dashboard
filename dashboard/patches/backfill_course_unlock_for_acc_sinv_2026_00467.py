"""
One-off retry for a specific invoice that failed course unlock because of
the ordering bug just fixed in course_unlock_on_payment.py's
_process_invoice: it tried to enrol the buyer in LMS before ensuring
their User account existed, which LMS Enrollment.member (a Link to LMS's
own "Member" record, created alongside a new User) needs to already be
there - see the Error Log entry "Course Unlock On Payment Failed -
ACC-SINV-2026-00467" (LinkValidationError: Could not find Member:
mshaw1280@hotmail.co.uk).

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
