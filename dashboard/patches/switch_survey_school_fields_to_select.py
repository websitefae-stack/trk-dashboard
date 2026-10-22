"""
Replaces the "school" Link-to-Client field on the Student Resilience
Survey and the Children's Wellbeing Check-In with a plain Select
dropdown, listing current School clients by name - Ashley's choice
after the Link approach turned out to be a dead end for these two
forms specifically: both are public, no-login forms a child fills in
themselves, and Client holds private family/child data that Guest
correctly can't search - so the Link field's live search silently had
nothing to search against and fell back to a free-type box, exactly
the typo risk Ashley flagged.

A Select has no search step at all - just a fixed list of real school
names, built here from whichever Client records currently have
client_type "School" (same filter used throughout this app - see
calendar.py's _get_school_options). No typing, no permissions problem,
nothing to silently fail a second time.

The tradeoff, accepted deliberately: this list is a snapshot as of
whenever this patch last ran, not live - a brand new school client
won't appear until a follow-up patch (the same "v2/v3" pattern used
elsewhere in this app, e.g. update_franchise_agreement_practice_
document_v8.py onwards) re-runs this same query and re-pushes the
refreshed list. Ashley's own school client list changes rarely, so
this is expected to need a refresh only occasionally, on request.

Also retires the client_script and link_filters the two previous
(Link-based) patches set on these Web Forms - no longer relevant to a
Select field, left in place they'd just be inert, but clearing them
keeps the Web Form record honest about what's actually driving it now.

Since a Select field's value IS the school's name directly (not a
Client record ID), _school_label() in student_resilience_survey.py and
wellbeing_forms.py no longer needs to look anything up - simplified in
the same change to just return the stored value as-is.
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
SCHOOL_CLIENT_TYPE = "School"


def execute():
    if not frappe.db.exists("DocType", CLIENT_DOCTYPE):
        return

    options = _build_school_options()

    _switch_doctype_field(RESILIENCE_DOCTYPE, options)
    _switch_web_form(RESILIENCE_WEB_FORM_ROUTE, options)

    _switch_doctype_field(STIRLING_DOCTYPE, options)
    _switch_web_form(STIRLING_WEB_FORM_ROUTE, options)


def _build_school_options():
    names = frappe.get_all(
        CLIENT_DOCTYPE,
        filters={"client_type": SCHOOL_CLIENT_TYPE},
        pluck="full_name",
        ignore_permissions=True,
    )
    names = sorted({(name or "").strip() for name in names if (name or "").strip()})
    return "\n".join([""] + names)


def _switch_doctype_field(doctype_name, options):
    if not frappe.db.exists("DocType", doctype_name):
        return

    doc = frappe.get_doc("DocType", doctype_name)
    changed = False

    for field in doc.fields:
        if field.fieldname == "school":
            if field.fieldtype != "Select":
                field.fieldtype = "Select"
                changed = True
            if field.options != options:
                field.options = options
                changed = True

    if changed:
        doc.save(ignore_permissions=True)
        frappe.clear_cache(doctype=doctype_name)


def _switch_web_form(route, options):
    name = frappe.db.exists("Web Form", {"route": route})
    if not name:
        return

    doc = frappe.get_doc("Web Form", name)
    changed = False

    for field in doc.web_form_fields:
        if field.fieldname == "school":
            if field.fieldtype != "Select":
                field.fieldtype = "Select"
                changed = True
            if field.options != options:
                field.options = options
                changed = True
            if field.meta.has_field("link_filters") and field.get("link_filters"):
                field.link_filters = None
                changed = True

    if (doc.client_script or "").strip():
        doc.client_script = ""
        changed = True

    if changed:
        doc.save(ignore_permissions=True)
        frappe.db.commit()
