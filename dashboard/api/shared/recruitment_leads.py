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

from werkzeug.utils import secure_filename

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

    rows = frappe.get_all(
        RECRUITMENT_LEAD_DOCTYPE,
        fields=LEAD_LIST_FIELDS,
        filters=filters,
        order_by="modified desc",
        limit_page_length=2000,
        ignore_permissions=True,
    )

    for row in rows:
        row["coach_label"] = get_coach_label(row.get("coach")) if row.get("coach") else ""

    return rows


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
        row["contract_franchisor_signature_name"] = doc.get("contract_franchisor_signature_name") or ""
        row["contract_franchisor_signed_at"] = (
            frappe.utils.format_datetime(doc.get("contract_franchisor_signed_at"), "dd-MM-yyyy HH:mm")
            if doc.get("contract_franchisor_signed_at") else ""
        )
        row["contract_territory_map"] = doc.get("contract_territory_map") or ""
        row["contract_trademark_certificate"] = doc.get("contract_trademark_certificate") or ""

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
        # A key ending "_html" (e.g. territory_map_html) is already a
        # safe, pre-built HTML fragment (see _contract_image_html) -
        # escaping it again here would show the raw tags as text instead
        # of rendering the image.
        if key.endswith("_html"):
            text = text.replace("{{ " + key + " }}", value or "")
        else:
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


def _contract_image_html(file_url, missing_note):
    if not file_url:
        return f'<p class="dashboard-help">{missing_note}</p>'
    return f'<p><img src="{frappe.utils.escape_html(file_url)}" style="max-width:100%; border:1px solid #D9E6E6; border-radius:8px;"></p>'


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
        "territory_map_html": _contract_image_html(
            doc.get("contract_territory_map"),
            "The postcode map for this franchisee's Territory hasn't been uploaded yet - add it to this lead's Territory Map Image field.",
        ),
        "trademark_certificate_html": _contract_image_html(
            doc.get("contract_trademark_certificate"),
            "Trade Mark certificate image not yet uploaded.",
        ),
        "franchisor_signature": doc.get("contract_franchisor_signature_name") or NDA_BLANK_PLACEHOLDER,
        "franchisee_signature": franchisee_signature,
        "franchisee_date": franchisee_date,
    }


@frappe.whitelist()
def get_contract_sign_url(name=None, commencement_date=None, territory_description=None, permitted_area=None, franchisor_signature_name=None):
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
        franchisor_signature_name = coalesce_str("franchisor_signature_name", franchisor_signature_name)

        if not commencement_date:
            frappe.throw(_("Enter the Commencement Date before generating the sign link."))
        if not territory_description:
            frappe.throw(_("Enter the Territory (postcode areas) before generating the sign link."))
        if not permitted_area:
            frappe.throw(_("Enter the Permitted Area before generating the sign link."))
        if not franchisor_signature_name:
            frappe.throw(_("Type your name to sign this agreement before it can be sent to the franchisee."))

        commencement_date = frappe.utils.getdate(commencement_date)

        doc.contract_token = frappe.generate_hash(length=40)
        doc.contract_agreement_date = frappe.utils.today()
        doc.contract_commencement_date = commencement_date
        doc.contract_expiry_date = frappe.utils.add_years(commencement_date, CONTRACT_TERM_YEARS)
        doc.contract_territory_description = territory_description
        doc.contract_permitted_area = permitted_area
        doc.contract_franchisor_signature_name = franchisor_signature_name
        doc.contract_franchisor_signed_at = frappe.utils.now_datetime()
        doc.contract_franchisor_signer_ip = frappe.local.request_ip
        doc.contract_franchisor_signer_user_agent = frappe.get_request_header("User-Agent") or ""
        doc.save(ignore_permissions=True)
        frappe.db.commit()

    return {"url": get_url(f"/recruitment-contract?token={doc.contract_token}")}


def _contract_email_text(doc, contract_url):
    contact_name = doc.contact_name or "there"
    subject = "Please sign: Franchise Agreement"
    message = f"Hi {contact_name},\n\nPlease read and sign the Franchise Agreement below:\n\n{contract_url}"
    return subject, message


