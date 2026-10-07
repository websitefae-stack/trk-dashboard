"""
Franchisee Call and Session Worker recruitment, on its own doctype
("Recruitment Lead" - see patches/create_recruitment_lead_doctype.py)
rather than sharing "Client Lead" with ordinary client enquiries. This
module is a close, deliberate port of leads.py's own recruitment
functions (Stage 1 pipeline, NDA/Intent to Proceed/Franchise Agreement
e-signing, Safer Recruitment Checklist, Session Worker Fees Guide,
conversion) - same behaviour, same Practice Document templates, same
whitelisted method shapes, just pointed at the new doctype and using
lead_type ("Franchisee"/"Session Worker") instead of leads.py's
appointment_type-substring matching.

This is PHASE 1 of a 3-phase migration (see create_recruitment_lead_
doctype.py's own docstring) - purely additive, Client Lead and its own
leads.py are completely untouched by this module.
"""

from urllib.parse import quote

import frappe
from frappe import _
from frappe.utils import get_url, fmt_money

from dashboard.api.shared.permissions import ensure_logged_in, is_franchisor_user, get_current_user_dashboard_type
from dashboard.api.shared.utils import coalesce_str, coalesce_raw, parse_date_input
from dashboard.api.shared.notifications import create_trk_notification, FRANCHISOR_USERS
from dashboard.api.shared.email_templates import plain_text_to_email_html, parse_email_list
from dashboard.api.shared.mail_throttle import send_email
from dashboard.api.shared.item_access import _get_coach_login
from dashboard.api.shared.clients import get_coach_label

RECRUITMENT_LEAD_DOCTYPE = "Recruitment Lead"

LEAD_STATUSES = ["New", "Converted", "Declined"]
DECLINE_STATUSES = ["Declined"]

NDA_BLANK_PLACEHOLDER = "_" * 24

# Same (done_field, date_field) shape as leads.py's STAGE1_MILESTONES/
# SESSION_WORKER_STAGE_MILESTONES - see that module for why each lead
# type gets a different list (a Session Worker's is shorter - no
# Discovery Day, Intent to Proceed, or Franchise Agreement).
STAGE1_MILESTONES = {
    "Franchisee": [
        ("stage1_call_done", "stage1_call_date"),
        ("stage1_nda_done", "stage1_nda_date"),
        ("stage1_discovery_day_done", "stage1_discovery_day_date"),
        ("stage1_intent_deposit_dbs_done", "stage1_intent_deposit_dbs_date"),
        ("stage1_agreement_invoice_done", "stage1_agreement_invoice_date"),
        ("stage1_recruitment_questions_done", "stage1_recruitment_questions_date"),
        ("stage1_contract_sent_done", "stage1_contract_sent_date"),
        ("stage1_final_invoice_done", "stage1_final_invoice_date"),
    ],
    "Session Worker": [
        ("stage1_call_done", "stage1_call_date"),
        ("stage1_nda_done", "stage1_nda_date"),
        ("stage1_agreement_invoice_done", "stage1_agreement_invoice_date"),
        ("fees_guide_done", "fees_guide_date"),
        ("sw_setup_done", "sw_setup_date"),
    ],
}


def _all_milestone_fields():
    seen = set()
    fields = []
    for milestones in STAGE1_MILESTONES.values():
        for done_field, date_field in milestones:
            if done_field not in seen:
                seen.add(done_field)
                fields.append((done_field, date_field))
    return fields


def _current_coach_name():
    user = frappe.session.user
    if not user or user == "Guest":
        return None
    return frappe.db.get_value("Coach", {"user": user}, "name") or frappe.db.get_value(
        "Coach", {"coach_email": user}, "name"
    )


def ensure_lead_access(name):
    ensure_logged_in()

    if not name or not frappe.db.exists(RECRUITMENT_LEAD_DOCTYPE, name):
        frappe.throw(_("Lead not found."))

    doc = frappe.get_doc(RECRUITMENT_LEAD_DOCTYPE, name)

    if is_franchisor_user():
        return doc

    coach_name = _current_coach_name()
    if coach_name and doc.coach == coach_name:
        return doc

    frappe.throw(_("You do not have permission to access this lead."), frappe.PermissionError)


def _notify_lead_allocated(doc, previous_coach=None):
    if not doc.coach or doc.coach == previous_coach:
        return

    coach_user = _get_coach_login(doc.coach)
    if not coach_user or coach_user == frappe.session.user:
        return

    try:
        create_trk_notification(
            recipient_user=coach_user,
            notification_type="Task",
            message="A new recruitment lead was allocated to you: {0}".format(doc.contact_name or "New Lead"),
            reference_doctype=RECRUITMENT_LEAD_DOCTYPE,
            reference_name=doc.name,
            coach=doc.coach,
        )
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"Recruitment Lead Allocated Notification Failed - {doc.name}")


def _notify_coach_of_lead_step(doc, step_label):
    """Mirrors leads.py's own _notify_coach_of_lead_step - see that
    function's docstring for the dedupe reasoning (none needed here
    either, since every sign_*/submit_* function below already throws
    on a second call for the same step)."""
    if doc.status == "Converted" and doc.get("converted_client"):
        return
    if doc.get("converted_session_worker") or doc.get("sw_setup_done"):
        return
    if not doc.coach:
        return

    coach_user = _get_coach_login(doc.coach)
    if not coach_user:
        return

    try:
        create_trk_notification(
            recipient_user=coach_user,
            notification_type="Client Request",
            message=f"{doc.contact_name} - {step_label}. Check their Stage 1 progress and action the next step.",
            priority="High",
            reference_doctype=RECRUITMENT_LEAD_DOCTYPE,
            reference_name=doc.name,
        )
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"Recruitment Lead Step Coach Notification Failed - {doc.name}")


# -------------------------------------------------------------------
# Core CRUD
# -------------------------------------------------------------------

LEAD_LIST_FIELDS = [
    "name", "lead_type", "status", "source", "contact_name", "contact_email", "contact_mobile",
    "coach", "modified", "creation", "stage1_contract_sent_done", "sw_setup_done", "converted_client",
    "converted_session_worker",
]


def _lead_filters_for_current_user(scope=None):
    ensure_logged_in()

    is_franchisor = is_franchisor_user()

    if is_franchisor and (scope or "mine").strip().lower() == "all":
        return None

    coach_name = _current_coach_name()

    if not coach_name:
        return None if is_franchisor else {"name": ["in", []]}

    return {"coach": coach_name}


@frappe.whitelist()
def get_recruitment_leads(scope=None, lead_type=None):
    ensure_logged_in()

    filters = _lead_filters_for_current_user(scope) or {}
    filters = dict(filters)

    lead_type = coalesce_str("lead_type", lead_type)
    if lead_type:
        filters["lead_type"] = lead_type

    return frappe.get_all(
        RECRUITMENT_LEAD_DOCTYPE,
        fields=LEAD_LIST_FIELDS,
        filters=filters,
        order_by="modified desc",
        limit_page_length=2000,
        ignore_permissions=True,
    )


