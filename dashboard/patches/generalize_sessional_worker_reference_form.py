"""
Follow-up to create_sessional_worker_reference_form.py - already live on
site (that patch created the DocType + Web Form with "Referee's Name" /
"Referee's Job Title" labels and Sessional-Worker-only wording). Ashley
wants this reused as a single generic reference questionnaire for BOTH
a Sessional Worker applicant and a prospective Franchisee, written in
the second person ("Your Name") since the person filling this in IS the
referee, not a third party describing one.

create_sessional_worker_reference_form's own _create_doctype/
_create_web_form both early-return once the DocType/Web Form already
exist, so re-running the patch (e.g. via the franchisor "repair"
endpoint in form_reports.py) would never pick up this reworded text -
this directly updates the live records instead. Pulls the final
wording straight from that module rather than duplicating the long
strings here, so the two can't drift apart again.
"""

import frappe

from dashboard.patches.create_sessional_worker_reference_form import (
    DOCTYPE_NAME,
    WEB_FORM_ROUTE,
    INTRODUCTION_TEXT,
)

RELABELLED_FIELDS = {
    "referee_name": "Your Name",
    "referee_job_title": "Your Job Title",
    "recommend_suitable": (
        "Would You Recommend This Person as Suitable to Work With Children and Young People "
        "Within The Resilient Kid?"
    ),
}

NEW_TITLE = "Reference Questionnaire"


def execute():
    _update_doctype()
    _update_web_form()


def _update_doctype():
    if not frappe.db.exists("DocType", DOCTYPE_NAME):
        return

    doc = frappe.get_doc("DocType", DOCTYPE_NAME)
    changed = False

    for field in doc.fields:
        new_label = RELABELLED_FIELDS.get(field.fieldname)
        if new_label and field.label != new_label:
            field.label = new_label
            changed = True

    if changed:
        doc.save(ignore_permissions=True)
        frappe.db.commit()


def _update_web_form():
    web_form_name = frappe.db.get_value("Web Form", {"route": WEB_FORM_ROUTE}, "name")
    if not web_form_name:
        return

    doc = frappe.get_doc("Web Form", web_form_name)
    changed = False

    if doc.title != NEW_TITLE:
        doc.title = NEW_TITLE
        changed = True

    if doc.introduction_text != INTRODUCTION_TEXT:
        doc.introduction_text = INTRODUCTION_TEXT
        changed = True

    for field in doc.web_form_fields:
        new_label = RELABELLED_FIELDS.get(field.fieldname)
        if new_label and field.label != new_label:
            field.label = new_label
            changed = True

    if changed:
        doc.save(ignore_permissions=True)
        frappe.db.commit()