@frappe.whitelist()
def get_contract_email_defaults(name=None, commencement_date=None, territory_description=None, permitted_area=None, franchisor_signature_name=None):
    name = coalesce_str("name", name)
    doc = ensure_lead_access(name)

    if not doc.contact_email:
        frappe.throw(_("This lead has no contact email address to send the agreement to."))

    contract_url = get_contract_sign_url(
        name=name, commencement_date=commencement_date,
        territory_description=territory_description, permitted_area=permitted_area,
        franchisor_signature_name=franchisor_signature_name,
    )["url"]
    subject, message = _contract_email_text(doc, contract_url)

    return {"subject": subject, "message": message, "recipient": doc.contact_email, "url": contract_url}


@frappe.whitelist()
def send_contract_link(name=None, commencement_date=None, territory_description=None, permitted_area=None, franchisor_signature_name=None, subject=None, message=None, cc=None, reply_to=None):
    name = coalesce_str("name", name)
    doc = ensure_lead_access(name)

    if not doc.contact_email:
        frappe.throw(_("This lead has no contact email address to send the agreement to."))

    contract_url = get_contract_sign_url(
        name=name, commencement_date=commencement_date,
        territory_description=territory_description, permitted_area=permitted_area,
        franchisor_signature_name=franchisor_signature_name,
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
        "recipient_address": doc.get("location_address") or "",
    }


@frappe.whitelist(allow_guest=True)
def download_contract_pdf(token=None):
    token = coalesce_str("token", token)
    doc = _get_lead_by_contract_token(token)

    if not doc.get("contract_signed_snapshot"):
        frappe.throw(_("This Franchise Agreement hasn't been signed yet."))

    from frappe.utils.pdf import get_pdf

    pdf_content = get_pdf(doc.get("contract_signed_snapshot"))

    frappe.local.response.filename = f"Franchise Agreement - {doc.contact_name or doc.name}.pdf"
    frappe.local.response.filecontent = pdf_content
    frappe.local.response.type = "download"


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


# -------------------------------------------------------------------
# Intake + DBS/Insurance form - shared by both lead types, the step
# after NDA, before conversion. Not a signature flow - personal
# details plus two file uploads (required DBS certificate, optional
# additional document e.g. insurance).
# -------------------------------------------------------------------

FRANCHISEE_INTAKE_FILE_FIELDS = {
    "dbs_certificate": "franchisee_intake_dbs_certificate",
    "additional_document": "franchisee_intake_additional_document",
}


def _get_lead_by_franchisee_intake_token(token):
    token = (token or "").strip()
    if not token:
        frappe.throw(_("This link is invalid."))
    lead_name = frappe.db.get_value(RECRUITMENT_LEAD_DOCTYPE, {"franchisee_intake_token": token}, "name")
    if not lead_name:
        frappe.throw(_("This link is invalid."))
    return frappe.get_doc(RECRUITMENT_LEAD_DOCTYPE, lead_name)


@frappe.whitelist()
def get_franchisee_intake_url(name=None):
    if not is_franchisor_user():
        frappe.throw(_("You do not have permission to do this."), frappe.PermissionError)

    name = coalesce_str("name", name)
    doc = ensure_lead_access(name)

    if not doc.get("franchisee_intake_token"):
        doc.franchisee_intake_token = frappe.generate_hash(length=40)
        doc.save(ignore_permissions=True)
        frappe.db.commit()

    return {"url": get_url(f"/recruitment-intake?token={doc.franchisee_intake_token}")}


def _franchisee_intake_email_text(doc, intake_url):
    contact_name = doc.contact_name or "there"

    if doc.lead_type == "Session Worker":
        subject = "Your Resilient Kid session worker intake form"
        message = (
            f"Hi {contact_name},\n\n"
            "Thanks for your interest in joining The Resilient Kid as a session worker. Please "
            "complete the short form below with your details and DBS certificate so we can "
            "keep things moving:\n\n"
            f"{intake_url}"
        )
        return subject, message

    subject = "Your Resilient franchisee intake form"
    message = (
        f"Hi {contact_name},\n\n"
        "Thanks for your continued interest in becoming a Resilient franchisee. Please "
        "complete the short form below with your details and DBS certificate so we can "
        "keep things moving:\n\n"
        f"{intake_url}"
    )
    return subject, message


