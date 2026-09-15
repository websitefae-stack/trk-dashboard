"""
The School Pipeline: outreach to prospective schools, run entirely from
the franchisor dashboard. See patches/create_school_pipeline_doctypes.py
for the five doctypes involved and the full reasoning behind the design -
the short version:

- School is deliberately its own record, never a Client, until the
  school actually buys something (convert_school_to_client below).
- A school can go through several Sequences over its lifetime - each
  run is its own School Sequence Enrollment record, so starting a new
  campaign later never conflicts with or overwrites a finished one.
- The automatic weekly-cadence sending (process_due_school_sequences)
  sends one combined email per step, To the school's Head contact (or
  the first contact if there's no Head), Cc everyone else - not N
  separate emails - always From/Reply-To office@theresilienthub.co.uk.
- Every send is tagged reference_doctype="School" so Frappe's own
  Communication timeline (and its reply-threading, since office@ is a
  two-way connected Email Account) becomes the school's full
  sent/received history for free - no separate log doctype needed.
- handle_incoming_school_reply reacts to an inbound reply landing
  against a School (via that same reference_doctype/reference_name
  threading) - marks the matching contact/school Responded and emails
  Ashley a heads-up, since she doesn't work inside Frappe day to day.
"""

import json
from email.utils import parseaddr

import frappe
from frappe import _
from frappe.utils import add_days, getdate, nowdate

from dashboard.api.shared.email_templates import _body_fieldname, plain_text_to_email_html, render_email
from dashboard.api.shared.permissions import ensure_logged_in, is_franchisor_user
from dashboard.api.shared.profile import ASHLEY_USER, OFFICE_USER

SCHOOL_DOCTYPE = "School"
CONTACT_DOCTYPE = "School Contact"
SEQUENCE_DOCTYPE = "School Sequence"
STEP_DOCTYPE = "School Sequence Step"
ENROLLMENT_DOCTYPE = "School Sequence Enrollment"

# Stages a school can already be past the point where the automatic
# sequence machinery (starting/finishing a run) should be allowed to move
# it backwards - e.g. a school that's already Responded or become a
# Customer should never get silently reset to "In Sequence" or "Idle"
# just because a sequence happened to start or finish around the same
# time.
RESTING_STAGES = ("Responded", "Call Booked", "Customer", "Declined")

VALID_STAGES = ("New", "In Sequence", "Idle", "Responded", "Call Booked", "Customer", "Declined")


def _ensure_franchisor():
    ensure_logged_in()
    if not is_franchisor_user():
        frappe.throw(_("Only the franchisor can access the school pipeline."), frappe.PermissionError)


def _parse_payload(value):
    if isinstance(value, str):
        return json.loads(value) if value else {}
    return value or {}


def _split_name(full_name):
    parts = (full_name or "").strip().split(" ", 1)
    first = parts[0] if parts else ""
    last = parts[1] if len(parts) > 1 else ""
    return first, last


# =====================================================
# SCHOOLS: LIST / DETAIL / SAVE
# =====================================================