@frappe.whitelist()
def get_recruitment_lead(name=None):
    name = coalesce_str("name", name)
    doc = ensure_lead_access(name)

    row = doc.as_dict()
    row["can_edit"] = 1

    milestones = STAGE1_MILESTONES.get(doc.lead_type, [])
    row["stage1"] = {
        done_field: {"done": int(doc.get(done_field) or 0), "date": doc.get(date_field) or ""}
        for done_field, date_field in milestones
    }

    row["nda_signed"] = 1 if doc.get("nda_signed_snapshot") else 0
    row["nda_link_generated"] = 1 if doc.get("nda_token") else 0
    row["nda_sent_at"] = frappe.utils.format_datetime(doc.get("nda_sent_at"), "dd-MM-yyyy HH:mm") if doc.get("nda_sent_at") else ""

    row["franchisee_intake_submitted"] = 1 if doc.get("franchisee_intake_submitted") else 0
    row["franchisee_intake_link_generated"] = 1 if doc.get("franchisee_intake_token") else 0
    row["franchisee_intake_sent_at"] = (
        frappe.utils.format_datetime(doc.get("franchisee_intake_sent_at"), "dd-MM-yyyy HH:mm")
        if doc.get("franchisee_intake_sent_at") else ""
    )

    if doc.lead_type == "Franchisee":
        row["intent_signed"] = 1 if doc.get("intent_signed_snapshot") else 0
        row["intent_link_generated"] = 1 if doc.get("intent_token") else 0
        row["intent_sent_at"] = frappe.utils.format_datetime(doc.get("intent_sent_at"), "dd-MM-yyyy HH:mm") if doc.get("intent_sent_at") else ""

        row["contract_signed"] = 1 if doc.get("contract_signed_snapshot") else 0
        row["contract_link_generated"] = 1 if doc.get("contract_token") else 0
        row["contract_sent_at"] = frappe.utils.format_datetime(doc.get("contract_sent_at"), "dd-MM-yyyy HH:mm") if doc.get("contract_sent_at") else ""

    if doc.lead_type == "Session Worker":
        row["fees_guide_signed"] = 1 if doc.get("fees_guide_signed_snapshot") else 0
        row["fees_guide_link_generated"] = 1 if doc.get("fees_guide_token") else 0
        row["fees_guide_sent_at"] = (
            frappe.utils.format_datetime(doc.get("fees_guide_sent_at"), "dd-MM-yyyy HH:mm")
            if doc.get("fees_guide_sent_at") else ""
        )

    current_coach_name = _current_coach_name()
    row["is_own_lead"] = 1 if (current_coach_name and doc.coach == current_coach_name) else 0

    return row


@frappe.whitelist()
def create_recruitment_lead(
    lead_type=None, contact_name=None, contact_email=None, contact_mobile=None,
    coach=None, postal_code=None, location_address=None, how_heard=None, consent_given=None,
):
    ensure_logged_in()

    if not is_franchisor_user():
        frappe.throw(_("Only the franchisor can add a recruitment lead."), frappe.PermissionError)

    lead_type = coalesce_str("lead_type", lead_type)
    contact_name = coalesce_str("contact_name", contact_name)
    coach = coalesce_str("coach", coach)

    if lead_type not in ("Franchisee", "Session Worker"):
        frappe.throw(_("Lead Type must be Franchisee or Session Worker."))

    if not contact_name:
        frappe.throw(_("Please enter the contact's name."))

    if coach and not frappe.db.exists("Coach", coach):
        frappe.throw(_("Selected coach was not found."))

    doc = frappe.new_doc(RECRUITMENT_LEAD_DOCTYPE)
    doc.lead_type = lead_type
    doc.status = "New"
    doc.source = "Coach Added"
    doc.appointment_type = "Franchisee Call" if lead_type == "Franchisee" else "Session Worker"
    doc.coach = coach
    doc.contact_name = contact_name
    doc.contact_email = coalesce_str("contact_email", contact_email)
    doc.contact_mobile = coalesce_str("contact_mobile", contact_mobile)
    doc.client_name = contact_name
    doc.postal_code = coalesce_str("postal_code", postal_code)
    doc.location_address = coalesce_str("location_address", location_address)
    doc.how_heard = coalesce_str("how_heard", how_heard)
    consent_given = coalesce_raw("consent_given", consent_given)
    doc.consent_given = 1 if str(consent_given).lower() in ["1", "true", "yes", "on"] else 0

    doc.insert(ignore_permissions=True)
    frappe.db.commit()

    _notify_lead_allocated(doc)

    return {"ok": True, "name": doc.name}


@frappe.whitelist()
def update_recruitment_lead(
    name=None, contact_name=None, contact_email=None, contact_mobile=None,
    postal_code=None, location_address=None, how_heard=None, consent_given=None, coach=None,
):
    name = coalesce_str("name", name)
    doc = ensure_lead_access(name)

    contact_name = coalesce_str("contact_name", contact_name)
    if not contact_name:
        frappe.throw(_("Please enter the contact's name."))

    doc.contact_name = contact_name
    doc.client_name = contact_name
    doc.contact_email = coalesce_str("contact_email", contact_email)
    doc.contact_mobile = coalesce_str("contact_mobile", contact_mobile)
    doc.postal_code = coalesce_str("postal_code", postal_code)
    doc.location_address = coalesce_str("location_address", location_address)
    doc.how_heard = coalesce_str("how_heard", how_heard)

    consent_given = coalesce_raw("consent_given", consent_given)
    doc.consent_given = 1 if str(consent_given).lower() in ["1", "true", "yes", "on"] else 0

    previous_coach = doc.coach
    coach = coalesce_str("coach", coach)
    if coach and is_franchisor_user() and coach != doc.coach:
        if not frappe.db.exists("Coach", coach):
            frappe.throw(_("Coach not found."))
        doc.coach = coach

    doc.save(ignore_permissions=True)
    frappe.db.commit()

    _notify_lead_allocated(doc, previous_coach=previous_coach)

    return {"ok": True, "name": doc.name}


@frappe.whitelist()
def update_recruitment_lead_status(name=None, status=None, decline_reason=None):
    name = coalesce_str("name", name)
    status = coalesce_str("status", status)
    decline_reason = coalesce_str("decline_reason", decline_reason)

    doc = ensure_lead_access(name)

    if status not in LEAD_STATUSES:
        frappe.throw(_("Invalid lead status."))

    if status in DECLINE_STATUSES and not decline_reason:
        frappe.throw(_("Please enter a reason before marking this lead {0}.").format(status))

    doc.status = status
    doc.decline_reason = decline_reason if status in DECLINE_STATUSES else doc.decline_reason
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {"ok": True, "name": doc.name, "status": doc.status}


@frappe.whitelist()
def delete_recruitment_lead(name=None):
    name = coalesce_str("name", name)
    doc = ensure_lead_access(name)

    if doc.status == "Converted" or doc.converted_client or doc.converted_session_worker:
        frappe.throw(_("Converted leads can't be deleted - they already have a record built from them."))

    try:
        frappe.delete_doc(RECRUITMENT_LEAD_DOCTYPE, doc.name, ignore_permissions=True)
    except frappe.LinkExistsError:
        frappe.throw(_(
            "This lead still has other records linked to it and can't be deleted until those are removed first."
        ))

    return {"ok": True}


@frappe.whitelist()
def add_recruitment_lead_note(name=None, note=None, note_date=None):
    name = coalesce_str("name", name)
    note = coalesce_str("note", note)
    note_date = coalesce_str("note_date", note_date)

    if not note:
        frappe.throw(_("Please enter a note."))

    doc = ensure_lead_access(name)

    doc.append("notes", {
        "note": note,
        "note_date": parse_date_input(note_date) or frappe.utils.nowdate(),
        "added_by": frappe.utils.get_fullname(frappe.session.user) or frappe.session.user,
        "added_on": frappe.utils.now_datetime(),
    })
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {"ok": True}


# -------------------------------------------------------------------
# Stage 1 pipeline
# -------------------------------------------------------------------