@frappe.whitelist()
def get_franchisee_intake_email_defaults(name=None):
    if not is_franchisor_user():
        frappe.throw(_("You do not have permission to do this."), frappe.PermissionError)

    name = coalesce_str("name", name)
    doc = ensure_lead_access(name)

    if not doc.contact_email:
        frappe.throw(_("This lead has no contact email address to send the form to."))

    intake_url = get_franchisee_intake_url(name=name)["url"]
    subject, message = _franchisee_intake_email_text(doc, intake_url)

    return {"subject": subject, "message": message, "recipient": doc.contact_email, "url": intake_url}


@frappe.whitelist()
def send_franchisee_intake_form(name=None, subject=None, message=None, cc=None, reply_to=None):
    if not is_franchisor_user():
        frappe.throw(_("You do not have permission to do this."), frappe.PermissionError)

    name = coalesce_str("name", name)
    doc = ensure_lead_access(name)

    if not doc.contact_email:
        frappe.throw(_("This lead has no contact email address to send the form to."))

    if not doc.get("franchisee_intake_token"):
        doc.franchisee_intake_token = frappe.generate_hash(length=40)
        doc.save(ignore_permissions=True)
        frappe.db.commit()

    intake_url = get_url(f"/recruitment-intake?token={doc.franchisee_intake_token}")

    subject = (subject or "").strip()
    message = (message or "").strip()
    if not subject or not message:
        default_subject, default_message = _franchisee_intake_email_text(doc, intake_url)
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

    doc.franchisee_intake_sent_at = frappe.utils.now_datetime()
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {
        "ok": 1,
        "url": intake_url,
        "sent_at": frappe.utils.format_datetime(doc.franchisee_intake_sent_at, "dd-MM-yyyy HH:mm"),
    }


@frappe.whitelist(allow_guest=True)
def get_franchisee_intake_status(token=None):
    token = coalesce_str("token", token)
    doc = _get_lead_by_franchisee_intake_token(token)

    return {
        "submitted": bool(doc.get("franchisee_intake_submitted")),
        "contact_name": doc.get("contact_name") or "",
        "is_session_worker": doc.lead_type == "Session Worker",
        "answers": {
            "first_name": doc.get("franchisee_intake_first_name") or "",
            "last_name": doc.get("franchisee_intake_last_name") or "",
            "phone": doc.get("franchisee_intake_phone") or "",
            "gender": doc.get("franchisee_intake_gender") or "",
            "dob": doc.get("franchisee_intake_dob") or "",
            "dbs_number": doc.get("franchisee_intake_dbs_number") or "",
            "dbs_date_received": doc.get("franchisee_intake_dbs_date_received") or "",
            "dbs_expiry_date": doc.get("franchisee_intake_dbs_expiry_date") or "",
            "dbs_certificate": doc.get("franchisee_intake_dbs_certificate") or "",
            "additional_document": doc.get("franchisee_intake_additional_document") or "",
            "qualifications": doc.get("franchisee_intake_qualifications") or "",
            "work_locations": doc.get("franchisee_intake_work_locations") or "",
            "public_liability_insurer": doc.get("franchisee_intake_public_liability_insurer") or "",
            "indemnity_insurer": doc.get("franchisee_intake_indemnity_insurer") or "",
            "insurance_renewal_date": doc.get("franchisee_intake_insurance_renewal_date") or "",
            "id_document_type": doc.get("franchisee_intake_id_document_type") or "",
            "right_to_work_status": doc.get("franchisee_intake_right_to_work_status") or "",
            "right_to_work_expiry": doc.get("franchisee_intake_right_to_work_expiry") or "",
            "address_history": doc.get("franchisee_intake_address_history") or "",
            "overseas_checks": doc.get("franchisee_intake_overseas_checks") or "",
            "work_history": doc.get("franchisee_intake_work_history") or "",
            "reference1_details": doc.get("franchisee_intake_reference1_details") or "",
            "reference2_details": doc.get("franchisee_intake_reference2_details") or "",
        },
    }


