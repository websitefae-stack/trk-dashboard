"""
Click tracking for the "Links" page (dashboard.api.shared.form_reports.
get_form_links) - confirmed requested live: there was no way to tell how
much a shared link/QR code was actually being used, or to jump straight
from a link to its own form's feedback.

Deliberately NOT a lookup table of "known links" - get_form_links()
already computes the list fresh every time (static pages, per-coach
booking cards, published Web Forms), so a tracked link's own real
destination/title/form doctype are encoded directly into its own
tracking URL (see _tracked_link_url() in form_reports.py) rather than
pre-registered here. This doctype only ever stores one row per actual
click, written by www/l.py's redirect handler.
"""

import frappe


def execute():
    if frappe.db.exists("DocType", "Dashboard Link Click"):
        return

    doc = frappe.get_doc({
        "doctype": "DocType",
        "name": "Dashboard Link Click",
        "module": "Dashboard",
        "custom": 1,
        "fields": [
            {"fieldname": "link_title", "fieldtype": "Data", "label": "Link Title", "in_list_view": 1},
            {"fieldname": "target_url", "fieldtype": "Small Text", "label": "Target URL", "reqd": 1, "in_list_view": 1},
            {"fieldname": "form_doctype", "fieldtype": "Data", "label": "Form DocType", "description": "Set only when this link is for a Forms-module Web Form - lets the Links page offer a direct \"View Feedback\" jump to that form's own submissions report."},
            {"fieldname": "clicked_on", "fieldtype": "Datetime", "label": "Clicked On", "in_list_view": 1},
        ],
        "permissions": [
            {
                "role": "System Manager",
                "read": 1, "write": 1, "create": 1, "delete": 1,
                "report": 1, "export": 1, "print": 1, "email": 1, "share": 1,
            },
        ],
        "sort_field": "clicked_on",
        "sort_order": "DESC",
    })
    doc.insert(ignore_permissions=True)
