import re
from urllib.parse import quote

import frappe
from frappe import _
from frappe.utils import now_datetime, get_url, get_fullname, fmt_money
from werkzeug.utils import secure_filename

from dashboard.api.shared.permissions import (
    ensure_logged_in,
    ensure_office_user,
    is_franchisor_user,
    get_current_coach_name,
    get_current_user_dashboard_type,
)
from dashboard.api.shared.clients import get_coach_label
from dashboard.api.shared.utils import coalesce_str, coalesce_raw
from dashboard.api.shared.notifications import create_trk_notification, FRANCHISOR_USERS
from dashboard.api.shared.appointment_types import creates_client_on_conversion
from dashboard.api.shared.email_templates import render_email, plain_text_to_email_html, parse_email_list, INTAKE_INVITE_TEMPLATE, PODCAST_INVITE_TEMPLATE
from dashboard.api.shared.item_access import _get_coach_login
from dashboard.api.shared.client_transfers import invoice_pending_transfer_fees_for_lead


INTAKE_ROUTE = "client-intake"
PODCAST_ROUTE = "podcast-guest-information"

# The actual intake form is the "Intake Doctype" Web Form (built and owned
# directly in Frappe Desk, not by this app). There's no reliable link field
# back to a Client Lead - Intake Doctype's own "created_lead" field turned
# out to point at a separate, unrelated Frappe CRM "Lead" doctype, and isn't
# something a public guest filling in the form could ever sensibly populate
# anyway - so sync_intake_doctype_submission() matches submissions back to a
# Client Lead by the name the guest actually typed in.
INTAKE_DOCTYPE = "Intake Doctype"

# The detailed intake questions, beyond the always-present "headline" fields
# (contact_name/contact_email/contact_mobile/client_name/client_age/
# postal_code/enquiry_reason/how_heard/consent_given) that drive the Lead
# list/Kanban display everywhere else in the app. These are only used for
# the richer Client record built on conversion - which section applies
# depends on client_type. Read via coalesce_str/coalesce_raw straight out of
# the request payload rather than as ~70 named function parameters.
INTAKE_TEXT_FIELDS = [
    "client_type",
    "young_person_first_name", "young_person_last_name", "young_person_preferred_name",
    "young_person_mobile", "young_person_email", "young_person_pronouns", "young_person_sex",
    "young_person_gender_identity", "young_person_address_line_1", "young_person_address_line_2",
    "young_person_city", "young_person_postalcode",
    "primary_caregiver_full_name", "primary_caregiver_mobile", "primary_caregiver_email",
    "primary_relationship_to_client", "siblings",
    "secondary_caregiver_full_name", "secondary_caregiver_mobile", "secondary_caregiver_email",
    "secondary_relationship", "account_responsible_person",
    "adult_first_name", "adult_last_name", "adult_preferred_name", "adult_address_1", "adult_address_2",
    "adult_city", "adult_postalcode", "adult_mobile", "adult_email", "adult_pronouns", "adult_sex",
    "adult_gender_identity", "adult_account_responsible_person",
    "next_of_kin_name", "next_of_kin_email", "next_of_kin_mobile",
    "school_name", "school_contact_name", "school_contact_role", "school_contact_email", "school_mobile",
    "school_address_line_1", "school_address_line_2", "school_city", "school_postalcode", "school_support_required",
    "company_name", "company_contact_name", "company_contact_role", "company_contact_email", "company_mobile",
    "company_address_line_1", "company_address_line_2", "company_city", "company_postalcode", "company_support_required",
    "family_first", "family_last", "family_email", "family_mobile", "family_address", "family_city", "family_zip",
    "family_dr", "family_get", "family_tried", "family_siblings", "family_challenge",
    "billing_contact_full_name", "billing_contact_email", "billing_contact_mobile",
    "billing_contact_address_line_1", "billing_contact_address_line_2", "billing_contact_city", "billing_contact_postal_code",
    "support_required", "allergies", "neurodiverse_status", "neurodiverse_information", "doctor_details",
    "main_therapy_location", "new_therapy_location_details",
    "education_establishment", "year_group_teacher", "sendco_involved", "education_contact",
    "signature_name",
]

INTAKE_DATE_FIELDS = ["young_person_date_of_birth", "adult_date_of_birth", "date_signed"]

INTAKE_CHECK_FIELDS = [
    "billing_contact_next_kin", "school_billing_same_as_contact", "company_billing_same_as_contact",
    "therapy_location_not_listed", "agreement_confirmed",
]

INTAKE_DETAIL_FIELDS = INTAKE_TEXT_FIELDS + INTAKE_DATE_FIELDS + INTAKE_CHECK_FIELDS

# Every email address the intake form might collect, across every
# client_type section - used to match a submission back to its Client
# Lead by email (see _find_client_lead_for_intake_submission), which is a
# much stronger signal than a typed name.
INTAKE_EMAIL_FIELDS = [
    "young_person_email", "primary_caregiver_email", "secondary_caregiver_email",
    "adult_email", "next_of_kin_email", "school_contact_email",
    "company_contact_email", "family_email", "billing_contact_email",
]

CLIENT_FIELD_LABELS = {
    "name1": "First Name",
    "last_name": "Last Name",
    "preferred_name": "Preferred Name",
    "mobile": "Mobile",
    "email": "Email",
    "pronouns": "Pronouns",
    "sex": "Sex",
    "gender_identity": "Gender Identity",
    "address": "Address",
    "city": "City",
    "zip_code": "Postal Code",
    "allergies": "Allergies",
    "neurodiverse_status": "Neurodiverse Status",
    "neurodiverse_information": "Neurodiverse Information",
    "main_therapy_location": "Main Therapy Location",
    "date_of_birth": "Date of Birth",
    "dob": "Date of Birth",
}


LEAD_DOCTYPE = "Client Lead"

# The 5 Stage 1 - Decide & Commit milestones (see
# add_franchise_lead_stage1_fields patch) - only meaningful on a
# Franchisee Call lead (is_franchise_lead below), franchisor-only to
# view/edit. (done_field, date_field) pairs, in pipeline order.
STAGE1_MILESTONES = [
    ("stage1_call_done", "stage1_call_date"),
    ("stage1_nda_done", "stage1_nda_date"),
    ("stage1_discovery_day_done", "stage1_discovery_day_date"),
    ("stage1_intent_deposit_dbs_done", "stage1_intent_deposit_dbs_date"),
    ("stage1_agreement_invoice_done", "stage1_agreement_invoice_date"),
]

# A Session Worker lead's own onboarding checklist - shorter than a
# Franchisee Call's (no Discovery Day, Intent to Proceed, or Franchise
# Agreement). Reuses the same "Call" and "Sign NDA" fields as
# STAGE1_MILESTONES above (the underlying nda_* e-signing fields don't
# care which kind of lead they're on) plus "Franchisee Intake + DBS/
# Insurance Submitted" reused as the shared Intake/DBS step, then its own
# Fees and Expectations Guide + final setup milestones below.
SESSION_WORKER_STAGE_MILESTONES = [
    ("stage1_call_done", "stage1_call_date"),
    ("stage1_nda_done", "stage1_nda_date"),
    ("stage1_agreement_invoice_done", "stage1_agreement_invoice_date"),
    ("fees_guide_done", "fees_guide_date"),
    ("sw_setup_done", "sw_setup_date"),
]


def is_franchise_lead(appointment_type):
    return "franchisee call" in (appointment_type or "").strip().lower()


def is_session_worker_lead(appointment_type):
    return "session worker" in (appointment_type or "").strip().lower()


def is_onboarding_pipeline_lead(appointment_type):
    """
    True for either lead kind that goes through the shared NDA + Intake/
    DBS steps (see STAGE1_MILESTONES's "Sign NDA" milestone and the
    franchisee_intake_* fields below) - a Franchisee Call and a Session
    Worker lead share those two steps; everything after (Intent to
    Proceed/Franchise Agreement for franchisees, the Fees and
    Expectations Guide for session workers) is kind-specific.
    """
    return is_franchise_lead(appointment_type) or is_session_worker_lead(appointment_type)


def is_podcast_lead(appointment_type):
    return "podcast" in (appointment_type or "").strip().lower()


LEAD_STATUSES = ["New", "Intake Sent", "Converted", "Declined"]

DECLINE_STATUSES = {"Declined"}

LEAD_LIST_FIELDS = [
    "name", "status", "source", "appointment_type", "coach", "active_transfer",
    "contact_name", "contact_email", "contact_mobile",
    "client_name", "client_age", "postal_code",
    "event", "converted_client", "intake_sent_on", "intake_email_status", "intake_completed_on", "modified", "creation",
]


def _normalize_lead_row(row):
    return {
        "name": row.get("name"),
        "status": row.get("status") or "New",
        "source": row.get("source") or "Coach Added",
        "appointment_type": row.get("appointment_type") or "",
        "coach": row.get("coach") or "",
        "coach_label": get_coach_label(row.get("coach")) if row.get("coach") else "",
        "active_transfer": row.get("active_transfer") or "",
        "contact_name": row.get("contact_name") or "",
        "contact_email": row.get("contact_email") or "",
        "contact_mobile": row.get("contact_mobile") or "",
        "client_name": row.get("client_name") or "",
        "client_age": row.get("client_age") or "",
        "postal_code": row.get("postal_code") or "",
        "event": row.get("event") or "",
        "converted_client": row.get("converted_client") or "",
        "intake_sent_on": row.get("intake_sent_on"),
        "intake_email_status": row.get("intake_email_status") or "",
        "intake_completed_on": row.get("intake_completed_on"),
        "needs_conversion_review": 1 if (
            row.get("intake_completed_on") and (row.get("status") or "New") not in ("Converted", "Declined")
        ) else 0,
        "has_invoice": 0,
        "modified": row.get("modified"),
        "creation": row.get("creation"),
    }


def _mark_converted_leads_with_invoices(rows):
    """
    Cheap "does this converted lead's client already have a Sales Invoice"
    flag so the board can prioritise showing the ones that still need
    billing set up, instead of just recency.
    """
    client_names = [
        row["converted_client"] for row in rows
        if row.get("status") == "Converted" and row.get("converted_client")
    ]

    if not client_names or not frappe.db.exists("DocType", "Sales Invoice"):
        return rows

    if not frappe.get_meta("Sales Invoice").has_field("custom_client"):
        return rows

    invoiced_clients = set(frappe.get_all(
        "Sales Invoice",
        filters={"custom_client": ["in", client_names]},
        pluck="custom_client",
        ignore_permissions=True,
    ))

    for row in rows:
        if row.get("converted_client") in invoiced_clients:
            row["has_invoice"] = 1

    return rows


def _current_coach_name():
    return get_current_coach_name(optional=True)


def _notify_lead_allocated(doc, previous_coach=None):
    """
    Tells a coach when a lead lands on their list because someone else put
    it there - HQ creating a lead straight onto a coach's board, or a
    franchisor reassigning an existing one - not a coach booking/creating
    a lead for themselves. Never fires when the lead's coach hasn't
    actually changed (previous_coach == doc.coach), and never notifies
    someone about their own action.
    """
    if not doc.coach or doc.coach == previous_coach:
        return

    coach_user = _get_coach_login(doc.coach)
    if not coach_user or coach_user == frappe.session.user:
        return

    try:
        create_trk_notification(
            recipient_user=coach_user,
            notification_type="Task",
            message="A new lead was allocated to you by {0}: {1}".format(
                get_fullname(frappe.session.user) or frappe.session.user,
                doc.client_name or doc.contact_name or "New Lead",
            ),
            reference_doctype=LEAD_DOCTYPE,
            reference_name=doc.name,
            coach=doc.coach,
        )
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"Lead Allocated Notification Failed - {doc.name}")


def _lead_filters_for_current_user(dashboard_type=None, scope=None):
    """
    None means "no filter" (see every lead). Any other value is a Frappe
    filters dict restricting to one coach's own leads.

    A coach/session worker always sees their own leads only, regardless of
    scope. A franchisor is often also a working coach with their own
    Client Leads (e.g. Ashley) - their board defaults to "mine" (scope
    omitted or "mine"), same as everyone else, but they can pass
    scope="all" to see the full board across every coach, matching the
    "my own first, but I can go look at everyone else's" pattern the rest
    of the franchisor dashboard already uses (see coach_view_mode.py).
    """
    ensure_logged_in()

    dashboard_type = dashboard_type or get_current_user_dashboard_type()
    is_franchisor = is_franchisor_user() or dashboard_type == "franchisor"

    if is_franchisor and (scope or "mine").strip().lower() == "all":
        return None

    coach_name = _current_coach_name()

    if not coach_name:
        # A franchisor with no Coach profile of their own has no "mine" to
        # show - fall back to everyone's rather than an empty board that
        # would otherwise look broken rather than intentional.
        return None if is_franchisor else {"name": ["in", []]}

    return {"coach": coach_name}


