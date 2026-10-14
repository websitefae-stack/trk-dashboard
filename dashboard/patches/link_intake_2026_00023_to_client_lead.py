"""
One-off fix for INTAKE-2026-00023, the submission that hit the ambiguous
Client Lead matching bug (logged as "Intake Submission - Client Lead
Match Failed" - two different Client Lead records each matched one of
the family's two emails/names) before source_client_lead existed to
prevent exactly this.

Confirmed by hand which Client Lead this submission actually belongs to:
1giinkkme2 - status "Intake Sent", contact_email meemichjames@gmail.com,
an exact match to the submission's own primary_caregiver_email, and the
only one of the two candidates an intake form was ever actually sent to.

Runs the submission through the normal _apply_intake_submission_to_lead()
copy logic directly, against that confirmed pairing - the exact same
thing every other (unambiguous) submission already goes through
automatically via sync_intake_doctype_submission - so this needed no
Desk field-editor work from anyone, just a deploy.
"""

import frappe

INTAKE_NAME = "INTAKE-2026-00023"
LEAD_NAME = "1giinkkme2"


def execute():
    if not frappe.db.exists("Intake Doctype", INTAKE_NAME) or not frappe.db.exists("Client Lead", LEAD_NAME):
        return

    from dashboard.api.shared.leads import _apply_intake_submission_to_lead

    doc = frappe.get_doc("Intake Doctype", INTAKE_NAME)
    _apply_intake_submission_to_lead(doc, LEAD_NAME)
    frappe.db.commit()
