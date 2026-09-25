"""
One-off run of the same backfill course_unlock_on_payment.py's
backfill_course_unlocks_for_paid_invoices() offers on demand - covers
whichever item(s) already have custom_unlocks_lms_course set (e.g. the
12 Session Coaching Pack) by the time this deploy runs, so clients who
paid before the auto-unlock feature existed still get retroactive
course access, portal login, and the access email. Only touches
invoices dated on or after COURSE_UNLOCK_CUTOFF_DATE
(course_unlock_on_payment.py) - an explicit business decision that
older purchases shouldn't retroactively gain course access. A no-op if
custom_unlocks_lms_course isn't set on anything yet - the franchisor
can re-run it any time afterwards via the whitelisted function instead,
since a patch only ever runs once per site.
"""

import frappe

from dashboard.api.shared.course_unlock_on_payment import _backfill_course_unlocks_for_paid_invoices


def execute():
    if not frappe.db.exists("DocType", "Sales Invoice"):
        return

    _backfill_course_unlocks_for_paid_invoices()