def ensure_lead_access(name):
    ensure_logged_in()

    if not name or not frappe.db.exists(LEAD_DOCTYPE, name):
        frappe.throw(_("Lead not found."))

    doc = frappe.get_doc(LEAD_DOCTYPE, name)

    if is_franchisor_user():
        return doc

    coach_name = _current_coach_name()

    if coach_name and doc.coach == coach_name:
        return doc

    frappe.throw(_("You do not have permission to access this lead."), frappe.PermissionError)


@frappe.whitelist()
def get_leads(dashboard_type=None, scope=None):
    ensure_logged_in()

    filters = _lead_filters_for_current_user(dashboard_type, scope)

    args = {
        "doctype": LEAD_DOCTYPE,
        "fields": LEAD_LIST_FIELDS,
        "order_by": "modified desc",
        "limit_page_length": 2000,
    }

    if filters is not None:
        args["filters"] = filters

    rows = frappe.get_all(**args, ignore_permissions=True)

    normalized = [_normalize_lead_row(row) for row in rows]
    return _mark_converted_leads_with_invoices(normalized)


def _get_lead_notes(doc):
    notes = []

    for row in doc.get("notes") or []:
        notes.append({
            "name": row.get("name"),
            "note": row.get("note") or "",
            "note_date": row.get("note_date"),
            "added_by": row.get("added_by") or "",
            "added_on": row.get("added_on"),
            "idx": row.get("idx") or 0,
        })

    notes.sort(key=lambda r: (str(r.get("note_date") or ""), r.get("idx") or 0), reverse=True)
    return notes


@frappe.whitelist()
def get_lead(name=None):
    name = coalesce_str("name", name)
    doc = ensure_lead_access(name)

    row = _normalize_lead_row(doc.as_dict())
    row["decline_reason"] = doc.get("decline_reason") or ""
    row["enquiry_reason"] = doc.get("enquiry_reason") or ""
    row["how_heard"] = doc.get("how_heard") or ""
    row["consent_given"] = int(doc.get("consent_given") or 0)
    row["notes"] = _get_lead_notes(doc)
    row["can_edit"] = 1
    row["intake_sent_on"] = doc.get("intake_sent_on")
    row["intake_completed_on"] = doc.get("intake_completed_on")
    row["converted_client"] = doc.get("converted_client") or ""
    row["converted_contact"] = doc.get("converted_contact") or ""
    row["intake_url"] = _intake_url(doc) if doc.get("intake_sent_on") else ""
    row["call"] = _get_lead_call_info(doc.event)
    row["location_address"] = doc.get("location_address") or ""
    row["is_franchise_lead"] = 1 if is_franchise_lead(doc.get("appointment_type")) else 0
    row["is_session_worker_lead"] = 1 if is_session_worker_lead(doc.get("appointment_type")) else 0
    # A Franchisee Call is deliberately excluded from creates_client_on_
    # conversion() (see LEGACY_NON_CLIENT_LABEL_FRAGMENTS) - that was
    # written before this Stage 1 pipeline existed, back when converting
    # one straight into an ordinary Client made no sense. It now does
    # (Stage 1 finishes with a real Client, client_type Franchise - see
    # convert_lead_to_client below), so it's forced on here regardless
    # of whatever creates_client_on_conversion() would otherwise say. A
    # Session Worker lead never becomes a Client at all (see sw_setup_done
    # below - Session Worker is a separate doctype set up manually in
    # Desk). creates_client_on_conversion() would otherwise say True for
    # a "Session Worker" label too (it isn't in LEGACY_NON_CLIENT_LABEL_
    # FRAGMENTS), so it's explicitly forced off here rather than left to
    # fall through.
    if row["is_session_worker_lead"]:
        row["is_client_conversion"] = 0
    else:
        row["is_client_conversion"] = 1 if (row["is_franchise_lead"] or creates_client_on_conversion(doc.get("appointment_type"))) else 0
    row["active_transfer"] = doc.get("active_transfer") or ""
    # For the franchisor: is this HER OWN lead (she's a working coach and
    # currently holds it herself), rather than one of some other coach's
    # leads she's just viewing/managing as admin? Drives whether her own
    # "Reassign To" starts a real 2-signature Client Transfer Agreement, or
    # keeps the instant admin-override reassignment - see leads.js and
    # update_lead(). Always true for a coach viewing their own lead
    # (ensure_lead_access already only let them get this far if it was).
    current_coach_name = _current_coach_name()
    row["is_own_lead"] = 1 if (current_coach_name and doc.get("coach") == current_coach_name) else 0
    row["active_transfer_status"] = (
        frappe.db.get_value("Client Transfer Agreement", row["active_transfer"], "status") or ""
        if row["active_transfer"] else ""
    )

    if row["is_franchise_lead"]:
        row["stage1"] = {
            done_field: {
                "done": int(doc.get(done_field) or 0),
                "date": doc.get(date_field) or "",
            }
            for done_field, date_field in STAGE1_MILESTONES
        }
        row["intent_signed"] = 1 if doc.get("intent_signed_snapshot") else 0
        row["intent_link_generated"] = 1 if doc.get("intent_token") else 0
        row["intent_sent_at"] = (
            frappe.utils.format_datetime(doc.get("intent_sent_at"), "dd-MM-yyyy HH:mm") if doc.get("intent_sent_at") else ""
        )

    if row["is_session_worker_lead"]:
        row["session_worker_stage"] = {
            done_field: {
                "done": int(doc.get(done_field) or 0),
                "date": doc.get(date_field) or "",
            }
            for done_field, date_field in SESSION_WORKER_STAGE_MILESTONES
        }
        row["fees_guide_signed"] = 1 if doc.get("fees_guide_signed_snapshot") else 0
        row["fees_guide_link_generated"] = 1 if doc.get("fees_guide_token") else 0
        row["fees_guide_sent_at"] = (
            frappe.utils.format_datetime(doc.get("fees_guide_sent_at"), "dd-MM-yyyy HH:mm")
            if doc.get("fees_guide_sent_at") else ""
        )
        row["converted_session_worker"] = doc.get("converted_session_worker") or ""

    if row["is_franchise_lead"] or row["is_session_worker_lead"]:
        # Shared between both lead kinds - the NDA and Intake/DBS steps
        # are identical regardless of which one this lead is (see
        # is_onboarding_pipeline_lead above).
        row["nda_signed"] = 1 if doc.get("nda_signed_snapshot") else 0
        row["nda_link_generated"] = 1 if doc.get("nda_token") else 0
        row["nda_sent_at"] = (
            frappe.utils.format_datetime(doc.get("nda_sent_at"), "dd-MM-yyyy HH:mm") if doc.get("nda_sent_at") else ""
        )
        row["franchisee_intake_submitted"] = 1 if doc.get("franchisee_intake_submitted") else 0
        row["franchisee_intake_link_generated"] = 1 if doc.get("franchisee_intake_token") else 0
        row["franchisee_intake_sent_at"] = (
            frappe.utils.format_datetime(doc.get("franchisee_intake_sent_at"), "dd-MM-yyyy HH:mm")
            if doc.get("franchisee_intake_sent_at") else ""
        )

    for fieldname in INTAKE_TEXT_FIELDS + INTAKE_DATE_FIELDS:
        row[fieldname] = doc.get(fieldname) or ""

    for fieldname in INTAKE_CHECK_FIELDS:
        row[fieldname] = int(doc.get(fieldname) or 0)

    row["intake_answers"] = [
        {"label": label, "value": str(value)} for label, value in _intake_pdf_rows(doc)
        if label != "Intake Completed On"
    ]

    return row


def _get_lead_call_info(event_name):
    if not event_name or not frappe.db.exists("Event", event_name):
        return None

    event_meta = frappe.get_meta("Event")
    fields = ["starts_on", "ends_on", "location"]

    for fieldname in ["google_meet_link", "custom_google_meet_url"]:
        if event_meta.has_field(fieldname):
            fields.append(fieldname)

    event = frappe.db.get_value("Event", event_name, fields, as_dict=True) or {}

    online_link = event.get("google_meet_link") or event.get("custom_google_meet_url") or ""

    starts_on = event.get("starts_on")
    ends_on = event.get("ends_on")

    return {
        "event": event_name,
        "date": starts_on.strftime("%Y-%m-%d") if starts_on else "",
        "start_time": starts_on.strftime("%H:%M") if starts_on else "",
        "end_time": ends_on.strftime("%H:%M") if ends_on else "",
        "location": event.get("location") or "",
        "online_link": online_link,
    }


@frappe.whitelist()
def create_lead(
    contact_name=None,
    contact_email=None,
    contact_mobile=None,
    client_name=None,
    client_age=None,
    postal_code=None,
    enquiry_reason=None,
    how_heard=None,
    consent_given=None,
    coach=None,
    appointment_type=None,
    location_address=None,
    dashboard_type=None,
):
    ensure_logged_in()

    contact_name = coalesce_str("contact_name", contact_name)
    contact_email = coalesce_str("contact_email", contact_email)
    contact_mobile = coalesce_str("contact_mobile", contact_mobile)
    client_name = coalesce_str("client_name", client_name)
    client_age = coalesce_raw("client_age", client_age)
    postal_code = coalesce_str("postal_code", postal_code)
    enquiry_reason = coalesce_str("enquiry_reason", enquiry_reason)
    how_heard = coalesce_str("how_heard", how_heard)
    consent_given = coalesce_raw("consent_given", consent_given)
    coach = coalesce_str("coach", coach)
    appointment_type = coalesce_str("appointment_type", appointment_type) or "Initial Consultation"
    location_address = coalesce_str("location_address", location_address)
    dashboard_type = coalesce_str("dashboard_type", dashboard_type) or get_current_user_dashboard_type()

    if not contact_name:
        frappe.throw(_("Please enter the contact's name."))

    if not client_name:
        frappe.throw(_("Please enter the client's (young person's) name."))

    if is_franchisor_user() or dashboard_type == "franchisor":
        if coach and not frappe.db.exists("Coach", coach):
            frappe.throw(_("Selected coach was not found."))
    else:
        coach = _current_coach_name()

        if not coach:
            frappe.throw(_("No Coach profile is linked to your user."), frappe.PermissionError)

    doc = frappe.new_doc(LEAD_DOCTYPE)
    doc.status = "New"
    doc.source = "Coach Added"
    doc.appointment_type = appointment_type
    doc.coach = coach
    doc.contact_name = contact_name
    doc.contact_email = contact_email
    doc.contact_mobile = contact_mobile
    doc.client_name = client_name

    if client_age not in (None, ""):
        try:
            doc.client_age = int(client_age)
        except Exception:
            pass

    doc.postal_code = postal_code
    doc.enquiry_reason = enquiry_reason
    doc.how_heard = how_heard
    doc.consent_given = 1 if str(consent_given).lower() in ["1", "true", "yes", "on"] else 0
    doc.location_address = location_address

    doc.insert(ignore_permissions=True)
    frappe.db.commit()

    _notify_lead_allocated(doc)

    return {"ok": True, "name": doc.name}


def create_lead_from_booking(contact_name, phone=None, coach=None):
    """
    Internal (not whitelisted) - called from calendar.create_booking() when
    an Initial Consultation is booked straight from the calendar rather than
    via this section's own "Book a Call" button, so that path still lands
    the enquiry in the Leads section instead of only the legacy Lead.
    """
    doc = frappe.new_doc(LEAD_DOCTYPE)
    doc.status = "New"
    doc.source = "Calendar Booking"
    doc.appointment_type = "Initial Consultation"
    doc.coach = coach
    doc.contact_name = contact_name
    doc.contact_mobile = phone or ""
    doc.client_name = contact_name
    doc.insert(ignore_permissions=True)
    frappe.db.commit()

    _notify_lead_allocated(doc)

    return doc.name


@frappe.whitelist()
def delete_lead(name=None):
    """
    Permanently removes a Client Lead - for bad/duplicate/test enquiries,
    not for undoing a real conversion. A Converted lead already has a real
    Client (and usually Contact) built from it, so it's blocked here
    rather than silently orphaning that record's own history of where it
    came from.

    Any Event booked against this lead (e.g. an Initial Consultation call)
    is deleted along with it, the same way deleting an appointment from
    the calendar does (force=True - a synced appointment also carries
    Calendar Sync Log rows that would otherwise block this) - so the
    on_trash hook that removes it from Google Calendar still fires, and
    the lead is never blocked by, or left leaving behind, a booking
    pointing at nothing. Anything else linked that this doesn't already
    know to expect is still caught by Frappe's own linked-document check
    and re-raised as a clear message rather than a raw traceback.
    """
    name = coalesce_str("name", name)
    doc = ensure_lead_access(name)

    if doc.status == "Converted" or doc.converted_client:
        frappe.throw(_("Converted leads can't be deleted - they already have a client record built from them."))

    linked_event_names = set(frappe.get_all(
        "Event",
        filters={"custom_client_lead": doc.name},
        pluck="name",
    ))
    if doc.event:
        linked_event_names.add(doc.event)

    for event_name in linked_event_names:
        if frappe.db.exists("Event", event_name):
            frappe.delete_doc("Event", event_name, ignore_permissions=True, force=True)

    try:
        frappe.delete_doc(LEAD_DOCTYPE, doc.name, ignore_permissions=True)
    except frappe.LinkExistsError:
        frappe.throw(_(
            "This lead still has other records linked to it and can't be deleted until those are removed first."
        ))

    return {"ok": True}


