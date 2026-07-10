import frappe
from frappe import _
from frappe.utils import now_datetime, get_url

from dashboard.api.shared.permissions import (
    ensure_logged_in,
    is_franchisor_user,
    get_current_coach_name,
    get_current_user_dashboard_type,
)
from dashboard.api.shared.clients import get_coach_label
from dashboard.api.shared.utils import coalesce_str, coalesce_raw
from dashboard.api.shared.notifications import create_trk_notification
from dashboard.api.shared.appointment_types import creates_client_on_conversion
from dashboard.api.shared.email_templates import render_email, plain_text_to_email_html, INTAKE_INVITE_TEMPLATE


INTAKE_ROUTE = "client-intake/new"


LEAD_DOCTYPE = "Client Lead"

LEAD_STATUSES = ["New", "Intake Sent", "Converted", "Declined"]

DECLINE_STATUSES = {"Declined"}

LEAD_LIST_FIELDS = [
    "name", "status", "source", "appointment_type", "coach",
    "contact_name", "contact_email", "contact_mobile",
    "client_name", "client_age", "postal_code",
    "event", "converted_client", "modified", "creation",
]


def _normalize_lead_row(row):
    return {
        "name": row.get("name"),
        "status": row.get("status") or "New",
        "source": row.get("source") or "Coach Added",
        "appointment_type": row.get("appointment_type") or "",
        "coach": row.get("coach") or "",
        "coach_label": get_coach_label(row.get("coach")) if row.get("coach") else "",
        "contact_name": row.get("contact_name") or "",
        "contact_email": row.get("contact_email") or "",
        "contact_mobile": row.get("contact_mobile") or "",
        "client_name": row.get("client_name") or "",
        "client_age": row.get("client_age") or "",
        "postal_code": row.get("postal_code") or "",
        "event": row.get("event") or "",
        "converted_client": row.get("converted_client") or "",
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


def _lead_filters_for_current_user(dashboard_type=None):
    """
    None means "no filter" (franchisor sees every lead). Any other value is
    a Frappe filters dict restricting to the current coach's own leads.
    """
    ensure_logged_in()

    dashboard_type = dashboard_type or get_current_user_dashboard_type()

    if is_franchisor_user() or dashboard_type == "franchisor":
        return None

    coach_name = _current_coach_name()

    if not coach_name:
        return {"name": ["in", []]}

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
def get_leads(dashboard_type=None):
    ensure_logged_in()

    filters = _lead_filters_for_current_user(dashboard_type)

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
    row["intake_url"] = _intake_url(doc.name) if doc.get("intake_sent_on") else ""
    row["call"] = _get_lead_call_info(doc.event)
    row["location_address"] = doc.get("location_address") or ""
    row["is_client_conversion"] = 1 if creates_client_on_conversion(doc.get("appointment_type")) else 0

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

    return doc.name


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
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {"ok": True, "notes": _get_lead_notes(doc)}


def _intake_url(name):
    return get_url(f"/{INTAKE_ROUTE}?lead={name}")


@frappe.whitelist()
def send_intake_form(name=None):
    doc = ensure_lead_access(coalesce_str("name", name))

    if not doc.contact_email:
        frappe.throw(_("This lead has no contact email address to send the intake form to."))

    intake_url = _intake_url(doc.name)

    try:
        context = {
            "contact_name": frappe.utils.escape_html(doc.contact_name or ""),
            "client_name": frappe.utils.escape_html(doc.client_name or "your young person"),
            "intake_url": intake_url,
        }

        fallback_message = (
            "Hi {{ contact_name }},\n"
            "\n"
            "Thanks for speaking with us. Please complete the short form below "
            "so we can get {{ client_name }} set up:\n"
            "\n"
            "{{ intake_url }}"
        )

        subject, message = render_email(
            INTAKE_INVITE_TEMPLATE,
            context,
            fallback_subject="Your Resilient Kid intake form",
            fallback_message=fallback_message,
        )

        frappe.sendmail(
            recipients=[doc.contact_email],
            subject=subject,
            message=plain_text_to_email_html(message),
            now=True,
        )
        email_sent = True
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Send Intake Form Email Failed")
        email_sent = False

    doc.status = "Intake Sent"
    doc.intake_sent_on = now_datetime()
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {"ok": True, "intake_url": intake_url, "email_sent": email_sent, "status": doc.status}


@frappe.whitelist(allow_guest=True)
def get_intake_lead(lead=None):
    """
    Public lookup for the intake form page - the Lead's own hash name is the
    unguessable token (no separate secret needed), so this only ever exposes
    the one record the link was generated for.
    """
    lead = coalesce_str("lead", lead)

    if not lead or not frappe.db.exists(LEAD_DOCTYPE, lead):
        frappe.throw(_("This intake link is invalid or has expired."))

    doc = frappe.get_doc(LEAD_DOCTYPE, lead)

    if doc.status in ("Converted",):
        return {"already_done": True, "status": doc.status}

    return {
        "already_done": False,
        "status": doc.status,
        "contact_name": doc.contact_name or "",
        "contact_email": doc.contact_email or "",
        "contact_mobile": doc.contact_mobile or "",
        "client_name": doc.client_name or "",
        "client_age": doc.client_age or "",
        "postal_code": doc.postal_code or "",
        "enquiry_reason": doc.enquiry_reason or "",
        "how_heard": doc.how_heard or "",
        "consent_given": int(doc.consent_given or 0),
    }


@frappe.whitelist(allow_guest=True)
def submit_intake(
    lead=None,
    contact_name=None,
    contact_email=None,
    contact_mobile=None,
    client_name=None,
    client_age=None,
    postal_code=None,
    enquiry_reason=None,
    how_heard=None,
    consent_given=None,
):
    lead = coalesce_str("lead", lead)

    if not lead or not frappe.db.exists(LEAD_DOCTYPE, lead):
        frappe.throw(_("This intake link is invalid or has expired."))

    doc = frappe.get_doc(LEAD_DOCTYPE, lead)

    if doc.status == "Converted":
        return {"ok": True, "already_done": True}

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

    client_age = coalesce_raw("client_age", client_age)
    if client_age not in (None, ""):
        try:
            doc.client_age = int(client_age)
        except Exception:
            pass

    doc.postal_code = coalesce_str("postal_code", postal_code)
    doc.enquiry_reason = coalesce_str("enquiry_reason", enquiry_reason)
    doc.how_heard = coalesce_str("how_heard", how_heard)

    consent_given = coalesce_raw("consent_given", consent_given)
    doc.consent_given = 1 if str(consent_given).lower() in ["1", "true", "yes", "on"] else 0

    # Status stays "Intake Sent" - the simplified pipeline (New / Intake
    # Sent / Converted / Declined) has no separate "completed" status, so
    # this timestamp is what tells the coach's "Convert to Client" button
    # to appear instead.
    doc.intake_completed_on = now_datetime()
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    if doc.coach:
        coach_user = frappe.db.get_value("Coach", doc.coach, "user") or frappe.db.get_value(
            "Coach", doc.coach, "coach_email"
        )

        if coach_user:
            # Best-effort - the intake submission itself is already saved
            # above, a broken notification config must not make it look
            # like the submission failed.
            try:
                create_trk_notification(
                    recipient_user=coach_user,
                    notification_type="Intake Form Completed",
                    message=f"{doc.client_name} - intake form has been completed. Review and convert to a client.",
                    priority="High",
                    reference_doctype=LEAD_DOCTYPE,
                    reference_name=doc.name,
                )
            except Exception:
                frappe.log_error(frappe.get_traceback(), "Intake Submission - Coach Notification Failed")

    return {"ok": True, "already_done": False}


def _split_name(full_name):
    parts = (full_name or "").strip().split(" ", 1)
    first = parts[0] if parts else ""
    last = parts[1] if len(parts) > 1 else ""
    return first, last


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
            for label, value in [
                ("Contact Name", doc.contact_name),
                ("Contact Email", doc.contact_email),
                ("Contact Mobile", doc.contact_mobile),
                ("Client Name", doc.client_name),
                ("Client Age", doc.client_age),
                ("Postal Code", doc.postal_code),
                ("Why They're Contacting Us", doc.enquiry_reason),
                ("How They Heard About Us", doc.how_heard),
                ("Consent To Be Contacted", "Yes" if doc.consent_given else "No"),
                ("Intake Completed On", doc.intake_completed_on),
            ]
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

    if doc.status == "Converted" and doc.converted_client:
        return {"ok": True, "client": doc.converted_client, "contact": doc.converted_contact}

    if not doc.contact_name or not doc.client_name:
        frappe.throw(_("This lead is missing contact or client details."))

    client_meta = frappe.get_meta("Client")
    client_first, client_last = _split_name(doc.client_name)

    client = frappe.new_doc("Client")
    if client_meta.has_field("full_name"):
        client.full_name = doc.client_name
    if client_meta.has_field("name1"):
        client.name1 = client_first
    if client_meta.has_field("last_name"):
        client.last_name = client_last
    if client_meta.has_field("primary_coach") and doc.coach:
        client.primary_coach = doc.coach
    if client_meta.has_field("attending_coach") and doc.coach:
        client.attending_coach = doc.coach
    if doc.client_age:
        # Client works out age from a date of birth via its own script rather
        # than storing age directly, so the Lead's approximate age (that's
        # all a phone enquiry ever gives us) is converted to an estimated
        # DOB here. It's a best guess (today's month/day, doc.client_age
        # years ago) - close enough for the age script to show the right
        # age immediately, but the coach should correct it to the real date
        # of birth once they have it.
        for dob_field in ["date_of_birth", "dob"]:
            if client_meta.has_field(dob_field):
                try:
                    estimated_dob = frappe.utils.add_years(frappe.utils.today(), -int(doc.client_age))
                    client.set(dob_field, estimated_dob)
                except Exception:
                    pass
                break

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
            "contact_name": doc.contact_name,
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
def link_lead_to_existing_client(name=None, client=None, contact=None):
    """
    For when the coach already created the Client/Contact themselves (e.g.
    before this Lead existed, or outside this flow) - links the Lead to
    those existing records instead of creating duplicates, and marks it
    Converted the same as a normal conversion would.
    """
    from dashboard.api.shared.permissions import ensure_client_access

    doc = ensure_lead_access(coalesce_str("name", name))
    client = coalesce_str("client", client)
    contact = coalesce_str("contact", contact)

    if not client:
        frappe.throw(_("Please select the client to link this lead to."))

    ensure_client_access(client)

    if contact and not frappe.db.exists("Contact", contact):
        frappe.throw(_("Selected contact was not found."))

    _attach_intake_pdf_to_client(doc, client)

    doc.converted_client = client
    doc.converted_contact = contact
    doc.status = "Converted"
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {"ok": True, "client": client, "contact": contact}
