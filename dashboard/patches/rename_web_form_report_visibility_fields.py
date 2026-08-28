"""
Replaces the original "Show In Dashboard Reports" / "Also Show To
Coaches" tick boxes (add_web_form_report_visibility_fields) with two
independent ones - "Show In Coach Reports" / "Show In Franchisor
Reports" - so a form's Reports visibility can be coach-only,
franchisor-only, or both, without one box depending on the other and
without needing to understand what either one actually does behind the
scenes. See form_reports.sync_web_form_report_visibility for what
ticking these does; the old pair could only ever express "franchisors
only" or "everyone", never "coaches only".
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

OLD_REPORTS_FIELD = "custom_show_in_reports"
OLD_COACH_FIELD = "custom_show_on_coach_dashboard"

NEW_WEB_FORM_FIELDS = [
    {
        "fieldname": "custom_show_in_coach_reports",
        "fieldtype": "Check",
        "label": "Show In Coach Reports",
        "description": (
            "Tick to have this form's submissions appear automatically in the Reports "
            "section of the COACH dashboard - no other setup needed."
        ),
        "insert_after": "is_standard",
        "module": "Dashboard",
    },
    {
        "fieldname": "custom_show_in_franchisor_reports",
        "fieldtype": "Check",
        "label": "Show In Franchisor Reports",
        "description": (
            "Tick to have this form's submissions appear automatically in the Reports "
            'section of the FRANCHISOR dashboard - no other setup needed. Tick both this '
            'and "Show In Coach Reports" for it to appear in both places.'
        ),
        "insert_after": "custom_show_in_coach_reports",
        "module": "Dashboard",
    },
]


def execute():
    if not frappe.db.exists("DocType", "Web Form"):
        return

    create_custom_fields({"Web Form": NEW_WEB_FORM_FIELDS}, ignore_validate=True)

    if frappe.db.has_column("Web Form", OLD_REPORTS_FIELD):
        old_rows = frappe.get_all(
            "Web Form",
            filters={OLD_REPORTS_FIELD: 1},
            fields=["name", OLD_COACH_FIELD],
        )
        for row in old_rows:
            frappe.db.set_value("Web Form", row.name, "custom_show_in_franchisor_reports", 1)
            if row.get(OLD_COACH_FIELD):
                frappe.db.set_value("Web Form", row.name, "custom_show_in_coach_reports", 1)

    for fieldname in (OLD_REPORTS_FIELD, OLD_COACH_FIELD):
        custom_field_name = f"Web Form-{fieldname}"
        if frappe.db.exists("Custom Field", custom_field_name):
            frappe.delete_doc("Custom Field", custom_field_name, ignore_permissions=True, force=True)

    frappe.clear_cache(doctype="Web Form")
    frappe.db.commit()