@frappe.whitelist()
def update_lead(
    name=None,
    contact_name=None,
    contact_email=None,
    contact_mobile=None,
    client_name=None,
    client_age=None,
    postal_code=None,
    enquiry_reason=None,
    how_heard=None,
    consent_given=None,
    location_address=None,
    coach=None,
):
    name = coalesce_str("name", name)
    doc = ensure_lead_access(name)

    contact_name = coalesce_str("contact_name", contact_name)
    client_name = coalesce_str("client_name", client_name)

    if not contact_name:
        frappe.throw(_("Please enter the contact's name."))

    if not client_name:
        frappe.throw(_("Please enter the client's (young person's) name."))

    doc.contact_name = contact_name
    doc.contact_email = coalesce_str("contact_email", contact_email)
    doc.contact_mobile = coalesce_str("contact_mobile", contact_mobile)
    doc.client_name = client_name

    # Reassigning which coach a lead belongs to - the franchisor can still
    # do this instantly when acting as an admin moving a lead between two
    # OTHER coaches. But when the franchisor is herself the lead's current
    # coach (she's one of the two actual parties to the handover, not just
    # correcting an assignment), it's a real transfer and has to go through
    # the same Client Transfer Agreement workflow as a coach's own
    # reassignment - just with only 2 signatures required (the receiving
    # coach, then her - see client_transfers._is_franchisor_coach()). A
    # coach handing off a lead of their own (see "Reassign To" in the
    # Enquiry section of their own Lead Details page) never takes effect
    # here at all - it goes through client_transfers.create_transfer(),
    # which only actually changes doc.coach once every required signature
    # is in (see sign_transfer()'s final step). Any "coach" value this
    # function itself won't apply is simply ignored rather than rejected,
    # since the general Save button still submits it on every save
    # regardless of whether a transfer was actually started instead.
    previous_coach = doc.coach
    coach = coalesce_str("coach", coach)
    current_coach_name = _current_coach_name()
    is_franchisors_own_lead = bool(current_coach_name) and previous_coach == current_coach_name

    if coach and is_franchisor_user() and not is_franchisors_own_lead and coach != doc.coach:
        if not frappe.db.exists("Coach", coach):
            frappe.throw(_("Coach not found."))

        doc.coach = coach

    client_age = coalesce_raw("client_age", client_age)
    if client_age not in (None, ""):
        try:
            doc.client_age = int(client_age)
        except Exception:
            pass
    else:
        doc.client_age = None

    doc.postal_code = coalesce_str("postal_code", postal_code)
    doc.enquiry_reason = coalesce_str("enquiry_reason", enquiry_reason)
    doc.how_heard = coalesce_str("how_heard", how_heard)

    consent_given = coalesce_raw("consent_given", consent_given)
    doc.consent_given = 1 if str(consent_given).lower() in ["1", "true", "yes", "on"] else 0
    doc.location_address = coalesce_str("location_address", location_address)

    doc.save(ignore_permissions=True)
    frappe.db.commit()

    _notify_lead_allocated(doc, previous_coach=previous_coach)

    return {"ok": True, "name": doc.name}


@frappe.whitelist()
def update_lead_status(name=None, status=None, decline_reason=None):
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
def update_franchise_pipeline(name=None, milestone=None, done=None, milestone_date=None):
    """
    Ticks (or unticks) one Stage 1 - Decide & Commit milestone on a
    Franchisee Call lead. Franchisor-only - this is HQ's own recruitment
    pipeline, not something a coach's lead view ever shows or edits.
    Unticking clears the date rather than leaving a stale one behind, so
    the date field never shows a value the tick box disagrees with.
    """
    if not is_franchisor_user():
        frappe.throw(_("You do not have permission to update this."), frappe.PermissionError)

    name = coalesce_str("name", name)
    milestone = coalesce_str("milestone", milestone)
    milestone_date = coalesce_str("milestone_date", milestone_date)
    done = coalesce_raw("done", done)
    is_done = str(done).lower() in ["1", "true", "yes", "on"]

    valid_fields = {done_field for done_field, _date_field in STAGE1_MILESTONES + SESSION_WORKER_STAGE_MILESTONES}
    if milestone not in valid_fields:
        frappe.throw(_("Unknown Stage 1 milestone."))

    doc = ensure_lead_access(name)

    if not is_onboarding_pipeline_lead(doc.get("appointment_type")):
        frappe.throw(_("This lead isn't a Franchisee Call or Session Worker - Stage 1 doesn't apply to it."))

    date_field = dict(STAGE1_MILESTONES + SESSION_WORKER_STAGE_MILESTONES)[milestone]

    doc.set(milestone, 1 if is_done else 0)
    doc.set(date_field, milestone_date if is_done else None)
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {"ok": True, "name": doc.name, milestone: doc.get(milestone), date_field: doc.get(date_field)}


# -------------------------------------------------------------------
# Franchisee NDA e-signing - a public, token-linked page (no login) a
# franchisee opens to read and sign the NDA. See
# add_franchise_lead_nda_fields.py / add_franchisee_nda_practice_document.py
# for the fields and template this is built on.
# -------------------------------------------------------------------

NDA_PRACTICE_DOCUMENT_TITLE = "Franchisee Non-Disclosure Agreement"
NDA_TERM_YEARS = 3
NDA_BLANK_PLACEHOLDER = "_" * 24


def _nda_template_text():
    name = frappe.db.get_value(
        "Practice Document", {"document_title": NDA_PRACTICE_DOCUMENT_TITLE}, "name"
    )
    if not name:
        frappe.throw(_("The Franchisee NDA template hasn't been set up yet."))

    return frappe.db.get_value("Practice Document", name, "document_text") or ""


def _render_nda_text(template_text, context):
    text = template_text
    for key, value in context.items():
        # Every value here is either franchisee-typed input or a plain
        # formatted date, never trusted as HTML - this is rendered
        # straight into an HTML template both for on-screen preview and
        # as the permanent signed snapshot.
        text = text.replace("{{ " + key + " }}", frappe.utils.escape_html(value or ""))
    return text


def _get_lead_by_nda_token(token):
    token = (token or "").strip()
    if not token:
        frappe.throw(_("This link is invalid."))

    lead_name = frappe.db.get_value("Client Lead", {"nda_token": token}, "name")
    if not lead_name:
        frappe.throw(_("This link is invalid."))

    return frappe.get_doc(LEAD_DOCTYPE, lead_name)


@frappe.whitelist()
def get_nda_sign_url(name=None):
    """
    Franchisor-only: generates (the first time) or reuses this lead's NDA
    sign link. nda_agreement_date is fixed the first time this is called
    - it's the agreement's "made and entered into on" date and the
    Franchisor's own signing date, which stay fixed even if the
    franchisee doesn't actually open/sign the link until later.
    """
    if not is_franchisor_user():
        frappe.throw(_("You do not have permission to do this."), frappe.PermissionError)

    name = coalesce_str("name", name)
    doc = ensure_lead_access(name)

    if not is_onboarding_pipeline_lead(doc.get("appointment_type")):
        frappe.throw(_("This lead isn't a Franchisee Call or Session Worker - the NDA flow doesn't apply to it."))

    if doc.get("nda_signed_snapshot"):
        frappe.throw(_("This lead's NDA has already been signed."))

    if not doc.get("nda_token"):
        doc.nda_token = frappe.generate_hash(length=40)
        doc.nda_agreement_date = frappe.utils.today()
        doc.save(ignore_permissions=True)
        frappe.db.commit()

    return {"url": get_url(f"/franchisee-nda?token={doc.nda_token}")}


def _nda_email_text(doc, nda_url):
    contact_name = doc.contact_name or "there"
    subject = "Please sign: Non-Disclosure Agreement"

    if is_session_worker_lead(doc.get("appointment_type")):
        continuing_as = "becoming a Resilient Kid session worker"
    else:
        continuing_as = "becoming a Resilient franchisee"

    message = (
        f"Hi {contact_name},\n\n"
        f"Please read and sign the Non-Disclosure Agreement below to continue with {continuing_as}:\n\n"
        f"{nda_url}"
    )
    return subject, message


@frappe.whitelist()
def get_nda_email_defaults(name=None):
    """
    Subject/message the compose modal pre-fills so Ashley can see and
    edit the NDA invite before it's actually sent - mirrors
    get_intake_email_defaults() above for the unrelated generic intake
    flow.
    """
    name = coalesce_str("name", name)
    doc = ensure_lead_access(name)

    if not doc.contact_email:
        frappe.throw(_("This lead has no contact email address to send the NDA to."))

    nda_url = get_nda_sign_url(name=name)["url"]
    subject, message = _nda_email_text(doc, nda_url)

    return {"subject": subject, "message": message, "recipient": doc.contact_email, "url": nda_url}


@frappe.whitelist()
def send_nda_link(name=None, subject=None, message=None, cc=None, reply_to=None):
    """
    Franchisor-only: emails the NDA sign link straight to this lead's
    own contact email, reusing get_nda_sign_url's generate-or-reuse
    logic so this never creates a second, different link. subject/
    message default to the standard wording when left blank (a direct
    resend without reopening the compose modal), same as
    send_intake_form does.
    """
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
        "now": True,
        "reply_to": reply_to,
    }

    cc_list = parse_email_list(cc)
    if cc_list:
        kwargs["cc"] = cc_list

    frappe.sendmail(**kwargs)

    doc.nda_sent_at = frappe.utils.now_datetime()
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {
        "ok": 1,
        "url": nda_url,
        "sent_at": frappe.utils.format_datetime(doc.nda_sent_at, "dd-MM-yyyy HH:mm"),
    }


@frappe.whitelist()
def get_signed_nda(name=None):
    """Franchisor-only: the frozen signed snapshot plus its audit trail, for the Lead Details page."""
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
    """
    Guest-accessible - what the public /franchisee-nda page shows. Blanks
    not yet known (address/signature/franchisee date/term) render as
    underscores, matching how the paper version looked before it was
    filled in, rather than showing raw {{ }} placeholder syntax.
    """
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

    # Audit trail - the same kind of evidence a real e-signature service
    # records alongside a typed signature (who, when, from where), in
    # case this is ever disputed. request_ip already accounts for a
    # proxy in front of the site (X-Forwarded-For), not just the raw
    # connecting address.
    doc.nda_signed_at = frappe.utils.now_datetime()
    doc.nda_signer_ip = frappe.local.request_ip
    doc.nda_signer_user_agent = frappe.get_request_header("User-Agent") or ""

    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {"ok": True}


# -------------------------------------------------------------------
# Deposit and Intent to Proceed Agreement - same e-signing shape as the
# NDA above, one step later in the Stage 1 pipeline. Territory/deposit
# amount/end date are Ashley's own inputs (the deal's business terms),
# fixed the first time she generates the link for a lead - the
# franchisee only ever supplies her name/address/signature, same as NDA.
# -------------------------------------------------------------------

INTENT_PRACTICE_DOCUMENT_TITLE = "Deposit and Intent to Proceed Agreement"


def _intent_template_text():
    name = frappe.db.get_value(
        "Practice Document", {"document_title": INTENT_PRACTICE_DOCUMENT_TITLE}, "name"
    )
    if not name:
        frappe.throw(_("The Intent to Proceed template hasn't been set up yet."))

    return frappe.db.get_value("Practice Document", name, "document_text") or ""


def _get_lead_by_intent_token(token):
    token = (token or "").strip()
    if not token:
        frappe.throw(_("This link is invalid."))

    lead_name = frappe.db.get_value("Client Lead", {"intent_token": token}, "name")
    if not lead_name:
        frappe.throw(_("This link is invalid."))

    return frappe.get_doc(LEAD_DOCTYPE, lead_name)


@frappe.whitelist()
def get_intent_sign_url(name=None, territory=None, deposit_amount=None, end_date=None):
    """
    Franchisor-only: generates (the first time) or reuses this lead's
    Intent to Proceed sign link. territory/deposit_amount/end_date are
    only used the first time - Ashley's own business terms for this
    deal, fixed from then on exactly like nda_agreement_date is for the
    NDA, so an already-generated link never changes underneath someone
    who's already been sent it.
    """
    if not is_franchisor_user():
        frappe.throw(_("You do not have permission to do this."), frappe.PermissionError)

    name = coalesce_str("name", name)
    doc = ensure_lead_access(name)

    if not is_franchise_lead(doc.get("appointment_type")):
        frappe.throw(_("This lead isn't a Franchisee Call - the Intent to Proceed flow doesn't apply to it."))

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

    return {"url": get_url(f"/franchisee-intent?token={doc.intent_token}")}


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
    """
    Subject/message the compose modal pre-fills before send_intent_link
    actually sends it. territory/deposit_amount/end_date are only used
    the first time (when the link doesn't exist yet) - same rule as
    get_intent_sign_url.
    """
    name = coalesce_str("name", name)
    doc = ensure_lead_access(name)

    if not doc.contact_email:
        frappe.throw(_("This lead has no contact email address to send the agreement to."))

    intent_url = get_intent_sign_url(
        name=name, territory=territory, deposit_amount=deposit_amount, end_date=end_date
    )["url"]
    subject, message = _intent_email_text(doc, intent_url)

    return {"subject": subject, "message": message, "recipient": doc.contact_email, "url": intent_url}


