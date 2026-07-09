import frappe
from frappe import _
from frappe.utils import now_datetime

from dashboard.api.shared.permissions import (
    ensure_logged_in,
    is_franchisor_user,
    get_current_coach_name,
    get_current_user_dashboard_type,
)
from dashboard.api.shared.clients import get_coach_label
from dashboard.api.shared.utils import coalesce_str, coalesce_raw


LEAD_DOCTYPE = "Client Lead"

LEAD_STATUSES = [
    "New", "Assessing", "Can Help", "Can't Help",
    "Intake Sent", "Intake Completed", "Converted", "Declined",
]

DECLINE_STATUSES = {"Can't Help", "Declined"}

LEAD_LIST_FIELDS = [
    "name", "status", "source", "coach",
    "contact_name", "contact_email", "contact_mobile",
    "client_name", "client_age", "postal_code",
    "event", "modified", "creation",
]


def _normalize_lead_row(row):
    return {
        "name": row.get("name"),
        "status": row.get("status") or "New",
        "source": row.get("source") or "Coach Added",
        "coach": row.get("coach") or "",
        "coach_label": get_coach_label(row.get("coach")) if row.get("coach") else "",
        "contact_name": row.get("contact_name") or "",
        "contact_email": row.get("contact_email") or "",
        "contact_mobile": row.get("contact_mobile") or "",
        "client_name": row.get("client_name") or "",
        "client_age": row.get("client_age") or "",
        "postal_code": row.get("postal_code") or "",
        "event": row.get("event") or "",
        "modified": row.get("modified"),
        "creation": row.get("creation"),
    }


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

    return [_normalize_lead_row(row) for row in rows]


def _get_lead_notes(doc):
    notes = []

    for row in doc.get("notes") or []:
        notes.append({
            "name": row.get("name"),
            "note": row.get("note") or "",
            "added_by": row.get("added_by") or "",
            "added_on": row.get("added_on"),
            "idx": row.get("idx") or 0,
        })

    notes.sort(key=lambda r: r.get("idx") or 0, reverse=True)
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

    return row


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

    doc.insert(ignore_permissions=True)
    frappe.db.commit()

    return {"ok": True, "name": doc.name}


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
def add_lead_note(name=None, note=None):
    name = coalesce_str("name", name)
    note = coalesce_str("note", note)

    if not note:
        frappe.throw(_("Please enter a note."))

    doc = ensure_lead_access(name)

    doc.append("notes", {
        "note": note,
        "added_by": frappe.session.user,
        "added_on": now_datetime(),
    })
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {"ok": True, "notes": _get_lead_notes(doc)}
