"""
Adds custom_email_account to Coach - an explicit, office-set link to the
Email Account a coach sends dashboard email from.

google_mail_connect.py's _get_email_account_row() otherwise has to guess
which Email Account belongs to a coach by matching email_id against
frappe.session.user or Coach.coach_email - both of which have turned out
to mismatch in practice (a coach's Frappe login, their Coach.coach_email
field, and their Email Account's email_id are three separate values that
aren't guaranteed to line up). This field lets the office point directly
at the right record from the Coach doctype in Desk when the heuristics
don't find it, without needing a code change each time.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

COACH_FIELDS = [
    {
        "fieldname": "custom_email_account",
        "fieldtype": "Link",
        "options": "Email Account",
        "label": "Email Account (for dashboard sending)",
        "module": "Dashboard",
        "insert_after": "coach_email",
        "description": "Only needed if this coach's Google Email connect button says not configured - set it directly here to the matching Email Account record.",
    },
]


def execute():
    if not frappe.db.exists("DocType", "Coach"):
        return

    create_custom_fields({"Coach": COACH_FIELDS}, ignore_validate=True)
    frappe.db.commit()