@frappe.whitelist()
def send_intent_link(name=None, territory=None, deposit_amount=None, end_date=None, subject=None, message=None, cc=None, reply_to=None):
    """
    Franchisor-only: emails the Deposit and Intent to Proceed sign link
    straight to this lead's own contact email, reusing get_intent_sign_
    url's generate-or-reuse logic (territory/deposit_amount/end_date are
    only used the first time, same as there). subject/message default to
    the standard wording when left blank.
    """
    name = coalesce_str("name", name)
    doc = ensure_lead_access(name)

    if not doc.contact_email:
        frappe.throw(_("This lead has no contact email address to send the agreement to."))

    intent_url = get_intent_sign_url(
        name=name, territory=territory, deposit_amount=deposit_amount, end_date=end_date
    )["url"]

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
        "now": True,
        "reply_to": reply_to,
    }

    cc_list = parse_email_list(cc)
    if cc_list:
        kwargs["cc"] = cc_list

    frappe.sendmail(**kwargs)

    doc.intent_sent_at = frappe.utils.now_datetime()
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {
        "ok": 1,
        "url": intent_url,
        "sent_at": frappe.utils.format_datetime(doc.intent_sent_at, "dd-MM-yyyy HH:mm"),
    }


@frappe.whitelist()
def get_signed_intent(name=None):
    """Franchisor-only: the frozen signed snapshot plus its audit trail, for the Lead Details page."""
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
    """Guest-accessible - what the public /franchisee-intent page shows."""
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
    # Stage1's "Intent to Proceed" milestone - auto-ticked the same way
    # sign_nda() above auto-ticks Sign NDA, rather than needing Ashley to
    # remember to also tick it by hand.
    doc.stage1_intent_deposit_dbs_done = 1
    doc.stage1_intent_deposit_dbs_date = today

    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {"ok": True}


# -------------------------------------------------------------------
# Franchisee Intake + DBS/Insurance form - the step after Intent to
# Proceed, before converting the lead to a real Client. Not a
# signature flow, just personal details plus two file uploads
# (required DBS certificate, optional additional document e.g.
# insurance). "franchisee_intake_" prefix deliberately avoids the
# "intake_"/INTAKE_* names already used above for the unrelated general
# client-enquiry Intake Doctype flow.
# -------------------------------------------------------------------

FRANCHISEE_INTAKE_FILE_FIELDS = {
    "dbs_certificate": "franchisee_intake_dbs_certificate",
    "additional_document": "franchisee_intake_additional_document",
}


def _get_lead_by_franchisee_intake_token(token):
    token = (token or "").strip()
    if not token:
        frappe.throw(_("This link is invalid."))

    lead_name = frappe.db.get_value("Client Lead", {"franchisee_intake_token": token}, "name")
    if not lead_name:
        frappe.throw(_("This link is invalid."))

    return frappe.get_doc(LEAD_DOCTYPE, lead_name)


@frappe.whitelist()
def get_franchisee_intake_url(name=None):
    """Franchisor-only: generates (the first time) or reuses this lead's Intake/DBS form link."""
    if not is_franchisor_user():
        frappe.throw(_("You do not have permission to do this."), frappe.PermissionError)

    name = coalesce_str("name", name)
    doc = ensure_lead_access(name)

    if not is_onboarding_pipeline_lead(doc.get("appointment_type")):
        frappe.throw(_("This lead isn't a Franchisee Call or Session Worker - the intake form doesn't apply to it."))

    if not doc.get("franchisee_intake_token"):
        doc.franchisee_intake_token = frappe.generate_hash(length=40)
        doc.save(ignore_permissions=True)
        frappe.db.commit()

    return {"url": get_url(f"/franchisee-intake?token={doc.franchisee_intake_token}")}


def _franchisee_intake_email_text(doc, intake_url):
    contact_name = doc.contact_name or "there"

    if is_session_worker_lead(doc.get("appointment_type")):
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
    """Subject/message the compose modal pre-fills before send_franchisee_intake_form actually sends it."""
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
    """
    Franchisor-only: emails the Intake/DBS form link straight to this
    lead's own contact email. Reuses whatever token already exists for
    this lead (generating one the first time, exactly like
    get_franchisee_intake_url) rather than ever creating a new one, so a
    link the franchisee has already opened (or partway filled in) keeps
    working after a resend. subject/message default to the standard
    wording when left blank.
    """
    if not is_franchisor_user():
        frappe.throw(_("You do not have permission to do this."), frappe.PermissionError)

    name = coalesce_str("name", name)
    doc = ensure_lead_access(name)

    if not is_onboarding_pipeline_lead(doc.get("appointment_type")):
        frappe.throw(_("This lead isn't a Franchisee Call or Session Worker - the intake form doesn't apply to it."))

    if not doc.contact_email:
        frappe.throw(_("This lead has no contact email address to send the form to."))

    if not doc.get("franchisee_intake_token"):
        doc.franchisee_intake_token = frappe.generate_hash(length=40)
        doc.save(ignore_permissions=True)
        frappe.db.commit()

    intake_url = get_url(f"/franchisee-intake?token={doc.franchisee_intake_token}")

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
        "now": True,
        "reply_to": reply_to,
    }

    cc_list = parse_email_list(cc)
    if cc_list:
        kwargs["cc"] = cc_list

    frappe.sendmail(**kwargs)

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
    """
    Guest-accessible - lets the public form show "already submitted"
    instead of a blank form, and tells it whether to show the extra
    session-worker-only fields (qualifications/insurance/work locations -
    not relevant to a franchisee).
    """
    token = coalesce_str("token", token)
    doc = _get_lead_by_franchisee_intake_token(token)

    return {
        "submitted": bool(doc.get("franchisee_intake_submitted")),
        "contact_name": doc.get("contact_name") or "",
        "is_session_worker": bool(is_session_worker_lead(doc.get("appointment_type"))),
    }


@frappe.whitelist(allow_guest=True)
def upload_franchisee_intake_file(token=None, field=None):
    """
    Guest-accessible file upload for the DBS certificate / additional
    document - scoped to a valid, not-yet-submitted intake token so
    this can never become an open upload endpoint, and to a fixed
    allow-list of target fields. Stored private - only reachable by
    someone who already has permission to open this Client Lead.
    """
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
        "attached_to_doctype": LEAD_DOCTYPE,
        "attached_to_name": doc.name,
        "attached_to_field": fieldname,
        "is_private": 1,
        "content": uploaded_file.stream.read(),
    })
    file_doc.insert(ignore_permissions=True)

    frappe.db.set_value(LEAD_DOCTYPE, doc.name, fieldname, file_doc.file_url)
    frappe.db.commit()

    return {"url": file_doc.file_url}


@frappe.whitelist(allow_guest=True)
def submit_franchisee_intake(token=None, first_name=None, last_name=None, phone=None, gender=None,
                              dob=None, dbs_number=None, dbs_date_received=None, dbs_expiry_date=None,
                              qualifications=None, work_locations=None, public_liability_insurer=None,
                              indemnity_insurer=None, insurance_renewal_date=None):
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

    # Session-worker-only self-report fields (see the Safer Recruitment
    # Checklist) - always accepted but only ever shown/filled in on the
    # public form for a Session Worker lead (get_franchisee_intake_status's
    # is_session_worker flag), so these stay blank for a franchisee.
    if is_session_worker_lead(doc.get("appointment_type")):
        doc.franchisee_intake_qualifications = coalesce_str("qualifications", qualifications)
        doc.franchisee_intake_work_locations = coalesce_str("work_locations", work_locations)
        doc.franchisee_intake_public_liability_insurer = coalesce_str("public_liability_insurer", public_liability_insurer)
        doc.franchisee_intake_indemnity_insurer = coalesce_str("indemnity_insurer", indemnity_insurer)
        doc.franchisee_intake_insurance_renewal_date = coalesce_raw("insurance_renewal_date", insurance_renewal_date) or None

    doc.franchisee_intake_submitted = 1
    doc.franchisee_intake_submitted_at = frappe.utils.now_datetime()
    # Stage1's "Franchisee Intake + DBS/Insurance Submitted" milestone -
    # this repurposes the field/label that used to mean "Franchisee
    # Agreement Signed + Final Invoice Paid" (that step now lives on the
    # Client record itself, post-conversion - see the Franchise
    # Onboarding section on Client Details).
    doc.stage1_agreement_invoice_done = 1
    doc.stage1_agreement_invoice_date = frappe.utils.today()

    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {"ok": True}


@frappe.whitelist()
def get_franchisee_intake(name=None):
    """Franchisor-only: the submitted intake details + file links, for the Lead Details page."""
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
        "submitted_at": frappe.utils.format_datetime(doc.get("franchisee_intake_submitted_at"), "dd-MM-yyyy HH:mm") if doc.get("franchisee_intake_submitted_at") else "",
    }


# -------------------------------------------------------------------
# Sessional Worker Fees and Expectations Guide - the step after Intake/
# DBS on a Session Worker lead, before setting them up as a real Session
# Worker record. Same e-signing shape as the NDA/Intent above, but the
# second party is the lead's own sponsoring Coach rather than Ashley -
# the Coach's name is looked up and printed into the document the same
# way Ashley's is on the NDA (nothing for the coach to separately click
# or sign; agreeing to the rates and sending the link IS the coach's
# side of this). rate_1to1/rate_group/rate_workshop/invoicing_frequency/
# effective_date are the coach's own business terms, fixed the first
# time the link is generated for this worker, exactly like Intent's
# territory/deposit/end_date.
# -------------------------------------------------------------------

FEES_GUIDE_PRACTICE_DOCUMENT_TITLE = "Sessional Worker Fees and Expectations Guide"


def _fees_guide_template_text():
    name = frappe.db.get_value(
        "Practice Document", {"document_title": FEES_GUIDE_PRACTICE_DOCUMENT_TITLE}, "name"
    )
    if not name:
        frappe.throw(_("The Fees and Expectations Guide template hasn't been set up yet."))

    return frappe.db.get_value("Practice Document", name, "document_text") or ""


def _get_lead_by_fees_guide_token(token):
    token = (token or "").strip()
    if not token:
        frappe.throw(_("This link is invalid."))

    lead_name = frappe.db.get_value("Client Lead", {"fees_guide_token": token}, "name")
    if not lead_name:
        frappe.throw(_("This link is invalid."))

    return frappe.get_doc(LEAD_DOCTYPE, lead_name)


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
    """
    Franchisor-only: generates (the first time) or reuses this Session
    Worker lead's Fees and Expectations Guide sign link. The rate/
    frequency/effective_date terms are only used the first time - the
    sponsoring coach's own business terms for this worker, fixed from
    then on exactly like Intent's territory/deposit/end_date.
    """
    if not is_franchisor_user():
        frappe.throw(_("You do not have permission to do this."), frappe.PermissionError)

    name = coalesce_str("name", name)
    doc = ensure_lead_access(name)

    if not is_session_worker_lead(doc.get("appointment_type")):
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

    return {"url": get_url(f"/session-worker-fees-guide?token={doc.fees_guide_token}")}


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
    """Subject/message the compose modal pre-fills before send_fees_guide_link actually sends it."""
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
    """
    Franchisor-only: emails the Fees and Expectations Guide sign link,
    reusing get_fees_guide_sign_url's generate-or-reuse logic. subject/
    message default to the standard wording when left blank.
    """
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
        "now": True,
        "reply_to": reply_to,
    }

    cc_list = parse_email_list(cc)
    if cc_list:
        kwargs["cc"] = cc_list

    frappe.sendmail(**kwargs)

    doc.fees_guide_sent_at = frappe.utils.now_datetime()
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {
        "ok": 1,
        "url": fees_guide_url,
        "sent_at": frappe.utils.format_datetime(doc.fees_guide_sent_at, "dd-MM-yyyy HH:mm"),
    }


@frappe.whitelist()
def get_signed_fees_guide(name=None):
    """Franchisor-only: the frozen signed snapshot plus its audit trail, for the Lead Details page."""
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
    """Guest-accessible - what the public /session-worker-fees-guide page shows."""
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

    return {"ok": True}


@frappe.whitelist()
def get_session_worker_setup_url(name=None):
    """
    Franchisor-only: a deep link to a pre-filled New Session Worker form
    in Desk. Session Worker is a doctype this app doesn't own (unlike
    Client Lead) - see session_workers.py's defensive field-name lookups
    - so rather than guess at its mandatory fields with an auto-insert
    that could fail unpredictably, Ashley finishes creating the record
    by hand in Desk, with what this lead already collected pre-filled.
    """
    if not is_franchisor_user():
        frappe.throw(_("You do not have permission to do this."), frappe.PermissionError)

    name = coalesce_str("name", name)
    doc = ensure_lead_access(name)

    if not is_session_worker_lead(doc.get("appointment_type")):
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
    query = "&".join(
        f"{key}={quote(str(value))}" for key, value in params.items() if value
    )

    return {"url": get_url(f"/app/session-worker/new?{query}" if query else "/app/session-worker/new")}