@frappe.whitelist()
def reopen_franchisee_intake(name=None):
    if not is_franchisor_user():
        frappe.throw(_("You do not have permission to do this."), frappe.PermissionError)

    name = coalesce_str("name", name)
    doc = ensure_lead_access(name)

    if not doc.get("franchisee_intake_submitted"):
        frappe.throw(_("This intake form hasn't been submitted yet."))

    if doc.status == "Converted" and doc.get("converted_client"):
        frappe.throw(_("This lead has already been converted to a Client - reopening the intake form now wouldn't reach them anymore."))

    if doc.get("converted_session_worker"):
        frappe.throw(_("This lead has already been set up as a Session Worker - reopening the intake form now wouldn't reach them anymore."))

    doc.franchisee_intake_submitted = 0
    doc.franchisee_intake_submitted_at = None
    doc.stage1_agreement_invoice_done = 0
    doc.stage1_agreement_invoice_date = None
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {"ok": True}


@frappe.whitelist(allow_guest=True)
def upload_franchisee_intake_file(token=None, field=None):
    token = coalesce_str("token", token)
    field = coalesce_str("field", field)

    doc = _get_lead_by_franchisee_intake_token(token)

    if doc.get("franchisee_intake_submitted"):
        frappe.throw(_("This intake form has already been submitted."))

    fieldname = FRANCHISEE_INTAKE_FILE_FIELDS.get(field)
    if not fieldname:
        frappe.throw(_("Invalid file field."))

    uploaded_file = frappe.request.files.get("file") if getattr(frappe, "request", None) else None
    if not uploaded_file:
        frappe.throw(_("No file was uploaded."))

    file_doc = frappe.get_doc({
        "doctype": "File",
        "file_name": secure_filename(uploaded_file.filename or field),
        "attached_to_doctype": RECRUITMENT_LEAD_DOCTYPE,
        "attached_to_name": doc.name,
        "attached_to_field": fieldname,
        "is_private": 1,
        "content": uploaded_file.stream.read(),
    })
    file_doc.insert(ignore_permissions=True)

    frappe.db.set_value(RECRUITMENT_LEAD_DOCTYPE, doc.name, fieldname, file_doc.file_url)
    frappe.db.commit()

    return {"url": file_doc.file_url}


@frappe.whitelist(allow_guest=True)
def submit_franchisee_intake(token=None, first_name=None, last_name=None, phone=None, gender=None,
                              dob=None, dbs_number=None, dbs_date_received=None, dbs_expiry_date=None,
                              qualifications=None, work_locations=None, public_liability_insurer=None,
                              indemnity_insurer=None, insurance_renewal_date=None, id_document_type=None,
                              right_to_work_status=None, right_to_work_expiry=None, address_history=None,
                              overseas_checks=None, work_history=None, reference1_details=None,
                              reference2_details=None):
    token = coalesce_str("token", token)
    doc = _get_lead_by_franchisee_intake_token(token)

    if doc.get("franchisee_intake_submitted"):
        frappe.throw(_("This intake form has already been submitted."))

    first_name = coalesce_str("first_name", first_name)
    last_name = coalesce_str("last_name", last_name)
    phone = coalesce_str("phone", phone)
    gender = coalesce_str("gender", gender)
    dbs_number = coalesce_str("dbs_number", dbs_number)

    if not first_name or not last_name:
        frappe.throw(_("Please enter your first and last name."))
    if not phone:
        frappe.throw(_("Please enter a phone number."))
    if not doc.get("franchisee_intake_dbs_certificate"):
        frappe.throw(_("Please upload your DBS certificate before submitting."))

    doc.franchisee_intake_first_name = first_name
    doc.franchisee_intake_last_name = last_name
    doc.franchisee_intake_phone = phone
    doc.franchisee_intake_gender = gender
    doc.franchisee_intake_dob = coalesce_raw("dob", dob) or None
    doc.franchisee_intake_dbs_number = dbs_number
    doc.franchisee_intake_dbs_date_received = coalesce_raw("dbs_date_received", dbs_date_received) or None
    doc.franchisee_intake_dbs_expiry_date = coalesce_raw("dbs_expiry_date", dbs_expiry_date) or None

    doc.franchisee_intake_qualifications = coalesce_str("qualifications", qualifications)
    doc.franchisee_intake_work_locations = coalesce_str("work_locations", work_locations)
    doc.franchisee_intake_public_liability_insurer = coalesce_str("public_liability_insurer", public_liability_insurer)
    doc.franchisee_intake_indemnity_insurer = coalesce_str("indemnity_insurer", indemnity_insurer)
    doc.franchisee_intake_insurance_renewal_date = coalesce_raw("insurance_renewal_date", insurance_renewal_date) or None
    doc.franchisee_intake_id_document_type = coalesce_str("id_document_type", id_document_type)
    doc.franchisee_intake_right_to_work_status = coalesce_str("right_to_work_status", right_to_work_status)
    doc.franchisee_intake_right_to_work_expiry = coalesce_raw("right_to_work_expiry", right_to_work_expiry) or None
    doc.franchisee_intake_address_history = coalesce_str("address_history", address_history)
    doc.franchisee_intake_overseas_checks = coalesce_str("overseas_checks", overseas_checks)
    doc.franchisee_intake_work_history = coalesce_str("work_history", work_history)
    doc.franchisee_intake_reference1_details = coalesce_str("reference1_details", reference1_details)
    doc.franchisee_intake_reference2_details = coalesce_str("reference2_details", reference2_details)

    doc.franchisee_intake_submitted = 1
    doc.franchisee_intake_submitted_at = frappe.utils.now_datetime()
    doc.stage1_agreement_invoice_done = 1
    doc.stage1_agreement_invoice_date = frappe.utils.today()

    doc.save(ignore_permissions=True)
    frappe.db.commit()

    _notify_coach_of_lead_step(doc, "submitted their Intake/DBS form")

    return {"ok": True}


