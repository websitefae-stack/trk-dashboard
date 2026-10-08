"""
Follow-up to create_franchise_brochure_nurture_sequence.py - Ashley wants
the full campaign to be 12 emails, one every 24 hours (not the original
3-step/2-5-9-day placeholder), and has already written her own copy into
the first 3 Email Templates.

delay_days on a step means "days after the PREVIOUS step was sent" (step
1's is "days after enrollment") - see email_sequences.py's own
_send_next_step/_first_step_delay. A uniform 24-hour cadence across all
12 steps is just every step's delay_days = 1, so this patch:

1. Fixes the first 3 steps' delay_days (2/5/9 -> 1/1/1) without touching
   their Email Templates at all - Ashley's already-written copy in those
   3 is left completely alone.
2. Adds 9 more steps/Email Templates (4-12), same "REPLACE ME"
   placeholder pattern as the original 3 so Ashley can tell at a glance
   which email is which while she writes the rest. All 12 (plus the
   immediate first email) can now use {{ brochure_url }} - that
   person's own no-signup-again brochure link - alongside
   {{ recipient_name }} and {{ booking_url }}, see email_sequences.py's
   _brochure_url_for_enrollment.
3. Pulls forward next_send_date on any already-Active enrollment of this
   sequence that's still waiting on the old, slower cadence (e.g.
   someone who requested the brochure before this patch ran, whose next
   email wouldn't otherwise be due for several more days under the old
   step-1 delay of 2) - capped at "today" so they're not left waiting
   longer than the new 24-hour cadence intends. Never touches an
   enrollment that's already Completed/Cancelled, or one whose
   next_send_date was already due (the normal daily job handles that).
"""

import frappe

SEQUENCE_NAME = "Franchise Brochure Nurture"
SEQUENCE_DOCTYPE = "Email Sequence"
STEP_DOCTYPE = "Email Sequence Step"
ENROLLMENT_DOCTYPE = "Email Sequence Enrollment"

BODY_FIELD_CANDIDATES = ["response", "response_html", "message", "content"]

# Steps 1-3 already exist (and 1-3's real copy is Ashley's own, written
# directly in Desk) - this only fixes their cadence.
EXISTING_STEP_DELAY_FIX = {1: 1, 2: 1, 3: 1}

NEW_STEPS = [
    (4, "Is a Resilient Kid franchise right for you?"),
    (5, "Meet some of our existing franchisees"),
    (6, "What does the first year look like?"),
    (7, "Your questions about franchise fees, answered"),
    (8, "The support you'd get as a Resilient Kid franchisee"),
    (9, "Why now might be the right time"),
    (10, "A behind-the-scenes look at running a Resilient Kid franchise"),
    (11, "Still thinking it over?"),
    (12, "Ready to take the next step?"),
]


def _template_name(step_number):
    return f"Franchise Brochure Follow-up {step_number} - Resilient Kid"


def _placeholder_body():
    return (
        "Hi {{ recipient_name }},\n"
        "\n"
        "REPLACE ME - Ashley's own follow-up copy goes here.\n"
        "\n"
        "{{ booking_url }}\n"
        "\n"
        "Warm regards,\n"
        "Ashley"
    )


def _body_fieldname(meta):
    for fieldname in BODY_FIELD_CANDIDATES:
        if meta.has_field(fieldname):
            return fieldname
    return None


def _ensure_email_template(meta, body_fieldname, template_name, subject, body):
    if frappe.db.exists("Email Template", template_name):
        return

    doc = frappe.new_doc("Email Template")
    doc.name = template_name
    if meta.has_field("subject"):
        doc.subject = subject
    doc.set(body_fieldname, body)
    doc.insert(ignore_permissions=True)


def execute():
    if not frappe.db.exists(SEQUENCE_DOCTYPE, SEQUENCE_NAME):
        return

    sequence = frappe.get_doc(SEQUENCE_DOCTYPE, SEQUENCE_NAME)

    existing_by_step = {row.step_number: row for row in sequence.steps}

    for step_number, new_delay in EXISTING_STEP_DELAY_FIX.items():
        row = existing_by_step.get(step_number)
        if row and row.delay_days != new_delay:
            row.delay_days = new_delay

    if 4 not in existing_by_step:
        meta = frappe.get_meta("Email Template")
        body_fieldname = _body_fieldname(meta)

        if body_fieldname:
            for step_number, subject in NEW_STEPS:
                template_name = _template_name(step_number)
                _ensure_email_template(meta, body_fieldname, template_name, subject, _placeholder_body())

                sequence.append("steps", {
                    "step_number": step_number,
                    "delay_days": 1,
                    "email_template": template_name,
                })

    sequence.save(ignore_permissions=True)
    frappe.db.commit()

    # Pull forward anyone already mid-sequence under the old, slower
    # cadence so they're not left waiting out a since-shortened delay.
    today = frappe.utils.today()
    stuck_enrollments = frappe.get_all(
        ENROLLMENT_DOCTYPE,
        filters={"sequence": SEQUENCE_NAME, "status": "Active", "next_send_date": [">", today]},
        pluck="name",
    )
    for name in stuck_enrollments:
        frappe.db.set_value(ENROLLMENT_DOCTYPE, name, "next_send_date", today)

    if stuck_enrollments:
        frappe.db.commit()