@frappe.whitelist()
def get_school_pipeline():
    _ensure_franchisor()

    # School/School Sequence/etc. only grant Frappe's own "System Manager"
    # doctype role permission (see create_school_pipeline_doctypes.py) -
    # Ashley's franchisor account isn't necessarily a Desk System Manager,
    # so frappe.get_all() would otherwise silently return zero rows for
    # her (Frappe's default permission filtering on get_all, not an
    # error - it just looks like the data isn't there). Every read in
    # this file passes ignore_permissions=True for that reason; access
    # is instead gated by _ensure_franchisor() above.
    schools = frappe.get_all(
        SCHOOL_DOCTYPE,
        fields=["name", "school_name", "stage", "website", "linked_client", "modified"],
        order_by="modified desc",
        ignore_permissions=True,
    )

    active_by_school = {}
    for row in frappe.get_all(
        ENROLLMENT_DOCTYPE,
        filters={"status": "Active"},
        fields=["name", "school", "sequence", "current_step", "next_send_date"],
        ignore_permissions=True,
    ):
        # A school should only ever have one Active enrollment at a time
        # (enroll_schools won't start a second one while one's still
        # running) - if that's ever violated, the most recent wins here,
        # display only.
        active_by_school[row.school] = row

    contact_counts = {}
    for row in frappe.get_all(CONTACT_DOCTYPE, filters={"parenttype": SCHOOL_DOCTYPE}, fields=["parent"], ignore_permissions=True):
        contact_counts[row.parent] = contact_counts.get(row.parent, 0) + 1

    step_totals_by_sequence = {}

    result = []
    for school in schools:
        active = active_by_school.get(school.name)
        active_summary = None

        if active:
            if active.sequence not in step_totals_by_sequence:
                step_totals_by_sequence[active.sequence] = frappe.db.count(
                    STEP_DOCTYPE, {"parent": active.sequence, "parenttype": SEQUENCE_DOCTYPE}
                )
            active_summary = {
                "sequence": active.sequence,
                "current_step": active.current_step,
                "total_steps": step_totals_by_sequence[active.sequence],
                "next_send_date": active.next_send_date,
            }

        result.append({
            "name": school.name,
            "school_name": school.school_name,
            "stage": school.stage,
            "website": school.website,
            "linked_client": school.linked_client,
            "contact_count": contact_counts.get(school.name, 0),
            "active_sequence": active_summary,
        })

    return result


@frappe.whitelist()
def get_school(name=None):
    _ensure_franchisor()
    name = (name or "").strip()

    if not name or not frappe.db.exists(SCHOOL_DOCTYPE, name):
        frappe.throw(_("School not found."))

    doc = frappe.get_doc(SCHOOL_DOCTYPE, name)

    enrollments = frappe.get_all(
        ENROLLMENT_DOCTYPE,
        filters={"school": name},
        fields=["name", "sequence", "status", "current_step", "start_date", "next_send_date", "last_sent_on"],
        order_by="start_date desc",
        ignore_permissions=True,
    )
    for row in enrollments:
        row["total_steps"] = frappe.db.count(STEP_DOCTYPE, {"parent": row.sequence, "parenttype": SEQUENCE_DOCTYPE})

    timeline = frappe.get_all(
        "Communication",
        filters={"reference_doctype": SCHOOL_DOCTYPE, "reference_name": name},
        fields=["name", "sent_or_received", "subject", "content", "sender", "recipients", "cc", "communication_date"],
        order_by="communication_date asc",
        limit_page_length=200,
        ignore_permissions=True,
    )

    return {
        "name": doc.name,
        "school_name": doc.school_name,
        "website": doc.website,
        "stage": doc.stage,
        "notes": doc.notes,
        "linked_client": doc.linked_client,
        "contacts": [
            {
                "name": row.name,
                "contact_name": row.contact_name,
                "role": row.role,
                "email": row.email,
                "responded": row.responded,
                "response_note": row.response_note,
            }
            for row in (doc.contacts or [])
        ],
        "enrollments": enrollments,
        "timeline": timeline,
    }


@frappe.whitelist()
def save_school(docname=None, data=None):
    _ensure_franchisor()
    payload = _parse_payload(data)

    school_name = (payload.get("school_name") or "").strip()
    if not school_name:
        frappe.throw(_("School name is required."))

    if docname:
        doc = frappe.get_doc(SCHOOL_DOCTYPE, docname)
    else:
        doc = frappe.new_doc(SCHOOL_DOCTYPE)
        doc.stage = "New"

    doc.school_name = school_name
    doc.website = (payload.get("website") or "").strip()
    doc.notes = payload.get("notes") or ""

    doc.set("contacts", [])
    for row in payload.get("contacts") or []:
        email = (row.get("email") or "").strip()
        contact_name = (row.get("contact_name") or "").strip()
        if not email or not contact_name:
            continue

        doc.append("contacts", {
            "contact_name": contact_name,
            "role": row.get("role") or "",
            "email": email,
            "responded": 1 if row.get("responded") else 0,
            "response_note": row.get("response_note") or "",
        })

    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {"ok": 1, "name": doc.name}