@frappe.whitelist()
def set_session_worker_link(name=None, session_worker=None):
    """
    Franchisor-only: records which Session Worker record this lead
    became (created manually in Desk - see get_session_worker_setup_url
    above) and ticks the final "Set Up As Session Worker" milestone.
    Clearing session_worker unticks it again, in case the wrong record
    was linked by mistake.
    """
    if not is_franchisor_user():
        frappe.throw(_("You do not have permission to do this."), frappe.PermissionError)

    name = coalesce_str("name", name)
    session_worker = coalesce_str("session_worker", session_worker)
    doc = ensure_lead_access(name)

    if not is_session_worker_lead(doc.get("appointment_type")):
        frappe.throw(_("This lead isn't a Session Worker."))

    if session_worker and not frappe.db.exists("Session Worker", session_worker):
        frappe.throw(_("That Session Worker record doesn't exist."))

    doc.converted_session_worker = session_worker or None
    doc.sw_setup_done = 1 if session_worker else 0
    doc.sw_setup_date = frappe.utils.today() if session_worker else None
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {"ok": True, "converted_session_worker": doc.converted_session_worker}


@frappe.whitelist()
def add_lead_note(name=None, note=None, note_date=None):
    name = coalesce_str("name", name)
    note = coalesce_str("note", note)
    note_date = coalesce_str("note_date", note_date)

    if not note:
        frappe.throw(_("Please enter a note."))

    doc = ensure_lead_access(name)

    doc.append("notes", {
        "note": note,
        "note_date": note_date or frappe.utils.today(),
        "added_by": frappe.session.user,
        "added_on": now_datetime(),
    })

    # doc.save() re-validates the whole Client Lead, not just the note row
    # just appended - if some mandatory field (e.g. a "Client" field added
    # to the Notes table via Customize Form at some point, on a site
    # that's drifted from what's in this repo) can't be filled in before
    # conversion, adding a note must not be blocked by it. This doc was
    # already valid before this call; the only new thing here is the note.
    doc.flags.ignore_mandatory = True
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {"ok": True, "notes": _get_lead_notes(doc)}


def _intake_url(doc):
    # No query param to pre-fill - the submission is matched back to this
    # Client Lead by name afterwards instead (see
    # sync_intake_doctype_submission()), since there's no field on the Web
    # Form a guest could sensibly be asked to fill in to link the two up.
    # A podcast-booking lead gets the Podcast Guest Booking Form instead of
    # the usual client intake form - it asks nothing relevant to signing up
    # a client, and vice versa.
    if is_podcast_lead(doc.get("appointment_type")):
        return get_url(f"/{PODCAST_ROUTE}")
    return get_url(f"/{INTAKE_ROUTE}/new")


def _intake_email_context(doc):
    return {
        "contact_name": frappe.utils.escape_html(doc.contact_name or ""),
        "client_name": frappe.utils.escape_html(doc.client_name or "your young person"),
        "intake_url": _intake_url(doc),
    }


_INTAKE_FALLBACK_MESSAGE = (
    "Hi {{ contact_name }},\n"
    "\n"
    "Thanks for speaking with us. Please complete the short form below "
    "so we can get {{ client_name }} set up:\n"
    "\n"
    "{{ intake_url }}"
)

_PODCAST_FALLBACK_MESSAGE = (
    "Hi {{ contact_name }},\n"
    "\n"
    "Thanks for your interest in joining The Resilient Kid Podcast! Please complete "
    "the short form below so we can start planning your episode:\n"
    "\n"
    "{{ intake_url }}"
)


def _render_intake_email(doc):
    if is_podcast_lead(doc.get("appointment_type")):
        return render_email(
            PODCAST_INVITE_TEMPLATE,
            _intake_email_context(doc),
            fallback_subject="Your Resilient Kid Podcast guest form",
            fallback_message=_PODCAST_FALLBACK_MESSAGE,
        )

    return render_email(
        INTAKE_INVITE_TEMPLATE,
        _intake_email_context(doc),
        fallback_subject="Your Resilient Kid intake form",
        fallback_message=_INTAKE_FALLBACK_MESSAGE,
    )


@frappe.whitelist()
def get_intake_email_defaults(name=None):
    """
    Subject/message the compose modal pre-fills so a coach can see and edit
    the intake invite before it's actually sent, instead of
    send_intake_form firing it straight away.
    """
    doc = ensure_lead_access(coalesce_str("name", name))

    if not doc.contact_email:
        frappe.throw(_("This lead has no contact email address to send the intake form to."))

    subject, message = _render_intake_email(doc)

    return {
        "subject": subject,
        "message": message,
        "recipient": doc.contact_email,
        "intake_url": _intake_url(doc),
    }


@frappe.whitelist()
def send_intake_form(name=None, subject=None, message=None, cc=None, sender=None, reply_to=None):
    doc = ensure_lead_access(coalesce_str("name", name))

    if not doc.contact_email:
        frappe.throw(_("This lead has no contact email address to send the intake form to."))

    intake_url = _intake_url(doc)
    subject = (subject or "").strip()
    message = (message or "").strip()

    # Default to whoever's actually sending this, not the shared outgoing
    # account - otherwise every reply lands in office's inbox regardless
    # of which coach actually emailed them.
    reply_to = (reply_to or "").strip() or frappe.session.user

    try:
        if not subject or not message:
            rendered_subject, rendered_message = _render_intake_email(doc)
            subject = subject or rendered_subject
            message = message or rendered_message

        kwargs = {
            "recipients": [doc.contact_email],
            "subject": subject,
            "message": plain_text_to_email_html(message),
            "now": True,
            "reply_to": reply_to,
        }

        cc_list = parse_email_list(cc)
        if cc_list:
            kwargs["cc"] = cc_list

        # Always the shared office account, never an individual coach's
        # own (Google-OAuth-connected, so intermittently expiring) Email
        # Account - see email_templates.get_email_sender_options().
        # reply_to above is what still routes a client's reply to the
        # coach personally.

        frappe.sendmail(**kwargs)
        email_sent = True
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Send Intake Form Email Failed")
        email_sent = False

    doc.status = "Intake Sent"
    doc.intake_sent_on = now_datetime()
    doc.intake_email_status = "Sent" if email_sent else "Failed"

    # Resending (this lead already had a completed intake) reopens it for
    # a fresh submission - clearing intake_completed_on hides the Convert
    # to Client button again until the corrected answers come back in, and
    # lets sync_intake_doctype_submission's was_already_complete check
    # treat the next submission as a genuine completion again, so the
    # coach gets notified and Convert to Client re-appears with the
    # corrected data rather than the old, mistaken answers.
    doc.intake_completed_on = None
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {"ok": True, "intake_url": intake_url, "email_sent": email_sent, "status": doc.status}


def _client_request_notification_exists(reference_name, recipient_user, reference_doctype=None):
    """
    True if a "Client Request" notification for this record has already
    gone to this recipient - guards _notify_intake_completed (and
    _notify_intake_match_failed) against double-notifying, since Intake
    Doctype is hooked on both after_insert and on_update, which both fire
    for a single fresh submission. reference_doctype defaults to
    LEAD_DOCTYPE (the original caller, _notify_intake_completed, always
    references a Client Lead); _notify_intake_match_failed passes
    INTAKE_DOCTYPE instead, since it has no Lead to reference.
    """
    if not frappe.db.exists("DocType", "Dashboard Conversation"):
        return False

    conversation_names = frappe.get_all(
        "Dashboard Conversation",
        filters={
            "reference_doctype": reference_doctype or LEAD_DOCTYPE,
            "reference_name": reference_name,
            "conversation_type": "Client Request",
        },
        pluck="name",
        ignore_permissions=True,
    )

    if not conversation_names:
        return False

    return bool(frappe.get_all(
        "Dashboard Conversation Recipient",
        filters={"parent": ["in", conversation_names], "recipient_user": recipient_user},
        limit_page_length=1,
        ignore_permissions=True,
    ))


def _notify_intake_completed(doc):
    """
    doc is the Client Lead. Fires the "intake form completed" notification
    to its coach - shared by anything that marks a Lead's intake complete
    (currently just sync_intake_doctype_submission below).

    Franchisor admins are only notified when there's no coach to notify
    instead (unassigned lead, or a Coach record with no linked
    user/coach_email) - every coach's own properly-assigned clients notify
    only that coach, not every franchisor admin as well.
    """
    notification_message = f"{doc.client_name} - intake form has been completed. Review and convert to a client."
    coach_user = ""

    if doc.coach:
        coach_user = frappe.db.get_value("Coach", doc.coach, "user") or frappe.db.get_value(
            "Coach", doc.coach, "coach_email"
        )

    if coach_user:
        if _client_request_notification_exists(doc.name, coach_user):
            return

        # Best-effort - the intake submission itself is already saved,
        # a broken notification config must not make it look like the
        # submission failed.
        try:
            create_trk_notification(
                recipient_user=coach_user,
                notification_type="Client Request",
                message=notification_message,
                priority="High",
                reference_doctype=LEAD_DOCTYPE,
                reference_name=doc.name,
            )
        except Exception:
            frappe.log_error(frappe.get_traceback(), "Intake Submission - Coach Notification Failed")
        return

    if doc.coach:
        # The lead has a coach assigned, but that Coach record has no
        # linked user/coach_email to notify - this would otherwise fail
        # completely silently (no exception, nothing to see in the Error
        # Log), so it's logged explicitly to be diagnosable.
        frappe.log_error(
            f"Lead {doc.name}: Coach {doc.coach} has no linked user or coach_email - notifying franchisor instead.",
            "Intake Submission - No Coach Recipient",
        )

    # Reached only when there's no coach to rely on - genuinely unassigned,
    # or a misconfigured Coach record - so someone still needs to see this
    # rather than it silently disappearing.
    for admin_user in FRANCHISOR_USERS:
        if not frappe.db.exists("User", admin_user):
            continue

        if _client_request_notification_exists(doc.name, admin_user):
            continue

        try:
            create_trk_notification(
                recipient_user=admin_user,
                notification_type="Client Request",
                message=notification_message,
                priority="High",
                reference_doctype=LEAD_DOCTYPE,
                reference_name=doc.name,
            )
        except Exception:
            frappe.log_error(frappe.get_traceback(), "Intake Submission - Admin Notification Failed")


def _intake_doctype_display_names(doc):
    """
    Candidate person-names straight from the guest's own intake submission -
    no separate field for anyone (guest or coach) to fill in, since a guest
    filling out a public form has no way to know which internal record is
    "theirs". Tried against Client Lead's own contact_name/client_name.
    """
    names = []

    young_person_last = (doc.get("young_person_last_name") or "").strip()
    for first_fieldname in ("young_person_preferred_name", "young_person_first_name"):
        # Preferred name first - Client Lead's own client_name is commonly
        # the nickname a family actually goes by (e.g. "Zac"), not the
        # formal first name on the intake form (e.g. "Zackary").
        first = (doc.get(first_fieldname) or "").strip()
        full = " ".join(part for part in [first, young_person_last] if part)
        if full:
            names.append(full)

    adult_last = (doc.get("adult_last_name") or "").strip()
    for first_fieldname in ("adult_preferred_name", "adult_first_name"):
        first = (doc.get(first_fieldname) or "").strip()
        full = " ".join(part for part in [first, adult_last] if part)
        if full:
            names.append(full)

    family_first = (doc.get("family_first") or "").strip()
    family_last = (doc.get("family_last") or "").strip()
    family_full = " ".join(part for part in [family_first, family_last] if part)
    if family_full:
        names.append(family_full)

    for fieldname in ("signature_name", "primary_caregiver_full_name"):
        value = (doc.get(fieldname) or "").strip()
        if value:
            names.append(value)

    return names


def _intake_doctype_display_emails(doc):
    """
    Every email address the guest's own submission actually collected
    (INTAKE_EMAIL_FIELDS, across every client_type section) - tried
    against Client Lead's own contact_email, which is exactly the address
    send_intake_form() sent the invite to in the first place. A much
    stronger signal than a name: two different families essentially never
    share an email address, whereas a name can be a nickname, a typo, or
    differently spaced/capitalised from what's stored on the Lead.
    """
    emails = []

    for fieldname in INTAKE_EMAIL_FIELDS:
        value = (doc.get(fieldname) or "").strip()
        if value:
            emails.append(value)

    return emails


def _normalize_match_text(value):
    """
    Trimmed, internal-whitespace-collapsed, case-folded - so "Zac Smith",
    " zac  smith", and "ZAC SMITH" all compare equal, instead of the old
    byte-for-byte match that broke on the first difference in spacing or
    capitalisation between what a guest typed and what's stored on the
    Lead.
    """
    return re.sub(r"\s+", " ", (value or "").strip()).casefold()


