"""
Adds two tick boxes directly onto Frappe's own "Web Form" doctype, so a
new form's Reports-section visibility is a checkbox at the point it's
created rather than a separate Desk step (setting the underlying
DocType's Module to "Forms", and/or adding a Form Visibility Rule row)
that's easy to forget - see form_reports.sync_web_form_report_visibility,
hooked on Web Form.on_update, for what ticking these actually does.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

WEB_FORM_FIELDS = [
    {
        "fieldname": "custom_show_in_reports",
        "fieldtype": "Check",
        "label": "Show In Dashboard Reports",
        "description": (
            "Tick to have this form's submissions appear automatically in the Reports "
            "section of the dashboard - no other setup needed."
        ),
        "insert_after": "is_standard",
        "module": "Dashboard",
    },
    {
        "fieldname": "custom_show_on_coach_dashboard",
        "fieldtype": "Check",
        "label": "Also Show To Coaches",
        "description": (
            "Leave unticked to keep this form's Reports view visible to franchisors/office "
            "only. Tick to also let coaches see it (their own clients'/leads' submissions "
            "only) in their own Reports section."
        ),
        "depends_on": "eval:doc.custom_show_in_reports",
        "insert_after": "custom_show_in_reports",
        "module": "Dashboard",
    },
]


def execute():
    if not frappe.db.exists("DocType", "Web Form"):
        return

    create_custom_fields({"Web Form": WEB_FORM_FIELDS}, ignore_validate=True)
    frappe.db.commit()
