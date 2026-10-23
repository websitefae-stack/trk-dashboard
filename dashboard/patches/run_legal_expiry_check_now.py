"""
Runs legal_expiry_reminders.send_legal_expiry_reminders() once,
immediately, as part of this deploy - rather than waiting for the next
10am cron run (see hooks.py). Ashley asked for exactly this: "check the
dates on all of them now and send notifications once i deploy".

Must run after add_legal_missing_since_fields.py (see patches.txt) -
the dbs_missing_since/insurance_missing_since/ico_missing_since fields
that patch creates are what this first run stamps for every coach/
session worker currently missing one of the three legal documents,
starting their 30-day grace period from today rather than
retroactively from whenever the gap actually began (this app has never
tracked that, and Ashley's own rule was "30 days from today").
"""

import frappe

from dashboard.api.shared.legal_expiry_reminders import send_legal_expiry_reminders


def execute():
    if not frappe.db.exists("DocType", "Coach") and not frappe.db.exists("DocType", "Session Worker"):
        return

    for doctype in ("Coach", "Session Worker"):
        if frappe.db.exists("DocType", doctype) and not frappe.get_meta(doctype).has_field("dbs_missing_since"):
            # add_legal_missing_since_fields.py hasn't actually taken
            # effect yet on this site for some reason - safer to skip
            # this run than half-process it; the next day's 10am cron
            # run will pick everything up correctly once it has.
            return

    send_legal_expiry_reminders()