def _open_client_leads_for_matching():
    """
    Every not-yet-converted Client Lead's own identity fields, fetched
    once and compared in Python (normalised - see _normalize_match_text)
    rather than one exact-match DB filter per candidate name/email.
    """
    return frappe.get_all(
        LEAD_DOCTYPE,
        filters={"status": ["!=", "Converted"]},
        fields=["name", "contact_name", "client_name", "contact_email"],
        limit_page_length=5000,
        ignore_permissions=True,
    )


def _find_client_lead_by_emails(emails):
    """
    Whichever not-yet-converted Client Lead has a contact_email matching
    (normalised) any of emails. Same "give up rather than guess" contract
    as _find_client_lead_by_names below - None with a reason unless
    exactly one match is found. Always also returns whatever candidates
    it found (even 0 or 2+) so a caller that can't get a confident single
    match can still see who was in the running - e.g. to notify the
    coach the near-miss(es) belong to instead of guessing which Lead.
    """
    normalized = {_normalize_match_text(email) for email in (emails or []) if email}

    if not normalized:
        return None, "the intake submission has no usable email to match on", []

    candidates = sorted({
        row.name
        for row in _open_client_leads_for_matching()
        if row.get("contact_email") and _normalize_match_text(row["contact_email"]) in normalized
    })

    if not candidates:
        return None, f"no not-yet-converted {LEAD_DOCTYPE} matches any of {sorted(normalized)!r} by email", []

    if len(candidates) > 1:
        return None, f"{len(candidates)} different {LEAD_DOCTYPE} records match {sorted(normalized)!r} by email - can't tell which one", candidates

    return candidates[0], None, candidates


def _find_client_lead_by_names(display_names):
    """
    Whichever not-yet-converted Client Lead has a contact_name or
    client_name matching (normalised - see _normalize_match_text) any of
    display_names. Returns None (and lets the caller log why) unless
    exactly one match is found, rather than risk silently syncing onto
    the wrong person's record. Always also returns whatever candidates it
    found - see _find_client_lead_by_emails above for why.
    """
    normalized = {_normalize_match_text(name) for name in (display_names or []) if name}

    if not normalized:
        return None, "the intake submission has no usable name to match on", []

    candidates = sorted({
        row.name
        for row in _open_client_leads_for_matching()
        if (row.get("contact_name") and _normalize_match_text(row["contact_name"]) in normalized)
        or (row.get("client_name") and _normalize_match_text(row["client_name"]) in normalized)
    })

    if not candidates:
        return None, f"no not-yet-converted {LEAD_DOCTYPE} matches any of {sorted(normalized)!r} by name", []

    if len(candidates) > 1:
        return None, f"{len(candidates)} different {LEAD_DOCTYPE} records match {sorted(normalized)!r} by name - can't tell which one", candidates

    return candidates[0], None, candidates


def _find_client_lead_for_intake_submission(doc):
    """
    Email first (_find_client_lead_by_emails) - it's exactly what the
    intake invite was sent to and essentially never collides between two
    different families, unlike a name. Falls back to name matching
    (_find_client_lead_by_names) only when no email match is found, so
    older/simpler leads with no email captured on their client_type
    section still resolve the way they always did.

    Returns (lead_name, reason, candidate_lead_names) - candidate_lead_names
    is every Lead either step turned up (matched or not, confident or
    ambiguous), used by _notify_intake_match_failed to route a failed
    match to the coach it's actually about instead of broadcasting.
    """
    email_lead, email_reason, email_candidates = _find_client_lead_by_emails(_intake_doctype_display_emails(doc))
    if email_lead:
        return email_lead, None, [email_lead]

    name_lead, name_reason, name_candidates = _find_client_lead_by_names(_intake_doctype_display_names(doc))
    if name_lead:
        return name_lead, None, [name_lead]

    candidates = sorted(set(email_candidates) | set(name_candidates))
    return None, f"by email: {email_reason}; by name: {name_reason}", candidates


# Every field _intake_doctype_display_emails/_intake_doctype_display_names
# read off an Intake Doctype submission - fetched once by
# _open_intake_submissions_for_matching so _find_intake_submission_for_lead
# can reuse those same two helpers on a bulk-fetched row exactly as they're
# used on a live submission doc.
INTAKE_SUBMISSION_MATCH_FIELDS = INTAKE_EMAIL_FIELDS + [
    "young_person_first_name", "young_person_preferred_name", "young_person_last_name",
    "adult_first_name", "adult_preferred_name", "adult_last_name",
    "family_first", "family_last", "signature_name", "primary_caregiver_full_name",
]


def _open_intake_submissions_for_matching():
    """
    Every Intake Doctype submission's own identity fields, fetched once
    for _find_intake_submission_for_lead to match against a stuck Lead -
    the reverse direction of _open_client_leads_for_matching above.
    """
    if not frappe.db.exists("DocType", INTAKE_DOCTYPE):
        return []

    intake_meta = frappe.get_meta(INTAKE_DOCTYPE)
    fields = ["name"] + [
        fieldname for fieldname in INTAKE_SUBMISSION_MATCH_FIELDS if intake_meta.has_field(fieldname)
    ]

    return frappe.get_all(INTAKE_DOCTYPE, fields=fields, limit_page_length=5000, ignore_permissions=True)


def _find_intake_submission_for_lead(lead_doc):
    """
    Reverse of _find_client_lead_for_intake_submission - given a stuck
    Lead (intake_sent_on set, intake_completed_on not, per the "Sent, not
    yet completed" status the Intake Forms report shows), looks for the
    Intake Doctype submission that actually belongs to it. Used by
    resync_stuck_intake_forms to catch up submissions that came in (or
    were already sitting there, already fully answered by the guest)
    before the matching fix existed - deploying the fix doesn't
    retroactively re-run the hook for a submission that already fired and
    failed to match once, so without this those Leads would stay stuck
    forever. Email first, name as a fallback - same priority and same
    normalised comparison as the forward direction.
    """
    lead_email = _normalize_match_text(lead_doc.contact_email or "")
    lead_names = {
        _normalize_match_text(name)
        for name in (lead_doc.contact_name, lead_doc.client_name)
        if name
    }

    if not lead_email and not lead_names:
        return None, "this lead has no contact_email or contact_name/client_name to match on"

    email_candidates = []
    name_candidates = []

    for row in _open_intake_submissions_for_matching():
        row_emails = {_normalize_match_text(email) for email in _intake_doctype_display_emails(row) if email}
        if lead_email and lead_email in row_emails:
            email_candidates.append(row.name)
            continue

        row_names = {_normalize_match_text(name) for name in _intake_doctype_display_names(row) if name}
        if lead_names & row_names:
            name_candidates.append(row.name)

    if len(email_candidates) == 1:
        return email_candidates[0], None

    if email_candidates:
        return None, f"{len(email_candidates)} intake submissions match this lead's email - can't tell which one"

    if len(name_candidates) == 1:
        return name_candidates[0], None

    if name_candidates:
        return None, f"{len(name_candidates)} intake submissions match this lead's name - can't tell which one"

    return None, "no intake submission matches this lead's email or name"


@frappe.whitelist()
def resync_stuck_intake_forms(confirm=0):
    """
    Read-only by default (confirm=0) - reports every not-yet-converted
    Client Lead currently stuck showing "Sent, not yet completed" (the
    Intake Forms report's own status) that actually has a matching,
    completed Intake Doctype submission sitting unlinked, and what it
    would apply. confirm=1 actually applies it, via the exact same
    _apply_intake_submission_to_lead the live hook uses.

    This only ever acts on an unambiguous single match per Lead (see
    _find_intake_submission_for_lead) - a Lead with no match, or more than
    one candidate submission, is left alone and reported separately
    rather than guessed at.
    """
    ensure_office_user()

    confirm = int(confirm or 0)

    stuck_leads = frappe.get_all(
        LEAD_DOCTYPE,
        filters={
            "status": ["!=", "Converted"],
            "intake_sent_on": ["is", "set"],
            "intake_completed_on": ["is", "not set"],
        },
        fields=["name", "contact_name", "client_name", "contact_email"],
        limit_page_length=1000,
        ignore_permissions=True,
    )

    resynced = []
    unmatched = []

    for row in stuck_leads:
        lead_doc = frappe.get_doc(LEAD_DOCTYPE, row.name)
        intake_name, reason = _find_intake_submission_for_lead(lead_doc)

        if not intake_name:
            unmatched.append({"lead": row.name, "reason": reason})
            continue

        resynced.append({"lead": row.name, "intake": intake_name})

        if confirm:
            try:
                intake_doc = frappe.get_doc(INTAKE_DOCTYPE, intake_name)
                _apply_intake_submission_to_lead(intake_doc, row.name)
            except Exception:
                frappe.log_error(frappe.get_traceback(), f"Resync Stuck Intake Forms - {row.name} - {intake_name}")

    if confirm:
        frappe.db.commit()

    return {
        "confirmed": bool(confirm),
        "resynced": resynced,
        "unmatched": unmatched,
    }


# Deliberately narrower than FRANCHISOR_USERS (which also includes
# hq@theresilientkid.co.uk and ashley@theresilientkid.co.uk) - a match
# failure with no identifiable coach still needs a human to see it, but
# not the wider franchisor broadcast list, since this is a single
# unrelated coach's client and not something every franchisor-level inbox
# needs visibility into.
INTAKE_MATCH_FAILED_FALLBACK_USER = "office@theresilienthub.co.uk"


def _coach_user_for_lead(lead_name):
    coach = frappe.db.get_value(LEAD_DOCTYPE, lead_name, "coach")
    if not coach:
        return None

    return frappe.db.get_value("Coach", coach, "user") or frappe.db.get_value("Coach", coach, "coach_email")


def _notify_intake_match_failed(doc, reason, candidate_lead_names=None):
    """
    A completed intake submission that couldn't be matched to any Client
    Lead used to only ever show up in the Error Log - nobody actively
    watches that, so a fully completed form could sit invisible
    indefinitely with nothing to convert. Someone now gets a notification
    instead, pointing at the raw Intake Doctype record so it can be
    reviewed and linked/converted by hand without waiting to stumble
    across the Error Log entry.

    Routing is deliberately narrow, not a franchisor-wide broadcast - this
    is one coach's client, and other coaches/franchisor staff have no
    reason to see it:
    - If every candidate Lead the match considered (an ambiguous 2+ match,
      or one rejected only for already being Converted) belongs to the
      same coach, that coach alone is notified - it's squarely their own
      client.
    - Otherwise (no candidates at all, or candidates split across more
      than one coach - genuinely nothing to attribute this to) it falls
      back to INTAKE_MATCH_FAILED_FALLBACK_USER alone, not the full
      FRANCHISOR_USERS list.
    """
    message = (
        f"An intake form was submitted but couldn't be automatically matched to a lead ({reason}). "
        f"Open {INTAKE_DOCTYPE} {doc.name} in the Desk to review the answers and create or link the client by hand."
    )

    recipient = None
    coach_users = {
        _coach_user_for_lead(lead_name) for lead_name in (candidate_lead_names or [])
    }
    coach_users.discard(None)
    coach_users.discard("")

    if len(coach_users) == 1:
        recipient = next(iter(coach_users))

    if not recipient:
        recipient = INTAKE_MATCH_FAILED_FALLBACK_USER

    if not frappe.db.exists("User", recipient):
        return

    if _client_request_notification_exists(doc.name, recipient, reference_doctype=INTAKE_DOCTYPE):
        return

    try:
        create_trk_notification(
            recipient_user=recipient,
            notification_type="Client Request",
            message=message,
            priority="High",
            reference_doctype=INTAKE_DOCTYPE,
            reference_name=doc.name,
        )
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Intake Submission - Match Failed Notification Failed")


# "headline" fields (contact_name/contact_email/contact_mobile/client_name/
# client_age/postal_code/enquiry_reason/how_heard/consent_given) aren't part
# of INTAKE_DETAIL_FIELDS, but if Intake Doctype happens to carry its own
# same-named versions (it's the guest's own submission, so it may be the
# more accurate/complete source - e.g. the Lead was created with only a name
# before the intake link was ever sent), sync those too. Convert to Client
# reads contact details straight off these Client Lead fields to build the
# Contact.
LEAD_HEADLINE_FIELDS = [
    "contact_name", "contact_email", "contact_mobile", "client_name",
    "client_age", "postal_code", "enquiry_reason", "how_heard", "consent_given",
]