@frappe.whitelist()
def update_recruitment_pipeline(name=None, milestone=None, done=None, milestone_date=None):
    """Ticks (or unticks) one Stage 1 milestone - mirrors leads.py's own
    update_franchise_pipeline exactly, including the same dd/mm/yyyy-or-
    ISO date tolerance (see parse_date_input)."""
    if not is_franchisor_user():
        frappe.throw(_("You do not have permission to update this."), frappe.PermissionError)

    name = coalesce_str("name", name)
    milestone = coalesce_str("milestone", milestone)
    milestone_date = coalesce_str("milestone_date", milestone_date)
    done = coalesce_raw("done", done)
    is_done = str(done).lower() in ["1", "true", "yes", "on"]

    doc = ensure_lead_access(name)

    valid_fields = {done_field for done_field, _date_field in _all_milestone_fields()}
    if milestone not in valid_fields:
        frappe.throw(_("Unknown Stage 1 milestone."))

    date_field = dict(_all_milestone_fields())[milestone]

    doc.set(milestone, 1 if is_done else 0)
    doc.set(date_field, parse_date_input(milestone_date) if is_done else None)
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {"ok": True, "name": doc.name, milestone: doc.get(milestone), date_field: doc.get(date_field)}


# -------------------------------------------------------------------
# Non-Disclosure Agreement - shared by both lead types, identical to
# leads.py's own NDA flow in every respect except the doctype/token lookup.
# -------------------------------------------------------------------

NDA_PRACTICE_DOCUMENT_TITLE = "Franchisee Non-Disclosure Agreement"
NDA_TERM_YEARS = 3


def _nda_template_text():
    name = frappe.db.get_value("Practice Document", {"document_title": NDA_PRACTICE_DOCUMENT_TITLE}, "name")
    if not name:
        frappe.throw(_("The Franchisee NDA template hasn't been set up yet."))
    return frappe.db.get_value("Practice Document", name, "document_text") or ""


def _render_nda_text(template_text, context):
    text = template_text
    for key, value in context.items():
        text = text.replace("{{ " + key + " }}", frappe.utils.escape_html(value or ""))
    return text


def _get_lead_by_nda_token(token):
    token = (token or "").strip()
    if not token:
        frappe.throw(_("This link is invalid."))
    lead_name = frappe.db.get_value(RECRUITMENT_LEAD_DOCTYPE, {"nda_token": token}, "name")
    if not lead_name:
        frappe.throw(_("This link is invalid."))
    return frappe.get_doc(RECRUITMENT_LEAD_DOCTYPE, lead_name)


@frappe.whitelist()
def get_nda_sign_url(name=None):
    if not is_franchisor_user():
        frappe.throw(_("You do not have permission to do this."), frappe.PermissionError)

    name = coalesce_str("name", name)
    doc = ensure_lead_access(name)

    if doc.get("nda_signed_snapshot"):
        frappe.throw(_("This lead's NDA has already been signed."))

    if not doc.get("nda_token"):
        doc.nda_token = frappe.generate_hash(length=40)
        doc.nda_agreement_date = frappe.utils.today()
        doc.save(ignore_permissions=True)
        frappe.db.commit()

    return {"url": get_url(f"/recruitment-nda?token={doc.nda_token}")}


def _nda_email_text(doc, nda_url):
    contact_name = doc.contact_name or "there"
    subject = "Please sign: Non-Disclosure Agreement"
    continuing_as = "becoming a Resilient Kid franchisee" if doc.lead_type == "Franchisee" else "becoming a Resilient Kid session worker"
    message = (
        f"Hi {contact_name},\n\n"
        f"Please read and sign the Non-Disclosure Agreement below to continue with {continuing_as}:\n\n"
        f"{nda_url}"
    )
    return subject, message


@frappe.whitelist()
def get_nda_email_defaults(name=None):
    name = coalesce_str("name", name)
    doc = ensure_lead_access(name)

    if not doc.contact_email:
        frappe.throw(_("This lead has no contact email address to send the NDA to."))

    nda_url = get_nda_sign_url(name=name)["url"]
    subject, message = _nda_email_text(doc, nda_url)

    return {"subject": subject, "message": message, "recipient": doc.contact_email, "url": nda_url}


@frappe.whitelist()
def send_nda_link(name=None, subject=None, message=None, cc=None, reply_to=None):
    name = coalesce_str("name", name)
    doc = ensure_lead_access(name)

    if not doc.contact_email:
        frappe.throw(_("This lead has no contact email address to send the NDA to."))

    nda_url = get_nda_sign_url(name=name)["url"]

    subject = (subject or "").strip()
    message = (message or "").strip()
    if not subject or not message:
        default_subject, default_message = _nda_email_text(doc, nda_url)
        subject = subject or default_subject
        message = message or default_message

    reply_to = (reply_to or "").strip() or frappe.session.user

    kwargs = {
        "recipients": [doc.contact_email],
        "subject": subject,
        "message": plain_text_to_email_html(message),
        "reply_to": reply_to,
    }

    cc_list = parse_email_list(cc)
    if cc_list:
        kwargs["cc"] = cc_list

    send_email(**kwargs)

    doc.nda_sent_at = frappe.utils.now_datetime()
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {"ok": 1, "url": nda_url, "sent_at": frappe.utils.format_datetime(doc.nda_sent_at, "dd-MM-yyyy HH:mm")}


@frappe.whitelist()
def get_signed_nda(name=None):
    name = coalesce_str("name", name)
    doc = ensure_lead_access(name)

    if not doc.get("nda_signed_snapshot"):
        frappe.throw(_("This NDA hasn't been signed yet."))

    return {
        "signed_html": doc.get("nda_signed_snapshot"),
        "signed_at": frappe.utils.format_datetime(doc.get("nda_signed_at"), "dd-MM-yyyy HH:mm") if doc.get("nda_signed_at") else "",
        "signer_ip": doc.get("nda_signer_ip") or "",
        "signer_user_agent": doc.get("nda_signer_user_agent") or "",
    }


@frappe.whitelist(allow_guest=True)
def get_nda_preview(token=None):
    token = coalesce_str("token", token)
    doc = _get_lead_by_nda_token(token)

    if doc.get("nda_signed_snapshot"):
        return {"already_signed": True, "signed_html": doc.get("nda_signed_snapshot")}

    context = {
        "agreement_date": frappe.utils.formatdate(doc.get("nda_agreement_date"), "dd-MM-yyyy"),
        "recipient_name": doc.get("contact_name") or NDA_BLANK_PLACEHOLDER,
        "recipient_address": NDA_BLANK_PLACEHOLDER,
        "franchisee_signature": NDA_BLANK_PLACEHOLDER,
        "franchisee_date": NDA_BLANK_PLACEHOLDER,
        "term_date": NDA_BLANK_PLACEHOLDER,
    }

    return {
        "already_signed": False,
        "preview_html": _render_nda_text(_nda_template_text(), context),
        "recipient_name": doc.get("contact_name") or "",
    }


