"""
Blocks an LMS Certificate from being issued until the member has
actually completed 100% of the course. Frappe Learning's own validation
(LMSCertificate.validate_course_enrollment, in the Learning app itself)
only checks progress when the course's own "Enable Certification"
checkbox is ticked - on any course where that's left off (the normal
state unless someone specifically turned it on), issuing a certificate
skips the progress check entirely and self-service create_certificate()
(and manual issuance by an evaluator/moderator) both go straight to
100%-complete's "Congratulations on getting certified!" email with no
gate at all.

Registered as a doc_events "validate" hook on LMS Certificate from this
app (see hooks.py) rather than a change to the Learning app's own
controller - Frappe runs every app's registered hooks for a doctype
alongside its own controller validate(), so this enforces the same way
regardless of whether the certificate was issued from the Desk, the
Learning frontend's self-service button, or the API directly, and
regardless of that course setting. See onboarding.py's LMS integration
for the same "don't touch a third-party app's files" reasoning.

Checks LMS Enrollment.progress rather than counting lessons directly -
that field is the exact number Frappe LMS itself keeps up to date
(lms.lms.utils.recalculate_course_progress, walking the course's real
Chapter Reference/Lesson Reference structure) and is what a member's own
"% complete" already shows, so this can never disagree with what they
see on screen.
"""

import frappe
from frappe import _
from frappe.utils import flt

LMS_ENROLLMENT_DOCTYPE = "LMS Enrollment"


def block_certificate_before_course_complete(doc, method=None):
    # Only gates a certificate actually being newly issued - never
    # blocks an evaluator editing one already on record (e.g. correcting
    # its expiry date), which is a different action than issuance.
    if not doc.is_new():
        return

    if not doc.course or not doc.member:
        return

    if not frappe.db.exists("DocType", LMS_ENROLLMENT_DOCTYPE):
        return

    progress = frappe.db.get_value(
        LMS_ENROLLMENT_DOCTYPE, {"course": doc.course, "member": doc.member}, "progress"
    )

    # No enrollment row at all is Frappe Learning's own problem to catch
    # (validate_course_enrollment already throws "not enrolled in this
    # course") - nothing to gate here either way.
    if progress is None:
        return

    if flt(progress) < 100:
        frappe.throw(
            _(
                "This certificate can't be issued yet - {0} has only completed {1}% of this course."
            ).format(doc.get("member_name") or doc.member, flt(progress, 1))
        )