@frappe.whitelist()
def set_school_stage(school=None, stage=None):
    """The manual override for the board - drag a card, or pick a stage
    directly, regardless of what the automatic sequence machinery would
    otherwise have done."""
    _ensure_franchisor()

    school = (school or "").strip()
    stage = (stage or "").strip()

    if not school or not frappe.db.exists(SCHOOL_DOCTYPE, school):
        frappe.throw(_("School not found."))
    if stage not in VALID_STAGES:
        frappe.throw(_("Invalid stage."))

    frappe.db.set_value(SCHOOL_DOCTYPE, school, "stage", stage)
    frappe.db.commit()

    return {"ok": 1}


@frappe.whitelist()
def mark_contact_responded(school=None, contact_row=None, response_note=None, responded=1):
    """Manual fallback for logging a response (and moving the school to
    Responded) - always available even when the automatic reply-detection
    hook can't tell who replied, or hasn't run yet."""
    _ensure_franchisor()

    school = (school or "").strip()
    if not school or not frappe.db.exists(SCHOOL_DOCTYPE, school):
        frappe.throw(_("School not found."))

    doc = frappe.get_doc(SCHOOL_DOCTYPE, school)
    row = next((c for c in (doc.contacts or []) if c.name == contact_row), None)

    if not row:
        frappe.throw(_("Contact not found on this school."))

    row.responded = 1 if int(responded or 0) else 0
    if response_note is not None:
        row.response_note = response_note

    if row.responded and doc.stage not in ("Call Booked", "Customer", "Declined"):
        doc.stage = "Responded"

    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {"ok": 1}


# =====================================================
# SEQUENCES: LIST / DETAIL / SAVE
# =====================================================

@frappe.whitelist()
def get_sequences():
    _ensure_franchisor()

    sequences = frappe.get_all(
        SEQUENCE_DOCTYPE,
        fields=["name", "sequence_name", "description", "is_active"],
        order_by="modified desc",
        ignore_permissions=True,
    )
    for row in sequences:
        row["step_count"] = frappe.db.count(STEP_DOCTYPE, {"parent": row.name, "parenttype": SEQUENCE_DOCTYPE})

    return sequences


@frappe.whitelist()
def get_sequence(name=None):
    _ensure_franchisor()
    name = (name or "").strip()

    if not name or not frappe.db.exists(SEQUENCE_DOCTYPE, name):
        frappe.throw(_("Sequence not found."))

    doc = frappe.get_doc(SEQUENCE_DOCTYPE, name)
    steps = []

    for row in sorted(doc.steps or [], key=lambda r: r.step_number or 0):
        subject, message = "", ""

        if row.email_template and frappe.db.exists("Email Template", row.email_template):
            tpl = frappe.get_doc("Email Template", row.email_template)
            subject = tpl.get("subject") or ""
            body_fieldname = _body_fieldname(tpl)
            message = (tpl.get(body_fieldname) if body_fieldname else "") or ""

        steps.append({
            "step_number": row.step_number,
            "delay_days": row.delay_days,
            "email_template": row.email_template,
            "subject": subject,
            "message": message,
        })

    return {
        "name": doc.name,
        "sequence_name": doc.sequence_name,
        "description": doc.description,
        "is_active": doc.is_active,
        "steps": steps,
    }