@frappe.whitelist(allow_guest=True)
def sign_nda(token=None, recipient_name=None, recipient_address=None, signature_name=None):
    token = coalesce_str("token", token)
    recipient_name = coalesce_str("recipient_name", recipient_name)
    recipient_address = coalesce_str("recipient_address", recipient_address)
    signature_name = coalesce_str("signature_name", signature_name)

    doc = _get_lead_by_nda_token(token)

    if doc.get("nda_signed_snapshot"):
        frappe.throw(_("This NDA has already been signed."))

    if not recipient_name:
        frappe.throw(_("Please enter your full name."))
    if not recipient_address:
        frappe.throw(_("Please enter your address."))
    if not signature_name:
        frappe.throw(_("Please type your name to sign."))

    today = frappe.utils.getdate(frappe.utils.today())
    term_date = frappe.utils.add_years(today, NDA_TERM_YEARS)

    context = {
        "agreement_date": frappe.utils.formatdate(doc.get("nda_agreement_date"), "dd-MM-yyyy"),
        "recipient_name": recipient_name,
        "recipient_address": recipient_address,
        "franchisee_signature": signature_name,
        "franchisee_date": frappe.utils.formatdate(today, "dd-MM-yyyy"),
        "term_date": frappe.utils.formatdate(term_date, "dd-MM-yyyy"),
    }

    doc.nda_recipient_name = recipient_name
    doc.nda_recipient_address = recipient_address
    doc.nda_signature_name = signature_name
    doc.nda_term_expiry = term_date
    doc.nda_signed_snapshot = _render_nda_text(_nda_template_text(), context)
    doc.stage1_nda_done = 1
    doc.stage1_nda_date = today
    doc.nda_signed_at = frappe.utils.now_datetime()
    doc.nda_signer_ip = frappe.local.request_ip
    doc.nda_signer_user_agent = frappe.get_request_header("User-Agent") or ""

    doc.save(ignore_permissions=True)
    frappe.db.commit()

    _notify_coach_of_lead_step(doc, "signed the NDA")

    return {"ok": True}


# -------------------------------------------------------------------
# Deposit and Intent to Proceed Agreement - Franchisee only
# -------------------------------------------------------------------

INTENT_PRACTICE_DOCUMENT_TITLE = "Deposit and Intent to Proceed Agreement"


def _intent_template_text():
    name = frappe.db.get_value("Practice Document", {"document_title": INTENT_PRACTICE_DOCUMENT_TITLE}, "name")
    if not name:
        frappe.throw(_("The Intent to Proceed template hasn't been set up yet."))
    return frappe.db.get_value("Practice Document", name, "document_text") or ""


def _get_lead_by_intent_token(token):
    token = (token or "").strip()
    if not token:
        frappe.throw(_("This link is invalid."))
    lead_name = frappe.db.get_value(RECRUITMENT_LEAD_DOCTYPE, {"intent_token": token}, "name")
    if not lead_name:
        frappe.throw(_("This link is invalid."))
    return frappe.get_doc(RECRUITMENT_LEAD_DOCTYPE, lead_name)


@frappe.whitelist()
def get_intent_sign_url(name=None, territory=None, deposit_amount=None, end_date=None):
    if not is_franchisor_user():
        frappe.throw(_("You do not have permission to do this."), frappe.PermissionError)

    name = coalesce_str("name", name)
    doc = ensure_lead_access(name)

    if doc.lead_type != "Franchisee":
        frappe.throw(_("This lead isn't a Franchisee lead - the Intent to Proceed flow doesn't apply to it."))

    if doc.get("intent_signed_snapshot"):
        frappe.throw(_("This lead's Intent to Proceed has already been signed."))

    if not doc.get("intent_token"):
        territory = coalesce_str("territory", territory)
        end_date = coalesce_raw("end_date", end_date)

        if not territory:
            frappe.throw(_("Enter the Territory before generating the sign link."))
        if not deposit_amount:
            frappe.throw(_("Enter the Deposit Amount before generating the sign link."))
        if not end_date:
            frappe.throw(_("Enter the Agreement End Date before generating the sign link."))

        doc.intent_token = frappe.generate_hash(length=40)
        doc.intent_agreement_date = frappe.utils.today()
        doc.intent_territory = territory
        doc.intent_deposit_amount = coalesce_raw("deposit_amount", deposit_amount)
        doc.intent_end_date = end_date
        doc.save(ignore_permissions=True)
        frappe.db.commit()

    return {"url": get_url(f"/recruitment-intent?token={doc.intent_token}")}


def _intent_email_text(doc, intent_url):
    contact_name = doc.contact_name or "there"
    subject = "Please sign: Deposit and Intent to Proceed Agreement"
    message = (
        f"Hi {contact_name},\n\n"
        "Please read and sign the Deposit and Intent to Proceed Agreement below to keep things "
        "moving:\n\n"
        f"{intent_url}"
    )
    return subject, message


@frappe.whitelist()
def get_intent_email_defaults(name=None, territory=None, deposit_amount=None, end_date=None):
    name = coalesce_str("name", name)
    doc = ensure_lead_access(name)

    if not doc.contact_email:
        frappe.throw(_("This lead has no contact email address to send the agreement to."))

    intent_url = get_intent_sign_url(name=name, territory=territory, deposit_amount=deposit_amount, end_date=end_date)["url"]
    subject, message = _intent_email_text(doc, intent_url)

    return {"subject": subject, "message": message, "recipient": doc.contact_email, "url": intent_url}


@frappe.whitelist()
def send_intent_link(name=None, territory=None, deposit_amount=None, end_date=None, subject=None, message=None, cc=None, reply_to=None):
    name = coalesce_str("name", name)
    doc = ensure_lead_access(name)

    if not doc.contact_email:
        frappe.throw(_("This lead has no contact email address to send the agreement to."))

    intent_url = get_intent_sign_url(name=name, territory=territory, deposit_amount=deposit_amount, end_date=end_date)["url"]

    subject = (subject or "").strip()
    message = (message or "").strip()
    if not subject or not message:
        default_subject, default_message = _intent_email_text(doc, intent_url)
        subject = subject or default_subject
        message = message or default_message

    reply_to = (reply_to or "").strip() or frappe.session.user

    kwargs = {
        "recipients": [doc.contact_email],
        "subject": subject,
        "message": plain_text_to_email_html(message),
        "reply_to": reply_to,
    }

    cc_list = parse_email_list(cc)
    if cc_list:
        kwargs["cc"] = cc_list

    send_email(**kwargs)

    doc.intent_sent_at = frappe.utils.now_datetime()
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {"ok": 1, "url": intent_url, "sent_at": frappe.utils.format_datetime(doc.intent_sent_at, "dd-MM-yyyy HH:mm")}


@frappe.whitelist()
def get_signed_intent(name=None):
    name = coalesce_str("name", name)
    doc = ensure_lead_access(name)

    if not doc.get("intent_signed_snapshot"):
        frappe.throw(_("This Intent to Proceed hasn't been signed yet."))

    return {
        "signed_html": doc.get("intent_signed_snapshot"),
        "signed_at": frappe.utils.format_datetime(doc.get("intent_signed_at"), "dd-MM-yyyy HH:mm") if doc.get("intent_signed_at") else "",
        "signer_ip": doc.get("intent_signer_ip") or "",
        "signer_user_agent": doc.get("intent_signer_user_agent") or "",
    }


@frappe.whitelist(allow_guest=True)
def get_intent_preview(token=None):
    token = coalesce_str("token", token)
    doc = _get_lead_by_intent_token(token)

    if doc.get("intent_signed_snapshot"):
        return {"already_signed": True, "signed_html": doc.get("intent_signed_snapshot")}

    context = {
        "agreement_date": frappe.utils.formatdate(doc.get("intent_agreement_date"), "dd-MM-yyyy"),
        "territory": doc.get("intent_territory") or "",
        "deposit_amount": fmt_money(doc.get("intent_deposit_amount") or 0, currency="GBP"),
        "end_date": frappe.utils.formatdate(doc.get("intent_end_date"), "dd-MM-yyyy") if doc.get("intent_end_date") else "",
        "recipient_name": doc.get("contact_name") or NDA_BLANK_PLACEHOLDER,
        "recipient_address": NDA_BLANK_PLACEHOLDER,
        "franchisee_signature": NDA_BLANK_PLACEHOLDER,
        "franchisee_date": NDA_BLANK_PLACEHOLDER,
    }

    return {
        "already_signed": False,
        "preview_html": _render_nda_text(_intent_template_text(), context),
        "recipient_name": doc.get("contact_name") or "",
    }


