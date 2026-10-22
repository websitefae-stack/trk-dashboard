"""
Switches the "school" field on both the Student Resilience Survey and
the Children's Wellbeing Check-In from a Link into the "School" sales-
pipeline doctype (create_school_pipeline_doctypes.py's School - an
outreach tracker named by a plain autoincrement number, with no title
field set, which is why it was showing up as a bare number like "1" on
both forms) to a Link into actual Client records filtered to
client_type = "School".

The School pipeline doctype tracks prospects before they ever become a
client - it's the wrong list for these two forms, which are about
schools already running the programme. Real schools already exist as
Client records (client_type "School", see school_licenses.py/
calendar.py's own _get_school_options for the same filter used
elsewhere), so that's the list these forms should offer instead.

Restricts the dropdown via each Web Form's client_script - the
documented way to override a Link field's query on a public Web Form
(frappe.web_form.fields_dict.<field>.get_query) - rather than a second
custom API + hand-built <select>, since these are public, no-login
forms and this is the one mechanism that reliably reaches the portal's
native Link search box with no extra page to build.

Existing responses already saved against a School pipeline record keep
that value - _school_label() in student_resilience_survey.py and
wellbeing_forms.py now looks the value up against Client, and falls
back to showing the raw value if that lookup comes back empty, so nothing
crashes - but any test Before/After pair submitted before this patch
ran (picking from the old School pipeline list) won't resolve to a
real school name any more and should be re-submitted against an actual
School client to show up properly in the comparison report.
"""

import frappe

from dashboard.patches.create_student_resilience_survey_form import (
    WEB_FORM_ROUTE as RESILIENCE_WEB_FORM_ROUTE,
)
from dashboard.patches.create_student_resilience_survey_form import (
    DOCTYPE_NAME as RESILIENCE_DOCTYPE,
)
from dashboard.patches.create_stirling_wellbeing_scale_form import (
    WEB_FORM_ROUTE as STIRLING_WEB_FORM_ROUTE,
)
from dashboard.patches.create_stirling_wellbeing_scale_form import (
    DOCTYPE_NAME as STIRLING_DOCTYPE,
)

CLIENT_DOCTYPE = "Client"

SCHOOL_FIELD_CLIENT_SCRIPT = """
frappe.web_form.on_load = () => {
    if (frappe.web_form.fields_dict.school) {
        frappe.web_form.fields_dict.school.get_query = () => {
            return { filters: { client_type: "School" } };
        };
    }
};
"""


def execute():
    if not frappe.db.exists("DocType", CLIENT_DOCTYPE):
        return

    _switch_doctype_field(RESILIENCE_DOCTYPE)
    _switch_web_form(RESILIENCE_WEB_FORM_ROUTE)

    _switch_doctype_field(STIRLING_DOCTYPE)
    _switch_web_form(STIRLING_WEB_FORM_ROUTE)


def _switch_doctype_field(doctype_name):
    if not frappe.db.exists("DocType", doctype_name):
        return

    doc = frappe.get_doc("DocType", doctype_name)
    changed = False

    for field in doc.fields:
        if field.fieldname == "school" and field.options != CLIENT_DOCTYPE:
            field.options = CLIENT_DOCTYPE
            changed = True

    if changed:
        doc.save(ignore_permissions=True)
        frappe.clear_cache(doctype=doctype_name)


def _switch_web_form(route):
    name = frappe.db.exists("Web Form", {"route": route})
    if not name:
        return

    doc = frappe.get_doc("Web Form", name)
    changed = False

    for field in doc.web_form_fields:
        if field.fieldname == "school" and field.options != CLIENT_DOCTYPE:
            field.options = CLIENT_DOCTYPE
            changed = True

    if (doc.client_script or "").strip() != SCHOOL_FIELD_CLIENT_SCRIPT.strip():
        doc.client_script = SCHOOL_FIELD_CLIENT_SCRIPT.strip()
        changed = True

    if changed:
        doc.save(ignore_permissions=True)
        frappe.db.commit()