@frappe.whitelist()
def save_sequence(docname=None, data=None):
    """
    A step's email content can be picked from an existing Email Template,
    or written inline here - in which case an Email Template gets
    created/updated automatically (named "School Sequence - <sequence> -
    Step <n>") so Ashley never has to leave the dashboard to write a
    sequence's wording, same as every other editable email in this app
    ultimately being a real Email Template underneath.
    """
    _ensure_franchisor()
    payload = _parse_payload(data)

    sequence_name = (payload.get("sequence_name") or "").strip()
    if not sequence_name:
        frappe.throw(_("Sequence name is required."))

    if docname:
        doc = frappe.get_doc(SEQUENCE_DOCTYPE, docname)
    else:
        doc = frappe.new_doc(SEQUENCE_DOCTYPE)
        doc.sequence_name = sequence_name

    doc.description = payload.get("description") or ""
    doc.is_active = 1 if payload.get("is_active", 1) else 0

    doc.set("steps", [])

    for index, step in enumerate(payload.get("steps") or [], start=1):
        email_template = (step.get("email_template") or "").strip()

        if not email_template:
            subject = (step.get("subject") or "").strip()
            message = step.get("message") or ""

            if not subject and not message:
                frappe.throw(_("Step {0} needs either an existing Email Template or its own subject/message.").format(index))

            template_name = f"School Sequence - {sequence_name} - Step {index}"

            if frappe.db.exists("Email Template", template_name):
                tpl = frappe.get_doc("Email Template", template_name)
            else:
                tpl = frappe.new_doc("Email Template")
                tpl.name = template_name

            tpl.subject = subject
            body_fieldname = _body_fieldname(tpl) or "response"
            tpl.set(body_fieldname, message)
            tpl.save(ignore_permissions=True)

            email_template = tpl.name

        doc.append("steps", {
            "step_number": index,
            "delay_days": int(step.get("delay_days") or 0),
            "email_template": email_template,
        })

    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {"ok": 1, "name": doc.name}


# =====================================================
# ENROLLMENT / SENDING
# =====================================================

@frappe.whitelist()
def enroll_schools(school_names=None, sequence=None, start_date=None):
    """
    Bulk-enrols the given schools into a sequence starting on start_date -
    call this once per cohort with a different start_date to stagger
    "school group A starts today, group B starts tomorrow" while each
    individual school still only gets one email a week. Schools that
    already have an Active enrollment are skipped rather than double-
    enrolled - a school only ever runs one sequence at a time.
    """
    _ensure_franchisor()

    if isinstance(school_names, str):
        school_names = frappe.parse_json(school_names)

    school_names = [name for name in (school_names or []) if name]
    sequence = (sequence or "").strip()

    if not school_names:
        frappe.throw(_("Choose at least one school."))
    if not sequence or not frappe.db.exists(SEQUENCE_DOCTYPE, sequence):
        frappe.throw(_("Choose a valid sequence."))

    seq_doc = frappe.get_doc(SEQUENCE_DOCTYPE, sequence)
    if not seq_doc.is_active:
        frappe.throw(_("That sequence is not active."))

    steps = sorted(seq_doc.steps or [], key=lambda r: r.step_number or 0)
    if not steps:
        frappe.throw(_("That sequence has no steps."))

    start = getdate(start_date) if start_date else getdate(nowdate())
    first_delay = steps[0].delay_days or 0

    enrolled = []
    skipped = []

    for school_name in school_names:
        if not frappe.db.exists(SCHOOL_DOCTYPE, school_name):
            continue

        if frappe.db.exists(ENROLLMENT_DOCTYPE, {"school": school_name, "status": "Active"}):
            skipped.append(school_name)
            continue

        enrollment = frappe.new_doc(ENROLLMENT_DOCTYPE)
        enrollment.school = school_name
        enrollment.sequence = sequence
        enrollment.status = "Active"
        enrollment.current_step = 0
        enrollment.start_date = start
        enrollment.next_send_date = add_days(start, first_delay)
        enrollment.insert(ignore_permissions=True)

        current_stage = frappe.db.get_value(SCHOOL_DOCTYPE, school_name, "stage")
        if current_stage not in RESTING_STAGES:
            frappe.db.set_value(SCHOOL_DOCTYPE, school_name, "stage", "In Sequence")

        enrolled.append(school_name)

    frappe.db.commit()

    return {"enrolled": enrolled, "skipped": skipped}


