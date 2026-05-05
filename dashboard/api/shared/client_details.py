import json
import frappe
from frappe import _

# -------------------------------------------------------------------
# AUTH / ACCESS
# -------------------------------------------------------------------

def require_logged_in_user():
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)


def ensure_client_access(client_name):
    require_logged_in_user()

    if not client_name or not frappe.db.exists("Client", client_name):
        frappe.throw(_("Client not found."))


# -------------------------------------------------------------------
# DISPLAY NAMES
# -------------------------------------------------------------------

def get_user_display_name(user):
    if not user:
        return ""
    return frappe.get_cached_value("User", user, "full_name") or user


def get_coach_name():
    return get_user_display_name(frappe.session.user)


def get_franchisor_name():
    return get_user_display_name(frappe.session.user)


def get_session_worker_name():
    return get_user_display_name(frappe.session.user)


# -------------------------------------------------------------------
# NOTES
# -------------------------------------------------------------------

def get_session_notes(doc):
    notes = []

    for row in doc.get("session_notes") or []:
        user = row.get("user") or row.get("owner") or ""

        notes.append({
            "session_date": row.get("session_date"),
            "session_type": row.get("session_type"),
            "notes": row.get("notes") or row.get("note") or row.get("note_text") or "",
            "user": user,
            "user_full_name": get_user_display_name(user),
            "idx": row.get("idx") or 0,
            "creation": row.get("creation"),
        })

    notes.sort(
        key=lambda x: (
            x.get("session_date") or "",
            x.get("creation") or "",
            x.get("idx") or 0,
        ),
        reverse=True,
    )

    return notes


@frappe.whitelist()
def add_client_note(client_name, note_text, session_date=None, session_type=None):
    ensure_client_access(client_name)

    if not note_text:
        frappe.throw(_("Note text is required."))

    doc = frappe.get_doc("Client", client_name)

    child = doc.append("session_notes", {})

    if child.meta.has_field("notes"):
        child.notes = note_text
    elif child.meta.has_field("note"):
        child.note = note_text
    elif child.meta.has_field("note_text"):
        child.note_text = note_text

    if child.meta.has_field("session_date"):
        child.session_date = session_date or frappe.utils.nowdate()

    if child.meta.has_field("session_type") and session_type:
        child.session_type = session_type

    if child.meta.has_field("user"):
        child.user = frappe.session.user

    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {"ok": 1}


# -------------------------------------------------------------------
# CONTACTS
# -------------------------------------------------------------------

def get_contact_data(contact_name):
    if not contact_name:
        return {}

    contact = frappe.db.get_value(
        "Contact",
        contact_name,
        ["name", "full_name", "email_id", "mobile_no", "phone", "company_name"],
        as_dict=True,
    ) or {}

    return {
        "display_name": contact.get("full_name") or contact_name,
        "phone": contact.get("mobile_no") or contact.get("phone") or "",
        "email": contact.get("email_id") or "",
        "company": contact.get("company_name") or "",
    }


def get_client_contacts(doc, base_url):
    contacts = []

    for row in doc.get("client_contacts") or []:
        contact_name = row.get("contact")
        data = get_contact_data(contact_name)

        contacts.append({
            "contact": contact_name,
            "contact_name": data.get("display_name") or contact_name,
            "phone": data.get("phone"),
            "email": data.get("email"),
            "company": data.get("company"),
            "relationship": row.get("relationship") or "",
            "link": f"{base_url}/contact_details?name={contact_name}" if contact_name else "",
        })

    return contacts


# -------------------------------------------------------------------
# APPOINTMENTS
# -------------------------------------------------------------------

def get_client_appointments(client_name, base_url):
    if not client_name:
        return []

    if not frappe.db.exists("DocType", "Event"):
        return []

    rows = frappe.get_all(
        "Event",
        filters={"custom_client": client_name},
        fields=["name", "subject", "starts_on", "status", "location"],
        order_by="starts_on desc",
        limit_page_length=200,
    )

    result = []

    for row in rows:
        result.append({
            "name": row.name,
            "date": row.starts_on,
            "status": row.status,
            "appointment_type": row.subject,
            "location": row.location,
            "record_url": f"{base_url}/calendar_details?event={row.name}",
        })

    return result


# -------------------------------------------------------------------
# SAVE CLIENT
# -------------------------------------------------------------------

@frappe.whitelist()
def save_client(docname=None, data=None):
    require_logged_in_user()

    payload = json.loads(data) if isinstance(data, str) else (data or {})

    if docname:
        doc = frappe.get_doc("Client", docname)
    else:
        doc = frappe.new_doc("Client")

    for key, value in payload.items():
        doc.set(key, value)

    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {"name": doc.name}


# -------------------------------------------------------------------
# LINK OPTIONS
# -------------------------------------------------------------------

@frappe.whitelist()
def get_link_options(doctype, txt=None, limit_page_length=500):
    require_logged_in_user()

    rows = frappe.get_all(
        doctype,
        fields=["name"],
        limit_page_length=limit_page_length,
    )

    return rows


# -------------------------------------------------------------------
# CONTEXT
# -------------------------------------------------------------------

def get_client_context_data(client_name=None, is_new=False, base_url="/coach_db", enforce_access=True):
    require_logged_in_user()

    if client_name and not is_new:
        ensure_client_access(client_name)
        doc = frappe.get_doc("Client", client_name)
    else:
        doc = frappe.new_doc("Client")

    return {
        "client_docname": doc.name or "",
        "client_title": doc.get("full_name") or "New Client",
        "tabs": [],  # keep existing UI working
        "billing_contact": None,
        "client_contacts": get_client_contacts(doc, base_url),
        "session_notes": get_session_notes(doc),
        "client_appointments": get_client_appointments(doc.name, base_url),
        "package_balances": [],
        "client_invoices": [],
        "travel_charged": doc.get("travel_charged") or 0,
        "travel_miles_one_way": doc.get("travel_miles_one_way") or 0,
    }


def get_client_for_context(client_name):
    ensure_client_access(client_name)
    return frappe.get_doc("Client", client_name)