@frappe.whitelist(allow_guest=True)
def sign_intent(token=None, recipient_name=None, recipient_address=None, signature_name=None):
    token = coalesce_str("token", token)
    recipient_name = coalesce_str("recipient_name", recipient_name)
    recipient_address = coalesce_str("recipient_address", recipient_address)
    signature_name = coalesce_str("signature_name", signature_name)

    doc = _get_lead_by_intent_token(token)

    if doc.get("intent_signed_snapshot"):
        frappe.throw(_("This Intent to Proceed has already been signed."))

    if not recipient_name:
        frappe.throw(_("Please enter your full name."))
    if not recipient_address:
        frappe.throw(_("Please enter your address."))
    if not signature_name:
        frappe.throw(_("Please type your name to sign."))

    today = frappe.utils.getdate(frappe.utils.today())

    context = {
        "agreement_date": frappe.utils.formatdate(doc.get("intent_agreement_date"), "dd-MM-yyyy"),
        "territory": doc.get("intent_territory") or "",
        "deposit_amount": fmt_money(doc.get("intent_deposit_amount") or 0, currency="GBP"),
        "end_date": frappe.utils.formatdate(doc.get("intent_end_date"), "dd-MM-yyyy") if doc.get("intent_end_date") else "",
        "recipient_name": recipient_name,
        "recipient_address": recipient_address,
        "franchisee_signature": signature_name,
        "franchisee_date": frappe.utils.formatdate(today, "dd-MM-yyyy"),
    }

    doc.intent_recipient_name = recipient_name
    doc.intent_recipient_address = recipient_address
    doc.intent_signature_name = signature_name
    doc.intent_signed_snapshot = _render_nda_text(_intent_template_text(), context)
    doc.intent_signed_at = frappe.utils.now_datetime()
    doc.intent_signer_ip = frappe.local.request_ip
    doc.intent_signer_user_agent = frappe.get_request_header("User-Agent") or ""
    doc.stage1_intent_deposit_dbs_done = 1
    doc.stage1_intent_deposit_dbs_date = today

    doc.save(ignore_permissions=True)
    frappe.db.commit()

    _notify_coach_of_lead_step(doc, "signed the Intent to Proceed agreement")

    return {"ok": True}


# -------------------------------------------------------------------
# Franchise Agreement - Franchisee only
# -------------------------------------------------------------------

CONTRACT_PRACTICE_DOCUMENT_TITLE = "Franchise Agreement"
CONTRACT_TERM_YEARS = 3


def _contract_template_text():
    name = frappe.db.get_value("Practice Document", {"document_title": CONTRACT_PRACTICE_DOCUMENT_TITLE}, "name")
    if not name:
        frappe.throw(_("The Franchise Agreement template hasn't been set up yet."))
    return frappe.db.get_value("Practice Document", name, "document_text") or ""


def _get_lead_by_contract_token(token):
    token = (token or "").strip()
    if not token:
        frappe.throw(_("This link is invalid."))
    lead_name = frappe.db.get_value(RECRUITMENT_LEAD_DOCTYPE, {"contract_token": token}, "name")
    if not lead_name:
        frappe.throw(_("This link is invalid."))
    return frappe.get_doc(RECRUITMENT_LEAD_DOCTYPE, lead_name)


def _contract_render_context(doc, franchisee_name, franchisee_address, franchisee_signature, franchisee_date):
    return {
        "agreement_date": frappe.utils.formatdate(doc.get("contract_agreement_date"), "dd-MM-yyyy"),
        "franchisee_name": franchisee_name,
        "franchisee_address": franchisee_address,
        "commencement_date": (
            frappe.utils.formatdate(doc.get("contract_commencement_date"), "dd-MM-yyyy")
            if doc.get("contract_commencement_date") else ""
        ),
        "expiry_date": (
            frappe.utils.formatdate(doc.get("contract_expiry_date"), "dd-MM-yyyy")
            if doc.get("contract_expiry_date") else ""
        ),
        "territory_description": doc.get("contract_territory_description") or "",
        "permitted_area": doc.get("contract_permitted_area") or "",
        "franchisee_signature": franchisee_signature,
        "franchisee_date": franchisee_date,
    }


@frappe.whitelist()
def get_contract_sign_url(name=None, commencement_date=None, territory_description=None, permitted_area=None):
    if not is_franchisor_user():
        frappe.throw(_("You do not have permission to do this."), frappe.PermissionError)

    name = coalesce_str("name", name)
    doc = ensure_lead_access(name)

    if doc.lead_type != "Franchisee":
        frappe.throw(_("This lead isn't a Franchisee lead - the Franchise Agreement flow doesn't apply to it."))

    if doc.get("contract_signed_snapshot"):
        frappe.throw(_("This lead's Franchise Agreement has already been signed."))

    if not doc.get("contract_token"):
        commencement_date = coalesce_raw("commencement_date", commencement_date)
        territory_description = coalesce_str("territory_description", territory_description)
        permitted_area = coalesce_str("permitted_area", permitted_area)

        if not commencement_date:
            frappe.throw(_("Enter the Commencement Date before generating the sign link."))
        if not territory_description:
            frappe.throw(_("Enter the Territory (postcode areas) before generating the sign link."))
        if not permitted_area:
            frappe.throw(_("Enter the Permitted Area before generating the sign link."))

        commencement_date = frappe.utils.getdate(commencement_date)

        doc.contract_token = frappe.generate_hash(length=40)
        doc.contract_agreement_date = frappe.utils.today()
        doc.contract_commencement_date = commencement_date
        doc.contract_expiry_date = frappe.utils.add_years(commencement_date, CONTRACT_TERM_YEARS)
        doc.contract_territory_description = territory_description
        doc.contract_permitted_area = permitted_area
        doc.save(ignore_permissions=True)
        frappe.db.commit()

    return {"url": get_url(f"/recruitment-contract?token={doc.contract_token}")}


def _contract_email_text(doc, contract_url):
    contact_name = doc.contact_name or "there"
    subject = "Please sign: Franchise Agreement"
    message = f"Hi {contact_name},\n\nPlease read and sign the Franchise Agreement below:\n\n{contract_url}"
    return subject, message


@frappe.whitelist()
def get_contract_email_defaults(name=None, commencement_date=None, territory_description=None, permitted_area=None):
    name = coalesce_str("name", name)
    doc = ensure_lead_access(name)

    if not doc.contact_email:
        frappe.throw(_("This lead has no contact email address to send the agreement to."))

    contract_url = get_contract_sign_url(
        name=name, commencement_date=commencement_date,
        territory_description=territory_description, permitted_area=permitted_area,
    )["url"]
    subject, message = _contract_email_text(doc, contract_url)

    return {"subject": subject, "message": message, "recipient": doc.contact_email, "url": contract_url}