@frappe.whitelist()
def send_one_off_school_email(school=None, contact_emails=None, subject=None, message=None):
    """
    The targeted-reply tool - pick one (or several) of a school's own
    contacts and send them something directly, entirely separate from the
    automatic sequence. Sends one email per selected contact (not one
    email to all of them) so {{ contact_name }} in the subject/message
    can actually resolve to the right person for each - the whole point
    of this tool being "target the Head only" or "target the SENCO
    only" rather than the sequence's shared group send.
    """
    _ensure_franchisor()

    school = (school or "").strip()
    if not school or not frappe.db.exists(SCHOOL_DOCTYPE, school):
        frappe.throw(_("School not found."))

    if isinstance(contact_emails, str):
        contact_emails = frappe.parse_json(contact_emails)
    contact_emails = [email for email in (contact_emails or []) if email]

    if not contact_emails:
        frappe.throw(_("Choose at least one contact to email."))

    subject = (subject or "").strip()
    message = (message or "").strip()

    if not subject or not message:
        frappe.throw(_("Subject and message are required."))

    doc = frappe.get_doc(SCHOOL_DOCTYPE, school)
    name_by_email = {c.email: c.contact_name for c in (doc.contacts or []) if c.email}

    for email in contact_emails:
        context = {"school_name": doc.school_name, "contact_name": name_by_email.get(email) or ""}

        frappe.sendmail(
            sender=OFFICE_USER,
            recipients=[email],
            reply_to=OFFICE_USER,
            subject=frappe.render_template(subject, context),
            message=plain_text_to_email_html(frappe.render_template(message, context)),
            reference_doctype=SCHOOL_DOCTYPE,
            reference_name=school,
            now=True,
        )

    frappe.db.commit()

    return {"ok": 1}


def _pick_recipients(contacts):
    """To: whoever's tagged Head (falls back to the first contact). Cc:
    everyone else - one combined email per step, not N separate sends,
    per Ashley's "cc for all" on the automatic sequence. Returns the
    primary contact's own row (not just their email) so callers can
    also pull their name for the {{ contact_name }} merge field - the
    Cc'd contacts don't get their own name in the body, since this is
    one shared email, not one per person."""
    contacts = [c for c in (contacts or []) if c.email]
    if not contacts:
        return None, []

    head = next((c for c in contacts if c.role == "Head"), None)
    primary = head or contacts[0]
    rest = [c.email for c in contacts if c.email != primary.email]

    return primary, rest


def process_due_school_sequences():
    """Daily scheduled job (see hooks.py) - sends whichever step is next
    due for every Active enrollment, then advances it."""
    if not frappe.db.exists("DocType", ENROLLMENT_DOCTYPE):
        return

    due_names = frappe.get_all(
        ENROLLMENT_DOCTYPE,
        filters={"status": "Active", "next_send_date": ["<=", nowdate()]},
        pluck="name",
        ignore_permissions=True,
    )

    for name in due_names:
        _send_next_school_step(name)


def _settle_school_stage_after_sequence(school_name):
    """A sequence finishing with no response settles the school into
    Idle rather than leaving it badged "In Sequence" forever - never
    downgrades a school that's already moved further along."""
    current_stage = frappe.db.get_value(SCHOOL_DOCTYPE, school_name, "stage")
    if current_stage == "In Sequence":
        frappe.db.set_value(SCHOOL_DOCTYPE, school_name, "stage", "Idle")


