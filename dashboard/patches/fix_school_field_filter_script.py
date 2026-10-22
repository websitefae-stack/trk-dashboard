"""
Follow-up to switch_survey_school_fields_to_client.py - that patch's
client_script used `frappe.web_form.on_load`, which isn't a real Web
Form client-script hook (the documented one is `after_load`), so it
silently never ran and the School field on both the Student Resilience
Survey and the Children's Wellbeing Check-In was showing every Client,
not just Schools, exactly as Ashley reported.

Fixes the hook name, and - since a client-script-only filter already
failed silently once - also sets link_filters directly on the field
itself (DocType and Web Form alike), the built-in, no-script Link
filtering property Frappe's own Form Builder "Filters" option uses.
Having both isn't a conflict: link_filters is the one the Link control
reads on its own, the client_script is a belt-and-braces backup in case
this site's Frappe version only honours one of the two.
"""

import json

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

SCHOOL_LINK_FILTERS = json.dumps([["Client", "client_type", "=", "School"]])

SCHOOL_FIELD_CLIENT_SCRIPT = """
frappe.web_form.after_load = () => {
    if (frappe.web_form.fields_dict.school) {
        frappe.web_form.fields_dict.school.get_query = () => {
            return { filters: { client_type: "School" } };
        };
    }
};
""".strip()


def execute():
    if not frappe.db.exists("DocType", CLIENT_DOCTYPE):
        return

    _fix_doctype_field(RESILIENCE_DOCTYPE)
    _fix_web_form(RESILIENCE_WEB_FORM_ROUTE)

    _fix_doctype_field(STIRLING_DOCTYPE)
    _fix_web_form(STIRLING_WEB_FORM_ROUTE)


def _set_link_filters_if_supported(field):
    if not field.meta.has_field("link_filters"):
        return False

    if field.get("link_filters") != SCHOOL_LINK_FILTERS:
        field.link_filters = SCHOOL_LINK_FILTERS
        return True

    return False


def _fix_doctype_field(doctype_name):
    if not frappe.db.exists("DocType", doctype_name):
        return

    doc = frappe.get_doc("DocType", doctype_name)
    changed = False

    for field in doc.fields:
        if field.fieldname == "school":
            if _set_link_filters_if_supported(field):
                changed = True

    if changed:
        doc.save(ignore_permissions=True)
        frappe.clear_cache(doctype=doctype_name)


def _fix_web_form(route):
    name = frappe.db.exists("Web Form", {"route": route})
    if not name:
        return

    doc = frappe.get_doc("Web Form", name)
    changed = False

    for field in doc.web_form_fields:
        if field.fieldname == "school":
            if _set_link_filters_if_supported(field):
                changed = True

    if (doc.client_script or "").strip() != SCHOOL_FIELD_CLIENT_SCRIPT:
        doc.client_script = SCHOOL_FIELD_CLIENT_SCRIPT
        changed = True

    if changed:
        doc.save(ignore_permissions=True)
        frappe.db.commit()
