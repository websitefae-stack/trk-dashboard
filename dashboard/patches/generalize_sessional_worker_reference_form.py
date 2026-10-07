"""
Follow-up to create_sessional_worker_reference_form.py - already live on
site (that patch created the DocType + Web Form at route
"sessional-worker-reference-form", with "Referee's Name" / "Referee's
Job Title" labels and Sessional-Worker-only wording). Ashley wants this
reused as a single generic reference questionnaire for BOTH a Sessional
Worker applicant and a prospective Franchisee, written in the second
person ("Your Name") since the person filling this in IS the referee,
not a third party describing one - and, since the form hadn't actually
gone out to anyone yet, confirmed it's safe to also shorten the URL
itself to /reference-form (no existing link out there would break).

create_sessional_worker_reference_form's own _create_doctype/
_create_web_form both early-return once the DocType/Web Form already
exist, so re-running the patch (e.g. via the franchisor "repair"
endpoint in form_reports.py) would never pick up this reworded text or
the new route - this directly updates the live records instead. Pulls
the final wording/route straight from that module rather than
duplicating them here, so the two can't drift apart again.
"""

import frappe

from dashboard.patches.create_sessional_worker_reference_form import (
    DOCTYPE_NAME,
    WEB_FORM_ROUTE,
    INTRODUCTION_TEXT,
)

# The route this Web Form actually has on a site where
# create_sessional_worker_reference_form already ran before WEB_FORM_
# ROUTE was shortened to "reference-form" above - look it up by this
# first, since WEB_FORM_ROUTE (the import) is now the NEW route, which
# won't exist yet on such a site.
OLD_WEB_FORM_ROUTE = "sessional-worker-reference-form"

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
    web_form_name = (
        frappe.db.get_value("Web Form", {"route": OLD_WEB_FORM_ROUTE}, "name")
        or frappe.db.get_value("Web Form", {"route": WEB_FORM_ROUTE}, "name")
    )
    if not web_form_name:
        return

    doc = frappe.get_doc("Web Form", web_form_name)
    changed = False

    if doc.route != WEB_FORM_ROUTE:
        doc.route = WEB_FORM_ROUTE
        changed = True

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