def _send_next_school_step(enrollment_name):
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

        school = frappe.get_doc(SCHOOL_DOCTYPE, enrollment.school)
        primary_contact, cc_emails = _pick_recipients(school.contacts)

        if not primary_contact:
            # No contacts to send to - park it rather than retrying (and
            # failing) the same due step every day forever.
            enrollment.status = "Cancelled"
            enrollment.save(ignore_permissions=True)
            frappe.db.commit()
            frappe.log_error(
                f"School '{school.name}' has no contacts - enrollment cancelled.",
                "School Sequence - No Contacts",
            )
            return

        steps = sorted(sequence.steps or [], key=lambda r: r.step_number or 0)
        step_index = enrollment.current_step or 0

        if step_index >= len(steps):
            enrollment.status = "Completed"
            enrollment.save(ignore_permissions=True)
            frappe.db.commit()
            _settle_school_stage_after_sequence(school.name)
            return

        step = steps[step_index]

        subject, message = render_email(
            step.email_template,
            {"school_name": school.school_name, "contact_name": primary_contact.contact_name or ""},
            fallback_subject="",
            fallback_message="",
        )

        if subject or message:
            frappe.sendmail(
                sender=OFFICE_USER,
                recipients=[primary_contact.email],
                cc=cc_emails,
                reply_to=OFFICE_USER,
                subject=subject or sequence.sequence_name,
                message=plain_text_to_email_html(message) if message else "",
                reference_doctype=SCHOOL_DOCTYPE,
                reference_name=school.name,
                now=True,
            )
            enrollment.last_sent_on = frappe.utils.now_datetime()
        else:
            frappe.log_error(
                f"Sequence '{sequence.name}' step {step.step_number} points at Email Template "
                f"'{step.email_template}', which has no subject/body - nothing was sent.",
                "School Sequence - Empty Template",
            )

        enrollment.current_step = step_index + 1

        if enrollment.current_step >= len(steps):
            enrollment.status = "Completed"
            enrollment.save(ignore_permissions=True)
            frappe.db.commit()
            _settle_school_stage_after_sequence(school.name)
            return

        next_step = steps[enrollment.current_step]
        enrollment.next_send_date = add_days(nowdate(), next_step.delay_days or 0)
        enrollment.save(ignore_permissions=True)
        frappe.db.commit()
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"School Sequence Send Failed - {enrollment_name}")


# =====================================================
# REPLY DETECTION (Communication.after_insert - see hooks.py)
# =====================================================

def handle_incoming_school_reply(doc, method=None):
    try:
        _handle_incoming_school_reply(doc)
    except Exception:
        # Same reasoning as every other wide-reach hook in this app -
        # a mail-pull failure here must never break incoming mail
        # processing for the rest of the site.
        frappe.log_error(frappe.get_traceback(), "School Sequence Reply Handling Failed")


def _handle_incoming_school_reply(doc):
    if doc.reference_doctype != SCHOOL_DOCTYPE or not doc.reference_name:
        return
    if doc.sent_or_received != "Received":
        return
    if not frappe.db.exists(SCHOOL_DOCTYPE, doc.reference_name):
        return

    school = frappe.get_doc(SCHOOL_DOCTYPE, doc.reference_name)
    sender_email = parseaddr(doc.sender or "")[1].strip().lower()

    matched_contact = next(
        (c for c in (school.contacts or []) if (c.email or "").strip().lower() == sender_email),
        None,
    )

    snippet = (doc.content or doc.subject or "").strip()
    if len(snippet) > 300:
        snippet = snippet[:300] + "..."

    changed = False

    if matched_contact:
        note = f"[Auto-logged reply, {frappe.utils.format_datetime(doc.communication_date, 'dd-MM-yyyy HH:mm')}] {snippet}"
        matched_contact.responded = 1
        matched_contact.response_note = ((matched_contact.response_note or "") + "\n\n" + note).strip()
        changed = True

    if school.stage not in ("Call Booked", "Customer", "Declined"):
        school.stage = "Responded"
        changed = True

    if changed:
        school.save(ignore_permissions=True)
        frappe.db.commit()

    _notify_ashley_of_school_reply(school, matched_contact, sender_email, snippet)


