"""
Adds dbs_missing_since / insurance_missing_since / ico_missing_since to
both Coach and Session Worker - set automatically (by legal_expiry_
reminders.send_legal_expiry_reminders, not by hand) the first day one
of the three legal requirements (DBS/DBS Update Service, Insurance,
ICO Certificate) has no record on file at all, and cleared again once
one is uploaded.

Ashley's own rule: a coach/session worker with nothing on file at all
for one of these gets 30 days from the day it's first noticed missing
before being locked out - not retroactively from whenever the gap
actually started, since that's not something this app has ever
tracked. These three fields ARE that starting point going forward; see
permissions.get_expired_legal_items for how the 30-day grace period is
then enforced, and legal_expiry_reminders.py for the 30/7/1-day
countdown reminders that use the same fields.

Immediately followed by run_legal_expiry_check_now.py, which sets
these fields (and sends the first round of notifications) for the
first time, straight after this patch creates the fields themselves -
both as part of the same deploy, which is why they're two separate,
sequential patches rather than one.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

MISSING_SINCE_FIELDS = [
    {
        "fieldname": "dbs_missing_since",
        "fieldtype": "Date",
        "label": "DBS Missing Since",
        "read_only": 1,
        "description": (
            "Set automatically the first day neither a DBS nor a DBS Update Service record is on "
            "file - 30 days after this date, access is locked until one is uploaded."
        ),
        "insert_after": "indemnity",
        "module": "Dashboard",
    },
    {
        "fieldname": "insurance_missing_since",
        "fieldtype": "Date",
        "label": "Insurance Missing Since",
        "read_only": 1,
        "description": (
            "Set automatically the first day no Insurance record is on file - 30 days after this "
            "date, access is locked until one is uploaded."
        ),
        "insert_after": "dbs_missing_since",
        "module": "Dashboard",
    },
    {
        "fieldname": "ico_missing_since",
        "fieldtype": "Date",
        "label": "ICO Certificate Missing Since",
        "read_only": 1,
        "description": (
            "Set automatically the first day no ICO Certificate record is on file - 30 days after "
            "this date, access is locked until one is uploaded."
        ),
        "insert_after": "insurance_missing_since",
        "module": "Dashboard",
    },
]


def execute():
    targets = [dt for dt in ("Coach", "Session Worker") if frappe.db.exists("DocType", dt)]
    if not targets:
        return

    create_custom_fields({dt: MISSING_SINCE_FIELDS for dt in targets}, ignore_validate=True)
    frappe.db.commit()
