"""
Wires up the Email Sequence (see email_sequences.py /
add_email_sequence_trigger_filter_fields.py) that sends Ashley's Parent
Course upsell email 5 days after someone buys the Primary Anxiety
Toolkit (£29) LMS course - "for people that purchase the anxiety
course we would like to send them a follow up email 5 days after
purchase".

Triggers off LMS Enrollment (created the moment access to a paid course
is granted - see course_unlock_on_payment.py/webshop_purchase.py),
filtered to just this one course via trigger_filter_field=course so
buyers of any OTHER course are never enrolled in it. Looked up by
title at patch time rather than hardcoded, since an LMS Course's
docname is its own slug, not something safe to guess.

Self-healing like every other patch here: if the sequence already
exists, only fills in trigger_filter_value when it's still blank
(e.g. the course didn't exist yet the first time this ran) - never
overwrites anything Ashley has since edited in Desk.
"""

import frappe

from dashboard.api.shared.email_templates import ANXIETY_COURSE_UPSELL_TEMPLATE

SEQUENCE_DOCTYPE = "Email Sequence"
SEQUENCE_NAME = "Anxiety Course - Parent Course Upsell"
COURSE_TITLE = "Primary Anxiety Toolkit"
FOLLOW_UP_DELAY_DAYS = 5


def execute():
    if not frappe.db.exists("DocType", SEQUENCE_DOCTYPE):
        return

    if not frappe.db.exists("DocType", "LMS Course"):
        return

    course_name = frappe.db.get_value("LMS Course", {"title": COURSE_TITLE}, "name")
    if not course_name:
        frappe.log_error(
            f"No LMS Course found with title '{COURSE_TITLE}' - the Anxiety Course upsell "
            "sequence was not created/updated. Re-run this patch once the course exists.",
            "Create Anxiety Course Upsell Sequence - Course Not Found",
        )
        return

    try:
        if frappe.db.exists(SEQUENCE_DOCTYPE, SEQUENCE_NAME):
            doc = frappe.get_doc(SEQUENCE_DOCTYPE, SEQUENCE_NAME)
            if not (doc.get("trigger_filter_value") or "").strip():
                doc.trigger_filter_value = course_name
                doc.save(ignore_permissions=True)
                frappe.db.commit()
            return

        doc = frappe.new_doc(SEQUENCE_DOCTYPE)
        doc.sequence_name = SEQUENCE_NAME
        doc.description = (
            f"Sent {FOLLOW_UP_DELAY_DAYS} days after someone buys the {COURSE_TITLE} course - "
            "pitches The Resilient Kid Parent Course (£199)."
        )
        doc.is_active = 1
        doc.trigger_doctype = "LMS Enrollment"
        doc.trigger_email_field = "member"
        doc.trigger_filter_field = "course"
        doc.trigger_filter_value = course_name
        doc.append("steps", {
            "step_number": 1,
            "delay_days": FOLLOW_UP_DELAY_DAYS,
            "email_template": ANXIETY_COURSE_UPSELL_TEMPLATE,
        })
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"Create Anxiety Course Upsell Sequence Failed: {SEQUENCE_NAME}")