def _apply_intake_submission_to_lead(doc, lead_name):
    """
    Copies one Intake Doctype submission's answers onto its
    already-identified Client Lead - shared by the live after_insert/
    on_update hook (sync_intake_doctype_submission) and
    resync_stuck_intake_forms's bulk repair, so both go through exactly
    the same field-copying/completion logic. Copies every field name
    Intake Doctype and Client Lead have in common (INTAKE_DETAIL_FIELDS -
    same names on both, by design) plus LEAD_HEADLINE_FIELDS, so the rest
    of this app (PDF generation, the Files tab, the "Submitted Intake
    Form" section, Convert to Client) keeps working exactly as it already
    does off the Client Lead's own fields, without needing to know
    anything about Intake Doctype specifically.

    Returns True if the Lead was newly completed or otherwise changed by
    this submission, False if it was a no-op (already Converted, or an
    already-complete Lead with nothing new to copy).
    """
    lead_doc = frappe.get_doc(LEAD_DOCTYPE, lead_name)

    if lead_doc.status == "Converted":
        return False

    lead_meta = frappe.get_meta(LEAD_DOCTYPE)
    intake_meta = frappe.get_meta(INTAKE_DOCTYPE)
    changed = False

    for fieldname in INTAKE_DETAIL_FIELDS + LEAD_HEADLINE_FIELDS:
        if not intake_meta.has_field(fieldname) or not lead_meta.has_field(fieldname):
            continue

        value = doc.get(fieldname)
        if value in (None, ""):
            continue

        if fieldname == "main_therapy_location":
            # Frappe validates Link fields against a real existing record on
            # save regardless of ignore_permissions - a stale/renamed value
            # would raise LinkValidationError and abort the whole save. Same
            # class of bug already guarded against for Link fields
            # elsewhere in this app (calendar.py).
            if not (frappe.db.exists("DocType", "Therapy Location") and frappe.db.exists("Therapy Location", value)):
                frappe.log_error(
                    f"Lead {lead_doc.name}: intake submitted main_therapy_location={value!r}, "
                    "which isn't a real Therapy Location - left unset rather than blocking the save.",
                    "Intake Submission - Invalid Therapy Location",
                )
                continue

        lead_doc.set(fieldname, value)
        changed = True

    # Family Session: the contact and client are the same person/family,
    # unlike every other client_type (a parent contacting on behalf of a
    # young person, a school's admin on behalf of the school, ...), where
    # they're normally different. contact_name/contact_email/contact_mobile
    # are what drive Contact creation on conversion regardless of
    # client_type, so refresh them from the family's own submitted answers
    # here rather than leaving them as whatever was typed in when this Lead
    # was first quickly created.
    if lead_doc.client_type == "Family Session":
        family_first = (doc.get("family_first") or "").strip()
        family_last = (doc.get("family_last") or "").strip()
        family_full_name = " ".join(part for part in [family_first, family_last] if part)

        if family_full_name and lead_meta.has_field("contact_name"):
            lead_doc.contact_name = family_full_name
            changed = True

        if doc.get("family_email") and lead_meta.has_field("contact_email"):
            lead_doc.contact_email = doc.get("family_email")
            changed = True

        if doc.get("family_mobile") and lead_meta.has_field("contact_mobile"):
            lead_doc.contact_mobile = doc.get("family_mobile")
            changed = True

    was_already_complete = bool(lead_doc.intake_completed_on)

    if changed or not was_already_complete:
        lead_doc.intake_completed_on = lead_doc.intake_completed_on or now_datetime()
        lead_doc.save(ignore_permissions=True)
        frappe.db.commit()

    if not was_already_complete:
        _notify_intake_completed(lead_doc)

    return changed or not was_already_complete


def sync_intake_doctype_submission(doc, method=None):
    """
    Hook target (see hooks.py doc_events["Intake Doctype"]) - fires whenever
    someone submits or edits the real "Intake Doctype" Web Form (owned and
    built directly in Frappe Desk, not by this app). doc is the Intake
    Doctype record itself - there's no link field to a Client Lead (the
    "created_lead" field turned out to point at a separate, unrelated Frappe
    CRM "Lead" doctype, and isn't something a public guest form-filler could
    ever sensibly populate anyway), so the Client Lead to sync onto is found
    by matching the email address (and, failing that, the name) the guest
    actually typed in (see _find_client_lead_for_intake_submission), and the
    actual field-copying is shared with resync_stuck_intake_forms via
    _apply_intake_submission_to_lead.
    """
    lead_name, reason, candidate_lead_names = _find_client_lead_for_intake_submission(doc)

    if not lead_name:
        frappe.log_error(
            f"Intake Doctype {doc.name}: {reason}.",
            "Intake Submission - Client Lead Match Failed",
        )
        _notify_intake_match_failed(doc, reason, candidate_lead_names)
        return

    _apply_intake_submission_to_lead(doc, lead_name)


def _split_name(full_name):
    parts = (full_name or "").strip().split(" ", 1)
    first = parts[0] if parts else ""
    last = parts[1] if len(parts) > 1 else ""
    return first, last


def _format_intake_notes(doc):
    """
    A few things the intake form collects have no single matching field on
    Client - either because Client has nothing for them at all (why they're
    getting in touch, how they heard about us, consent), or because the
    obvious target is a child table (Session Notes) whose real field names
    aren't known here (Client lives in a different app). Consolidating
    everything into Additional Comments is a deliberate simplification -
    safer than guessing at an unfamiliar child table's schema and risking a
    failed conversion.
    """
    lines = []
    if doc.enquiry_reason:
        lines.append(f"Why they're contacting us: {doc.enquiry_reason}")
    if doc.how_heard:
        lines.append(f"How they heard about us: {doc.how_heard}")
    if doc.consent_given:
        lines.append("Consent to be contacted: Yes")
    if doc.support_required:
        lines.append(f"What support they'd like: {doc.support_required}")
    if doc.siblings:
        lines.append(f"Siblings: {doc.siblings}")
    if doc.school_support_required:
        lines.append(f"Support the school is interested in: {doc.school_support_required}")
    if doc.company_support_required:
        lines.append(f"Support the company is interested in: {doc.company_support_required}")
    if doc.doctor_details:
        lines.append(f"GP / Doctor details: {doc.doctor_details}")
    if doc.therapy_location_not_listed and doc.new_therapy_location_details:
        lines.append(f"Therapy location (not in the list): {doc.new_therapy_location_details}")
    if doc.education_establishment:
        lines.append(f"Education establishment: {doc.education_establishment}")
    if doc.year_group_teacher:
        lines.append(f"Class / year group / teacher: {doc.year_group_teacher}")
    if doc.sendco_involved:
        lines.append(f"SENDCO department involved: {doc.sendco_involved}")
    if doc.education_contact:
        lines.append(f"Other education contact: {doc.education_contact}")
    if doc.family_dr:
        sent_on = frappe.utils.formatdate(doc.intake_sent_on) if doc.intake_sent_on else "unknown date"
        lines.append(f"GP / Doctor details: {doc.family_dr} (intake form sent {sent_on})")
    if doc.family_get:
        lines.append(f"What they'd like to get from sessions: {doc.family_get}")
    if doc.family_tried:
        lines.append(f"What they've already tried: {doc.family_tried}")
    if doc.family_siblings:
        lines.append(f"Siblings: {doc.family_siblings}")
    if doc.family_challenge:
        lines.append(f"Main challenges: {doc.family_challenge}")

    if not lines:
        return ""

    return "<p><strong>From intake form:</strong></p><p>" + "</p><p>".join(lines) + "</p>"


def _client_field_values(doc):
    """
    Maps the detailed intake answers onto real Client field names, per
    doc.client_type (which section of the intake form was filled in). An
    empty dict means there's no detailed intake data (older/simpler leads,
    or a lead created without going through the public form) - conversion
    falls back to the always-present headline fields in that case.
    """
    client_type = doc.client_type or ""
    values = {}

    if client_type in ("Kid", "Teen", "Uni Student"):
        values.update({
            "name1": doc.young_person_first_name,
            "last_name": doc.young_person_last_name,
            "preferred_name": doc.young_person_preferred_name,
            "mobile": doc.young_person_mobile,
            "email": doc.young_person_email,
            "date_of_birth": doc.young_person_date_of_birth,
            "pronouns": doc.young_person_pronouns,
            "sex": doc.young_person_sex,
            "gender_identity": doc.young_person_gender_identity,
            "address": doc.young_person_address_line_1,
            "city": doc.young_person_city,
            "zip_code": doc.young_person_postalcode,
        })
    elif client_type == "Adult":
        values.update({
            "name1": doc.adult_first_name,
            "last_name": doc.adult_last_name,
            "preferred_name": doc.adult_preferred_name,
            "address": doc.adult_address_1,
            "city": doc.adult_city,
            "zip_code": doc.adult_postalcode,
            "mobile": doc.adult_mobile,
            "email": doc.adult_email,
            "pronouns": doc.adult_pronouns,
            "sex": doc.adult_sex,
            "gender_identity": doc.adult_gender_identity,
            "date_of_birth": doc.adult_date_of_birth,
        })
    elif client_type == "School":
        values.update({
            "name1": doc.school_name,
            "email": doc.school_contact_email,
            "mobile": doc.school_mobile,
            "address": doc.school_address_line_1,
            "city": doc.school_city,
            "zip_code": doc.school_postalcode,
        })
    elif client_type == "Company":
        values.update({
            "name1": doc.company_name,
            "email": doc.company_contact_email,
            "mobile": doc.company_mobile,
            "address": doc.company_address_line_1,
            "city": doc.company_city,
            "zip_code": doc.company_postalcode,
        })
    elif client_type == "Family Session":
        values.update({
            "name1": doc.family_first,
            "last_name": doc.family_last,
            "email": doc.family_email,
            "mobile": doc.family_mobile,
            "address": doc.family_address,
            "city": doc.family_city,
            "zip_code": doc.family_zip,
        })

    if client_type in ("Kid", "Teen", "Uni Student", "Adult"):
        values.update({
            "allergies": doc.allergies,
            "neurodiverse_status": doc.neurodiverse_status,
            "neurodiverse_information": doc.neurodiverse_information,
            "main_therapy_location": doc.main_therapy_location,
        })

    return {k: v for k, v in values.items() if v}


def _create_supplementary_contact(full_name, email, mobile, primary_contact_name):
    """
    Creates an extra Contact for a named person the intake form collected
    (caregiver/next of kin/school or company contact/billing contact) -
    skipped if blank, or if it's clearly the same person as the lead's own
    top-level contact (avoids an obvious duplicate Contact record).
    """
    full_name = (full_name or "").strip()
    if not full_name:
        return None

    if full_name.lower() == (primary_contact_name or "").strip().lower():
        return None

    first, last = _split_name(full_name)
    contact = frappe.new_doc("Contact")
    contact.first_name = first
    if last:
        contact.last_name = last
    if email:
        contact.append("email_ids", {"email_id": email, "is_primary": 1})
    if mobile:
        contact.append("phone_nos", {"phone": mobile, "is_primary_mobile_no": 1})
    contact.insert(ignore_permissions=True)
    return contact.name


def _extra_contacts_for_lead(doc):
    """
    (label, full_name, email, mobile) tuples for every additional named
    person the intake form may have collected, beyond the lead's own
    top-level contact - which of these actually turn into new Contact
    records depends on whether a name was given (see
    _create_supplementary_contact).
    """
    client_type = doc.client_type or ""
    extras = []

    if client_type in ("Kid", "Teen", "Uni Student"):
        extras.append(("Primary Caregiver", doc.primary_caregiver_full_name, doc.primary_caregiver_email, doc.primary_caregiver_mobile))
        extras.append(("Secondary Caregiver", doc.secondary_caregiver_full_name, doc.secondary_caregiver_email, doc.secondary_caregiver_mobile))
    elif client_type == "Adult":
        extras.append(("Next of Kin", doc.next_of_kin_name, doc.next_of_kin_email, doc.next_of_kin_mobile))
    elif client_type == "School":
        extras.append(("School Contact", doc.school_contact_name, doc.school_contact_email, doc.school_mobile))
    elif client_type == "Company":
        extras.append(("Company Contact", doc.company_contact_name, doc.company_contact_email, doc.company_mobile))

    # A dedicated billing contact is only filled in when billing isn't the
    # same as one of the contacts above - Client.billing_contact itself
    # links to a Customer, not a Contact, and this app doesn't create
    # Customer records as part of conversion (that's a separate, existing
    # manual step when Ashley first invoices), so this just makes sure the
    # person's details aren't lost even though nothing wires them up as the
    # billing party automatically yet.
    extras.append(("Billing Contact", doc.billing_contact_full_name, doc.billing_contact_email, doc.billing_contact_mobile))

    return extras


def _proposed_client_field_values(doc):
    """
    Everything the intake form has to offer for the Client record, headline
    fields plus whichever detailed section applies - used both when
    creating a brand new Client (convert_lead_to_client) and when comparing
    against an existing one (get_lead_client_diff/link_lead_to_existing_client).
    """
    field_values = {
        "email": doc.contact_email,
        "mobile": doc.contact_mobile,
        "zip_code": doc.postal_code,
        "address": doc.location_address,
    }
    field_values.update(_client_field_values(doc))
    return {k: v for k, v in field_values.items() if v}


_INTAKE_PDF_SKIP_FIELDTYPES = {"Section Break", "Column Break", "Table", "HTML"}
_INTAKE_PDF_SKIP_FIELDS = {
    "status", "source", "coach", "event", "converted_client", "converted_contact",
    "intake_sent_on", "decline_reason",
}