@frappe.whitelist()
def send_contract_link(name=None, commencement_date=None, territory_description=None, permitted_area=None, subject=None, message=None, cc=None, reply_to=None):
    name = coalesce_str("name", name)
    doc = ensure_lead_access(name)

    if not doc.contact_email:
        frappe.throw(_("This lead has no contact email address to send the agreement to."))

    contract_url = get_contract_sign_url(
        name=name, commencement_date=commencement_date,
        territory_description=territory_description, permitted_area=permitted_area,
    )["url"]

    subject = (subject or "").strip()
    message = (message or "").strip()
    if not subject or not message:
        default_subject, default_message = _contract_email_text(doc, contract_url)
        subject = subject or default_subject
        message = message or default_message

    reply_to = (reply_to or "").strip() or frappe.session.user

    kwargs = {
        "recipients": [doc.contact_email],
        "subject": subject,
        "message": plain_text_to_email_html(message),
        "reply_to": reply_to,
    }

    cc_list = parse_email_list(cc)
    if cc_list:
        kwargs["cc"] = cc_list

    send_email(**kwargs)

    doc.contract_sent_at = frappe.utils.now_datetime()
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {"ok": 1, "url": contract_url, "sent_at": frappe.utils.format_datetime(doc.contract_sent_at, "dd-MM-yyyy HH:mm")}


@frappe.whitelist()
def get_signed_contract(name=None):
    name = coalesce_str("name", name)
    doc = ensure_lead_access(name)

    if not doc.get("contract_signed_snapshot"):
        frappe.throw(_("This Franchise Agreement hasn't been signed yet."))

    return {
        "signed_html": doc.get("contract_signed_snapshot"),
        "signed_at": frappe.utils.format_datetime(doc.get("contract_signed_at"), "dd-MM-yyyy HH:mm") if doc.get("contract_signed_at") else "",
        "signer_ip": doc.get("contract_signer_ip") or "",
        "signer_user_agent": doc.get("contract_signer_user_agent") or "",
    }


@frappe.whitelist(allow_guest=True)
def get_contract_preview(token=None):
    token = coalesce_str("token", token)
    doc = _get_lead_by_contract_token(token)

    if doc.get("contract_signed_snapshot"):
        return {"already_signed": True, "signed_html": doc.get("contract_signed_snapshot")}

    context = _contract_render_context(
        doc,
        franchisee_name=doc.get("contact_name") or NDA_BLANK_PLACEHOLDER,
        franchisee_address=NDA_BLANK_PLACEHOLDER,
        franchisee_signature=NDA_BLANK_PLACEHOLDER,
        franchisee_date=NDA_BLANK_PLACEHOLDER,
    )

    return {
        "already_signed": False,
        "preview_html": _render_nda_text(_contract_template_text(), context),
        "recipient_name": doc.get("contact_name") or "",
    }


@frappe.whitelist(allow_guest=True)
def sign_contract(token=None, recipient_name=None, recipient_address=None, signature_name=None):
    token = coalesce_str("token", token)
    recipient_name = coalesce_str("recipient_name", recipient_name)
    recipient_address = coalesce_str("recipient_address", recipient_address)
    signature_name = coalesce_str("signature_name", signature_name)

    doc = _get_lead_by_contract_token(token)

    if doc.get("contract_signed_snapshot"):
        frappe.throw(_("This Franchise Agreement has already been signed."))

    if not recipient_name:
        frappe.throw(_("Please enter your full name."))
    if not recipient_address:
        frappe.throw(_("Please enter your address."))
    if not signature_name:
        frappe.throw(_("Please type your name to sign."))

    today = frappe.utils.getdate(frappe.utils.today())

    context = _contract_render_context(
        doc,
        franchisee_name=recipient_name,
        franchisee_address=recipient_address,
        franchisee_signature=signature_name,
        franchisee_date=frappe.utils.formatdate(today, "dd-MM-yyyy"),
    )

    doc.contract_recipient_name = recipient_name
    doc.contract_recipient_address = recipient_address
    doc.contract_signature_name = signature_name
    doc.contract_signed_snapshot = _render_nda_text(_contract_template_text(), context)
    doc.contract_signed_at = frappe.utils.now_datetime()
    doc.contract_signer_ip = frappe.local.request_ip
    doc.contract_signer_user_agent = frappe.get_request_header("User-Agent") or ""
    doc.stage1_contract_sent_done = 1
    doc.stage1_contract_sent_date = today

    doc.save(ignore_permissions=True)
    frappe.db.commit()

    _notify_coach_of_lead_step(doc, "signed the Franchise Agreement")

    return {"ok": True}


# -------------------------------------------------------------------
# Safer Recruitment Checklist - shared by both lead types
# -------------------------------------------------------------------

SAFER_RECRUITMENT_CHECKLIST_ITEMS = [
    # (section, item_key, item_label, scope) - scope "both" applies to a
    # Franchisee and a Session Worker lead alike; "session_worker" only
    # ever applies to a Session Worker lead. Mirrors leads.py's own list
    # exactly - see that module for why some items were deliberately
    # left off (safeguarding induction, duplicate signature ticks, etc).
    ("Identity, right to work and overseas checks", "identity_verified", "Identity verified", "both"),
    ("Identity, right to work and overseas checks", "right_to_work_verified", "UK right to work verified", "both"),
    ("Identity, right to work and overseas checks", "address_history_confirmed", "Address history confirmed", "both"),
    ("Identity, right to work and overseas checks", "overseas_police_clearance_reviewed", "Overseas police clearance reviewed (if applicable)", "both"),
    ("Identity, right to work and overseas checks", "working_with_children_check_reviewed", "Working With Children Check reviewed (if applicable)", "both"),
    ("UK DBS and barred-list checks", "role_eligibility_assessed", "Role eligibility assessed", "both"),
    ("UK DBS and barred-list checks", "enhanced_dbs_application_submitted", "Enhanced DBS application submitted", "both"),
    ("UK DBS and barred-list checks", "barred_list_eligibility_confirmed", "Children's Barred List eligibility confirmed", "both"),
    ("UK DBS and barred-list checks", "original_dbs_certificate_reviewed", "Original DBS certificate reviewed", "both"),
    ("UK DBS and barred-list checks", "dbs_risk_assessment_completed", "DBS risk assessment completed", "both"),
    ("UK DBS and barred-list checks", "dbs_update_service_discussed", "DBS Update Service discussed", "both"),
    ("Qualifications, work history and references", "work_history_reviewed", "Application / work history reviewed", "both"),
    ("Qualifications, work history and references", "qualifications_verified", "Qualifications and training verified", "both"),
    ("Qualifications, work history and references", "reference1_obtained", "Reference 1 obtained and verified", "both"),
    ("Qualifications, work history and references", "reference2_obtained", "Reference 2 obtained and verified", "both"),
    ("Qualifications, work history and references", "safer_recruitment_interview_completed", "Safer-recruitment interview completed", "both"),
    ("Contracting, insurance and readiness", "employment_status_confirmed", "Employment-status / tax position confirmed", "both"),
    ("Contracting, insurance and readiness", "insurance_confirmed", "Insurance confirmed", "both"),
    ("Contracting, insurance and readiness", "supervision_arrangements_agreed", "Supervision arrangements agreed", "session_worker"),
    ("Contracting, insurance and readiness", "role_boundaries_and_escalation_agreed", "Role boundaries and escalation agreed", "session_worker"),
]


def _applicable_safer_recruitment_items(doc):
    is_sw = doc.lead_type == "Session Worker"
    return [
        (section, item_key, item_label)
        for section, item_key, item_label, scope in SAFER_RECRUITMENT_CHECKLIST_ITEMS
        if scope == "both" or (scope == "session_worker" and is_sw)
    ]


def _ensure_safer_recruitment_checklist_seeded(doc):
    existing_keys = {row.item_key for row in (doc.get("safer_recruitment_checklist") or [])}
    changed = False

    for section, item_key, item_label in _applicable_safer_recruitment_items(doc):
        if item_key in existing_keys:
            continue

        doc.append("safer_recruitment_checklist", {
            "section": section,
            "item_key": item_key,
            "item_label": item_label,
            "status": "Pending",
        })
        changed = True

    if changed:
        doc.save(ignore_permissions=True)
        frappe.db.commit()


