"""
create_student_resilience_survey_form.py shipped the Web Form with both
custom_show_in_coach_reports and custom_show_in_franchisor_reports off,
so it never got a Form Visibility Rule and so never appeared on the
Links page at all - Ashley couldn't actually find or share the survey
URL. Turns both on now that form_reports.py's generic per-submission
view has been taught to hide this form's two name fields (see
FORM_HIDDEN_FIELDNAMES) - coaches and the franchisor can see this form
on Links and in the generic Form Results picker, with no name ever
shown either way; the "View Feedback" button on Links opens its own
dedicated Before/After comparison report instead of the generic one
(see FORM_REPORT_URL_OVERRIDES), since that's the properly useful view
of this particular form's data.

Calls sync_web_form_report_visibility() directly (the same function its
own on_update hook runs) since frappe.db.set_value() doesn't fire
hooks - without this the Form Visibility Rule row and the DocType's
module would never actually get created/updated.
"""

import frappe

from dashboard.patches.create_student_resilience_survey_form import DOCTYPE_NAME, WEB_FORM_ROUTE


def execute():
    if not frappe.db.exists("DocType", DOCTYPE_NAME):
        return

    name = frappe.db.exists("Web Form", {"route": WEB_FORM_ROUTE})
    if not name:
        return

    frappe.db.set_value(
        "Web Form",
        name,
        {
            "custom_show_in_franchisor_reports": 1,
            "custom_show_in_coach_reports": 1,
        },
    )
    frappe.db.commit()

    from dashboard.api.shared.form_reports import sync_web_form_report_visibility

    sync_web_form_report_visibility(frappe.get_doc("Web Form", name))