# -------------------------------------------------------------------
# Convert to Client - Franchisee leads only (a Session Worker lead is
# set up via set_session_worker_link instead, never becomes a Client).
# Deliberately simpler than leads.py's own convert_lead_to_client:
# Recruitment Lead carries none of the generic client-intake fields
# (client_type, young person/adult/school/company answers) that
# function maps across, since this doctype only ever represents a
# franchisee or session worker application, never an ordinary client
# enquiry.
# -------------------------------------------------------------------

FRANCHISEE_CLIENT_ASHLEY_LOGIN = "ashley@theresilientkid.co.uk"
FRANCHISEE_CLIENT_BANK_ACCOUNT = "HQ Bank Account - Starling"
FRANCHISEE_CLIENT_PRICE_LIST = "Ashley Pricelist"
FRANCHISEE_CLIENT_COMPANY = "The Resilient Kid"


def _split_name(full_name):
    parts = (full_name or "").strip().split(" ", 1)
    first = parts[0] if parts else ""
    last = parts[1] if len(parts) > 1 else ""
    return first, last


def _format_franchisee_intake_notes(doc):
    """Everything the Intake/DBS form collects that has no matching field
    on Client - see leads.py's own _format_franchisee_intake_notes for the
    original, identical reasoning."""
    lines = []

    if doc.get("franchisee_intake_id_document_type"):
        lines.append(f"ID document type: {doc.franchisee_intake_id_document_type}")
    if doc.get("franchisee_intake_right_to_work_status"):
        lines.append(f"Right to work status: {doc.franchisee_intake_right_to_work_status}")
    if doc.get("franchisee_intake_right_to_work_expiry"):
        lines.append(f"Right to work expiry: {frappe.utils.formatdate(doc.franchisee_intake_right_to_work_expiry)}")
    if doc.get("franchisee_intake_address_history"):
        lines.append(f"Address history: {doc.franchisee_intake_address_history}")
    if doc.get("franchisee_intake_overseas_checks"):
        lines.append(f"Overseas police clearance / checks: {doc.franchisee_intake_overseas_checks}")
    if doc.get("franchisee_intake_work_history"):
        lines.append(f"Work history: {doc.franchisee_intake_work_history}")
    if doc.get("franchisee_intake_qualifications"):
        lines.append(f"Qualifications: {doc.franchisee_intake_qualifications}")
    if doc.get("franchisee_intake_work_locations"):
        lines.append(f"Work locations: {doc.franchisee_intake_work_locations}")
    if doc.get("franchisee_intake_dbs_number"):
        lines.append(f"DBS number: {doc.franchisee_intake_dbs_number}")
    if doc.get("franchisee_intake_dbs_date_received"):
        lines.append(f"DBS date received: {frappe.utils.formatdate(doc.franchisee_intake_dbs_date_received)}")
    if doc.get("franchisee_intake_dbs_expiry_date"):
        lines.append(f"DBS expiry date: {frappe.utils.formatdate(doc.franchisee_intake_dbs_expiry_date)}")
    if doc.get("franchisee_intake_public_liability_insurer"):
        lines.append(f"Public liability insurer: {doc.franchisee_intake_public_liability_insurer}")
    if doc.get("franchisee_intake_indemnity_insurer"):
        lines.append(f"Indemnity insurer: {doc.franchisee_intake_indemnity_insurer}")
    if doc.get("franchisee_intake_insurance_renewal_date"):
        lines.append(f"Insurance renewal date: {frappe.utils.formatdate(doc.franchisee_intake_insurance_renewal_date)}")
    if doc.get("franchisee_intake_reference1_details"):
        lines.append(f"Reference 1: {doc.franchisee_intake_reference1_details}")
    if doc.get("franchisee_intake_reference2_details"):
        lines.append(f"Reference 2: {doc.franchisee_intake_reference2_details}")
    if doc.get("franchisee_intake_dbs_certificate"):
        lines.append("DBS certificate: uploaded - see the original lead record's Files for the document itself.")
    if doc.get("franchisee_intake_additional_document"):
        lines.append("Additional document: uploaded - see the original lead record's Files for the document itself.")

    if not lines:
        return ""

    return "<p><strong>From Intake/DBS form:</strong></p><p>" + "</p><p>".join(lines) + "</p>"