def _notify_ashley_of_school_reply(school, matched_contact, sender_email, snippet):
    """Ashley doesn't work inside Frappe day to day, so the alert has to
    reach her own inbox directly rather than a dashboard notification she
    might not see - this is a plain email, not a Dashboard Conversation."""
    who = matched_contact.contact_name if matched_contact else sender_email
    role = f" ({matched_contact.role})" if matched_contact and matched_contact.role else ""

    frappe.sendmail(
        sender=OFFICE_USER,
        recipients=[ASHLEY_USER],
        subject=f"School replied: {school.school_name}",
        message=plain_text_to_email_html(
            f"{who}{role} at {school.school_name} replied:\n\n"
            f"{snippet}\n\n"
            "This has been logged automatically against the school in the pipeline. "
            "Reply via office@theresilienthub.co.uk (not your own inbox) to keep your reply on record too."
        ),
        now=True,
    )


# =====================================================
# CONVERSION TO CLIENT
# =====================================================

@frappe.whitelist()
def convert_school_to_client(school=None, client=None, client_type="School"):
    """
    Links (or creates) a real Client the moment a school actually buys
    something - see this module's docstring for why School stays
    separate from Client until this point. Every School Contact is
    carried over as a real Contact on the Client (Ashley confirmed: all
    of them, not just whoever drove the sale) - same pattern
    leads.py's own convert_lead_to_client uses for its supplementary
    contacts (a plain Contact record + a client_contacts row, no
    Dynamic Link needed).
    """
    _ensure_franchisor()

    school = (school or "").strip()
    if not school or not frappe.db.exists(SCHOOL_DOCTYPE, school):
        frappe.throw(_("School not found."))

    doc = frappe.get_doc(SCHOOL_DOCTYPE, school)
    client = (client or "").strip()

    if client:
        if not frappe.db.exists("Client", client):
            frappe.throw(_("Client not found."))
        client_doc = frappe.get_doc("Client", client)
    else:
        client_doc = frappe.new_doc("Client")
        if client_doc.meta.has_field("client_name"):
            client_doc.client_name = doc.school_name
        if client_doc.meta.has_field("client_type"):
            client_doc.client_type = client_type
        client_doc.insert(ignore_permissions=True)

    client_meta = frappe.get_meta("Client")

    if client_meta.has_field("client_contacts"):
        from dashboard.api.shared.client_details import sanitize_name_part

        existing_emails = {
            (row.get("email_id") or "").strip().lower()
            for row in (client_doc.get("client_contacts") or [])
        }

        for row in doc.contacts or []:
            if not row.email or row.email.strip().lower() in existing_emails:
                continue

            first, last = _split_name(row.contact_name)
            contact = frappe.new_doc("Contact")
            contact.first_name = first
            if last:
                contact.last_name = last
            contact.append("email_ids", {"email_id": row.email, "is_primary": 1})
            contact.insert(ignore_permissions=True)

            client_doc.append("client_contacts", {
                "contact": contact.name,
                "contact_name": sanitize_name_part(row.contact_name),
                "email_id": row.email,
            })

        client_doc.save(ignore_permissions=True)

    doc.linked_client = client_doc.name
    doc.stage = "Customer"
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {"ok": 1, "client": client_doc.name}


@frappe.whitelist()
def get_school_for_client(client=None):
    """Reverse lookup used by the Client Details page - the linked
    School's full outreach history, if this client came from the school
    pipeline."""
    client = (client or "").strip()
    if not client:
        return None

    school_name = frappe.db.get_value(SCHOOL_DOCTYPE, {"linked_client": client}, "name")
    if not school_name:
        return None

    return get_school(school_name)