@frappe.whitelist()
def get_safer_recruitment_checklist(name=None):
    if not is_franchisor_user():
        frappe.throw(_("You do not have permission to do this."), frappe.PermissionError)

    name = coalesce_str("name", name)
    doc = ensure_lead_access(name)

    _ensure_safer_recruitment_checklist_seeded(doc)
    doc.reload()

    applicable_keys = {item_key for _section, item_key, _label in _applicable_safer_recruitment_items(doc)}

    rows = [
        {
            "item_key": row.item_key,
            "section": row.section,
            "item_label": row.item_label,
            "status": row.status or "Pending",
            "checked_date": row.checked_date or "",
            "checked_by": row.checked_by or "",
            "notes": row.notes or "",
        }
        for row in (doc.get("safer_recruitment_checklist") or [])
        if row.item_key in applicable_keys
    ]

    return {"rows": rows, "outstanding_actions": doc.get("safer_recruitment_outstanding_actions") or ""}


@frappe.whitelist()
def update_safer_recruitment_checklist_item(name=None, item_key=None, status=None, checked_date=None, notes=None):
    if not is_franchisor_user():
        frappe.throw(_("You do not have permission to do this."), frappe.PermissionError)

    name = coalesce_str("name", name)
    item_key = coalesce_str("item_key", item_key)
    doc = ensure_lead_access(name)

    _ensure_safer_recruitment_checklist_seeded(doc)
    doc.reload()

    row = next((r for r in (doc.get("safer_recruitment_checklist") or []) if r.item_key == item_key), None)
    if not row:
        frappe.throw(_("Unknown checklist item."))

    status = coalesce_str("status", status)
    if status:
        row.status = status
    if checked_date is not None:
        row.checked_date = coalesce_raw("checked_date", checked_date) or None
    if notes is not None:
        row.notes = coalesce_str("notes", notes)

    if status and status != "Pending" and not row.checked_by:
        row.checked_by = frappe.utils.get_fullname(frappe.session.user)
    if not row.checked_date and status and status != "Pending":
        row.checked_date = frappe.utils.today()

    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {"ok": True}


@frappe.whitelist()
def update_safer_recruitment_outstanding_actions(name=None, outstanding_actions=None):
    if not is_franchisor_user():
        frappe.throw(_("You do not have permission to do this."), frappe.PermissionError)

    name = coalesce_str("name", name)
    doc = ensure_lead_access(name)

    doc.safer_recruitment_outstanding_actions = coalesce_str("outstanding_actions", outstanding_actions)
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {"ok": True}


# -------------------------------------------------------------------
# Sessional Worker Fees and Expectations Guide - Session Worker only.
# Second party is the lead's own sponsoring Coach, not Ashley - same
# shape as leads.py's own version.
# -------------------------------------------------------------------

FEES_GUIDE_PRACTICE_DOCUMENT_TITLE = "Sessional Worker Fees and Expectations Guide"


def _fees_guide_template_text():
    name = frappe.db.get_value("Practice Document", {"document_title": FEES_GUIDE_PRACTICE_DOCUMENT_TITLE}, "name")
    if not name:
        frappe.throw(_("The Fees and Expectations Guide template hasn't been set up yet."))
    return frappe.db.get_value("Practice Document", name, "document_text") or ""


def _get_lead_by_fees_guide_token(token):
    token = (token or "").strip()
    if not token:
        frappe.throw(_("This link is invalid."))
    lead_name = frappe.db.get_value(RECRUITMENT_LEAD_DOCTYPE, {"fees_guide_token": token}, "name")
    if not lead_name:
        frappe.throw(_("This link is invalid."))
    return frappe.get_doc(RECRUITMENT_LEAD_DOCTYPE, lead_name)


def _fees_guide_context(doc, worker_name="", worker_address="", worker_signature=""):
    today = frappe.utils.getdate(frappe.utils.today())
    return {
        "franchisee_name": get_coach_label(doc.get("coach")) or NDA_BLANK_PLACEHOLDER,
        "effective_date": frappe.utils.formatdate(doc.get("fees_guide_agreement_date"), "dd-MM-yyyy"),
        "rate_1to1": fmt_money(doc.get("fees_guide_rate_1to1") or 0, currency="GBP"),
        "rate_group": fmt_money(doc.get("fees_guide_rate_group") or 0, currency="GBP"),
        "rate_workshop": fmt_money(doc.get("fees_guide_rate_workshop") or 0, currency="GBP"),
        "invoicing_frequency": doc.get("fees_guide_invoicing_frequency") or NDA_BLANK_PLACEHOLDER,
        "dbs_number": doc.get("franchisee_intake_dbs_number") or NDA_BLANK_PLACEHOLDER,
        "dbs_date_received": frappe.utils.formatdate(doc.get("franchisee_intake_dbs_date_received"), "dd-MM-yyyy") if doc.get("franchisee_intake_dbs_date_received") else NDA_BLANK_PLACEHOLDER,
        "public_liability_insurer": doc.get("franchisee_intake_public_liability_insurer") or NDA_BLANK_PLACEHOLDER,
        "indemnity_insurer": doc.get("franchisee_intake_indemnity_insurer") or NDA_BLANK_PLACEHOLDER,
        "worker_name": worker_name or doc.get("contact_name") or NDA_BLANK_PLACEHOLDER,
        "worker_signature": worker_signature or NDA_BLANK_PLACEHOLDER,
        "worker_date": frappe.utils.formatdate(today, "dd-MM-yyyy") if worker_signature else NDA_BLANK_PLACEHOLDER,
        "coach_date": frappe.utils.formatdate(doc.get("fees_guide_agreement_date"), "dd-MM-yyyy"),
    }


@frappe.whitelist()
def get_fees_guide_sign_url(name=None, rate_1to1=None, rate_group=None, rate_workshop=None, invoicing_frequency=None, effective_date=None):
    if not is_franchisor_user():
        frappe.throw(_("You do not have permission to do this."), frappe.PermissionError)

    name = coalesce_str("name", name)
    doc = ensure_lead_access(name)

    if doc.lead_type != "Session Worker":
        frappe.throw(_("This lead isn't a Session Worker - the Fees and Expectations Guide doesn't apply to it."))

    if doc.get("fees_guide_signed_snapshot"):
        frappe.throw(_("This lead's Fees and Expectations Guide has already been signed."))

    if not doc.get("fees_guide_token"):
        effective_date = coalesce_raw("effective_date", effective_date)
        invoicing_frequency = coalesce_str("invoicing_frequency", invoicing_frequency)

        if not rate_1to1 or not rate_group or not rate_workshop:
            frappe.throw(_("Enter the session fee rates before generating the sign link."))
        if not invoicing_frequency:
            frappe.throw(_("Choose an invoicing frequency before generating the sign link."))
        if not effective_date:
            frappe.throw(_("Enter the Effective From date before generating the sign link."))
        if not doc.get("coach"):
            frappe.throw(_("This lead has no coach assigned to sponsor this worker."))

        doc.fees_guide_token = frappe.generate_hash(length=40)
        doc.fees_guide_agreement_date = effective_date
        doc.fees_guide_rate_1to1 = coalesce_raw("rate_1to1", rate_1to1)
        doc.fees_guide_rate_group = coalesce_raw("rate_group", rate_group)
        doc.fees_guide_rate_workshop = coalesce_raw("rate_workshop", rate_workshop)
        doc.fees_guide_invoicing_frequency = invoicing_frequency
        doc.save(ignore_permissions=True)
        frappe.db.commit()

    return {"url": get_url(f"/recruitment-fees-guide?token={doc.fees_guide_token}")}


