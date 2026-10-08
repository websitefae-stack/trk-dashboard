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
from frappe import _

from dashboard.api.shared.email_templates import render_email, plain_text_to_email_html, wrap_branded_email_html, _looks_like_html
from dashboard.api.shared.profile import PUBLIC_SITE_URL
from dashboard.api.shared.mail_throttle import send_email
from dashboard.api.shared.franchise_brochure import BROCHURE_PAGE_PATH

SEQUENCE_DOCTYPE = "Email Sequence"
STEP_DOCTYPE = "Email Sequence Step"
ENROLLMENT_DOCTYPE = "Email Sequence Enrollment"
BROCHURE_REQUEST_DOCTYPE = "Franchise Brochure Request"

# Never let a sequence trigger off the engine's own bookkeeping -
# otherwise an Email Sequence Enrollment being created could itself
# match a trigger_doctype and spiral. Also skip Frappe's own schema/
# metadata doctypes outright - creating a brand new DocType (or a
# Custom Field, Property Setter, etc.) is itself a document insert
# ("doc.doctype" is "DocType", not whatever's being defined), which
# this hook has no business reacting to, and which can happen before
# the doctype being defined even has a database table yet (see the
# try/except below - that's exactly what broke a live migrate).
_ENGINE_DOCTYPES = {SEQUENCE_DOCTYPE, STEP_DOCTYPE, ENROLLMENT_DOCTYPE}
_META_DOCTYPES = {"DocType", "DocField", "DocPerm", "Custom Field", "Property Setter", "Web Form", "Web Form Field"}


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
    if doc.doctype in _ENGINE_DOCTYPES or doc.doctype in _META_DOCTYPES:
        return

    try:
        _enrol_matching_sequences(doc)
    except Exception:
        # This hook runs on every single document insert on the site, so
        # it must never be able to take an unrelated insert down with it.
        # The concrete case that bit us live: a brand new doctype's own
        # DocType record can exist (frappe.db.exists("DocType", ...)
        # below returns True immediately) before its actual database
        # table has been created - schema sync for a new doctype is a
        # separate migrate step that can run after this hook has already
        # fired once for it (e.g. while ANOTHER new doctype is being
        # inserted in the same migrate run, as happened here). Treat
        # "the table isn't ready yet" - or anything else unexpected here
        # - as a no-op rather than letting it propagate, and log it so
        # it's still visible.
        frappe.log_error(frappe.get_traceback(), "Email Sequence Trigger Check Failed")


def _enrol_matching_sequences(doc):
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


@frappe.whitelist()
def backfill_sequence_enrollments(sequence_name=None):
    """
    One-off, franchisor-triggered: enrols everyone who already has a real
    record of a sequence's trigger_doctype (e.g. every existing Franchise
    Brochure Request) but was never enrolled, because they signed up
    before the sequence was switched Active - check_sequence_triggers
    only ever fires once, at the moment a NEW document is created, so
    nobody who already existed beforehand is ever picked up
    automatically just by flipping Active on afterwards.

    Safe to re-run any time: _enrol_matching_sequences already skips
    anyone who already has an enrollment for this sequence, so running
    this twice (or running it after the sequence has already caught up
    naturally) never double-enrols anyone.

    Visit this URL directly while logged in as Ashley/office:
    /api/method/dashboard.api.shared.email_sequences.backfill_sequence_
    enrollments?sequence_name=Franchise Brochure Nurture
    """
    from dashboard.api.shared.permissions import is_franchisor_user

    if not is_franchisor_user():
        frappe.throw(_("You do not have permission to do this."), frappe.PermissionError)

    sequence_name = (sequence_name or "").strip()
    if not sequence_name or not frappe.db.exists(SEQUENCE_DOCTYPE, sequence_name):
        frappe.throw(_("Sequence not found."))

    sequence = frappe.get_doc(SEQUENCE_DOCTYPE, sequence_name)

    if not sequence.is_active:
        frappe.throw(_("Switch this sequence's Active box on first, then run this again."))

    existing_names = frappe.get_all(sequence.trigger_doctype, pluck="name", limit_page_length=5000)
    before_count = frappe.db.count(ENROLLMENT_DOCTYPE, filters={"sequence": sequence.name})

    for name in existing_names:
        doc = frappe.get_doc(sequence.trigger_doctype, name)
        _enrol_matching_sequences(doc)

    after_count = frappe.db.count(ENROLLMENT_DOCTYPE, filters={"sequence": sequence.name})

    return {
        "ok": True,
        "candidates_checked": len(existing_names),
        "newly_enrolled": after_count - before_count,
    }


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


def _brochure_url_for_enrollment(enrollment):
    """
    The same one-time, no-signup-again brochure link as the immediate
    "Franchise Brochure Link" email (see franchise_brochure.py's own
    send_brochure_link) - reads the token straight off the Franchise
    Brochure Request this enrollment was triggered from, so every step
    in a brochure-nurture sequence can reuse {{ brochure_url }} too, not
    just that first email. Blank for any enrollment NOT triggered off a
    Franchise Brochure Request (a sequence's trigger_doctype can be
    anything), so a template using this merge field elsewhere just
    renders nothing rather than erroring.
    """
    if enrollment.reference_doctype != BROCHURE_REQUEST_DOCTYPE or not enrollment.reference_name:
        return ""

    token = frappe.db.get_value(BROCHURE_REQUEST_DOCTYPE, enrollment.reference_name, "token")
    if not token:
        return ""

    return f"{PUBLIC_SITE_URL}{BROCHURE_PAGE_PATH}?token={token}"


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
                # Every sequence's templates can embed this regardless of
                # what they're nurturing towards - currently always the
                # Franchisee Call booking link (see
                # resilient_domains' /book-franchise-call), the only
                # "book a call" CTA any sequence in this system sends
                # people to so far.
                "booking_url": PUBLIC_SITE_URL + "/book-franchise-call",
                # Only ever populated for a Franchise Brochure Request
                # enrollment (see _brochure_url_for_enrollment) - blank
                # for any other sequence, so a template using this merge
                # field in a non-brochure sequence just renders nothing
                # rather than erroring.
                "brochure_url": _brochure_url_for_enrollment(enrollment),
            },
            fallback_subject="",
            fallback_message="",
            strip_html_message=False,
        )

        if subject or message:
            # A fully custom HTML step template is sent exactly as
            # authored - wrap_branded_email_html would otherwise add a
            # second logo header/footer on top of its own.
            if message and _looks_like_html(message):
                final_message = message
            elif message:
                final_message = wrap_branded_email_html(plain_text_to_email_html(message))
            else:
                final_message = ""

            send_email(
                recipients=[enrollment.recipient_email],
                subject=subject or sequence.sequence_name,
                message=final_message,
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