def _apply_franchisee_client_defaults(client, client_meta):
    """Every Franchisee lead becomes a Client tracked centrally under
    Ashley - see leads.py's own _apply_franchisee_client_defaults for the
    original, identical reasoning."""
    if client_meta.has_field("status"):
        client.status = "Active"

    if client_meta.has_field("session_worker"):
        client.session_worker = None

    ashley_coach = (
        frappe.db.get_value("Coach", {"user": FRANCHISEE_CLIENT_ASHLEY_LOGIN}, "name")
        or frappe.db.get_value("Coach", {"coach_email": FRANCHISEE_CLIENT_ASHLEY_LOGIN}, "name")
    )

    if ashley_coach:
        if client_meta.has_field("primary_coach"):
            client.primary_coach = ashley_coach
        if client_meta.has_field("attending_coach"):
            client.attending_coach = ashley_coach

    for fieldname, record_doctype, record_name in [
        ("coach_banking_details", "Bank Account", FRANCHISEE_CLIENT_BANK_ACCOUNT),
        ("banking", "Bank Account", FRANCHISEE_CLIENT_BANK_ACCOUNT),
        ("pricelist", "Price List", FRANCHISEE_CLIENT_PRICE_LIST),
        ("price_list", "Price List", FRANCHISEE_CLIENT_PRICE_LIST),
        ("company", "Company", FRANCHISEE_CLIENT_COMPANY),
    ]:
        if client_meta.has_field(fieldname) and frappe.db.exists(record_doctype, record_name):
            client.set(fieldname, record_name)


