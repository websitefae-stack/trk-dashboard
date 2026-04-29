import frappe
from frappe import _
from frappe.utils import nowdate


CLIENT_DOCTYPE = "Client"

CLIENT_NOTES_PARENT_FIELD_CANDIDATES = ("notes", "client_notes", "session_notes")
CLIENT_NOTE_TEXT_FIELD_CANDIDATES = ("note", "notes", "note_text", "content")
CLIENT_NOTE_DATE_FIELD_CANDIDATES = ("session_date", "date", "note_date", "created_on")
CLIENT_NOTE_USER_FIELD_CANDIDATES = ("user", "owner", "owner_name", "created_by")


def require_logged_in_user():
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)
    return frappe.session.user


def _first_existing_field(meta, candidates):
    for fieldname in candidates:
        if meta.has_field(fieldname):
            return fieldname
    return None


def _get_notes_parent_field():
    meta = frappe.get_meta(CLIENT_DOCTYPE)
    return _first_existing_field(meta, CLIENT_NOTES_PARENT_FIELD_CANDIDATES)


def _get_child_row_value(row, candidates):
    for fieldname in candidates:
        value = row.get(fieldname)
        if value not in (None, ""):
            return value
    return ""


def _get_user_full_name(user):
    if not user:
        return ""

    return (
        frappe.get_cached_value("User", user, "full_name")
        or user
    )


# =========================================================
# NOTES (FIXES YOUR ISSUE)
# =========================================================

def get_client_notes(client_name):
    require_logged_in_user()

    doc = frappe.get_doc(CLIENT_DOCTYPE, client_name)

    notes_parent_field = _get_notes_parent_field()
    if not notes_parent_field:
        return []

    child_rows = doc.get(notes_parent_field) or []
    result = []

    for row in child_rows:
        note_date = _get_child_row_value(row, CLIENT_NOTE_DATE_FIELD_CANDIDATES)

        if hasattr(note_date, "strftime"):
            note_date = note_date.strftime("%Y-%m-%d")

        user_id = _get_child_row_value(row, CLIENT_NOTE_USER_FIELD_CANDIDATES)

        result.append(
            {
                "name": row.get("name"),
                "note_text": _get_child_row_value(row, CLIENT_NOTE_TEXT_FIELD_CANDIDATES),
                "note_date": note_date or "",
                "note_user": user_id,
                "note_user_name": _get_user_full_name(user_id),  # 🔥 FIX HERE
                "idx": row.get("idx") or 0,
            }
        )

    result.sort(
        key=lambda d: ((d.get("note_date") or ""), d.get("idx") or 0),
        reverse=True,
    )

    return result


def add_client_note(client_name, note_text, session_date=None, session_type=None):
    require_logged_in_user()

    note_text = (note_text or "").strip()
    if not note_text:
        frappe.throw(_("Note text is required."))

    client_doc = frappe.get_doc(CLIENT_DOCTYPE, client_name)

    notes_parent_field = _get_notes_parent_field()
    if not notes_parent_field:
        frappe.throw(_("No client notes child table field found."))

    child_doctype = client_doc.meta.get_field(notes_parent_field).options
    child_meta = frappe.get_meta(child_doctype)

    note_text_field = _first_existing_field(child_meta, CLIENT_NOTE_TEXT_FIELD_CANDIDATES)
    note_date_field = _first_existing_field(child_meta, CLIENT_NOTE_DATE_FIELD_CANDIDATES)
    note_user_field = _first_existing_field(child_meta, CLIENT_NOTE_USER_FIELD_CANDIDATES)

    row = {}

    if note_text_field:
        row[note_text_field] = note_text

    if note_date_field:
        row[note_date_field] = session_date or nowdate()

    if note_user_field:
        row[note_user_field] = frappe.session.user

    client_doc.append(notes_parent_field, row)
    client_doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {"ok": 1}


# =========================================================
# CONTACTS (shared)
# =========================================================

def get_client_contacts(client_name, contact_detail_base_url=""):
    require_logged_in_user()

    doc = frappe.get_doc(CLIENT_DOCTYPE, client_name)

    parent_field = None
    for f in ("client_contacts", "contacts"):
        if doc.meta.has_field(f):
            parent_field = f
            break

    if not parent_field:
        return []

    result = []

    for row in doc.get(parent_field) or []:
        contact_name = row.get("contact") or row.get("contact_name")
        if not contact_name:
            continue

        contact = frappe.db.get_value(
            "Contact",
            contact_name,
            ["name", "full_name", "email_id", "mobile_no", "company_name"],
            as_dict=True,
        ) or {}

        result.append(
            {
                "name": contact.get("name"),
                "display_name": contact.get("full_name") or contact_name,
                "email": contact.get("email_id") or "",
                "mobile": contact.get("mobile_no") or "",
                "company": contact.get("company_name") or "",
                "link": f"{contact_detail_base_url}?name={contact.get('name')}" if contact.get("name") else "",
            }
        )

    return result
