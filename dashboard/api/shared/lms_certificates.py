"""
Blocks an LMS Certificate from being issued until the member has
actually completed every lesson in the course. Frappe Learning's own
validation (LMSCertificate.validate_criteria, in the Learning app
itself) only checks that the member is enrolled and that the issuer
holds an evaluator/moderator role - nothing there checks progress, so
an evaluator could otherwise issue (and the certificate's own
after_insert immediately emails) a "Congratulations on getting
certified!" certificate to someone who hasn't finished a single lesson.

Registered as a doc_events "validate" hook on LMS Certificate from this
app (see hooks.py) rather than a change to the Learning app's own
controller - Frappe runs every app's registered hooks for a doctype
alongside its own controller validate(), so this enforces the same way
regardless of whether the certificate was issued from the Desk, the
Learning frontend, or the API directly. See onboarding.py's LMS
integration for the same "don't touch a third-party app's files"
reasoning, and _resolve_lms_chapter there for the doctype names this
mirrors at chapter level.
"""

import frappe
from frappe import _

LMS_COURSE_PROGRESS_DOCTYPE = "LMS Course Progress"
LMS_COURSE_LESSON_DOCTYPE = "Course Lesson"


def block_certificate_before_course_complete(doc, method=None):
    # Only gates a certificate actually being newly issued - never
    # blocks an evaluator editing one already on record (e.g. correcting
    # its expiry date), which is a different action than issuance.
    if not doc.is_new():
        return

    if not doc.course or not doc.member:
        return

    if not frappe.db.exists("DocType", LMS_COURSE_PROGRESS_DOCTYPE):
        return

    total_lessons = frappe.db.count(LMS_COURSE_LESSON_DOCTYPE, {"course": doc.course})
    if not total_lessons:
        return

    completed_lessons = frappe.db.count(
        LMS_COURSE_PROGRESS_DOCTYPE,
        {"member": doc.member, "course": doc.course, "status": "Complete"},
    )

    if completed_lessons < total_lessons:
        frappe.throw(
            _(
                "This certificate can't be issued yet - {0} has only completed {1} of {2} lessons in this course."
            ).format(doc.get("member_name") or doc.member, completed_lessons, total_lessons)
        )