@frappe.whitelist()
def convert_recruitment_lead_to_client(name=None):
    doc = ensure_lead_access(coalesce_str("name", name))

    if doc.lead_type != "Franchisee":
        frappe.throw(_("A Session Worker lead doesn't convert to a Client - set them up as a Session Worker instead."))

    if doc.status == "Converted" and doc.converted_client:
        return {"ok": True, "client": doc.converted_client, "contact": doc.converted_contact}

    if not doc.contact_name or not doc.client_name:
        frappe.throw(_("This lead is missing contact or client details."))

    from dashboard.api.shared.client_details import set_full_name_from_parts, sanitize_name_part

    client_meta = frappe.get_meta("Client")
    client_first, client_last = _split_name(doc.client_name)

    client = frappe.new_doc("Client")

    set_full_name_from_parts(client, {"name1": client_first, "last_name": client_last})

    if client_meta.has_field("date_added"):
        client.date_added = frappe.utils.today()

    if client_meta.has_field("mobile") and doc.contact_mobile:
        client.mobile = doc.contact_mobile
    if client_meta.has_field("email") and doc.contact_email:
        client.email = doc.contact_email
    if client_meta.has_field("address") and doc.location_address:
        client.address = doc.location_address
    if client_meta.has_field("zip_code") and doc.postal_code:
        client.zip_code = doc.postal_code

    if client_meta.has_field("client_type"):
        client.client_type = "Franchise"

    intake_notes = _format_franchisee_intake_notes(doc)
    if intake_notes and client_meta.has_field("additional_comments"):
        client.additional_comments = intake_notes

    _apply_franchisee_client_defaults(client, client_meta)

    client.insert(ignore_permissions=True)

    existing_contact = (
        frappe.db.get_value("Contact Email", {"email_id": doc.contact_email}, "parent")
        if doc.contact_email else None
    )

    if existing_contact:
        contact = frappe.get_doc("Contact", existing_contact)
    else:
        contact_first, contact_last = _split_name(doc.contact_name)
        contact = frappe.new_doc("Contact")
        contact.first_name = contact_first
        if contact_last:
            contact.last_name = contact_last
        if doc.contact_email:
            contact.append("email_ids", {"email_id": doc.contact_email, "is_primary": 1})
        if doc.contact_mobile:
            contact.append("phone_nos", {"phone": doc.contact_mobile, "is_primary_mobile_no": 1})
        contact.insert(ignore_permissions=True)

    if client_meta.has_field("client_contacts"):
        client.append("client_contacts", {
            "contact": contact.name,
            "contact_name": sanitize_name_part(doc.contact_name),
            "phone": doc.contact_mobile or "",
            "email_id": doc.contact_email or "",
        })
        client.save(ignore_permissions=True)

    doc.converted_client = client.name
    doc.converted_contact = contact.name
    doc.status = "Converted"
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {"ok": True, "client": client.name, "contact": contact.name}


@frappe.whitelist()
def get_franchisee_intake(name=None):
    """Franchisor-only: the submitted intake details + file links, for the
    Recruitment Lead detail page."""
    name = coalesce_str("name", name)
    doc = ensure_lead_access(name)

    if not doc.get("franchisee_intake_submitted"):
        frappe.throw(_("This intake form hasn't been submitted yet."))

    return {
        "first_name": doc.get("franchisee_intake_first_name") or "",
        "last_name": doc.get("franchisee_intake_last_name") or "",
        "phone": doc.get("franchisee_intake_phone") or "",
        "gender": doc.get("franchisee_intake_gender") or "",
        "dob": doc.get("franchisee_intake_dob") or "",
        "dbs_number": doc.get("franchisee_intake_dbs_number") or "",
        "dbs_date_received": doc.get("franchisee_intake_dbs_date_received") or "",
        "dbs_expiry_date": doc.get("franchisee_intake_dbs_expiry_date") or "",
        "dbs_certificate": doc.get("franchisee_intake_dbs_certificate") or "",
        "additional_document": doc.get("franchisee_intake_additional_document") or "",
        "qualifications": doc.get("franchisee_intake_qualifications") or "",
        "work_locations": doc.get("franchisee_intake_work_locations") or "",
        "public_liability_insurer": doc.get("franchisee_intake_public_liability_insurer") or "",
        "indemnity_insurer": doc.get("franchisee_intake_indemnity_insurer") or "",
        "insurance_renewal_date": doc.get("franchisee_intake_insurance_renewal_date") or "",
        "id_document_type": doc.get("franchisee_intake_id_document_type") or "",
        "right_to_work_status": doc.get("franchisee_intake_right_to_work_status") or "",
        "right_to_work_expiry": doc.get("franchisee_intake_right_to_work_expiry") or "",
        "address_history": doc.get("franchisee_intake_address_history") or "",
        "overseas_checks": doc.get("franchisee_intake_overseas_checks") or "",
        "work_history": doc.get("franchisee_intake_work_history") or "",
        "reference1_details": doc.get("franchisee_intake_reference1_details") or "",
        "reference2_details": doc.get("franchisee_intake_reference2_details") or "",
        "submitted_at": frappe.utils.format_datetime(doc.get("franchisee_intake_submitted_at"), "dd-MM-yyyy HH:mm") if doc.get("franchisee_intake_submitted_at") else "",
    }