def _fees_guide_email_text(doc, fees_guide_url):
    contact_name = doc.contact_name or "there"
    coach_display = get_coach_label(doc.get("coach")) or "your Franchisee"
    subject = "Please sign: Fees and Expectations Guide"
    message = (
        f"Hi {contact_name},\n\n"
        f"Please read and sign the Fees and Expectations Guide below, agreed with {coach_display}, "
        "to finish setting you up as a session worker:\n\n"
        f"{fees_guide_url}"
    )
    return subject, message


@frappe.whitelist()
def get_fees_guide_email_defaults(name=None, rate_1to1=None, rate_group=None, rate_workshop=None, invoicing_frequency=None, effective_date=None):
    name = coalesce_str("name", name)
    doc = ensure_lead_access(name)

    if not doc.contact_email:
        frappe.throw(_("This lead has no contact email address to send the guide to."))

    fees_guide_url = get_fees_guide_sign_url(
        name=name, rate_1to1=rate_1to1, rate_group=rate_group, rate_workshop=rate_workshop,
        invoicing_frequency=invoicing_frequency, effective_date=effective_date,
    )["url"]
    subject, message = _fees_guide_email_text(doc, fees_guide_url)

    return {"subject": subject, "message": message, "recipient": doc.contact_email, "url": fees_guide_url}


@frappe.whitelist()
def send_fees_guide_link(name=None, rate_1to1=None, rate_group=None, rate_workshop=None, invoicing_frequency=None,
                          effective_date=None, subject=None, message=None, cc=None, reply_to=None):
    name = coalesce_str("name", name)
    doc = ensure_lead_access(name)

    if not doc.contact_email:
        frappe.throw(_("This lead has no contact email address to send the guide to."))

    fees_guide_url = get_fees_guide_sign_url(
        name=name, rate_1to1=rate_1to1, rate_group=rate_group, rate_workshop=rate_workshop,
        invoicing_frequency=invoicing_frequency, effective_date=effective_date,
    )["url"]

    subject = (subject or "").strip()
    message = (message or "").strip()
    if not subject or not message:
        default_subject, default_message = _fees_guide_email_text(doc, fees_guide_url)
        subject = subject or default_subject
        message = message or default_message

    reply_to = (reply_to or "").strip() or frappe.session.user

    kwargs = {
        "recipients": [doc.contact_email],
        "subject": subject,
        "message": plain_text_to_email_html(message),
        "reply_to": reply_to,
    }

    cc_list = parse_email_list(cc)
    if cc_list:
        kwargs["cc"] = cc_list

    send_email(**kwargs)

    doc.fees_guide_sent_at = frappe.utils.now_datetime()
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {"ok": 1, "url": fees_guide_url, "sent_at": frappe.utils.format_datetime(doc.fees_guide_sent_at, "dd-MM-yyyy HH:mm")}


@frappe.whitelist()
def get_signed_fees_guide(name=None):
    name = coalesce_str("name", name)
    doc = ensure_lead_access(name)

    if not doc.get("fees_guide_signed_snapshot"):
        frappe.throw(_("This Fees and Expectations Guide hasn't been signed yet."))

    return {
        "signed_html": doc.get("fees_guide_signed_snapshot"),
        "signed_at": frappe.utils.format_datetime(doc.get("fees_guide_signed_at"), "dd-MM-yyyy HH:mm") if doc.get("fees_guide_signed_at") else "",
        "signer_ip": doc.get("fees_guide_signer_ip") or "",
        "signer_user_agent": doc.get("fees_guide_signer_user_agent") or "",
    }


@frappe.whitelist(allow_guest=True)
def get_fees_guide_preview(token=None):
    token = coalesce_str("token", token)
    doc = _get_lead_by_fees_guide_token(token)

    if doc.get("fees_guide_signed_snapshot"):
        return {"already_signed": True, "signed_html": doc.get("fees_guide_signed_snapshot")}

    return {
        "already_signed": False,
        "preview_html": _render_nda_text(_fees_guide_template_text(), _fees_guide_context(doc)),
        "recipient_name": doc.get("contact_name") or "",
    }


@frappe.whitelist(allow_guest=True)
def sign_fees_guide(token=None, recipient_name=None, signature_name=None):
    token = coalesce_str("token", token)
    recipient_name = coalesce_str("recipient_name", recipient_name)
    signature_name = coalesce_str("signature_name", signature_name)

    doc = _get_lead_by_fees_guide_token(token)

    if doc.get("fees_guide_signed_snapshot"):
        frappe.throw(_("This Fees and Expectations Guide has already been signed."))

    if not recipient_name:
        frappe.throw(_("Please enter your full name."))
    if not signature_name:
        frappe.throw(_("Please type your name to sign."))

    context = _fees_guide_context(doc, worker_name=recipient_name, worker_signature=signature_name)

    doc.fees_guide_recipient_name = recipient_name
    doc.fees_guide_signature_name = signature_name
    doc.fees_guide_signed_snapshot = _render_nda_text(_fees_guide_template_text(), context)
    doc.fees_guide_signed_at = frappe.utils.now_datetime()
    doc.fees_guide_signer_ip = frappe.local.request_ip
    doc.fees_guide_signer_user_agent = frappe.get_request_header("User-Agent") or ""
    doc.fees_guide_done = 1
    doc.fees_guide_date = frappe.utils.getdate(frappe.utils.today())

    doc.save(ignore_permissions=True)
    frappe.db.commit()

    _notify_coach_of_lead_step(doc, "signed the Fees and Expectations Guide")

    return {"ok": True}


@frappe.whitelist()
def get_session_worker_setup_url(name=None):
    """Franchisor-only: a deep link to a pre-filled New Session Worker
    form in Desk - mirrors leads.py's own get_session_worker_setup_url."""
    if not is_franchisor_user():
        frappe.throw(_("You do not have permission to do this."), frappe.PermissionError)

    name = coalesce_str("name", name)
    doc = ensure_lead_access(name)

    if doc.lead_type != "Session Worker":
        frappe.throw(_("This lead isn't a Session Worker."))

    full_name = (
        f"{doc.get('franchisee_intake_first_name') or ''} {doc.get('franchisee_intake_last_name') or ''}".strip()
        or doc.contact_name or ""
    )

    params = {
        "sw_name": full_name,
        "sw_email": doc.contact_email or "",
        "phone": doc.get("franchisee_intake_phone") or doc.contact_mobile or "",
    }
    query = "&".join(f"{key}={quote(str(value))}" for key, value in params.items() if value)

    return {"url": get_url(f"/app/session-worker/new?{query}" if query else "/app/session-worker/new")}


@frappe.whitelist()
def set_session_worker_link(name=None, session_worker=None):
    if not is_franchisor_user():
        frappe.throw(_("You do not have permission to do this."), frappe.PermissionError)

    name = coalesce_str("name", name)
    session_worker = coalesce_str("session_worker", session_worker)
    doc = ensure_lead_access(name)

    if doc.lead_type != "Session Worker":
        frappe.throw(_("This lead isn't a Session Worker."))

    if session_worker and not frappe.db.exists("Session Worker", session_worker):
        frappe.throw(_("That Session Worker record doesn't exist."))

    doc.converted_session_worker = session_worker or None
    doc.sw_setup_done = 1 if session_worker else 0
    doc.sw_setup_date = frappe.utils.today() if session_worker else None
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {"ok": True, "converted_session_worker": doc.converted_session_worker}
