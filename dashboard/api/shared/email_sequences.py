"""
The Email Sequence engine - see patches/create_email_sequence_doctypes.py
for the three doctypes involved (Email Sequence, Email Sequence Step,
Email Sequence Enrollment) and the reasoning for the design.

Two entry points:

- check_sequence_triggers(doc, method=None): a wildcard after_insert
  hook (registered on "*" in hooks.py's doc_events, so it fires for
  every single new document on the site) that enrols the recipient in
  any active Email Sequence whose trigger_doctype matches what was
  just created. Self-service by design - a new sequence needs no code
  change, just a new Email Sequence record in Desk.

- process_due_sequence_steps(): a daily scheduled job (see hooks.py's
  scheduler_events) that sends whichever step is next due for every
  Active enrollment, then advances it (or marks it Completed once
  every step has gone out).
"""

import frappe

from dashboard.api.shared.email_templates import render_email, plain_text_to_email_html

SEQUENCE_DOCTYPE = "Email Sequence"
STEP_DOCTYPE = "Email Sequence Step"
ENROLLMENT_DOCTYPE = "Email Sequence Enrollment"

# Never let a sequence trigger off the engine's own bookkeeping -
# otherwise an Email Sequence Enrollment being created could itself
# match a trigger_doctype and spiral.
_ENGINE_DOCTYPES = {SEQUENCE_DOCTYPE, STEP_DOCTYPE, ENROLLMENT_DOCTYPE}


def _first_step_delay(sequence_name):
    steps = frappe.get_all(
        STEP_DOCTYPE,
        filters={"parent": sequence_name, "parenttype": SEQUENCE_DOCTYPE},
        fields=["delay_days"],
        order_by="step_number asc",
        limit_page_length=1,
    )
    return steps[0].delay_days if steps and steps[0].delay_days else 0


def check_sequence_triggers(doc, method=None):
    if doc.doctype in _ENGINE_DOCTYPES:
        return

    if not frappe.db.exists("DocType", SEQUENCE_DOCTYPE):
        return

    sequences = frappe.get_all(
        SEQUENCE_DOCTYPE,
        filters={"trigger_doctype": doc.doctype, "is_active": 1},
        fields=["name", "trigger_email_field", "trigger_name_field"],
    )
    if not sequences:
        return

    enrolled_any = False

    for seq in sequences:
        email_value = (doc.get(seq.trigger_email_field) or "").strip() if seq.trigger_email_field else ""
        if not email_value:
            continue

        if frappe.db.exists(ENROLLMENT_DOCTYPE, {
            "sequence": seq.name,
            "reference_doctype": doc.doctype,
            "reference_name": doc.name,
        }):
            continue

        name_value = (doc.get(seq.trigger_name_field) or "") if seq.trigger_name_field else ""
        delay_days = _first_step_delay(seq.name)

        enrollment = frappe.new_doc(ENROLLMENT_DOCTYPE)
        enrollment.sequence = seq.name
        enrollment.recipient_email = email_value
        enrollment.recipient_name = name_value
        enrollment.reference_doctype = doc.doctype
        enrollment.reference_name = doc.name
        enrollment.status = "Active"
        enrollment.current_step = 0
        enrollment.next_send_date = frappe.utils.add_days(frappe.utils.today(), delay_days)
        enrollment.insert(ignore_permissions=True)
        enrolled_any = True

    if enrolled_any:
        frappe.db.commit()


def process_due_sequence_steps():
    if not frappe.db.exists("DocType", ENROLLMENT_DOCTYPE):
        return

    due_names = frappe.get_all(
        ENROLLMENT_DOCTYPE,
        filters={"status": "Active", "next_send_date": ["<=", frappe.utils.today()]},
        pluck="name",
    )

    for name in due_names:
        _send_next_step(name)


def _send_next_step(enrollment_name):
    try:
        enrollment = frappe.get_doc(ENROLLMENT_DOCTYPE, enrollment_name)

        if not frappe.db.exists(SEQUENCE_DOCTYPE, enrollment.sequence):
            enrollment.status = "Cancelled"
            enrollment.save(ignore_permissions=True)
            frappe.db.commit()
            return

        sequence = frappe.get_doc(SEQUENCE_DOCTYPE, enrollment.sequence)

        if not sequence.is_active:
            enrollment.status = "Cancelled"
            enrollment.save(ignore_permissions=True)
            frappe.db.commit()
            return

        steps = sorted(sequence.steps, key=lambda row: row.step_number or 0)
        step_index = enrollment.current_step or 0

        if step_index >= len(steps):
            enrollment.status = "Completed"
            enrollment.save(ignore_permissions=True)
            frappe.db.commit()
            return

        step = steps[step_index]

        subject, message = render_email(
            step.email_template,
            {
                "recipient_name": enrollment.recipient_name or "",
                "recipient_email": enrollment.recipient_email,
            },
            fallback_subject="",
            fallback_message="",
        )

        if subject or message:
            frappe.sendmail(
                recipients=[enrollment.recipient_email],
                subject=subject or sequence.sequence_name,
                message=plain_text_to_email_html(message) if message else "",
                now=True,
            )
            enrollment.last_sent_on = frappe.utils.now_datetime()
        else:
            frappe.log_error(
                f"Sequence '{sequence.name}' step {step.step_number} points at Email Template "
                f"'{step.email_template}', which has no subject/body - nothing was sent.",
                "Email Sequence - Empty Template",
            )

        enrollment.current_step = step_index + 1

        if enrollment.current_step >= len(steps):
            enrollment.status = "Completed"
        else:
            next_step = steps[enrollment.current_step]
            enrollment.next_send_date = frappe.utils.add_days(
                frappe.utils.today(), next_step.delay_days or 0
            )

        enrollment.save(ignore_permissions=True)
        frappe.db.commit()
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"Email Sequence Send Failed - {enrollment_name}")