def get_intake_question_fields():
    """
    The Lead fields that make up "the intake form's questions", in the
    doctype's own field layout order - shared by _intake_pdf_rows() below
    and the Reports section's per-question/per-person breakdowns
    (form_reports.py), so both answer "what counts as a question" the same
    way. Reads straight off the doctype's meta rather than one particular
    Lead's answers, so it works even before anyone has filled anything in.
    """
    meta = frappe.get_meta(LEAD_DOCTYPE)
    fields = []
    seen = {"client_name", "contact_name"}

    for df in meta.fields:
        if df.fieldname in seen or df.fieldname in _INTAKE_PDF_SKIP_FIELDS:
            continue
        if df.fieldtype in _INTAKE_PDF_SKIP_FIELDTYPES:
            continue

        fields.append(df)
        seen.add(df.fieldname)

    return fields


def get_intake_field_value(doc, df):
    """One Lead's formatted answer to a single intake question field."""
    value = doc.get(df.fieldname)

    if df.fieldtype == "Check":
        return "Yes" if value else None
    if df.fieldtype == "Date" and value:
        return frappe.utils.formatdate(value, "dd-MM-yyyy")

    return value or None


def _intake_pdf_rows(doc):
    """
    Every filled-in answer on the Lead, in the same order as the doctype's
    own field layout - so the PDF stays a complete record of the intake as
    the form grows, rather than a hardcoded handful of fields going stale.
    """
    rows = [("Client Name", doc.client_name), ("Contact Name", doc.contact_name)]

    for df in get_intake_question_fields():
        value = get_intake_field_value(doc, df)
        if value is None:
            continue

        rows.append((df.label or df.fieldname, value))

    completed_on = doc.intake_completed_on
    rows.append((
        "Intake Completed On",
        frappe.utils.format_datetime(completed_on, "dd-MM-yyyy HH:mm") if completed_on else completed_on,
    ))
    return rows


def _attach_intake_pdf_to_client(doc, client_name):
    """
    Best-effort - a completed intake is data on the Lead, not a file, so
    this renders a simple summary PDF and attaches it to the new Client so
    it shows up on the Client's own Files tab. Never blocks conversion if
    PDF generation fails for any reason (e.g. wkhtmltopdf not available on
    the site).
    """
    if not doc.intake_completed_on:
        return

    try:
        from frappe.utils.pdf import get_pdf

        rows = "".join(
            f"<tr><td style='padding:4px 8px;color:#839898;'>{label}</td>"
            f"<td style='padding:4px 8px;'>{frappe.utils.escape_html(str(value or '-'))}</td></tr>"
            for label, value in _intake_pdf_rows(doc)
        )

        html = f"<h2>Intake Form - {frappe.utils.escape_html(doc.client_name)}</h2><table>{rows}</table>"
        pdf_content = get_pdf(html)

        file_doc = frappe.get_doc({
            "doctype": "File",
            "file_name": f"Intake Form - {doc.client_name}.pdf",
            "attached_to_doctype": "Client",
            "attached_to_name": client_name,
            "attached_to_field": "intake_form",
            "is_private": 1,
            "content": pdf_content,
        })
        file_doc.insert(ignore_permissions=True)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Attach Intake PDF to Client Failed")


@frappe.whitelist()
def convert_lead_to_client(name=None):
    doc = ensure_lead_access(coalesce_str("name", name))

    if is_session_worker_lead(doc.get("appointment_type")):
        frappe.throw(_("A Session Worker lead doesn't convert to a Client - set them up as a Session Worker instead."))

    if doc.status == "Converted" and doc.converted_client:
        return {"ok": True, "client": doc.converted_client, "contact": doc.converted_contact}

    if not doc.contact_name or not doc.client_name:
        frappe.throw(_("This lead is missing contact or client details."))

    from dashboard.api.shared.client_details import (
        set_full_name_from_parts,
        sanitize_name_part,
        apply_age_and_client_type,
        get_coach_defaults_from_coach,
    )

    client_meta = frappe.get_meta("Client")
    client_first, client_last = _split_name(doc.client_name)

    # The detailed intake answers (young person/adult/school/company,
    # per doc.client_type) take priority over the headline contact_email/
    # contact_mobile/postal_code/location_address fields where both exist -
    # they're the more specific, correct source (e.g. the young person's own
    # email, not the parent's). The headline fields are the only thing
    # available for older/simpler leads with no detailed intake data.
    field_values = _proposed_client_field_values(doc)

    client = frappe.new_doc("Client")

    # Reuses the same name-combining logic the Client Details page's own
    # save uses, rather than this flow's own simpler (and, it turned out,
    # incomplete - full_name ended up missing the last name) version.
    # Preferred/nickname first, same priority as the Lead-matching logic in
    # sync_intake_doctype_submission - it's what the client_name shown
    # everywhere else in this app (the Lead's own title, this contact_name
    # match) is normally built from.
    set_full_name_from_parts(client, {
        "name1": field_values.get("preferred_name") or field_values.get("name1") or client_first,
        "last_name": field_values.get("last_name") or client_last,
    })

    if client_meta.has_field("primary_coach") and doc.coach:
        client.primary_coach = doc.coach
    if client_meta.has_field("attending_coach") and doc.coach:
        client.attending_coach = doc.coach
    if client_meta.has_field("date_added"):
        client.date_added = frappe.utils.today()
    if client_meta.has_field("additional_comments"):
        intake_notes = _format_intake_notes(doc)
        if intake_notes:
            client.additional_comments = intake_notes

    for fieldname in [
        "preferred_name", "mobile", "email", "pronouns", "sex", "gender_identity",
        "address", "city", "zip_code", "allergies", "neurodiverse_status",
        "neurodiverse_information", "main_therapy_location",
    ]:
        value = field_values.get(fieldname)
        if value and client_meta.has_field(fieldname):
            client.set(fieldname, value)

    dob_value = field_values.get("date_of_birth")
    if dob_value:
        for dob_field in ["date_of_birth", "dob"]:
            if client_meta.has_field(dob_field):
                client.set(dob_field, dob_value)
                break
    elif doc.client_age:
        # No exact date of birth on file (older/simpler leads only ever
        # captured an age) - Client works out age from a date of birth via
        # its own script rather than storing age directly, so this is
        # converted to an estimated DOB (today's month/day, doc.client_age
        # years ago). Close enough for the age script to show the right age
        # immediately, but the coach should correct it once they have the
        # real date of birth.
        for dob_field in ["date_of_birth", "dob"]:
            if client_meta.has_field(dob_field):
                try:
                    estimated_dob = frappe.utils.add_years(frappe.utils.today(), -int(doc.client_age))
                    client.set(dob_field, estimated_dob)
                except Exception:
                    pass
                break

    # Derives age + client_type (Kid/Teen/Uni Student/Adult) from whichever
    # date_of_birth was just set above - previously client_type was never
    # set at all on conversion.
    apply_age_and_client_type(client)

    # A Franchisee Call lead converts into a Client tracked as their own
    # "Franchise" (see client_transfers.py's own use of this same
    # client_type, for billing a coach directly) - overrides whatever
    # Kid/Teen/Adult/etc apply_age_and_client_type just derived, which
    # never makes sense for a franchisee (no date of birth/client age on
    # a lead like this to derive it from anyway).
    if is_franchise_lead(doc.get("appointment_type")) and client_meta.has_field("client_type"):
        client.client_type = "Franchise"

    # Coach-level defaults (bank account, price list, company) the client
    # inherits from their assigned primary coach - previously never applied
    # on conversion, so every converted client needed these filled in by
    # hand afterwards. These must win over whatever the Client doctype's
    # own field-level default put on the new doc (e.g. a blanket default
    # Company) - a not-already-set check here would just leave that
    # doctype default in place and never reach the coach's real value.
    coach_defaults = get_coach_defaults_from_coach(doc.coach)
    for fieldname in ["coach_banking_details", "banking", "pricelist", "price_list", "company"]:
        if client_meta.has_field(fieldname) and coach_defaults.get(fieldname):
            client.set(fieldname, coach_defaults.get(fieldname))

    client.insert(ignore_permissions=True)
    _attach_intake_pdf_to_client(doc, client.name)

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

        for _label, full_name, email, mobile in _extra_contacts_for_lead(doc):
            # Best-effort, same as _attach_intake_pdf_to_client below - a
            # bad value on one supplementary contact (e.g. a malformed
            # email the intake form didn't validate) must never blow up
            # the whole conversion. Frappe rolls back the entire request
            # on an unhandled exception, so without this the Client that
            # was already inserted above would vanish along with it,
            # while the Lead's own status never reaches "Converted" -
            # leaving no record either side happened.
            try:
                extra_contact_name = _create_supplementary_contact(full_name, email, mobile, doc.contact_name)
            except Exception:
                frappe.log_error(frappe.get_traceback(), f"Convert Lead to Client - Supplementary Contact Failed - {doc.name}")
                extra_contact_name = None

            if extra_contact_name:
                client.append("client_contacts", {
                    "contact": extra_contact_name,
                    "contact_name": sanitize_name_part(full_name),
                    "phone": mobile or "",
                    "email_id": email or "",
                })

        client.save(ignore_permissions=True)

    doc.converted_client = client.name
    doc.converted_contact = contact.name
    doc.status = "Converted"
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    invoice_pending_transfer_fees_for_lead(doc.name)

    return {"ok": True, "client": client.name, "contact": contact.name}


@frappe.whitelist()
def get_client_link_options():
    """Clients the current user is allowed to see, for the 'Link to Existing
    Client' picker on a Lead - reuses the same scoping as the Clients page."""
    from dashboard.api.shared.clients import get_clients

    return [
        {"value": row.get("name"), "label": row.get("display_name") or row.get("name")}
        for row in get_clients()
    ]


@frappe.whitelist()
def get_client_contact_options(client=None):
    from dashboard.api.shared.permissions import ensure_client_access

    client = coalesce_str("client", client)
    if not client:
        return []

    client_doc = ensure_client_access(client)

    return [
        {
            "value": row.get("contact"),
            "label": row.get("contact_name") or row.get("contact"),
        }
        for row in client_doc.get("client_contacts") or []
        if row.get("contact")
    ]


@frappe.whitelist()
def get_lead_client_diff(name=None, client=None):
    """
    For the "link this lead to an existing client" flow: compares what the
    intake form collected against the client's current field values, so a
    coach can see exactly what's proposed to change and choose, field by
    field, whether to keep what's already on the client or take the new
    answer instead - e.g. keep an existing Allergies note but take the
    newly-given doctor details. Only returns fields that actually differ;
    nothing to decide means nothing is shown.
    """
    from dashboard.api.shared.permissions import ensure_client_access

    doc = ensure_lead_access(coalesce_str("name", name))
    client = coalesce_str("client", client)

    if not client:
        frappe.throw(_("Please select the client to compare against."))

    client_doc = ensure_client_access(client)
    client_meta = frappe.get_meta("Client")

    field_values = _proposed_client_field_values(doc)

    rows = []
    for fieldname, new_value in field_values.items():
        if not client_meta.has_field(fieldname):
            continue

        current_value = client_doc.get(fieldname)

        if str(current_value or "").strip().lower() == str(new_value).strip().lower():
            continue

        rows.append({
            "fieldname": fieldname,
            "label": CLIENT_FIELD_LABELS.get(fieldname, fieldname.replace("_", " ").title()),
            "current_value": current_value or "",
            "new_value": new_value,
        })

    return {"rows": rows}


@frappe.whitelist()
def link_lead_to_existing_client(name=None, client=None, contact=None, field_choices=None):
    """
    For when the coach already created the Client/Contact themselves (e.g.
    before this Lead existed, or outside this flow) - links the Lead to
    those existing records instead of creating duplicates, and marks it
    Converted the same as a normal conversion would. field_choices (from
    the compare screen backed by get_lead_client_diff) is a
    fieldname -> "keep"/"use_new" map - only fields explicitly marked
    "use_new" are written onto the existing Client; anything else, or no
    field_choices at all, leaves the client untouched.
    """
    from dashboard.api.shared.permissions import ensure_client_access

    doc = ensure_lead_access(coalesce_str("name", name))
    client = coalesce_str("client", client)
    contact = coalesce_str("contact", contact)

    if not client:
        frappe.throw(_("Please select the client to link this lead to."))

    client_doc = ensure_client_access(client)

    if contact and not frappe.db.exists("Contact", contact):
        frappe.throw(_("Selected contact was not found."))

    field_choices = coalesce_raw("field_choices", field_choices)
    if isinstance(field_choices, str):
        try:
            field_choices = frappe.parse_json(field_choices)
        except Exception:
            field_choices = {}

    if field_choices:
        client_meta = frappe.get_meta("Client")
        field_values = _proposed_client_field_values(doc)

        changed = False
        for fieldname, choice in field_choices.items():
            if choice != "use_new":
                continue

            value = field_values.get(fieldname)
            if value and client_meta.has_field(fieldname):
                client_doc.set(fieldname, value)
                changed = True

        if changed:
            client_doc.save(ignore_permissions=True)

    _attach_intake_pdf_to_client(doc, client)

    doc.converted_client = client
    doc.converted_contact = contact
    doc.status = "Converted"
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    invoice_pending_transfer_fees_for_lead(doc.name)

    return {"ok": True, "client": client, "contact": contact}
